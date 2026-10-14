from django import template

from property_app.models import Location

register = template.Library()


@register.inclusion_tag("partials/location_datalist.html")
def location_datalist(datalist_id="location-options"):
    """Render a <datalist> of active locations for the search input's suggestions."""
    return {
        "datalist_id": datalist_id,
        "locations": Location.objects.filter(is_active=True).values_list("name", flat=True),
    }
