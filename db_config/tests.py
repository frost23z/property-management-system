from django.db import connection
from django.test import TestCase


class ExtensionTests(TestCase):
    def test_postgis_and_pgvector_enabled(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT extname FROM pg_extension")
            names = {row[0] for row in cursor.fetchall()}
        self.assertIn("postgis", names)
        self.assertIn("vector", names)
