from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.utils.html import format_html

from .models import Amenity, Location, Property, PropertyImage


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


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ("preview", "image", "alt_text", "caption", "is_primary", "sort_order")
    readonly_fields = ("preview",)
    ordering = ("sort_order",)

    @admin.display(description="Preview")
    def preview(self, obj):
        if obj.pk and obj.image:
            return format_html(
                '<img src="{}" alt="{}" style="height:80px;border-radius:4px">',
                obj.image.url,
                obj.alt_text,
            )
        return "-"


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
    inlines = (PropertyImageInline,)
    prepopulated_fields = {"slug": ("title",)}  # noqa: RUF012
    exclude = ("embedding",)
