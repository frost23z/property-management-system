# Property Management System

A vacation-rental search site for Bangladeshi tourist destinations, built with **Django 6**, **GeoDjango / PostGIS** and **pgvector**. Visitors search by place and see stays ranked by real distance. Location suggestions understand meaning as well as spelling: "sea beach" finds Inani Beach, Kuakata and Cox's Bazar even though none of those names contain the words.

## Features

- **Spatial search**: stays within a chosen radius of a place (`ST_DWithin` on a PostGIS `geography` column), nearest first, with distances shown on the cards.
- **Semantic location search**: location names and descriptions are embedded with `all-MiniLM-L6-v2` and stored in pgvector (384-d, HNSW cosine index). If a typed place matches nothing, the closest location by meaning is used.
- **Autocomplete API** (`GET /api/locations/autocomplete/`): blends typed matches with semantic matches; validated with DRF serializers.
- **Listing, detail and home pages**: pagination, sorting (nearest / price / bedrooms), image gallery, amenities, distance to the city centre, nearby stays and nearby destinations.
- **Admin**: filters (including a custom price-range filter), inline image uploads with previews, map widgets for geometry fields.
- **Bulk import**: pandas-based `import_data` command, atomic for the database phase and resumable for image downloads.

## Stack

| Layer | Choice |
| --- | --- |
| Language / tooling | Python 3.14, [uv](https://docs.astral.sh/uv/), Ruff, pre-commit |
| Web | Django 6.1, Django REST Framework |
| Database | PostgreSQL 17 + PostGIS 3 + pgvector (Docker) |
| Driver | psycopg 3 (`psycopg[binary]`) |
| Embeddings | FastEmbed (ONNX Runtime, no PyTorch), model `sentence-transformers/all-MiniLM-L6-v2` |
| Data | pandas, Pillow, requests |
| Frontend | Server-rendered Django templates, plain CSS and vanilla JS |

## Quick start

### Prerequisites

- Python 3.14 and [uv](https://docs.astral.sh/uv/)
- Docker with Compose
- GDAL and GEOS system libraries (required by `django.contrib.gis`). On Debian/Ubuntu: `sudo apt install gdal-bin libgdal-dev libgeos-dev`; on macOS: `brew install gdal geos`.

### 1. Configure

```bash
cp .env.example .env
# set DJANGO_SECRET_KEY, e.g.
uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 2. Start the database

```bash
docker compose up -d
```

This builds `postgres:17` with PostGIS and pgvector installed. The `postgis` and `vector` extensions are enabled by a Django migration (`db_config/0001_setup_extensions.py`), so no manual SQL is needed.

### 3. Install, migrate, load data

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py import_data                   # locations, properties, amenities, images
uv run python manage.py generate_location_embeddings   # downloads the ~90 MB model on first run
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Open <http://localhost:8000/> for the site and <http://localhost:8000/admin/> for the admin.

`import_data` downloads property images from the internet; if some downloads fail, run it again and only the missing ones are fetched.

## Configuration

Read from `.env`.

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `DJANGO_SECRET_KEY` | yes | | Django secret key |
| `DJANGO_DEBUG` | no | `False` | Debug mode |
| `DJANGO_ALLOWED_HOSTS` | no | empty | Comma-separated hosts |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | yes | | Database credentials (also used by Compose) |
| `POSTGRES_HOST`, `POSTGRES_PORT` | no | `localhost`, `5432` | Database address; the port is also the one Compose publishes |
| `EMBEDDING_MODEL` | no | `sentence-transformers/all-MiniLM-L6-v2` | Must output 384 dimensions |
| `SEMANTIC_MAX_DISTANCE` | no | `0.5` | Largest cosine distance that counts as a semantic match; lower is stricter |
| `FASTEMBED_CACHE_PATH` | no | temp folder | Where the model is cached |

## Routes

| URL | Purpose |
| --- | --- |
| `/` | Home: search form, featured stays, popular destinations |
| `/properties/` | All stays; `?location=...&radius=...&sort=...&page=...` searches |
| `/properties/<slug>/` | Property detail |
| `/api/locations/autocomplete/` | Autocomplete JSON API |
| `/admin/` | Django admin |

## Data model

- **Location**: name, slug, country, state, city, address, `description`, `point` (geography), optional `boundary`, `embedding` (384-d, HNSW cosine index), `is_active`.
- **Amenity**: name, slug.
- **Property**: belongs to a Location; title, slug, description, type, status, price, bedrooms, bathrooms, area, `point` (geography), `footprint` polygon, amenities (many-to-many), `is_featured`, `is_active`.
- **PropertyImage**: belongs to a Property; image, alt text, caption, size, `is_primary`, `sort_order`.

## How search works

All search logic is in `property_app/search.py`.

### 1. Resolving what the visitor typed

The text is matched (case-insensitive substring) against each active location's name, city, state and country, and the best match is ranked:

| Rank | Meaning |
| --- | --- |
| exact | whole name or city equals the text |
| prefix | city or name starts with the text |
| city | city contains the text |
| broad | only the name, state or country contains it (e.g. "Bangladesh") |
| semantic | nothing matched as text; picked by meaning |

Ties go to the shortest city name. **A text match always wins.** Only if there is none is the text embedded and compared against the stored location vectors with pgvector cosine distance (`<=>`, served by the HNSW index). Matches farther than `SEMANTIC_MAX_DISTANCE` are discarded. If the model can't load, the error is logged and the search returns no match rather than failing.

### 2. Finding stays

- **Specific place** (exact, prefix, city or semantic): properties within the chosen radius of the place's centre (`ST_DWithin`, default 25 km, options 5/10/25/50/100), plus the place's own properties even if outside the radius. Ordered nearest first by default, or by price (either direction) or bedrooms.
- **Broad match** (state or country only): every property in the matching locations, alphabetical, no distances.

So meaning picks the *place*; geography orders the *stays*. The listing page says when a semantic match was used.

### 3. Detail page

- Distance to the city centre: `Distance(property.point, location.point)`.
- Nearby stays: other properties within 15 km (`DWithin`), nearest first, up to 4.
- Nearby destinations: other locations whose centre lies inside a 40 km circle around the stay (`Intersects`), up to 5. The circle is built in the stay's UTM zone and transformed back, so it is a true circle rather than an oval.

### 4. Embeddings

Each location is embedded as `"<name>. <description>"`. Run `generate_location_embeddings` after importing (only locations without a vector by default; `--all` re-embeds everything; `--batch-size N`). Changing a location's description via the import, or its name or description in the admin, clears its vector so it gets regenerated.

## API

### `GET /api/locations/autocomplete/`

| Parameter | Required | Rules |
| --- | --- | --- |
| `q` | yes | 2-100 characters, whitespace collapsed, at least one letter |
| `limit` | no | 1-10, default 5 |

Returns locations whose name, city, state or country contains `q`, then locations whose name and description are semantically close to it (pgvector cosine search), so misspellings and descriptive words still get suggestions. Both searches always run; with `limit=5`, one slot (`limit // 3`, minimum 1) is reserved for semantic matches, and either side uses the other's unused slots. Each result has `match` (`"text"` or `"semantic"`) and `semantic_distance` (cosine distance, `null` for text matches). Invalid parameters return `400` with per-field errors. If embeddings haven't been generated, only typed matches are returned.

**Exact (text) match**

```
GET /api/locations/autocomplete/?q=cox&limit=5
HTTP 200 OK
```

```json
{
    "query": "cox",
    "count": 1,
    "results": [
        {
            "id": 1,
            "name": "Cox's Bazar, Chattogram, Bangladesh",
            "slug": "cox-s-bazar",
            "city": "Cox's Bazar",
            "state": "Chattogram",
            "country": "Bangladesh",
            "latitude": 21.4272,
            "longitude": 91.979,
            "match": "text",
            "semantic_distance": null
        }
    ]
}
```

**Semantic match**

```
GET /api/locations/autocomplete/?q=sea%20beach&limit=5
HTTP 200 OK
```

```json
{
    "query": "sea beach",
    "count": 3,
    "results": [
        {
            "id": 2,
            "name": "Inani Beach, Chattogram, Bangladesh",
            "slug": "inani-beach",
            "city": "Inani Beach",
            "state": "Chattogram",
            "country": "Bangladesh",
            "latitude": 21.253,
            "longitude": 92.041,
            "match": "semantic",
            "semantic_distance": 0.41419047117233276
        },
        {
            "id": 20,
            "name": "Kuakata, Barishal, Bangladesh",
            "slug": "kuakata",
            "city": "Kuakata",
            "state": "Barishal",
            "country": "Bangladesh",
            "latitude": 21.8167,
            "longitude": 90.1167,
            "match": "semantic",
            "semantic_distance": 0.4383091926574707
        },
        {
            "id": 1,
            "name": "Cox's Bazar, Chattogram, Bangladesh",
            "slug": "cox-s-bazar",
            "city": "Cox's Bazar",
            "state": "Chattogram",
            "country": "Bangladesh",
            "latitude": 21.4272,
            "longitude": 91.979,
            "match": "semantic",
            "semantic_distance": 0.46779751777648926
        }
    ]
}
```

The search box on the home and listing pages (`static/js/autocomplete.js`) calls this endpoint as the visitor types; without JavaScript the form still works as a plain search.

## Data import

Seed data in `data/`: `locations.csv` (46 locations) and `properties.csv` (431 properties), generated for this project.

```bash
python manage.py import_data
python manage.py import_data --locations a.csv --properties b.csv
```

- **Phase 1, database (one transaction):** locations, properties, amenities. All or nothing. Existing slugs are skipped, so re-running is safe. Properties with an unknown `location_slug` are skipped with a message.
- **Phase 2, images (resumable):** downloaded in parallel with retries, validated with Pillow, saved as file and row together. Only missing images are fetched, so re-run after any failure to fill the gaps. The first successful image becomes the primary one.

`locations.csv` columns: `name, slug, country, state, city, address, latitude, longitude, description`.
`properties.csv` columns: `title, slug, location_slug, description, property_type, status, price, bedrooms, bathrooms, area_sqft, address, latitude, longitude, footprint_wkt, amenities, is_featured, is_active, image_urls`. `amenities` and `image_urls` are `|`-separated; `is_featured`/`is_active` are `True`/`False`; `footprint_wkt` is optional WKT in SRID 4326. Seed images are placeholder house photos from a public dataset, so importing needs internet access.

## Project layout

```
core/                     Django project (settings, root URLs)
db_config/                Enables the PostGIS and pgvector extensions
property_app/
  models.py               Location, Amenity, Property, PropertyImage
  search.py               Text, semantic, radius, nearby and autocomplete logic
  selectors.py            Reusable read queries
  embeddings.py           FastEmbed wrapper (model loaded lazily, cached)
  forms.py                Search form with custom validation
  views.py                home, property_list, property_detail
  api.py, serializers.py  Autocomplete endpoint and DRF serializers
  admin.py                Admin configuration
  management/commands/    import_data, generate_location_embeddings
  templates/              Page templates
static/                   CSS and JS
data/                     Seed CSVs
```

## Development

```bash
uv run ruff check .
uv run ruff format .
uv run python manage.py test
```

Pre-commit hooks (`pre-commit install`) run Ruff and basic file checks.
