from django.urls import path

from . import views

app_name = "property_app"

urlpatterns = [
    path("", views.home, name="home"),
    path("properties/", views.property_list, name="property_list"),
]
