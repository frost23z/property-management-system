from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import Amenity, Location


@admin.register(Location)
class LocationAdmin(GISModelAdmin):
    list_display = ("name", "city", "state", "country", "is_active", "updated_at")
    list_filter = ("country", "state", "is_active")
    search_fields = ("name", "city", "state", "country")
    prepopulated_fields = {"slug": ("name",)}  # noqa: RUF012
    exclude = ("embedding",)


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}  # noqa: RUF012
