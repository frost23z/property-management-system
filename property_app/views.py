from django.http import HttpResponse
from django.shortcuts import render

from .forms import PropertySearchForm
from .selectors import public_properties


def home(request):
    featured = public_properties().filter(is_featured=True).order_by("?")[:6]
    context = {"form": PropertySearchForm(), "featured_properties": featured}
    return render(request, "home.html", context)


def property_list(request):
    # placeholder: replaced by the real listing page in the next commits
    return HttpResponse("Search results coming soon")
