import logging
import time
from datetime import datetime, timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from app.job_matching.snapshot import TBILISI

logger = logging.getLogger(__name__)

RUN_HOUR = 15


def next_run_after(now: datetime) -> datetime:
    """Next 15:00 on the Asia/Tbilisi wall clock, strictly after ``now``."""
    local = now.astimezone(TBILISI)
    target = local.replace(hour=RUN_HOUR, minute=0, second=0, microsecond=0)
    if target <= local:
        target = (local + timedelta(days=1)).replace(hour=RUN_HOUR, minute=0, second=0, microsecond=0)
    return target


class Command(BaseCommand):
    help = "Long-running worker: sends job-match emails every day at 15:00 Asia/Tbilisi."

    def handle(self, *args, **options):
        while True:
            target = next_run_after(datetime.now(TBILISI))
            self.stdout.write(f"Next job-match email run at {target.isoformat()}")
            while (remaining := (target - datetime.now(TBILISI)).total_seconds()) > 0:
                time.sleep(min(remaining, 60))
            close_old_connections()
            try:
                call_command("send_job_match_emails", stdout=self.stdout)
            except Exception:
                logger.exception("Job-match email run failed")
            finally:
                close_old_connections()
