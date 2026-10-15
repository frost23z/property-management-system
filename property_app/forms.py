from django import forms

from .search import DEFAULT_RADIUS_KM, DEFAULT_SORT, RADIUS_CHOICES_KM, SORT_CHOICES


class PropertySearchForm(forms.Form):
    location = forms.CharField(
        label="Where to?",
        min_length=2,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search a city or destination, e.g. Cox's Bazar",
                "autocomplete": "off",
            }
        ),
        error_messages={"required": "Please enter a destination to search."},
    )

    def clean_location(self):
        # collapse repeated whitespace so "  Cox's   Bazar " matches "Cox's Bazar"
        location = " ".join(self.cleaned_data["location"].split())
        if not any(char.isalpha() for char in location):
            raise forms.ValidationError("Enter a place name, e.g. Sylhet or Cox's Bazar.")
        return location

    radius = forms.ChoiceField(
        label="Search radius",
        required=False,
        choices=[(km, f"Within {km} km") for km in RADIUS_CHOICES_KM],
        initial=DEFAULT_RADIUS_KM,
    )

    def clean_radius(self):
        return int(self.cleaned_data.get("radius") or DEFAULT_RADIUS_KM)

    sort = forms.ChoiceField(
        label="Sort by",
        required=False,
        choices=SORT_CHOICES,
        initial=DEFAULT_SORT,
    )

    def clean_sort(self):
        return self.cleaned_data.get("sort") or DEFAULT_SORT
