"""Place at: property_app/management/commands/import_data.py
(also create empty __init__.py in management/ and management/commands/)

Usage:
    python manage.py import_data   # reads BASE_DIR/data/locations.csv and properties.csv
    python manage.py import_data --locations a.csv --properties b.csv   # override paths

Design:
  * Phase 1 (one atomic transaction): locations, properties, amenities.
    Either everything is committed or nothing is. Re-running skips existing slugs.
  * Phase 2 (resumable, outside the transaction): images.
    Each image is saved as file + DB row together and only images that are
    still missing are downloaded, so a re-run after a crash, kill or failed
    download fills the gaps without duplicating anything.
"""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, Point
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from PIL import Image

from property_app.models import Amenity, Location, Property, PropertyImage


def read_csv(path):
    if not Path(path).exists():
        raise CommandError(f"File not found: {path}")
    # keep_default_na=False: strings like "NA" / "null" are kept as real text
    return pd.read_csv(path, keep_default_na=False).fillna("")


class Command(BaseCommand):
    help = "Import locations and properties from CSV using pandas"

    def add_arguments(self, parser):
        data_dir = Path(settings.BASE_DIR) / "data"
        parser.add_argument("--locations", default=str(data_dir / "locations.csv"))
        parser.add_argument("--properties", default=str(data_dir / "properties.csv"))

    def handle(self, *args, **opts):
        self.session = requests.Session()  # reuses connections across downloads
        loc_df = read_csv(opts["locations"])
        prop_df = read_csv(opts["properties"])

        # Phase 1: all-or-nothing database import
        with transaction.atomic():
            self.import_locations(loc_df)
            self.import_properties(prop_df)

        # Phase 2: resumable image import (safe to re-run any number of times)
        self.import_images(prop_df)

    # ------------------------------------------------------------------ locations
    def import_locations(self, df):
        existing = {loc.slug: loc for loc in Location.objects.all()}
        has_description = "description" in df.columns
        rows, changed = [], []
        for r in df.itertuples():
            description = str(r.description).strip() if has_description else ""
            loc = existing.get(r.slug)
            if loc is None:
                rows.append(
                    Location(
                        name=r.name,
                        slug=r.slug,
                        country=r.country,
                        state=r.state,
                        city=r.city,
                        address=r.address,
                        description=description,
                        point=Point(float(r.longitude), float(r.latitude), srid=4326),  # lon first
                    )
                )
            elif description and loc.description != description:
                loc.description = description
                loc.embedding = None
                changed.append(loc)
        Location.objects.bulk_create(rows)
        Location.objects.bulk_update(changed, ["description", "embedding"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Locations created: {len(rows)}, descriptions updated: {len(changed)}"
            )
        )

    # ----------------------------------------------------------------- properties
    def import_properties(self, df):
        locs = {loc.slug: loc for loc in Location.objects.all()}
        existing = set(Property.objects.values_list("slug", flat=True))
        new_rows, meta, unknown_loc = [], [], 0
        for r in df.itertuples():
            if r.slug in existing:
                continue
            if r.location_slug not in locs:
                unknown_loc += 1
                self.stderr.write(f"skip property {r.slug}: unknown location '{r.location_slug}'")
                continue
            new_rows.append(
                Property(
                    location=locs[r.location_slug],
                    title=r.title,
                    slug=r.slug,
                    description=r.description,
                    property_type=r.property_type,
                    status=r.status,
                    price=r.price,
                    bedrooms=int(r.bedrooms),
                    bathrooms=int(r.bathrooms),
                    area_sqft=r.area_sqft or None,
                    address=r.address,
                    point=Point(float(r.longitude), float(r.latitude), srid=4326),
                    footprint=GEOSGeometry(r.footprint_wkt, srid=4326) if r.footprint_wkt else None,
                    is_featured=str(r.is_featured) == "True",
                    is_active=str(r.is_active) == "True",
                )
            )
            meta.append((r.slug, r.amenities))

        Property.objects.bulk_create(new_rows)
        props = {p.slug: p for p in Property.objects.filter(slug__in=[m[0] for m in meta])}

        # amenities: get_or_create once per unique name, then link via through table
        names = {n.strip() for _, a in meta for n in str(a).split("|") if n.strip()}
        amenity = {
            n: Amenity.objects.get_or_create(slug=slugify(n), defaults={"name": n})[0]
            for n in names
        }
        Through = Property.amenities.through
        Through.objects.bulk_create(
            [
                Through(property_id=props[slug].id, amenity_id=amenity[n.strip()].id)
                for slug, a in meta
                for n in str(a).split("|")
                if n.strip()
            ],
            ignore_conflicts=True,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Properties: {len(new_rows)}, amenities: {len(amenity)}, "
                f"skipped (unknown location): {unknown_loc}"
            )
        )

    # --------------------------------------------------------------------- images
    def fetch(self, job):
        url = job[2]
        err = None
        for _ in range(3):  # small retry for flaky downloads
            try:
                resp = self.session.get(url, timeout=30)
                if 400 <= resp.status_code < 500:  # client error: retrying won't help
                    err = f"HTTP {resp.status_code}"
                    break
                resp.raise_for_status()
                return resp.content
            except requests.RequestException as exc:
                err = exc
        self.stderr.write(f"skip {url}: {err}")
        return None

    def import_images(self, df):
        props = {p.slug: p for p in Property.objects.filter(slug__in=df["slug"].tolist())}

        # what is already in the DB, so only missing images are downloaded
        have = set(
            PropertyImage.objects.filter(property__slug__in=props).values_list(
                "property__slug", "sort_order"
            )
        )
        has_primary = set(
            PropertyImage.objects.filter(property__slug__in=props, is_primary=True).values_list(
                "property__slug", flat=True
            )
        )

        jobs = [
            (slug, i, url)
            for slug, urls in zip(df["slug"], df["image_urls"])
            if slug in props
            for i, url in enumerate(u for u in str(urls).split("|") if u)
            if (slug, i) not in have
        ]
        self.stdout.write(f"Downloading {len(jobs)} missing images...")
        with ThreadPoolExecutor(max_workers=16) as pool:
            downloaded = list(pool.map(self.fetch, jobs))

        created = 0
        for (slug, i, url), data in zip(jobs, downloaded):
            if data is None:
                continue
            try:
                with Image.open(BytesIO(data)) as im:
                    width, height, fmt = im.width, im.height, im.format
            except (OSError, ValueError, Image.DecompressionBombError) as exc:
                # not a valid image: skip, don't abort the run
                self.stderr.write(f"bad image {url}: {exc}")
                continue

            is_primary = slug not in has_primary  # first successful image becomes primary
            has_primary.add(slug)
            img = PropertyImage(
                property=props[slug],
                sort_order=i,
                is_primary=is_primary,
                alt_text=slug.replace("-", " ").title(),
                file_size=len(data),
                width=width,
                height=height,
            )
            ext = "jpg" if fmt == "JPEG" else (fmt or "jpg").lower()
            # save=True writes the file and the DB row together, so a crash can leave
            # at most one orphan file instead of a whole batch
            img.image.save(f"{slug}-{i + 1}.{ext}", ContentFile(data), save=True)
            created += 1

        failed = len(jobs) - created
        self.stdout.write(self.style.SUCCESS(f"Images created: {created}/{len(jobs)}"))
        if failed:
            self.stderr.write(f"{failed} images failed. Re-run the command to retry them.")
