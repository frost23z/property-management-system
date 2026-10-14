from django.db.models import Prefetch

from .models import Property, PropertyImage


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
