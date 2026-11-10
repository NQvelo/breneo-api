import io
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from app.ats.exceptions import (
    CorruptResumeFile,
    EmptyResumeError,
    LlmNotConfigured,
    PasswordProtectedPDF,
    ResumeTooLarge,
    UnsupportedResumeFormat,
)
from app.ats.extractor.engine import extract_resume
from app.ats.extractor.ground import ground_resume
from app.ats.extractor.heuristic import extract_with_heuristics
from app.ats.matcher.engine import score_resume
from app.ats.parsers import read_resume
from app.ats.parsers.georgian import clean_georgian_text
from app.ats.parsers.layout import words_to_text
from app.ats.schemas.resume import (
    BilingualText,
    ResumeData,
    SkillItem,
    WorkExperienceItem,
    _clean_date,
    missing_fields,
)
from app.ats.service import read_upload
from app.models import Job, Skill


def _both(en: str, ka: str) -> dict:
    return {"en": en, "ka": ka}


COMPLETE_RESUME = {
    "full_name": _both("Nino Beridze", "ნინო ბერიძე"),
    "headline": _both("Python Developer", "პითონ დეველოპერი"),
    "email": "nino@example.com",
    "phone": "+995555123456",
    "location": _both("Tbilisi", "თბილისი"),
    "summary": _both("Python Django developer", "პითონ და ჯანგოს დეველოპერი"),
    "skills": [
        {"name_en": "Python", "name_ka": "პითონ"},
        {"name_en": "Django", "name_ka": "ჯანგო"},
        {"name_en": "PostgreSQL", "name_ka": "პოსტგრესქლ"},
    ],
    "languages": [
        {"name_en": "Georgian", "name_ka": "ქართული"},
        {"name_en": "English", "name_ka": "ინგლისური"},
    ],
    "work_experience": [
        {
            "title": _both("Python Developer", "პითონ დეველოპერი"),
            "company": _both("Acme", "აკმე"),
            "location": _both("Tbilisi", "თბილისი"),
            "start_date": "2019",
            "end_date": "2024",
            "is_current": False,
            "description": _both("Built Django services on PostgreSQL.", "აშენებდა ჯანგოს სერვისებს."),
        }
    ],
    "education": [
        {
            "school": _both("Tbilisi State University", "თბილისის სახელმწიფო უნივერსიტეტი"),
            "degree": _both("Bachelor", "ბაკალავრი"),
            "field_of_study": _both("Computer Science", "კომპიუტერული მეცნიერება"),
            "start_date": "2015",
            "end_date": "2019",
            "is_current": False,
        }
    ],
    "certifications": [_both("AWS Cloud Practitioner", "AWS ღრუბლის პრაქტიკოსი")],
    "language": "mixed",
    "extraction_method": "llm",
}


GEORGIAN_RESUME = """ნინო ბერიძე
პროგრამისტი
nino@example.com
+995 555 123 456

შეჯამება
Django და PostgreSQL სერვისებზე ვმუშაობ Python-ით.

უნარები
Python, Django, PostgreSQL

სამუშაო გამოცდილება
პროგრამისტი | კომპანია | 2019 - 2024
Django სერვისების შექმნა PostgreSQL ბაზაზე.
"""


class GeorgianCleanupTests(SimpleTestCase):
    def test_folds_mtavruli_and_strips_invisible_characters(self):
        self.assertEqual(clean_georgian_text(chr(0x1C90)), "ა")
        self.assertEqual(clean_georgian_text("ა\u200bბ"), "აბ")

    def test_repairs_utf8_read_as_latin1_or_cp1252(self):
        original = "გამარჯობა საქართველო"
        latin1 = original.encode("utf-8").decode("latin-1")
        self.assertEqual(clean_georgian_text(latin1), original)

        chars = []
        for byte in original.encode("utf-8"):
            try:
                chars.append(bytes([byte]).decode("cp1252"))
            except UnicodeDecodeError:
                chars.append(chr(byte))
        self.assertIn("áƒ", "".join(chars))
        self.assertEqual(clean_georgian_text("".join(chars)), original)

    def test_converts_ascii_georgian_font_encoding(self):
        self.assertEqual(clean_georgian_text("saqarTvelo"), "საქართველო")
        converted = clean_georgian_text("gamarjoba saqarTvelo")
        self.assertIn("გამარჯობა", converted)
        self.assertIn("საქართველო", converted)

    def test_leaves_english_prose_intact(self):
        sentence = "The Software Engineer builds APIs in London."
        self.assertEqual(clean_georgian_text(sentence), sentence)

    def test_converts_only_the_georgian_token_inside_english(self):
        cleaned = clean_georgian_text("I worked in saqarTvelo for years.")
        self.assertIn("საქართველო", cleaned)
        self.assertIn("worked", cleaned)


class LayoutTests(SimpleTestCase):
    def test_reads_left_column_before_right_column(self):
        words = [
            {"text": "Left1", "x0": 10, "x1": 50, "top": 10, "bottom": 20},
            {"text": "Right1", "x0": 400, "x1": 460, "top": 12, "bottom": 22},
            {"text": "Left2", "x0": 10, "x1": 50, "top": 30, "bottom": 40},
            {"text": "Right2", "x0": 400, "x1": 460, "top": 32, "bottom": 42},
        ]
        text = words_to_text(words, page_width=600)
        self.assertLess(text.find("Left1"), text.find("Left2"))
        self.assertLess(text.find("Left2"), text.find("Right1"))
        self.assertLess(text.find("Right1"), text.find("Right2"))


class ResumeSchemaTests(SimpleTestCase):
    def test_present_end_date_marks_role_current(self):
        role = WorkExperienceItem.model_validate(
            {"title": {"en": "Developer"}, "end_date": "present"}
        )
        self.assertTrue(role.is_current)
        self.assertEqual(role.end_date, "present")

    def test_string_skill_keeps_georgian_on_the_georgian_side(self):
        resume = ResumeData.model_validate({"skills": ["Python", "გუნდური მუშაობა"]})
        self.assertEqual(resume.skills[0].name_en, "Python")
        self.assertEqual(resume.skills[1].name_ka, "გუნდური მუშაობა")


class HeuristicExtractorTests(SimpleTestCase):
    def test_parses_bilingual_sections(self):
        resume = extract_with_heuristics(GEORGIAN_RESUME, filename="nino.docx")
        self.assertEqual(resume.full_name.ka, "ნინო ბერიძე")
        self.assertEqual(resume.email, "nino@example.com")
        self.assertEqual(resume.phone, "+995 555 123 456")
        skill_names = {skill.name_en for skill in resume.skills}
        self.assertEqual(skill_names, {"Python", "Django", "PostgreSQL"})
        self.assertEqual(len(resume.work_experience), 1)
        self.assertEqual(resume.work_experience[0].start_date, "2019")
        self.assertEqual(resume.work_experience[0].end_date, "2024")
        self.assertEqual(resume.language, "mixed")
        self.assertEqual(resume.extraction_method, "heuristic")

    @patch("app.ats.extractor.engine.extract_with_llm", side_effect=LlmNotConfigured("no key"))
    def test_extract_resume_uses_text_parser_when_ai_is_down(self, _llm):
        resume = extract_resume("ნინო ბერიძე\nუნარები\nPython, Django", filename="cv.pdf")
        self.assertEqual(resume.extraction_method, "heuristic")
        self.assertIn("llm_not_configured", resume.warnings)
        self.assertTrue(resume.full_name.ka or resume.skills)

    def test_dates_stay_as_printed_on_the_cv(self):
        self.assertEqual(_clean_date("Jan 2024"), "Jan 2024")
        self.assertEqual(_clean_date("01/2024"), "01/2024")
        self.assertEqual(_clean_date("2024/01"), "2024/01")
        self.assertEqual(_clean_date("202O"), "202O")
        self.assertEqual(_clean_date("Present"), "Present")

    def test_job_text_is_replaced_with_the_cv_wording(self):
        source = "\n".join(
            [
                "Python Developer | Acme Corp | Jan 2019 - Present",
                "Built Django services on PostgreSQL.",
                "Kept the API under 200ms.",
            ]
        )
        resume = ResumeData(
            work_experience=[
                WorkExperienceItem(
                    title=BilingualText(en="Software Engineer"),
                    company=BilingualText(en="Acme Corporation"),
                    description=BilingualText(en="Developed web services for the company."),
                    start_date="2019-01",
                    end_date=None,
                    is_current=True,
                )
            ]
        )
        grounded = ground_resume(resume, source)
        role = grounded.work_experience[0]
        self.assertEqual(role.company.en, "Acme Corp")
        self.assertEqual(role.company.ka, "Acme Corp")
        self.assertEqual(role.start_date, "Jan 2019")
        self.assertEqual(role.end_date, "Present")
        self.assertIn("Built Django services on PostgreSQL.", role.description.en)
        self.assertIn("Kept the API under 200ms.", role.description.en)
        self.assertNotIn("Developed web services", role.description.en)

    def test_complete_resume_has_no_missing_fields(self):
        self.assertEqual(missing_fields(ResumeData.model_validate(COMPLETE_RESUME)), [])

    def test_missing_fields_lists_every_empty_value(self):
        gaps = missing_fields(ResumeData())
        self.assertIn("full_name.en", gaps)
        self.assertIn("email", gaps)
        self.assertIn("skills", gaps)
        self.assertIn("work_experience", gaps)
        self.assertIn("education", gaps)
        self.assertNotIn("certifications", gaps)
        self.assertNotIn("languages", gaps)


class MatcherTests(SimpleTestCase):
    def _strong_resume(self):
        return ResumeData(
            language="en",
            summary=BilingualText(en="Python Django PostgreSQL developer"),
            skills=[
                SkillItem(name_en="Python"),
                SkillItem(name_en="Django"),
                SkillItem(name_en="PostgreSQL"),
            ],
            work_experience=[
                WorkExperienceItem(
                    title=BilingualText(en="Python Developer"),
                    company=BilingualText(en="Acme"),
                    start_date="2019",
                    end_date="2024",
                    description=BilingualText(en="Built Django services on PostgreSQL."),
                )
            ],
        )

    def test_scores_a_close_english_match_above_a_weak_one(self):
        job = "We need a Python Developer with Django and PostgreSQL. 3 years of experience."
        strong = score_resume(
            self._strong_resume(),
            job,
            job_title="Python Developer",
            required_skills=["PostgreSQL"],
        )
        weak = score_resume(
            ResumeData(
                language="en",
                summary=BilingualText(en="Graphic designer focused on print layouts."),
                skills=[SkillItem(name_en="Figma")],
            ),
            job,
            job_title="Python Developer",
            required_skills=["PostgreSQL"],
        )
        self.assertGreaterEqual(strong.scores.overall, 60)
        self.assertGreater(strong.scores.overall, weak.scores.overall)
        self.assertEqual(strong.candidate_years_experience, 5.0)
        self.assertEqual(strong.required_years_experience, 3.0)
        self.assertIn("PostgreSQL", strong.matched_keywords)
        self.assertTrue(weak.missing_keywords)
        self.assertTrue(strong.recommendations)

    def test_georgian_job_matches_latin_skill_names(self):
        result = score_resume(
            self._strong_resume(),
            "ვეძებთ Python Django დეველოპერს 3 წლიანი გამოცდილებით. საჭიროა PostgreSQL.",
            job_title="Python დეველოპერი",
            required_skills=["PostgreSQL"],
        )
        self.assertEqual(result.job_language, "mixed")
        self.assertGreater(result.scores.keyword_overlap, 30)
        self.assertEqual(result.required_years_experience, 3.0)
        self.assertTrue(result.recommendations)


class ParserErrorTests(SimpleTestCase):
    def test_rejects_unknown_extension_and_unreadable_doc(self):
        with self.assertRaises(UnsupportedResumeFormat):
            read_resume(b"hello resume", "cv.xyz")
        with self.assertRaises(EmptyResumeError):
            read_resume(b"hello resume", "cv.txt")
        with self.assertRaises(UnsupportedResumeFormat):
            read_resume(b"hello", "cv.doc")

    def test_rejects_corrupt_pdf_bytes(self):
        with self.assertRaises(CorruptResumeFile):
            read_resume(b"this is not a pdf", "cv.pdf")

    def test_password_protected_pdf(self):
        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            self.skipTest("pdfplumber is not installed")
        with patch("pdfplumber.open", side_effect=RuntimeError("PDF password required")):
            with self.assertRaises(PasswordProtectedPDF):
                read_resume(b"%PDF-1.4 fake", "locked.pdf")

    def test_empty_docx_is_rejected(self):
        try:
            from docx import Document
        except ImportError:
            self.skipTest("python-docx is not installed")
        buffer = io.BytesIO()
        Document().save(buffer)
        with self.assertRaises(EmptyResumeError):
            read_resume(buffer.getvalue(), "empty.docx")

    def test_docx_text_survives_round_trip(self):
        try:
            from docx import Document
        except ImportError:
            self.skipTest("python-docx is not installed")
        document = Document()
        document.add_paragraph("ნინო ბერიძე")
        document.add_paragraph("Python Django PostgreSQL developer in Tbilisi")
        buffer = io.BytesIO()
        document.save(buffer)
        parsed = read_resume(buffer.getvalue(), "cv.docx")
        self.assertEqual(parsed.method, "docx")
        self.assertIn("ნინო", parsed.text)
        self.assertIn("PostgreSQL", parsed.text)

    @override_settings(ATS_MAX_UPLOAD_BYTES=10)
    def test_upload_limit(self):
        class _Upload:
            name = "cv.pdf"
            size = 20

            def read(self):
                return b"x" * 20

        with self.assertRaises(ResumeTooLarge):
            read_upload(_Upload())


class AtsApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ats_user",
            email="ats@example.com",
            password="pass12345",
        )
        self.client = APIClient()
        self.resume_payload = COMPLETE_RESUME

    def test_parse_requires_auth(self):
        response = self.client.post("/api/ats/parse/", {})
        self.assertEqual(response.status_code, 401)

    def test_parse_docx(self):
        try:
            from docx import Document
        except ImportError:
            self.skipTest("python-docx is not installed")
        document = Document()
        for line in GEORGIAN_RESUME.splitlines():
            document.add_paragraph(line)
        buffer = io.BytesIO()
        document.save(buffer)
        upload = SimpleUploadedFile(
            "cv.docx",
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.client.force_authenticate(user=self.user)
        parsed = ResumeData.model_validate(COMPLETE_RESUME)
        with patch("app.ats.extractor.engine.extract_with_llm", return_value=parsed):
            response = self.client.post("/api/ats/parse/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["email"], "nino@example.com")
        self.assertEqual(response.data["parser_method"], "docx")
        self.assertEqual(response.data["extraction_method"], "llm")
        self.assertEqual(response.data["full_name"]["ka"], "ნინო ბერიძე")

        saved = self.client.get("/api/me/resume/")
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(saved.data["resume"]["email"], "nino@example.com")
        self.assertEqual(saved.data["source_filename"], "cv.docx")

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Nino")
        self.assertEqual(self.user.last_name, "Beridze")
        profile = self.client.get("/api/me/profile/")
        self.assertEqual(profile.status_code, 200, profile.data)
        self.assertEqual(profile.data["phone_number"], "+995555123456")
        self.assertIn("Django", profile.data["about_me"])

        work = self.client.get("/api/work-experiences/")
        self.assertEqual(work.status_code, 200, work.data)
        self.assertEqual(len(work.data), 1)
        self.assertEqual(work.data[0]["job_title"], "Python Developer")

        skills = self.client.get("/api/me/skills/")
        skill_names = {item["skill_name"] for item in skills.data}
        self.assertIn("Python", skill_names)
        self.assertIn("Django", skill_names)

    def test_parse_keeps_a_partial_cv_and_reports_the_gaps(self):
        upload = SimpleUploadedFile("cv.pdf", b"%PDF-1.4 not-really", content_type="application/pdf")
        self.client.force_authenticate(user=self.user)
        partial = ResumeData(full_name=BilingualText(en="Nino Beridze", ka="ნინო ბერიძე"))
        with patch("app.ats.parsers.extract_pdf", return_value=("Nino Beridze resume text " * 5, "digital", 1, [])):
            with patch("app.ats.extractor.engine.extract_with_llm", return_value=partial):
                response = self.client.post("/api/ats/parse/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["full_name"]["en"], "Nino Beridze")
        self.assertIn("missing_email", response.data["warnings"])
        saved = self.client.get("/api/me/resume/")
        self.assertEqual(saved.data["resume"]["full_name"]["en"], "Nino Beridze")

    def test_parse_uses_text_parser_when_ai_is_not_configured(self):
        upload = SimpleUploadedFile("cv.pdf", b"%PDF-1.4 not-really", content_type="application/pdf")
        self.client.force_authenticate(user=self.user)
        with patch("app.ats.parsers.extract_pdf", return_value=(GEORGIAN_RESUME, "digital", 1, [])):
            with patch("app.ats.extractor.engine.extract_with_llm", side_effect=LlmNotConfigured("no key")):
                response = self.client.post("/api/ats/parse/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["extraction_method"], "heuristic")
        self.assertEqual(response.data["email"], "nino@example.com")
        self.assertIn("llm_not_configured", response.data["warnings"])

    def test_resume_page_is_empty_before_parse(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/me/resume/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data["resume"])

    def test_parse_plain_text_resume(self):
        body = b"Nino Beridze\nnino@example.com\n+995555123456\nPython Developer\nSkills: Python, Django\n"
        upload = SimpleUploadedFile("cv.txt", body, content_type="text/plain")
        self.client.force_authenticate(user=self.user)
        parsed = ResumeData.model_validate(COMPLETE_RESUME)
        with patch("app.ats.extractor.engine.extract_with_llm", return_value=parsed):
            response = self.client.post("/api/ats/parse/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["parser_method"], "txt")
        self.assertEqual(response.data["email"], "nino@example.com")

    def test_html_and_rtf_keep_visible_text(self):
        html = read_resume(
            b"<html><body><h1>Nino Beridze</h1><p>nino@example.com Python Django developer</p></body></html>",
            "cv.html",
        )
        self.assertIn("Nino Beridze", html.text)
        self.assertIn("nino@example.com", html.text)
        self.assertEqual(html.method, "html")
        rtf = read_resume(
            b"{\\rtf1\\ansi Nino Beridze\\par nino@example.com Python developer}",
            "cv.rtf",
        )
        self.assertIn("Nino Beridze", rtf.text)
        self.assertEqual(rtf.method, "rtf")

    def test_match_against_stored_job(self):
        skill, _created = Skill.objects.get_or_create(name="PostgreSQL")
        job = Job.objects.create(
            id="ats-job-1",
            title="Python Developer",
            description="Build services with Django. 3 years of experience required.",
        )
        job.required_skills.add(skill)
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/ats/match/",
            {"resume": self.resume_payload, "job_id": job.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertGreaterEqual(response.data["match"]["scores"]["overall"], 40)
        self.assertIn("PostgreSQL", response.data["match"]["matched_keywords"])
        self.assertEqual(response.data["match"]["required_years_experience"], 3.0)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Nino")
        self.assertEqual(self.user.last_name, "Beridze")
        saved = self.client.get("/api/me/resume/")
        self.assertEqual(saved.data["resume"]["full_name"]["en"], "Nino Beridze")

    def test_match_unknown_job(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/ats/match/",
            {"resume": self.resume_payload, "job_id": "missing-job"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "job_not_found")
