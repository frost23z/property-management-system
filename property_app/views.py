from django.shortcuts import render

from .forms import PropertySearchForm
from .search import DEFAULT_RADIUS_KM, RANK_BROAD, resolve_location, search_properties
from .selectors import popular_locations, public_properties


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
        location = resolve_location(form.cleaned_data["location"])
        radius = form.cleaned_data["radius"]
        properties = search_properties(location, form.cleaned_data["location"], radius)
    else:
        properties = public_properties().none()

    context = {
        "form": form,
        "location": location,
        "radius": radius,
        # a specific place (not just a state/country) gets distances and a radius
        "radius_search": location is not None and location.rank != RANK_BROAD,
        "properties": properties,
    }
    return render(request, "property_list.html", context)
