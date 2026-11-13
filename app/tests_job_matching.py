import hashlib
from datetime import date, timedelta
from unittest import mock

import requests
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from app.job_matching import snapshot as snap
from app.job_matching.daily_email import run_daily_job_match_emails
from app.management.commands.run_job_match_scheduler import next_run_after
from app.models import (
    Employer,
    JobMatchEmail,
    Skill,
    SkillTestResult,
    UserIndustryProfile,
    UserProfile,
    UserResume,
    UserSkill,
    WorkExperience,
)

AGGREGATOR = {"AGGREGATOR_BASE_URL": "http://aggregator.test", "INTERNAL_API_KEY": "secret-key"}
TODAY = date(2026, 11, 13)


def make_candidate(email, **extra):
    user = User.objects.create(username=email, email=email, is_active=True, **extra)
    UserProfile.objects.create(user=user)
    return user


def add_skill(user, name):
    skill = Skill.objects.filter(name__iexact=name).first() or Skill.objects.create(name=name)
    UserSkill.objects.get_or_create(user=user, skill=skill)


def fake_response(status_code, payload):
    response = mock.Mock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


def job(job_id, percent, **extra):
    data = {
        "id": job_id,
        "title": f"Job {job_id}",
        "company": "Acme & Co",
        "location": "Tbilisi",
        "posted_at": "2026-11-01T00:00:00Z",
        "match_percent": percent,
        "skills_percent": None,
        "experience_percent": 40,
        "industry_percent": None,
    }
    data.update(extra)
    return data


class SnapshotTestBase(TestCase):
    def setUp(self):
        snap.snapshot_cache().clear()
        patcher = mock.patch("app.job_matching.snapshot.tbilisi_today", return_value=TODAY)
        patcher.start()
        self.addCleanup(patcher.stop)


class SnapshotTests(SnapshotTestBase):
    def test_empty_profile_is_still_a_snapshot(self):
        user = make_candidate("new@example.com")
        s = snap.build_user_snapshot(user.pk)
        self.assertEqual(s["userId"], str(user.pk))
        self.assertEqual(s["skills"], [])
        self.assertEqual(s["seniority"], "unknown")
        self.assertIsNone(s["yearsExperienceTotal"])
        self.assertEqual(s["industryYears"], {})
        self.assertEqual(s["languages"], [])
        self.assertRegex(s["profileVersion"], r"^[0-9a-f]{64}$")

    def test_skills_merge_profile_and_latest_skill_test_only(self):
        user = make_candidate("skills@example.com")
        for name in ["  Search  Engine   Optimization ", "QuickBooks", "HIPAA", "Salesforce", "AutoCAD", "Epic EMR"]:
            add_skill(user, name)
        old = SkillTestResult.objects.create(
            user=user, final_role="x", total_score="1 / 2", skills_json={"tech": {"OldOnly": "50%"}}
        )
        SkillTestResult.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=400))
        SkillTestResult.objects.create(
            user=user,
            final_role="x",
            total_score="1 / 2",
            skills_json={"tech": {"Financial Modelling": "90%", "quickbooks": "10%"}, "soft": ["Negotiation", "", 3]},
        )
        s = snap.build_user_snapshot(user.pk)
        self.assertEqual(
            s["skills"],
            [
                "autocad",
                "epic emr",
                "financial modelling",
                "hipaa",
                "negotiation",
                "quickbooks",
                "salesforce",
                "search engine optimization",
            ],
        )

    def test_entry_level_title_is_junior(self):
        user = make_candidate("entry@example.com")
        WorkExperience.objects.create(
            user=user, job_title="Entry Level Analyst", company="A", start_date=date(2016, 1, 1), is_current=True
        )
        self.assertEqual(snap.build_user_snapshot(user.pk)["seniority"], "junior")

    def test_senior_checked_before_lead(self):
        self.assertEqual(snap.seniority_from_title("Senior Lead Engineer"), "senior")
        self.assertEqual(snap.seniority_from_title("Principal Consultant"), "lead")
        self.assertEqual(snap.seniority_from_title("Mid-level Accountant"), "mid")
        self.assertIsNone(snap.seniority_from_title("Internal Auditor"))

    def test_title_without_level_uses_year_bands(self):
        self.assertEqual(snap.seniority_from_years(2.99), "junior")
        self.assertEqual(snap.seniority_from_years(3.0), "mid")
        self.assertEqual(snap.seniority_from_years(6.0), "senior")
        self.assertEqual(snap.seniority_from_years(None), "unknown")

        user = make_candidate("sixyears@example.com")
        WorkExperience.objects.create(
            user=user, job_title="Accountant", company="A", start_date=TODAY - timedelta(days=2192), is_current=True
        )
        s = snap.build_user_snapshot(user.pk)
        self.assertEqual(s["yearsExperienceTotal"], 6.0)
        self.assertEqual(s["seniority"], "senior")

    def test_years_count_old_and_overlapping_roles_and_skip_reversed(self):
        user = make_candidate("years@example.com")
        WorkExperience.objects.create(
            user=user, job_title="Clerk", company="A", start_date=date(2010, 1, 1), end_date=date(2011, 1, 1)
        )
        WorkExperience.objects.create(
            user=user, job_title="Clerk", company="B", start_date=date(2010, 6, 1), end_date=date(2011, 6, 1)
        )
        WorkExperience.objects.create(
            user=user, job_title="Broken", company="C", start_date=date(2012, 1, 1), end_date=date(2011, 1, 1)
        )
        WorkExperience.objects.create(user=user, job_title="Undated", company="D")
        s = snap.build_user_snapshot(user.pk)
        self.assertEqual(s["yearsExperienceTotal"], round((365 + 365) / 365.25, 2))
        self.assertIsInstance(s["yearsExperienceTotal"], float)

    def test_title_from_current_role_with_latest_start(self):
        user = make_candidate("current@example.com")
        WorkExperience.objects.create(
            user=user, job_title="Lead Nurse", company="A", start_date=date(2025, 1, 1), end_date=date(2026, 1, 1)
        )
        WorkExperience.objects.create(
            user=user, job_title="Junior Nurse", company="B", start_date=date(2020, 1, 1), is_current=True
        )
        WorkExperience.objects.create(
            user=user, job_title="Senior Nurse", company="C", start_date=date(2022, 1, 1), is_current=True
        )
        self.assertEqual(snap.build_user_snapshot(user.pk)["seniority"], "senior")

    def test_industry_years_dict_and_list(self):
        self.assertEqual(
            snap.normalize_industry_years({" FinTech ": 1, "fintech": 1.5, "Health  Care": 0, "": 3, "x": "abc"}),
            {"fintech": 2.5},
        )
        self.assertEqual(
            snap.normalize_industry_years([{"tag": "Retail", "years": 1.234}, {"tag": "retail", "years": 1}]),
            {"retail": 2.23},
        )
        self.assertEqual(snap.normalize_industry_years([{"tag": "Gov", "years": -1}]), {})

    def test_languages_from_resume(self):
        user = make_candidate("lang@example.com")
        UserResume.objects.create(
            user=user,
            data={"languages": [{"name_en": "  English   C1 ", "name_ka": ""}, {"name_en": "", "name_ka": "ქართული"}, "Russian"]},
        )
        self.assertEqual(snap.build_user_snapshot(user.pk)["languages"], ["English C1", "Russian", "ქართული"])

    def test_profile_version_matches_documented_canonical_json(self):
        expected = hashlib.sha256(
            b'{"industryYears":{"fintech":2.0},"languages":["English C1"],"seniority":"mid",'
            b'"skills":["quickbooks","seo"],"yearsExperienceTotal":4.0}'
        ).hexdigest()
        version = snap.profile_version(
            {
                "skills": ["quickbooks", "seo"],
                "seniority": "mid",
                "yearsExperienceTotal": 4.0,
                "industryYears": {"fintech": 2.0},
                "languages": ["English C1"],
            }
        )
        self.assertEqual(version, expected)

    def test_cache_shared_and_deleted_on_every_profile_edit(self):
        user = make_candidate("cache@example.com")
        add_skill(user, "SEO")
        first = snap.build_user_snapshot(user.pk)
        self.assertEqual(snap.build_user_snapshot(user.pk), first)

        versions = {first["profileVersion"]}
        edits = [
            lambda: add_skill(user, "QuickBooks"),
            lambda: SkillTestResult.objects.create(
                user=user, final_role="r", total_score="1 / 1", skills_json={"soft": ["Mentoring"]}
            ),
            lambda: WorkExperience.objects.create(
                user=user, job_title="Analyst", company="A", start_date=date(2020, 1, 1), is_current=True
            ),
            lambda: UserIndustryProfile.objects.create(
                user=user, industry_years_json={"fintech": 2}, updated_at=timezone.now()
            ),
            lambda: UserResume.objects.create(user=user, data={"languages": ["English C1"]}),
            lambda: UserSkill.objects.filter(user=user, skill__name="SEO").delete(),
        ]
        for edit in edits:
            edit()
            versions.add(snap.build_user_snapshot(user.pk)["profileVersion"])
        self.assertEqual(len(versions), len(edits) + 1)

    def test_skill_rename_clears_holders(self):
        user = make_candidate("rename@example.com")
        add_skill(user, "Quickbooks")
        before = snap.build_user_snapshot(user.pk)
        skill = Skill.objects.get(name="Quickbooks")
        skill.name = "QuickBooks Online"
        skill.save()
        self.assertEqual(snap.build_user_snapshot(user.pk)["skills"], ["quickbooks online"])
        self.assertNotEqual(snap.build_user_snapshot(user.pk)["profileVersion"], before["profileVersion"])


@override_settings(**AGGREGATOR)
class JobMatchEndpointTests(SnapshotTestBase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.user = make_candidate("old@example.com")
        User.objects.filter(pk=self.user.pk).update(date_joined=timezone.now() - timedelta(days=2000))
        add_skill(self.user, "SEO")
        WorkExperience.objects.create(
            user=self.user, job_title="Marketer", company="A", start_date=date(2018, 1, 1), end_date=date(2022, 1, 1)
        )
        self.client.force_authenticate(self.user)

    @mock.patch("app.job_matching.aggregator.requests.post")
    def test_old_user_gets_aggregator_list_unchanged(self, post):
        payload = [job(7, 88), job(3, 51, location=None, posted_at=None)]
        post.return_value = fake_response(200, payload)
        response = self.client.get("/api/me/job-matches/?scope=worldwide&limit=300&userId=999")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        self.assertEqual(response["Cache-Control"], "no-store")

        url = post.call_args.args[0]
        body = post.call_args.kwargs["json"]
        self.assertEqual(url, "http://aggregator.test/internal/job-matches")
        self.assertEqual(post.call_args.kwargs["headers"]["X-Internal-Key"], "secret-key")
        self.assertEqual(post.call_args.kwargs["timeout"], 10)
        self.assertEqual(body["userId"], str(self.user.pk))
        self.assertEqual(body["limit"], 300)
        self.assertIs(type(body["limit"]), int)
        self.assertEqual(body["scope"], "worldwide")
        self.assertEqual(body["skills"], ["seo"])
        self.assertEqual(body["seniority"], "mid")

    @mock.patch("app.job_matching.aggregator.requests.post")
    def test_empty_list_is_200_and_default_limit_is_9(self, post):
        post.return_value = fake_response(200, [])
        response = self.client.get("/api/me/job-matches/?scope=georgia")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        self.assertEqual(post.call_args.kwargs["json"]["limit"], 9)

    @mock.patch("app.job_matching.aggregator.requests.post")
    def test_validation(self, post):
        for query in ["", "?scope=Georgia", "?scope=all", "?scope=georgia&limit=0", "?scope=georgia&limit=301",
                      "?scope=georgia&limit=abc", "?scope=georgia&limit=-1", "?scope=georgia&limit=5.0"]:
            response = self.client.get(f"/api/me/job-matches/{query}")
            self.assertEqual(response.status_code, 400, query)
        post.assert_not_called()

    def test_requires_login(self):
        response = APIClient().get("/api/me/job-matches/?scope=georgia")
        self.assertEqual(response.status_code, 401)

    @mock.patch("app.job_matching.aggregator.requests.post")
    def test_employer_without_candidate_profile_is_forbidden(self, post):
        employer = User.objects.create(username="boss@example.com", email="boss@example.com")
        Employer.objects.create(user=employer)
        client = APIClient()
        client.force_authenticate(employer)
        self.assertEqual(client.get("/api/me/job-matches/?scope=georgia").status_code, 403)
        self.assertEqual(client.get("/api/me/job-matches/5/").status_code, 403)
        post.assert_not_called()

    @mock.patch("app.job_matching.aggregator.requests.post")
    def test_retries_on_gateway_errors_and_network_errors(self, post):
        post.side_effect = [requests.ConnectionError(), fake_response(503, {}), fake_response(200, [job(1, 60)])]
        response = self.client.get("/api/me/job-matches/?scope=georgia")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(post.call_count, 3)

    @mock.patch("app.job_matching.aggregator.requests.post")
    def test_gives_up_after_two_retries(self, post):
        post.return_value = fake_response(504, {})
        response = self.client.get("/api/me/job-matches/?scope=georgia")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(post.call_count, 3)

    @mock.patch("app.job_matching.aggregator.requests.post")
    def test_wrong_key_is_502_without_retry_or_leak(self, post):
        post.return_value = fake_response(401, {"error": "bad key secret-key"})
        response = self.client.get("/api/me/job-matches/?scope=georgia")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(post.call_count, 1)
        self.assertNotIn("secret-key", response.content.decode())

    @mock.patch("app.job_matching.aggregator.requests.post")
    def test_400_is_not_retried(self, post):
        post.return_value = fake_response(400, {"error": "userId required"})
        self.assertEqual(self.client.get("/api/me/job-matches/?scope=georgia").status_code, 502)
        self.assertEqual(post.call_count, 1)

    @mock.patch("app.job_matching.aggregator.requests.post")
    def test_single_job_passthrough_and_404(self, post):
        post.return_value = fake_response(200, job(42, 73))
        response = self.client.get("/api/me/job-matches/42/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), job(42, 73))
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(post.call_args.args[0], "http://aggregator.test/internal/job-matches/one")
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["jobId"], 42)
        self.assertNotIn("scope", body)
        self.assertNotIn("limit", body)

        post.return_value = fake_response(404, {"error": "Job not found."})
        response = self.client.get("/api/me/job-matches/43/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": "Job not found."})

    @mock.patch("app.job_matching.aggregator.requests.post")
    def test_two_devices_share_profile_version_until_edit(self, post):
        post.return_value = fake_response(200, [])
        other_device = APIClient()
        other_device.force_authenticate(self.user)
        self.client.get("/api/me/job-matches/?scope=georgia")
        first = post.call_args.kwargs["json"]["profileVersion"]
        other_device.get("/api/me/job-matches/?scope=georgia")
        self.assertEqual(post.call_args.kwargs["json"]["profileVersion"], first)

        self.client.post("/api/me/skills/", {"name": "HIPAA"}, format="json")
        other_device.get("/api/me/job-matches/?scope=georgia")
        self.assertNotEqual(post.call_args.kwargs["json"]["profileVersion"], first)
        self.assertIn("hipaa", post.call_args.kwargs["json"]["skills"])


@override_settings(**AGGREGATOR, JOB_MATCH_JOB_URL="https://app.test/jobs/{id}")
class DailyEmailTests(SnapshotTestBase):
    def setUp(self):
        super().setUp()
        tz_patch = mock.patch("app.job_matching.daily_email.tbilisi_today", return_value=TODAY)
        tz_patch.start()
        self.addCleanup(tz_patch.stop)
        send_patch = mock.patch("app.views.send_email_safely", return_value=(True, None))
        self.send = send_patch.start()
        self.addCleanup(send_patch.stop)

    def _post_returning(self, payload_by_user=None, default=None):
        def post(url, json, headers, timeout):
            self.assertEqual(timeout, 15)
            self.assertEqual(json["scope"], "worldwide")
            payload = (payload_by_user or {}).get(json["userId"], default)
            if isinstance(payload, Exception):
                raise payload
            return fake_response(200, payload)

        return post

    def test_visits_every_eligible_user_across_many_pages(self):
        users = [make_candidate(f"u{i}@example.com") for i in range(60)]
        unverified = make_candidate("first@example.com")
        unverified.email = "changed@example.com"
        unverified.save()
        no_email = User.objects.create(username="noemail", email="")
        employer = User.objects.create(username="emp@example.com", email="emp@example.com")
        Employer.objects.create(user=employer)
        dual = User.objects.create(username="dual@example.com", email="dual@example.com")
        Employer.objects.create(user=dual)
        UserProfile.objects.bulk_create([UserProfile(user=dual)])

        with mock.patch("app.job_matching.aggregator.requests.post", side_effect=self._post_returning(default=[job(1, 50)])) as post:
            stats = run_daily_job_match_emails()

        called = {c.kwargs["json"]["userId"] for c in post.call_args_list}
        expected = {str(u.pk) for u in users} | {str(dual.pk)}
        self.assertEqual(called, expected)
        self.assertEqual(stats.sent, len(expected))
        self.assertEqual(JobMatchEmail.objects.filter(sent_on=TODAY, delivered=True).count(), len(expected))
        self.assertNotIn(str(no_email.pk), called)
        self.assertNotIn(str(employer.pk), called)
        self.assertNotIn(str(unverified.pk), called)

    def test_threshold_limit_and_email_content(self):
        at_50 = make_candidate("fifty@example.com")
        at_49 = make_candidate("fortynine@example.com")
        empty = make_candidate("empty@example.com")
        payloads = {
            str(at_50.pk): [job(9, 50, location=None), job(4, 12)],
            str(at_49.pk): [job(8, 49)],
            str(empty.pk): [],
        }
        with mock.patch("app.job_matching.aggregator.requests.post", side_effect=self._post_returning(payloads)) as post:
            stats = run_daily_job_match_emails(limit=300)

        self.assertTrue(all(c.kwargs["json"]["limit"] == 300 for c in post.call_args_list))
        self.assertEqual(stats.matched, 3)
        self.assertEqual(stats.sent, 1)
        self.assertEqual(self.send.call_count, 1)
        subject, text, html, _from, to = self.send.call_args.args
        self.assertEqual(to, "fifty@example.com")
        self.assertIn("50% match", text)
        self.assertIn("12% match", text)
        self.assertIn("Acme & Co", text)
        self.assertIn("https://app.test/jobs/9", html)
        self.assertNotIn("None", text)
        self.assertEqual(list(JobMatchEmail.objects.values_list("user_id", flat=True)), [at_50.pk])

    def test_one_email_per_day_and_failed_send_can_retry(self):
        user = make_candidate("once@example.com")
        with mock.patch("app.job_matching.aggregator.requests.post", side_effect=self._post_returning(default=[job(1, 90)])):
            self.send.return_value = (False, "provider down")
            stats = run_daily_job_match_emails()
            self.assertEqual(stats.send_failed, 1)
            self.assertFalse(JobMatchEmail.objects.exists())

            self.send.return_value = (True, None)
            run_daily_job_match_emails()
            run_daily_job_match_emails()
        self.assertEqual(self.send.call_count, 2)
        row = JobMatchEmail.objects.get(user=user)
        self.assertEqual(row.sent_on, TODAY)
        self.assertTrue(row.delivered)

    def test_stale_sending_row_is_retried_and_fresh_one_is_skipped(self):
        user = make_candidate("stale@example.com")
        row = JobMatchEmail.objects.create(user=user, sent_on=TODAY)
        with mock.patch("app.job_matching.aggregator.requests.post", side_effect=self._post_returning(default=[job(1, 90)])):
            run_daily_job_match_emails()
            self.send.assert_not_called()

            JobMatchEmail.objects.filter(pk=row.pk).update(created_at=timezone.now() - timedelta(minutes=16))
            run_daily_job_match_emails()
        self.assertEqual(self.send.call_count, 1)
        self.assertTrue(JobMatchEmail.objects.get(user=user).delivered)

    def test_aggregator_failure_skips_only_that_user(self):
        broken = make_candidate("broken@example.com")
        fine = make_candidate("fine@example.com")
        payloads = {str(broken.pk): requests.Timeout(), str(fine.pk): [job(1, 75)]}
        with mock.patch("app.job_matching.aggregator.requests.post", side_effect=self._post_returning(payloads)) as post:
            stats = run_daily_job_match_emails()
        self.assertEqual(stats.aggregator_failed, 1)
        self.assertEqual(stats.sent, 1)
        self.assertEqual(sum(1 for c in post.call_args_list if c.kwargs["json"]["userId"] == str(broken.pk)), 3)
        self.assertEqual(list(JobMatchEmail.objects.values_list("user_id", flat=True)), [fine.pk])

    def test_command_runs(self):
        make_candidate("cmd@example.com")
        with mock.patch("app.job_matching.aggregator.requests.post", side_effect=self._post_returning(default=[])):
            call_command("send_job_match_emails", "--limit", "7", stdout=mock.Mock())


class SchedulerTests(TestCase):
    def test_next_run_is_15_tbilisi_not_15_utc(self):
        from datetime import datetime, timezone as dt_timezone

        before = datetime(2026, 11, 13, 10, 59, tzinfo=dt_timezone.utc)  # 14:59 Tbilisi
        run = next_run_after(before)
        self.assertEqual((run.hour, run.date()), (15, date(2026, 11, 13)))
        self.assertEqual(run.astimezone(dt_timezone.utc).hour, 11)

        after = datetime(2026, 11, 13, 11, 0, tzinfo=dt_timezone.utc)  # 15:00 Tbilisi
        self.assertEqual(next_run_after(after).date(), date(2026, 11, 14))
