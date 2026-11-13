from django.core.management.base import BaseCommand, CommandError

from app.job_matching.daily_email import run_daily_job_match_emails


class Command(BaseCommand):
    help = "Send today's job-match email (Asia/Tbilisi date) to every eligible candidate. Safe to re-run."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Jobs per email, 1-300. Defaults to JOB_MATCH_EMAIL_LIMIT.")

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit is not None and not 1 <= limit <= 300:
            raise CommandError("--limit must be an integer from 1 to 300.")
        stats = run_daily_job_match_emails(limit=limit)
        self.stdout.write(
            f"Job-match emails for {stats.sent_on}: visited={stats.visited} skipped={stats.skipped} "
            f"matched={stats.matched} sent={stats.sent} below_threshold={stats.not_qualified} "
            f"already_sent={stats.already_sent} aggregator_failed={stats.aggregator_failed} "
            f"send_failed={stats.send_failed} errors={len(stats.errors)}"
        )
