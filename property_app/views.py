from django.shortcuts import render

from .forms import PropertySearchForm
from .search import resolve_location, search_properties
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
    if not form.is_bound:
        properties = public_properties().order_by("title")
    elif form.is_valid():
        location = resolve_location(form.cleaned_data["location"])
        properties = search_properties(location)
    else:
        properties = public_properties().none()

    context = {"form": form, "location": location, "properties": properties}
    return render(request, "property_list.html", context)
