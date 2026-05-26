from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from app.models import JobNotification, Notification

INTERNAL_KEY = "test-notifications-internal-key"


@override_settings(NOTIFICATIONS_INTERNAL_KEY=INTERNAL_KEY)
class NotificationAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="notify_user",
            email="notify@example.com",
            password="pass12345",
        )
        self.other = User.objects.create_user(
            username="other_user",
            email="other@example.com",
            password="pass12345",
        )
        self.client = APIClient()
        self.internal = APIClient()

    def test_internal_post_creates_notification(self):
        response = self.internal.post(
            "/api/internal/notifications/",
            {
                "recipient_id": str(self.user.id),
                "title": "Company join request",
                "message": "Jane wants to join Acme.",
                "type": "info",
                "metadata": {
                    "kind": "employer_join_request",
                    "request_id": "550e8400-e29b-41d4-a716-446655440000",
                    "company_id": 123,
                },
            },
            format="json",
            HTTP_X_INTERNAL_KEY=INTERNAL_KEY,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.user, kind="employer_join_request"
            ).exists()
        )
        body = response.json()
        self.assertEqual(body["recipient_id"], str(self.user.id))
        self.assertEqual(body["metadata"]["request_id"], "550e8400-e29b-41d4-a716-446655440000")

    def test_internal_post_invalid_key(self):
        response = self.internal.post(
            "/api/internal/notifications/",
            {"recipient_id": str(self.user.id), "title": "x", "message": "y", "type": "info"},
            format="json",
            HTTP_X_INTERNAL_KEY="wrong",
        )
        self.assertEqual(response.status_code, 401)

    def test_me_list_includes_personal_and_broadcast(self):
        Notification.objects.create(
            recipient=self.user, title="Personal", message="Hi", type="info"
        )
        Notification.objects.create(
            recipient=None, title="Broadcast", message="All", type="warning"
        )
        Notification.objects.create(
            recipient=self.other, title="Other", message="Secret", type="info"
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/me/notifications/")
        self.assertEqual(response.status_code, 200)
        titles = {n["title"] for n in response.json()["results"]}
        self.assertEqual(titles, {"Personal", "Broadcast"})

    def test_me_list_filter_by_kind(self):
        Notification.objects.create(
            recipient=self.user,
            title="Join",
            message="m",
            type="info",
            kind="employer_join_request",
            metadata={"kind": "employer_join_request", "request_id": "abc"},
        )
        Notification.objects.create(
            recipient=self.user,
            title="Job",
            message="m",
            type="info",
            kind="job_match",
            metadata={"kind": "job_match", "job_id": "j1"},
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            "/api/me/notifications/", {"kind": "employer_join_request"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertEqual(response.json()["results"][0]["kind"], "employer_join_request")

    def test_mark_read_and_forbid_other_user(self):
        notification = Notification.objects.create(
            recipient=self.user,
            title="T",
            message="M",
            type="info",
            is_read=False,
        )
        other_notification = Notification.objects.create(
            recipient=self.other,
            title="T2",
            message="M2",
            type="info",
            is_read=False,
        )
        broadcast = Notification.objects.create(
            recipient=None,
            title="B",
            message="All",
            type="info",
            is_read=False,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(f"/api/me/notifications/{notification.id}/read/", {})
        self.assertEqual(response.status_code, 200)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

        response = self.client.patch(
            f"/api/me/notifications/{other_notification.id}/read/", {}
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.patch(f"/api/me/notifications/{broadcast.id}/read/", {})
        self.assertEqual(response.status_code, 403)

    def test_read_all_updates_only_current_user(self):
        Notification.objects.create(
            recipient=self.user, title="A", message="m", type="info", is_read=False
        )
        Notification.objects.create(
            recipient=self.user, title="B", message="m", type="info", is_read=False
        )
        Notification.objects.create(
            recipient=self.other, title="C", message="m", type="info", is_read=False
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.patch("/api/me/notifications/read-all/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["updated"], 2)
        self.assertFalse(
            Notification.objects.filter(recipient=self.user, is_read=False).exists()
        )
        self.assertTrue(
            Notification.objects.filter(recipient=self.other, is_read=False).exists()
        )

    def test_me_post_sets_recipient_to_self(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/me/notifications/",
            {
                "title": "New Job Match! 🎯",
                "message": "Role matches",
                "type": "info",
                "metadata": {"kind": "job_match", "job_id": "job-123"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        n = Notification.objects.get(pk=response.json()["id"])
        self.assertEqual(n.recipient_id, self.user.id)
        self.assertEqual(n.kind, "job_match")

    def test_job_notification_dedup(self):
        self.client.force_authenticate(user=self.user)
        r1 = self.client.post(
            "/api/me/job-notifications/", {"job_id": "job-1"}, format="json"
        )
        self.assertEqual(r1.status_code, 201)
        r2 = self.client.post(
            "/api/me/job-notifications/", {"job_id": "job-1"}, format="json"
        )
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(JobNotification.objects.filter(user=self.user).count(), 1)

        response = self.client.get("/api/me/job-notifications/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job_ids"], ["job-1"])
