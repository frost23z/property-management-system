from django.db.models import Count, OuterRef, Prefetch, Q, Subquery

from .models import Location, Property, PropertyImage


def public_properties():
    """Active properties with their location and ordered images preloaded.

    Images are exposed as ``property.gallery`` (primary image first) so templates can
    render cards without issuing a query per property.
    """
    images = PropertyImage.objects.order_by("-is_primary", "sort_order")
    return (
        Property.objects.filter(is_active=True)
        .select_related("location")
        .prefetch_related(Prefetch("images", queryset=images, to_attr="gallery"))
    )


def popular_locations(limit=8):
    """Active locations ranked by how many active properties they have.

    Each location also gets ``cover`` (file name of one of its properties' primary
    images) so a destination tile can show a photo.
    """
    cover = PropertyImage.objects.filter(
        property__location=OuterRef("pk"), property__is_active=True, is_primary=True
    ).order_by("property__title")
    return (
        Location.objects.filter(is_active=True)
        .annotate(
            property_count=Count("properties", filter=Q(properties__is_active=True)),
            cover=Subquery(cover.values("image")[:1]),
        )
        .filter(property_count__gt=0)
        .order_by("-property_count", "name")[:limit]
    )
