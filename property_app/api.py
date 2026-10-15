from rest_framework.response import Response
from rest_framework.views import APIView

from .search import autocomplete_locations
from .serializers import AutocompleteQuerySerializer, LocationSuggestionSerializer


class LocationAutocompleteView(APIView):
    """GET /api/locations/autocomplete/?q=cox&limit=5

    Returns locations whose name starts with or contains ``q``, then ones whose name is
    semantically close to it (pgvector cosine search), so misspellings still get suggestions.
    Invalid parameters get a 400 with per-field errors.
    """

    def get(self, request):
        params = AutocompleteQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        query = params.validated_data["q"]
        locations = autocomplete_locations(query, limit=params.validated_data["limit"])
        return Response(
            {
                "query": query,
                "count": len(locations),
                "results": LocationSuggestionSerializer(locations, many=True).data,
            }
        )
