from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from app.models import Atom, Profession, ProfessionOfUser, UserProgress


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class ProfessionAtomsAPITests(TestCase):
    """Integration tests for Profession list + Atoms learning flow."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="prof_api_user",
            email="prof_api@test.com",
            password="pass12345",
        )
        cls.profession = Profession.objects.create(
            title="API Test Developer",
            description="Integration test profession",
            market_popularity=[{"year": "2024", "value": 80}],
        )
        cls.atom1 = Atom.objects.create(
            profession=cls.profession,
            title="Intro Atom",
            sequence_order=1,
            content_cards=[
                {
                    "card_index": 0,
                    "content_type": "markdown",
                    "content_body": "# Welcome",
                }
            ],
            quiz_data={
                "options": ["Correct", "Wrong A", "Wrong B"],
                "correct_index": 0,
                "explanation": "Because it is correct.",
            },
        )
        cls.atom2 = Atom.objects.create(
            profession=cls.profession,
            title="Second Atom",
            sequence_order=2,
            content_cards=[
                {
                    "card_index": 0,
                    "content_type": "markdown",
                    "content_body": "# Part 2",
                }
            ],
            quiz_data={
                "options": ["Wrong", "Correct", "Wrong B"],
                "correct_index": 1,
                "explanation": "Second answer is correct.",
            },
        )
        ProfessionOfUser.objects.create(
            user=cls.user,
            profession=cls.profession,
            match_score=92.5,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_professions_shape(self):
        response = self.client.get("/api/professions/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

        sample = next(p for p in data if p["id"] == self.profession.id)
        self.assertEqual(
            set(sample.keys()),
            {
                "id",
                "title",
                "description",
                "skills",
                "market_popularity",
                "relevant_courses",
                "created_at",
                "updated_at",
            },
        )
        self.assertNotIn("salary_info", sample)

    def test_me_profession_assignments(self):
        response = self.client.get("/api/me/profession/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        item = data[0]
        self.assertEqual(item["match_score"], 92.5)
        profession = item["profession"]
        self.assertEqual(profession["id"], self.profession.id)
        self.assertEqual(profession["title"], "API Test Developer")
        self.assertNotIn("salary_info", profession)

    def test_next_atom_full_learning_flow(self):
        response = self.client.get(
            f"/api/v1/professions/{self.profession.id}/next-atom/"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], self.atom1.id)
        self.assertEqual(body["profession_id"], self.profession.id)
        self.assertEqual(body["profession_title"], "API Test Developer")
        self.assertEqual(len(body["content_cards"]), 1)
        self.assertEqual(len(body["quiz"]["options"]), 3)
        self.assertNotIn("correct_index", body["quiz"])

        submit = self.client.post(
            f"/api/v1/atoms/{self.atom1.id}/submit/",
            {"selected_option_index": 0},
            format="json",
        )
        self.assertEqual(submit.status_code, 200)
        result = submit.json()
        self.assertEqual(result["profession_id"], self.profession.id)
        self.assertTrue(result["passed"])
        self.assertTrue(result["is_completed"])
        self.assertEqual(result["explanation"], "Because it is correct.")

        progress = UserProgress.objects.get(user=self.user, atom=self.atom1)
        self.assertTrue(progress.is_completed)

        response = self.client.get(
            f"/api/v1/professions/{self.profession.id}/next-atom/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.atom2.id)

    def test_list_professions_requires_auth(self):
        client = APIClient()
        response = client.get("/api/professions/")
        self.assertEqual(response.status_code, 401)

    def test_seed_professions_have_atoms_in_db(self):
        """Verify seeded career paths still have atoms linked via profession FK."""
        for title in ("Frontend Developer", "UI/UX Designer", "Product Owner"):
            profession = Profession.objects.filter(title=title).first()
            if profession is None:
                continue
            self.assertGreaterEqual(
                profession.atoms.count(),
                4,
                f"{title} should have seeded atoms",
            )
