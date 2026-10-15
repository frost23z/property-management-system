"""Embed location names and descriptions with FastEmbed and store the vectors in pgvector.

Usage:
    python manage.py generate_location_embeddings            # only locations without a vector
    python manage.py generate_location_embeddings --all      # re-embed every location
    python manage.py generate_location_embeddings --batch-size 16

Safe to re-run: by default it only touches locations whose embedding is still empty.
"""

from django.core.management.base import BaseCommand

from property_app import embeddings
from property_app.models import Location


class Command(BaseCommand):
    help = "Generate embeddings from each location's name and description (semantic search)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all", action="store_true", help="re-embed every location, not just the missing ones"
        )
        parser.add_argument("--batch-size", type=int, default=64)

    def handle(self, *args, **opts):
        locations = Location.objects.all()
        if not opts["all"]:
            locations = locations.filter(embedding__isnull=True)
        locations = list(locations)
        if not locations:
            self.stdout.write("Nothing to embed: every location already has an embedding.")
            return

        self.stdout.write(f"Embedding {len(locations)} location names...")
        size = max(opts["batch_size"], 1)
        for start in range(0, len(locations), size):
            batch = locations[start : start + size]
            vectors = embeddings.embed_texts([location.embedding_text for location in batch])
            for location, vector in zip(batch, vectors):
                location.embedding = vector
            Location.objects.bulk_update(batch, ["embedding"])

        self.stdout.write(self.style.SUCCESS(f"Embeddings stored: {len(locations)}"))
