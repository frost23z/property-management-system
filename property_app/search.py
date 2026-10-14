from django.db.models import Case, IntegerField, Q, Value, When
from django.db.models.functions import Length

from .models import Location
from .selectors import public_properties

# How a location matched the text a visitor typed (lower is a better match).
RANK_EXACT = 0  # whole name or city equals the text
RANK_PREFIX = 1  # city or name starts with the text
RANK_CITY = 2  # city contains the text
RANK_BROAD = 3  # only the state, country or full name contains it ("Bangladesh")


def resolve_location(text):
    """Return the active Location that best matches free text, or None.

    The result carries a ``rank`` attribute (see the RANK_* constants) saying how good
    the match was. Ties are broken by the shortest city name, so "Chattogram" picks
    "Chattogram City" over "Chattogram (Patenga)".
    """
    text = (text or "").strip()
    if not text:
        return None
    return (
        Location.objects.filter(is_active=True)
        .filter(
            Q(name__icontains=text)
            | Q(city__icontains=text)
            | Q(state__icontains=text)
            | Q(country__icontains=text)
        )
        .annotate(
            rank=Case(
                When(Q(name__iexact=text) | Q(city__iexact=text), then=Value(RANK_EXACT)),
                When(
                    Q(city__istartswith=text) | Q(name__istartswith=text), then=Value(RANK_PREFIX)
                ),
                When(city__icontains=text, then=Value(RANK_CITY)),
                default=Value(RANK_BROAD),
                output_field=IntegerField(),
            )
        )
        .order_by("rank", Length("city"), "name")
        .first()
    )


def search_properties(location):
    """Active properties for a resolved location (None means no match)."""
    if location is None:
        return public_properties().none()
    return public_properties().filter(location=location).order_by("title")
