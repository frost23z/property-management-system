from django.http import HttpResponse
from django.shortcuts import render

from .forms import PropertySearchForm


def home(request):
    return render(request, "home.html", {"form": PropertySearchForm()})


def property_list(request):
    # placeholder: replaced by the real listing page in the next commits
    return HttpResponse("Search results coming soon")
