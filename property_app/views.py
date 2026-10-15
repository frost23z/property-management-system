from django.contrib.gis.db.models.functions import Distance
from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import get_object_or_404, render

from .forms import PropertySearchForm
from .search import (
    DEFAULT_RADIUS_KM,
    NEARBY_PLACES_KM,
    NEARBY_STAYS_KM,
    RANK_BROAD,
    RANK_SEMANTIC,
    find_location,
    nearby_locations,
    nearby_properties,
    search_properties,
    sort_properties,
)
from .selectors import popular_locations, public_properties

PAGE_SIZE = 12


def home(request):
    featured = public_properties().filter(is_featured=True).order_by("?")[:6]
    context = {
        "form": PropertySearchForm(),
        "featured_properties": featured,
        "popular_locations": popular_locations(),
    }
    return render(request, "home.html", context)


def property_list(request):
    """Browse all stays, or search them by location when a query is given."""
    # only a submitted search binds the form; a bare ?page=2 must still browse all stays
    form = PropertySearchForm(request.GET if "location" in request.GET else None)
    location = None
    radius = DEFAULT_RADIUS_KM
    if not form.is_bound:
        properties = public_properties().order_by("title")
    elif form.is_valid():
        location = find_location(form.cleaned_data["location"])
        radius = form.cleaned_data["radius"]
        properties = search_properties(location, form.cleaned_data["location"], radius)
        properties = sort_properties(properties, form.cleaned_data["sort"])
    else:
        properties = public_properties().none()

    paginator = Paginator(properties, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))  # bad page numbers fall back safely
    # keep the search in the page links, but let each link set its own page number
    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "form": form,
        "location": location,
        "radius": radius,
        "page_obj": page_obj,
        "page_range": paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1),
        "querystring": params.urlencode(),
        # only needed on a dead end, so skip the query when there are results
        "suggested_locations": [] if page_obj else popular_locations(6),
        # a specific place (not just a state/country) gets distances and a radius
        "radius_search": location is not None and location.rank != RANK_BROAD,
        # nothing matched the text, so this place was picked because its name is similar
        "semantic_match": location is not None and location.rank == RANK_SEMANTIC,
    }
    return render(request, "property_list.html", context)


def property_detail(request, slug):
    stays = (
        public_properties()
        .prefetch_related("amenities")
        # straight-line distance from the property to the centre of its city
        .annotate(distance_to_city=Distance("point", F("location__point")))
    )
    stay = get_object_or_404(stays, slug=slug)
    context = {
        "property": stay,
        "nearby_stays": nearby_properties(stay),
        "nearby_locations": nearby_locations(stay),
        "nearby_stays_km": NEARBY_STAYS_KM,
        "nearby_places_km": NEARBY_PLACES_KM,
    }
    return render(request, "property_detail.html", context)
