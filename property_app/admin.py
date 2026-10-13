from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import Amenity, Location, Property


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


@admin.register(Property)
class PropertyAdmin(GISModelAdmin):
    list_display = (
        "title",
        "location",
        "property_type",
        "status",
        "price",
        "bedrooms",
        "bathrooms",
        "is_featured",
        "is_active",
    )
    list_filter = (
        "status",
        "property_type",
        "is_featured",
        "is_active",
        "location__country",
        "location__state",
        "bedrooms",
    )
    list_select_related = ("location",)
    search_fields = ("title", "address", "location__name")
    autocomplete_fields = ("location",)
    filter_horizontal = ("amenities",)
    prepopulated_fields = {"slug": ("title",)}  # noqa: RUF012
    exclude = ("embedding",)
