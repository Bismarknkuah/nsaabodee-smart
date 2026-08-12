"""
Shared pagination helper for the handful of custom APIView endpoints in
this platform that return a list but aren't a DRF generic/ViewSet (which
already paginate automatically via ListModelMixin). Used anywhere a list
could plausibly grow large: a funeral's contribution ledger, its gift
donations, its expenses, its attendance records, and the community-wide
defaulters list — none of which should ever hand back an unbounded JSON
array just because nobody happened to build them as a ViewSet.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


def paginate_response(request, queryset, serializer_class, serializer_context=None) -> Response:
    paginator = PageNumberPagination()
    paginator.page_size = 25
    page = paginator.paginate_queryset(queryset, request)
    serializer = serializer_class(page, many=True, context=serializer_context or {})
    return paginator.get_paginated_response(serializer.data)
