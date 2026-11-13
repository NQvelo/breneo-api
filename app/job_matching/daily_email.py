"""Daily 15:00 Asia/Tbilisi job-match email. Scores come from the aggregator; nothing is recomputed here."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .accounts import has_verified_email, is_candidate
from .aggregator import AggregatorError, fetch_job_matches
from .snapshot import build_user_snapshot, tbilisi_today

logger = logging.getLogger(__name__)

PAGE_SIZE = 25
REQUEST_TIMEOUT_SECONDS = 15
MIN_TOP_MATCH_PERCENT = 50
STALE_SENDING_AFTER = timedelta(minutes=15)


@dataclass
class RunStats:
    sent_on: date
    visited: int = 0
    skipped: int = 0
    matched: int = 0
    sent: int = 0
    not_qualified: int = 0
    already_sent: int = 0
    aggregator_failed: int = 0
    send_failed: int = 0
    errors: list = field(default_factory=list)


def email_limit() -> int:
    return int(getattr(settings, "JOB_MATCH_EMAIL_LIMIT", 5))


def job_url(job_id) -> str:
    return settings.JOB_MATCH_JOB_URL.format(id=job_id)


def run_daily_job_match_emails(limit: int | None = None) -> RunStats:
    """Visit every candidate with a verified email, 25 users in memory at a time, in id order."""
    limit = email_limit() if limit is None else int(limit)
    stats = RunStats(sent_on=tbilisi_today())
    User = get_user_model()

    last_id = 0
    while True:
        page = list(
            User.objects.filter(pk__gt=last_id, is_active=True)
            .exclude(email="")
            .order_by("pk")[:PAGE_SIZE]
        )
        if not page:
            break
        for user in page:
            stats.visited += 1
            try:
                _process_user(user, stats, limit)
            except Exception as exc:
                logger.exception("Job-match email failed for user %s", user.pk)
                stats.errors.append((user.pk, type(exc).__name__))
        last_id = page[-1].pk
    return stats


def _process_user(user, stats: RunStats, limit: int) -> None:
    from app.models import JobMatchEmail

    if not has_verified_email(user) or not is_candidate(user):
        stats.skipped += 1
        return
    if JobMatchEmail.objects.filter(user=user, sent_on=stats.sent_on, delivered=True).exists():
        stats.already_sent += 1
        return

    snapshot = build_user_snapshot(user.pk)
    try:
        result = fetch_job_matches(snapshot, "worldwide", limit, REQUEST_TIMEOUT_SECONDS)
    except AggregatorError:
        stats.aggregator_failed += 1
        return
    if result.status_code != 200 or not isinstance(result.data, list):
        logger.error("Job aggregator returned HTTP %s for user %s", result.status_code, user.pk)
        stats.aggregator_failed += 1
        return
    stats.matched += 1

    jobs = result.data
    if not jobs or not _top_match_qualifies(jobs[0]):
        stats.not_qualified += 1
        return

    row = _claim_send(user, stats.sent_on)
    if row is None:
        stats.already_sent += 1
        return

    ok = _send(user, jobs[:limit])
    if ok:
        JobMatchEmail.objects.filter(pk=row.pk).update(delivered=True)
        stats.sent += 1
    else:
        JobMatchEmail.objects.filter(pk=row.pk).delete()
        stats.send_failed += 1


def _top_match_qualifies(job) -> bool:
    percent = job.get("match_percent") if isinstance(job, dict) else None
    return isinstance(percent, int) and not isinstance(percent, bool) and percent >= MIN_TOP_MATCH_PERCENT


def _claim_send(user, sent_on: date):
    """Insert the (user, date) row in its own short transaction. None means someone already has it."""
    from app.models import JobMatchEmail

    stale_before = timezone.now() - STALE_SENDING_AFTER
    try:
        with transaction.atomic():
            JobMatchEmail.objects.filter(
                user=user, sent_on=sent_on, delivered=False, created_at__lt=stale_before
            ).delete()
            return JobMatchEmail.objects.create(user=user, sent_on=sent_on)
    except IntegrityError:
        return None


def _send(user, jobs: list) -> bool:
    from app.views import send_email_safely

    context = {
        "first_name": (user.first_name or "").strip(),
        "jobs": [
            {
                "title": job.get("title") or "",
                "company": job.get("company") or "",
                "location": job.get("location") or "",
                "match_percent": job.get("match_percent"),
                "url": job_url(job.get("id")),
            }
            for job in jobs
        ],
        "logo_url": getattr(settings, "BRENEO_LOGO_URL", ""),
    }
    html = render_to_string("emails/job_matches.html", context)
    text = render_to_string("emails/job_matches.txt", context)
    ok, error = send_email_safely(
        "Your top job matches today", text, html, settings.DEFAULT_FROM_EMAIL, user.email
    )
    if not ok:
        logger.warning("Job-match email to user %s was not accepted: %s", user.pk, error)
    return ok
