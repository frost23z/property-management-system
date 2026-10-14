from django import forms


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
