import logging

from django.conf import settings
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.db.models import Case, F, IntegerField, Q, Value, When
from django.db.models.functions import Length
from pgvector.django import CosineDistance

from . import embeddings
from .models import Location
from .selectors import public_properties

logger = logging.getLogger(__name__)

# How a location matched the text a visitor typed (lower is a better match).
RANK_EXACT = 0  # whole name or city equals the text
RANK_PREFIX = 1  # city or name starts with the text
RANK_CITY = 2  # city contains the text
RANK_BROAD = 3  # only the state, country or full name contains it ("Bangladesh")
RANK_SEMANTIC = 4  # no text match; chosen because its name is close in meaning (pgvector)

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


def semantic_locations(text, limit=5, max_distance=None):
    """Active locations whose name embedding is close to the text, closest first.

    The text is embedded with the same model used for the stored location names and compared
    with pgvector's cosine distance (``<=>``), which the HNSW index on ``Location.embedding``
    speeds up. Each result carries a ``semantic_distance`` annotation (0 is identical); anything
    farther than ``max_distance`` (default ``settings.SEMANTIC_MAX_DISTANCE``) is dropped.
    """
    text = (text or "").strip()
    if not text:
        return Location.objects.none()
    if max_distance is None:
        max_distance = settings.SEMANTIC_MAX_DISTANCE
    return (
        Location.objects.filter(is_active=True, embedding__isnull=False)
        .annotate(semantic_distance=CosineDistance("embedding", embeddings.embed_text(text)))
        .filter(semantic_distance__lte=max_distance)
        .order_by("semantic_distance")[:limit]
    )


def find_location(text):
    """Resolve what a visitor typed to a Location: by text first, then by meaning.

    A plain text match ("Sylhet", "cox") always wins. Only when nothing matches does the text
    get embedded and compared against the stored location vectors, so a misspelling or a
    different wording ("Coxs Bazaar") still lands on the right place. The semantic match comes
    back with ``rank == RANK_SEMANTIC`` and a ``semantic_distance``; the caller then runs the
    usual PostGIS radius search around it, so the final ranking fuses both signals: meaning
    picks the place, geography orders the stays.
    """
    location = resolve_location(text)
    if location is not None:
        return location
    try:
        location = next(iter(semantic_locations(text, limit=1)), None)
    except Exception:  # model missing/offline must not turn a no-match into a server error
        logger.exception("Semantic location search failed for %r", text)
        return None
    if location is not None:
        location.rank = RANK_SEMANTIC
    return location


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


NEARBY_STAYS_KM = 15
NEARBY_PLACES_KM = 40


def circle_around(point, radius_km):
    """A true-radius circle (as a 4326 polygon) around a point.

    Buffering in degrees would give an oval, because a degree of longitude is shorter than a
    degree of latitude. So the point is moved into its UTM zone (metres), buffered there, and
    moved back.
    """
    zone = int((point.x + 180) // 6) + 1
    utm_srid = (32600 if point.y >= 0 else 32700) + zone
    circle = point.transform(utm_srid, clone=True).buffer(radius_km * 1000)
    circle.transform(4326)
    return circle


def nearby_properties(stay, radius_km=NEARBY_STAYS_KM, limit=4):
    """Other stays within ``radius_km`` of this one (PostGIS DWithin), nearest first."""
    if stay.point is None:
        return public_properties().none()
    return (
        public_properties()
        .filter(point__dwithin=(stay.point, D(km=radius_km)))
        .exclude(pk=stay.pk)
        .annotate(distance=Distance("point", stay.point))
        .order_by("distance", "title")[:limit]
    )


def nearby_locations(stay, radius_km=NEARBY_PLACES_KM, limit=5):
    """Other destinations whose centre falls inside a circle around this stay (Intersects).

    The stay's own location is left out. Results are nearest first and carry a ``distance``.
    """
    if stay.point is None:
        return Location.objects.none()
    return (
        Location.objects.filter(
            is_active=True, point__intersects=circle_around(stay.point, radius_km)
        )
        .exclude(pk=stay.location_id)
        .annotate(distance=Distance("point", stay.point))
        .order_by("distance")[:limit]
    )
