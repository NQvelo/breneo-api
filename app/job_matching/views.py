from __future__ import annotations

import re

from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .accounts import is_candidate
from .aggregator import AggregatorError, fetch_job_match, fetch_job_matches
from .snapshot import build_user_snapshot

SCOPES = ("georgia", "worldwide")
DEFAULT_LIMIT = 9
MAX_LIMIT = 300
REQUEST_TIMEOUT_SECONDS = 10
_DIGITS = re.compile(r"^[0-9]+$")


def _unavailable():
    return Response({"error": "Job matches are temporarily unavailable."}, status=status.HTTP_502_BAD_GATEWAY)


def _parse_limit(raw):
    if raw is None:
        return DEFAULT_LIMIT
    if not _DIGITS.match(raw):
        return None
    value = int(raw)
    return value if 1 <= value <= MAX_LIMIT else None


class _JobMatchView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not is_candidate(request.user):
            raise PermissionDenied("Job matches are available to candidate accounts only.")

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


class MeJobMatchListView(_JobMatchView):
    """GET /api/me/job-matches/?scope=georgia|worldwide&limit=9"""

    def get(self, request):
        scope = request.query_params.get("scope")
        if scope not in SCOPES:
            return Response({"error": 'scope must be "georgia" or "worldwide".'}, status=status.HTTP_400_BAD_REQUEST)
        limit = _parse_limit(request.query_params.get("limit"))
        if limit is None:
            return Response(
                {"error": f"limit must be an integer from 1 to {MAX_LIMIT}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        snapshot = build_user_snapshot(request.user.pk)
        try:
            result = fetch_job_matches(snapshot, scope, limit, REQUEST_TIMEOUT_SECONDS)
        except AggregatorError:
            return _unavailable()
        if result.status_code != 200 or not isinstance(result.data, list):
            return _unavailable()
        return Response(result.data)


class MeJobMatchDetailView(_JobMatchView):
    """GET /api/me/job-matches/<job_id>/"""

    def get(self, request, job_id: int):
        snapshot = build_user_snapshot(request.user.pk)
        try:
            result = fetch_job_match(snapshot, job_id, REQUEST_TIMEOUT_SECONDS)
        except AggregatorError:
            return _unavailable()
        if result.status_code == 404 and isinstance(result.data, dict):
            return Response(result.data, status=status.HTTP_404_NOT_FOUND)
        if result.status_code != 200 or not isinstance(result.data, dict):
            return _unavailable()
        return Response(result.data)
