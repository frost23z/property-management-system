from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.db.models import Case, F, IntegerField, Q, Value, When
from django.db.models.functions import Length

from .models import Location
from .selectors import public_properties

# How a location matched the text a visitor typed (lower is a better match).
RANK_EXACT = 0  # whole name or city equals the text
RANK_PREFIX = 1  # city or name starts with the text
RANK_CITY = 2  # city contains the text
RANK_BROAD = 3  # only the state, country or full name contains it ("Bangladesh")

RADIUS_CHOICES_KM = (5, 10, 25, 50, 100)
DEFAULT_RADIUS_KM = 25

# "nearest" keeps the order search_properties() already chose (distance, or title for
# searches that have no distance); the others re-order the results.
SORT_CHOICES = (
    ("nearest", "Nearest first"),
    ("price_asc", "Price: low to high"),
    ("price_desc", "Price: high to low"),
    ("bedrooms", "Most bedrooms"),
)
DEFAULT_SORT = "nearest"
_SORT_ORDERINGS = {
    "price_asc": ("price", "title"),
    "price_desc": ("-price", "title"),
    "bedrooms": ("-bedrooms", "title"),
}


def _matches(text):
    return (
        Q(name__icontains=text)
        | Q(city__icontains=text)
        | Q(state__icontains=text)
        | Q(country__icontains=text)
    )


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
        .filter(_matches(text))
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


def search_properties(location, text="", radius_km=DEFAULT_RADIUS_KM):
    """Active properties for a resolved location (None means no match).

    * A specific place: every property within ``radius_km`` of the place's centre (PostGIS
      ``ST_DWithin`` on the geography column), plus the place's own properties even if they
      sit outside the radius. Results carry a ``distance`` annotation and are nearest first.
    * A broad match (state or country only): every property in the matching locations,
      alphabetically, with no distance.
    """
    if location is None:
        return public_properties().none()

    if location.rank == RANK_BROAD:
        locations = Location.objects.filter(is_active=True).filter(_matches(text.strip()))
        return public_properties().filter(location__in=locations).order_by("title")

    origin = location.point
    if origin is None:  # place has no coordinates, so only exact membership is possible
        return public_properties().filter(location=location).order_by("title")

    return (
        public_properties()
        .filter(Q(location=location) | Q(point__dwithin=(origin, D(km=radius_km))))
        .annotate(distance=Distance("point", origin))
        .order_by(F("distance").asc(nulls_last=True), "title")
    )


def sort_properties(properties, sort=DEFAULT_SORT):
    ordering = _SORT_ORDERINGS.get(sort)
    return properties.order_by(*ordering) if ordering else properties
