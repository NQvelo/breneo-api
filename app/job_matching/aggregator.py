"""Server-to-server calls to the job aggregator. The browser never reaches it directly."""

from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

RETRYABLE_STATUSES = {502, 503, 504}
RETRIES = 2


class AggregatorError(Exception):
    """The aggregator could not be reached or did not give a usable answer."""


class AggregatorResponse:
    def __init__(self, status_code: int, data):
        self.status_code = status_code
        self.data = data


def _post(path: str, body: dict, timeout: float) -> AggregatorResponse:
    base_url = (getattr(settings, "AGGREGATOR_BASE_URL", "") or "").rstrip("/")
    key = getattr(settings, "INTERNAL_API_KEY", "") or ""
    if not base_url or not key:
        logger.error("Job aggregator is not configured: AGGREGATOR_BASE_URL or INTERNAL_API_KEY is empty")
        raise AggregatorError("not configured")

    url = f"{base_url}{path}"
    headers = {"X-Internal-Key": key, "Content-Type": "application/json"}
    last_problem = ""
    for attempt in range(RETRIES + 1):
        try:
            response = requests.post(url, json=body, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            last_problem = type(exc).__name__
            logger.warning("Job aggregator %s attempt %d failed: %s", path, attempt + 1, last_problem)
            continue

        if response.status_code in RETRYABLE_STATUSES:
            last_problem = f"HTTP {response.status_code}"
            logger.warning("Job aggregator %s attempt %d returned %s", path, attempt + 1, last_problem)
            continue

        if response.status_code == 401:
            logger.error("Job aggregator rejected X-Internal-Key on %s; check INTERNAL_API_KEY", path)
            raise AggregatorError("unauthorized")

        try:
            data = response.json()
        except ValueError:
            logger.error("Job aggregator %s returned non-JSON with HTTP %s", path, response.status_code)
            raise AggregatorError("bad response")
        return AggregatorResponse(response.status_code, data)

    logger.error("Job aggregator %s gave up after %d attempts: %s", path, RETRIES + 1, last_problem)
    raise AggregatorError(last_problem or "unavailable")


def fetch_job_matches(snapshot: dict, scope: str, limit: int, timeout: float) -> AggregatorResponse:
    body = {**snapshot, "scope": scope, "limit": int(limit)}
    return _post("/internal/job-matches", body, timeout)


def fetch_job_match(snapshot: dict, job_id: int, timeout: float) -> AggregatorResponse:
    body = {**snapshot, "jobId": int(job_id)}
    return _post("/internal/job-matches/one", body, timeout)


def fetch_job_match_search(snapshot: dict, filters: dict, limit: int, timeout: float) -> AggregatorResponse:
    body = {**snapshot, **filters, "limit": int(limit)}
    return _post("/internal/job-matches/search", body, timeout)
