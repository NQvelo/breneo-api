from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from app.models import Academy, Course, Skill


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class AcademyCourseManageTests(TestCase):
    """Academy accounts can create and update their courses."""

    @classmethod
    def setUpTestData(cls):
        cls.academy_user = User.objects.create_user(
            username="academy_course_user",
            email="academy_course@test.com",
            password="pass12345",
            first_name="Test Academy",
        )
        cls.academy = Academy.objects.create(
            user=cls.academy_user,
            phone_number="555-0100",
            password=make_password("pass12345"),
        )
        cls.regular_user = User.objects.create_user(
            username="regular_course_user",
            email="regular_course@test.com",
            password="pass12345",
        )
        cls.skill = Skill.objects.create(name="CourseTestSkill")

    def setUp(self):
        self.client = APIClient()

    def _auth(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_academy_can_create_course(self):
        self._auth(self.academy_user)
        response = self.client.post(
            "/api/courses/",
            {
                "title": "New Academy Course",
                "description": "Learn things",
                "skills_taught": [self.skill.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["title"], "New Academy Course")
        self.assertEqual(response.data["academy_id"], self.academy.id)
        self.assertTrue(Course.objects.filter(id=response.data["id"], academy=self.academy).exists())

    def test_academy_can_create_with_skill_names_and_objects(self):
        self._auth(self.academy_user)
        response = self.client.post(
            "/api/courses/",
            {
                "title": "Skill Shape Course",
                "required_skills": [self.skill.name],
                "skills_taught": [{"id": self.skill.id, "name": self.skill.name}],
                "price": "",
                "lessons_count": "",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["required_skills"], [self.skill.name])
        self.assertEqual(response.data["skills_taught"][0]["id"], self.skill.id)

    def test_academy_can_put_and_patch_own_course(self):
        self._auth(self.academy_user)
        create = self.client.post(
            "/api/courses/",
            {"title": "Editable Course", "price": "10.00"},
            format="json",
        )
        self.assertEqual(create.status_code, 201, create.data)
        course_id = create.data["id"]

        put = self.client.put(
            f"/api/courses/{course_id}/",
            {
                "title": "Updated Via Put",
                "skills_taught": [{"id": self.skill.id, "name": self.skill.name}],
            },
            format="json",
        )
        self.assertEqual(put.status_code, 200, put.data)
        self.assertEqual(put.data["title"], "Updated Via Put")

        patch = self.client.patch(
            f"/api/courses/{course_id}/",
            {"title": "Updated Via Patch", "required_skills": [self.skill.name]},
            format="json",
        )
        self.assertEqual(patch.status_code, 200, patch.data)
        self.assertEqual(patch.data["title"], "Updated Via Patch")
        self.assertEqual(patch.data["required_skills"], [self.skill.name])

    def test_regular_user_cannot_create_course(self):
        self._auth(self.regular_user)
        response = self.client.post(
            "/api/courses/",
            {"title": "Should Fail"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_academy_cannot_edit_other_academy_course(self):
        other_user = User.objects.create_user(
            username="other_academy_user",
            email="other_academy@test.com",
            password="pass12345",
            first_name="Other Academy",
        )
        other_academy = Academy.objects.create(
            user=other_user,
            phone_number="555-0200",
            password=make_password("pass12345"),
        )
        course = Course.objects.create(
            id="other-academy-course-1",
            title="Other Course",
            academy=other_academy,
            user=other_user,
        )

        self._auth(self.academy_user)
        response = self.client.patch(
            f"/api/courses/{course.id}/",
            {"title": "Hijacked"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
