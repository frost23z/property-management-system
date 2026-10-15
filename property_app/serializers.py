from rest_framework import serializers

from .models import Location

AUTOCOMPLETE_DEFAULT_LIMIT = 8
AUTOCOMPLETE_MAX_LIMIT = 20


class AutocompleteQuerySerializer(serializers.Serializer):
    """Validates the query string of the autocomplete endpoint (``?q=...&limit=...``)."""

    q = serializers.CharField(min_length=2, max_length=100)
    limit = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=AUTOCOMPLETE_MAX_LIMIT,
        default=AUTOCOMPLETE_DEFAULT_LIMIT,
    )

    def validate_q(self, value):
        # collapse repeated whitespace, like the search form does
        value = " ".join(value.split())
        if not any(char.isalpha() for char in value):
            raise serializers.ValidationError("Enter a place name, e.g. Sylhet or Cox's Bazar.")
        return value


class LocationSuggestionSerializer(serializers.ModelSerializer):
    """One autocomplete suggestion. ``match`` says how the location was found."""

    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    match = serializers.ChoiceField(choices=["text", "semantic"], read_only=True)
    semantic_distance = serializers.FloatField(read_only=True, allow_null=True, default=None)

    class Meta:
        model = Location
        fields = (
            "id",
            "name",
            "slug",
            "city",
            "state",
            "country",
            "latitude",
            "longitude",
            "match",
            "semantic_distance",
        )
        read_only_fields = fields

    def get_latitude(self, obj):
        return obj.point.y if obj.point else None

    def get_longitude(self, obj):
        return obj.point.x if obj.point else None
