from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from app.models import Atom, Profession, UserProgress


SAMPLE_CARDS = [
    {
        "card_index": 0,
        "content_type": "markdown",
        "content_body": "# Hello React\nWelcome to components.",
    },
    {
        "card_index": 1,
        "content_type": "code",
        "content_body": "function App() { return <h1>Hi</h1>; }",
    },
]

SAMPLE_QUIZ = {
    "options": ["A component", "A function", "A database"],
    "correct_index": 0,
    "explanation": "React UI is built from components.",
}


def _create_profession_with_atoms(title="Atom Test Profession"):
    profession = Profession.objects.create(
        title=title,
        description="Intro to React",
    )
    atom1 = Atom.objects.create(
        profession=profession,
        title="What is React?",
        sequence_order=1,
        content_cards=SAMPLE_CARDS,
        quiz_data=SAMPLE_QUIZ,
    )
    atom2 = Atom.objects.create(
        profession=profession,
        title="JSX Basics",
        sequence_order=2,
        content_cards=[
            {
                "card_index": 0,
                "content_type": "markdown",
                "content_body": "JSX looks like HTML.",
            }
        ],
        quiz_data={
            "options": ["JavaScript XML", "JSON XML", "Java Syntax"],
            "correct_index": 0,
            "explanation": "JSX stands for JavaScript XML.",
        },
    )
    return profession, atom1, atom2


class AtomAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="atom_user",
            email="atom@example.com",
            password="pass12345",
        )
        self.client = APIClient()
        self.profession, self.atom1, self.atom2 = _create_profession_with_atoms()

    def test_next_atom_requires_auth(self):
        response = self.client.get(
            f"/api/v1/professions/{self.profession.id}/next-atom/"
        )
        self.assertEqual(response.status_code, 401)

    def test_next_atom_returns_first_atom(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            f"/api/v1/professions/{self.profession.id}/next-atom/"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], self.atom1.id)
        self.assertEqual(body["sequence_order"], 1)
        self.assertEqual(body["profession_id"], self.profession.id)
        self.assertEqual(len(body["content_cards"]), 2)
        self.assertEqual(body["quiz"]["options"], SAMPLE_QUIZ["options"])
        self.assertNotIn("correct_index", body["quiz"])
        self.assertNotIn("explanation", body["quiz"])

    def test_cannot_skip_to_second_atom(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            f"/api/v1/professions/{self.profession.id}/next-atom/"
        )
        self.assertEqual(response.json()["id"], self.atom1.id)

    def test_submit_correct_answer_completes_atom(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/atoms/{self.atom1.id}/submit/",
            {"selected_option_index": 0},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["score_percentage"], 100.0)
        self.assertTrue(body["is_completed"])
        self.assertFalse(body["requires_retake"])
        self.assertTrue(body["passed"])
        self.assertEqual(body["profession_id"], self.profession.id)
        self.assertEqual(body["explanation"], SAMPLE_QUIZ["explanation"])

        progress = UserProgress.objects.get(user=self.user, atom=self.atom1)
        self.assertTrue(progress.is_completed)
        self.assertFalse(progress.requires_retake)

    def test_submit_wrong_answer_requires_retake(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/atoms/{self.atom1.id}/submit/",
            {"selected_option_index": 2},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["score_percentage"], 0.0)
        self.assertFalse(body["is_completed"])
        self.assertTrue(body["requires_retake"])
        self.assertFalse(body["passed"])

    def test_next_atom_after_completion_advances(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(
            f"/api/v1/atoms/{self.atom1.id}/submit/",
            {"selected_option_index": 0},
            format="json",
        )
        response = self.client.get(
            f"/api/v1/professions/{self.profession.id}/next-atom/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.atom2.id)

    def test_failed_atom_is_returned_for_retake(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(
            f"/api/v1/atoms/{self.atom1.id}/submit/",
            {"selected_option_index": 1},
            format="json",
        )
        response = self.client.get(
            f"/api/v1/professions/{self.profession.id}/next-atom/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.atom1.id)

    def test_submit_second_atom_blocked_until_first_completed(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/atoms/{self.atom2.id}/submit/",
            {"selected_option_index": 0},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_all_completed_returns_404(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(
            f"/api/v1/atoms/{self.atom1.id}/submit/",
            {"selected_option_index": 0},
            format="json",
        )
        self.client.post(
            f"/api/v1/atoms/{self.atom2.id}/submit/",
            {"selected_option_index": 0},
            format="json",
        )
        response = self.client.get(
            f"/api/v1/professions/{self.profession.id}/next-atom/"
        )
        self.assertEqual(response.status_code, 404)

    def test_profession_not_found(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/professions/99999/next-atom/")
        self.assertEqual(response.status_code, 404)
