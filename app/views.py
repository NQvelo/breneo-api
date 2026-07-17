import joblib
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.decorators import api_view,permission_classes
from rest_framework.response import Response
from .models import (
    Assessment,
    Badge,
    AssessmentSession,
    UserSkill,
    Job,
    Profession,
    ProfessionOfUser,
    Course,
    DynamicTechQuestion,
    Skill,
    CareerCategory,
    DynamicSoftSkillsQuestion,
    SkillScore,
    SkillTestResult,
    TemporaryUser,
    UserProfile,
    PasswordResetCode,
    SocialLinks,
    CareerQuestion,
    Academy,
    Employer,
    Industry,
    TemporaryAcademy,
    TemporaryEmployer,
    SavedCourse,
    SavedJob,
    Education,
    WorkExperience,
    UserIndustryProfile,
    SubscriptionPlan,
    UserSubscription,
    PaymentHistory,
)
from .serializers import (
    QuestionTechSerializer,
    CareerCategorySerializer,
    ProfessionSerializer,
    ProfessionOfUserSerializer,
    QuestionSoftSkillsSerializer,
    CustomTokenObtainPairSerializer,
    SkillTestResultSerializer,
    RegisterSerializer,
    TemporaryAcademyRegisterSerializer,
    UserProfileUpdateSerializer,
    AcademyUpdateSerializer,
    AcademyChangePasswordSerializer,
    SocialLinksSerializer,
    AcademyDetailSerializer,
    CareerQuestionSerializer,
    UserProfileSerializer,
    PublicSocialLinksSerializer,
    EducationSerializer,
    WorkExperienceSerializer,
    SkillSearchSerializer,
    UserSkillAttachSerializer,
    UserSkillResponseSerializer,
    CourseListSerializer,
    CourseManageSerializer,
    SubscriptionPlanSerializer,
    TemporaryEmployerRegisterSerializer,
    EmployerUpdateSerializer,
    EmployerChangePasswordSerializer,
    IndustrySerializer,
)
from django.contrib.auth.models import User
import os, requests, random
import uuid
from rest_framework import status
from rest_framework import generics
import json
import pandas as pd
from groq import Groq
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import generics, permissions, viewsets
from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers
import time
from django.contrib.auth.hashers import make_password,check_password
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.parsers import JSONParser, FormParser,MultiPartParser
from random import randint
from .serializers import (
    PasswordResetRequestSerializer, 
    PasswordResetVerifySerializer, 
    SetNewPasswordSerializer
)
from django.contrib.auth import get_user_model
User = get_user_model()
from .serializers import ChangePasswordSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .profession_match import update_profession_of_user_from_skill_test






GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ---------------- "I don't know" option ----------------
I_DONT_KNOW = "I don't know"


def is_i_dont_know(answer):
    """Check if user selected 'I don't know' (various formats accepted)."""
    if not answer:
        return False
    normalized = str(answer).strip().lower().replace("'", "").replace(" ", "")
    return normalized in ("idontknow", "i_dont_know", "dontknow")


def _user_is_academy(user):
    return bool(user and user.is_authenticated and Academy.objects.filter(user_id=user.pk).exists())


def _user_is_employer(user):
    return bool(user and user.is_authenticated and Employer.objects.filter(user_id=user.pk).exists())


def _subscription_audience_for_user(user):
    """Map authenticated account type to SubscriptionPlan.audience."""
    if _user_is_employer(user):
        return SubscriptionPlan.AUDIENCE_COMPANY
    if _user_is_academy(user):
        return SubscriptionPlan.AUDIENCE_ACADEMY
    return SubscriptionPlan.AUDIENCE_USER


def _reject_non_regular_user_profile(request):
    """User/UserProfile social APIs are for default users only."""
    if _user_is_academy(request.user):
        return Response(
            {"error": "Academy accounts should use /api/academy/profile/"},
            status=status.HTTP_403_FORBIDDEN,
        )
    if _user_is_employer(request.user):
        return Response(
            {"error": "Employer accounts should use /api/employer/profile/"},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


# ---------------- Email Helper ----------------
import logging
logger = logging.getLogger(__name__)

def send_email_safely(subject, text_message, html_message, from_email, to_email):
    """Send email via Resend HTTP API (avoids SMTP timeouts on Railway) or Django backend."""
    resend_key = getattr(settings, "RESEND_API_KEY", "") or os.getenv("RESEND_API_KEY", "")
    if resend_key:
        try:
            import resend
            resend.api_key = resend_key
            params = {
                "from": from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_message or text_message,
            }
            if text_message and html_message:
                params["text"] = text_message
            resend.Emails.send(params)
            return True, None
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}", exc_info=True)
            return False, str(e)
    # Fallback: Django SMTP (e.g. local dev with console backend)
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=from_email,
            to=[to_email]
        )
        if html_message:
            msg.attach_alternative(html_message, "text/html")
        msg.send(fail_silently=False)
        return True, None
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}", exc_info=True)
        return False, str(e)

# ---------------- Home ----------------
def home(request):
    return HttpResponse("Welcome to Breneo Student Dashboard!")

# ---------------- Dashboard API ----------------
class DashboardProgressAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        
        results = SkillTestResult.objects.filter(user=user).order_by('-created_at')
        last_result = results.first()

        skill_summary = last_result.skills_json if last_result else {}
        final_role = last_result.final_role if last_result else None
        total_score = last_result.total_score if last_result else None

        badges = Badge.objects.filter(user=user)

        return Response({
            "user": {
                "username": user.username,
                "skills": skill_summary or {}
            },
            "progress": {
                "total_tests": results.count(),
                "last_total_score": total_score,
                "total_badges": badges.count(),
            },
            "last_result": {
                "final_role": final_role,
                "total_score": total_score,
            }
        }, status=200)


# ---------------- Recommended Jobs ----------------

class RecommendedJobsAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        last_result = SkillTestResult.objects.filter(user=user).order_by('-created_at').first()
        if not last_result:
            return Response({
                "final_role": None,
                "recommended_jobs": []
            }, status=200)

        final_role = last_result.final_role or None
        skills_json = last_result.skills_json or {}

        
        if not final_role and not skills_json:
            return Response({
                "final_role": None,
                "recommended_jobs": []
            }, status=200)

       
        user_skills = []
        for skill_name, status in skills_json.items():
            skill_obj, _ = Skill.objects.get_or_create(name=skill_name)
            points = 1 if status.lower() == "strong" else 0
            user_skills.append(UserSkill(user=user, skill=skill_obj, points=points))

        jobs_data = []
        jobs_qs = Job.objects.filter(role__iexact=final_role) if final_role else Job.objects.all()

        for job in jobs_qs:
            match_data = calculate_match(user_skills, job)
            try:
                ai_salary = fetch_salary_from_groq(job.title, location="Georgia")
            except Exception:
                ai_salary = "$0 - $0"
            match_data["ai_salary_range"] = ai_salary
            jobs_data.append(match_data)

        return Response({
            "final_role": final_role,
            "recommended_jobs": jobs_data
        }, status=200)


def _course_queryset_with_relations():
    return (
        Course.objects.select_related("academy", "academy__user")
        .prefetch_related("required_skills", "skills_taught", "enrolled_users")
    )


# ---------------- Courses List API ----------------
class CoursesListAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request):
        qs = _course_queryset_with_relations().all()

        name = request.query_params.get("name")
        academy_name = request.query_params.get("academy_name") or request.query_params.get("academy")
        skills_param = request.query_params.get("skills")
        location = request.query_params.get("location")

        if name:
            qs = qs.filter(title__icontains=name)

        if academy_name:
            # Academy.name property maps to user.first_name
            qs = qs.filter(academy__user__first_name__icontains=academy_name)

        if skills_param:
            tokens = [t.strip() for t in skills_param.split(",") if t.strip()]
            if tokens:
                if all(t.isdigit() for t in tokens):
                    qs = qs.filter(required_skills__id__in=[int(t) for t in tokens])
                else:
                    qs = qs.filter(required_skills__name__in=tokens)

        if location:
            qs = qs.filter(location__icontains=location)

        qs = qs.distinct().order_by("title")

        enrolled_course_ids = set()
        if request.user and request.user.is_authenticated:
            enrolled_course_ids = set(
                Course.objects.filter(enrolled_users=request.user).values_list("id", flat=True)
            )

        serializer = CourseListSerializer(
            qs,
            many=True,
            context={"request": request, "enrolled_course_ids": enrolled_course_ids},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        academy = Academy.objects.filter(user=request.user).first()
        if not academy:
            return Response(
                {"error": "Only academy accounts can create courses."},
                status=status.HTTP_403_FORBIDDEN,
            )

        payload = request.data.copy()
        if not payload.get("id"):
            payload["id"] = str(uuid.uuid4())

        serializer = CourseManageSerializer(data=payload)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        course = serializer.save(academy=academy, user=request.user)
        course = _course_queryset_with_relations().filter(pk=course.pk).first() or course
        response_serializer = CourseListSerializer(
            course,
            context={
                "request": request,
                "enrolled_course_ids": set(
                    Course.objects.filter(enrolled_users=request.user).values_list("id", flat=True)
                ),
            },
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class CourseDetailAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_course(self, course_id):
        return _course_queryset_with_relations().filter(id=course_id).first()

    def get(self, request, course_id):
        course = self.get_course(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=status.HTTP_404_NOT_FOUND)

        enrolled_course_ids = set()
        if request.user and request.user.is_authenticated:
            enrolled_course_ids = set(
                Course.objects.filter(enrolled_users=request.user).values_list("id", flat=True)
            )

        serializer = CourseListSerializer(
            course,
            context={"request": request, "enrolled_course_ids": enrolled_course_ids},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _get_owner_academy(self, request, course):
        if not request.user or not request.user.is_authenticated:
            return None, Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        academy = Academy.objects.filter(user=request.user).first()
        if not academy:
            return None, Response(
                {"error": "Only academy accounts can edit courses."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if course.academy_id != academy.id:
            return None, Response(
                {"error": "You can only edit your own courses."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return academy, None

    def put(self, request, course_id):
        course = self.get_course(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=status.HTTP_404_NOT_FOUND)
        _, error_response = self._get_owner_academy(request, course)
        if error_response:
            return error_response

        serializer = CourseManageSerializer(course, data=request.data, partial=False)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        updated = serializer.save()
        updated = _course_queryset_with_relations().filter(pk=updated.pk).first() or updated
        enrolled_course_ids = set()
        if request.user and request.user.is_authenticated:
            enrolled_course_ids = set(
                Course.objects.filter(enrolled_users=request.user).values_list("id", flat=True)
            )
        return Response(
            CourseListSerializer(
                updated,
                context={"request": request, "enrolled_course_ids": enrolled_course_ids},
            ).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, course_id):
        course = self.get_course(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=status.HTTP_404_NOT_FOUND)
        _, error_response = self._get_owner_academy(request, course)
        if error_response:
            return error_response

        serializer = CourseManageSerializer(course, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        updated = serializer.save()
        updated = _course_queryset_with_relations().filter(pk=updated.pk).first() or updated
        enrolled_course_ids = set()
        if request.user and request.user.is_authenticated:
            enrolled_course_ids = set(
                Course.objects.filter(enrolled_users=request.user).values_list("id", flat=True)
            )
        return Response(
            CourseListSerializer(
                updated,
                context={"request": request, "enrolled_course_ids": enrolled_course_ids},
            ).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, course_id):
        course = self.get_course(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=status.HTTP_404_NOT_FOUND)
        _, error_response = self._get_owner_academy(request, course)
        if error_response:
            return error_response

        course.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CourseEnrollAPIView(APIView):
    """
    Learners add/remove themselves on Course.enrolled_users (M2M).
    Academy accounts cannot use this (they own courses).
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _course(self, course_id):
        return _course_queryset_with_relations().filter(id=course_id).first()

    def _enrolled_ids_for_user(self, user):
        if not user or not user.is_authenticated:
            return set()
        return set(
            Course.objects.filter(enrolled_users=user).values_list("id", flat=True)
        )

    def post(self, request, course_id):
        if _user_is_academy(request.user):
            return Response(
                {"error": "Academy accounts cannot enroll in courses."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if _user_is_employer(request.user):
            return Response(
                {"error": "Employer accounts cannot enroll in courses."},
                status=status.HTTP_403_FORBIDDEN,
            )
        course = self._course(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=status.HTTP_404_NOT_FOUND)
        course.enrolled_users.add(request.user)
        course = self._course(course_id)
        return Response(
            CourseListSerializer(
                course,
                context={
                    "request": request,
                    "enrolled_course_ids": self._enrolled_ids_for_user(request.user),
                },
            ).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, course_id):
        if _user_is_academy(request.user):
            return Response(
                {"error": "Academy accounts cannot use learner unenroll."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if _user_is_employer(request.user):
            return Response(
                {"error": "Employer accounts cannot use learner unenroll."},
                status=status.HTTP_403_FORBIDDEN,
            )
        course = self._course(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=status.HTTP_404_NOT_FOUND)
        course.enrolled_users.remove(request.user)
        course = self._course(course_id)
        return Response(
            CourseListSerializer(
                course,
                context={
                    "request": request,
                    "enrolled_course_ids": self._enrolled_ids_for_user(request.user),
                },
            ).data,
            status=status.HTTP_200_OK,
        )


# ---------------- Recommended Courses API ----------------
class RecommendedCoursesAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        user_skills = UserSkill.objects.filter(user=user)
        if not user_skills.exists():
            return Response({"recommended_courses": []}, status=200)

        courses_set = set()
        for job in Job.objects.all():
            match_data = calculate_match(user_skills, job)
            missing = match_data.get("missing_skills", [])
            if not missing:
                continue
            courses = Course.objects.filter(
                skills_taught__name__in=missing
            ).values_list("title", flat=True)
            courses_set.update(courses)

        return Response({"recommended_courses": list(courses_set)}, status=200)
        

        
def calculate_match(user_skills_qs, job):
    if not user_skills_qs.exists():
        return {
            "job_title": job.title,
            "description": job.description or "",
            "match_percentage": 0,
            "have_skills": [],
            "missing_skills": list(job.required_skills.values_list("name", flat=True)),
            "salary_range": f"${job.salary_min:,} - ${job.salary_max:,}" if job.salary_min else "",
            "time_to_ready": job.time_to_ready or "",
        }

    user_skill_names = set(user_skills_qs.values_list("skill__name", flat=True))
    required = set(job.required_skills.values_list("name", flat=True))

    overlap = required.intersection(user_skill_names)
    missing = required - user_skill_names
    match_percentage = (len(overlap) / len(required)) * 100 if required else 0

    return {
        "job_title": job.title,
        "description": job.description or "",
        "match_percentage": round(match_percentage, 2),
        "have_skills": list(overlap),
        "missing_skills": list(missing),
        "salary_range": f"${job.salary_min:,} - ${job.salary_max:,}" if job.salary_min else "",
        "time_to_ready": job.time_to_ready or "",
    }


class CareerPathAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        
        user_skills_qs = UserSkill.objects.filter(user=user)
        if not user_skills_qs.exists():
            return Response({
                "job_title": None,
                "description": "",
                "salary_range": "",
                "time_to_ready": "",
                "missing_skills": [],
                "recommended_courses": []
            }, status=200)

        
        model_path = os.path.join("app", "ml", "model.pkl")
        skill_vector = {s.skill.name: s.points for s in user_skills_qs}
        predicted_job_title = None

        if os.path.exists(model_path) and skill_vector:
            try:
                clf = joblib.load(model_path)
                X = pd.DataFrame([skill_vector])
                predicted_job_title = clf.predict(X)[0]
            except Exception:
                predicted_job_title = None

        
        if not predicted_job_title and skill_vector:
            strongest_skill = max(skill_vector.items(), key=lambda x: x[1])[0].lower()
            role_mapping = {
                "communication": "Team Player",
                "teamwork": "Team Player",
                "adaptability": "Problem Solver",
                "task management": "Efficient Planner",
                "time management": "Organized Worker",
                "leadership": "Leader / Manager",
                "project management": "Project Manager",
                "learning ability": "Curious Learner",
                "react": "Frontend Developer",
                "vue": "Frontend Developer",
                "angular": "Frontend Developer",
                "javascript": "Frontend Developer",
                "typescript": "Frontend Developer",
                "ios": "iOS Developer",
                "android": "Android Developer",
                "react native": "React Native Developer",
                "ui/ux": "UI/UX Designer",
                "python": "Backend Developer",
                "django": "Backend Developer",
                "sql": "Data Analyst",
                "mongodb": "Data Analyst",
            }
            predicted_job_title = role_mapping.get(strongest_skill, None)

        
        if not predicted_job_title:
            return Response({
                "job_title": None,
                "description": "",
                "salary_range": "",
                "time_to_ready": "",
                "missing_skills": [],
                "recommended_courses": []
            }, status=200)

        
        job_obj = Job.objects.filter(title__iexact=predicted_job_title).first()
        if not job_obj:
            return Response({
                "job_title": predicted_job_title,
                "description": "",
                "salary_range": "",
                "time_to_ready": "",
                "missing_skills": [],
                "recommended_courses": []
            }, status=200)

        
        user_skills = set(user_skills_qs.values_list("skill__name", flat=True))
        required_skills = set(job_obj.required_skills.values_list("name", flat=True))
        missing_skills = list(required_skills - user_skills)

       
        rec_courses = Course.objects.filter(
            skills_taught__name__in=missing_skills
        ).values_list("title", flat=True)

        return Response({
            "job_title": job_obj.title,
            "description": job_obj.description or "",
            "salary_range": f"${job_obj.salary_min:,} - ${job_obj.salary_max:,}" if job_obj.salary_min else "",
            "time_to_ready": job_obj.time_to_ready or "",
            "missing_skills": missing_skills,
            "recommended_courses": list(rec_courses)
        }, status=200)

# ---------------- Questions API ----------------

class DynamictestquestionsAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        questions = list(DynamicTechQuestion.objects.filter(isactive=True))
        random.shuffle(questions)
        serializer = QuestionTechSerializer(questions, many=True)
        return Response(serializer.data)
    

class DynamicSoftSkillsquestionsAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        questions = list(DynamicSoftSkillsQuestion.objects.filter(isactive=True))
        random.shuffle(questions)
        serializer = QuestionSoftSkillsSerializer(questions, many=True)
        return Response(serializer.data)





class CareerCategoryListAPIView(generics.ListAPIView):
    queryset = CareerCategory.objects.all()
    serializer_class = CareerCategorySerializer
    authentication_classes = [JWTAuthentication]


class ProfessionListAPIView(generics.ListAPIView):
    """GET /api/professions/ - list all professions with market_popularity (chart data), skills, courses."""
    queryset = Profession.objects.all().prefetch_related("skills", "relevant_courses")
    serializer_class = ProfessionSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


class MyProfessionAssignmentsAPIView(generics.ListAPIView):
    """
    GET /api/me/profession/ — current user's matched professions with full profession details.
    Requires auth. Each item includes: profession (id, title, description, skills,
    market_popularity, relevant_courses, created_at, updated_at), match_score, created_at.
    Ordered by match_score descending.
    """
    serializer_class = ProfessionOfUserSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            ProfessionOfUser.objects.filter(user=self.request.user)
            .select_related("profession")
            .prefetch_related("profession__skills", "profession__relevant_courses")
            .order_by("-match_score")
        )

# ---------------- AI Next Question Helper ----------------
def get_next_question_domain(answers, previous_domain):
    """
    AI determines next question domain based on user's previous answers.
    """
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }
        prompt = f"""
        User has answered these questions: {answers}.
        Suggest the next question domain for this user.
        Prefer switching topic if user shows strength in previous domain {previous_domain}.
        Give only a single word domain.
        """
        data = {
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 10
        }
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        return content or previous_domain
    except Exception:
        return previous_domain

# ---------------- Start Assessment API ----------------
class StartAssessmentAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        role_mapping = request.data.get("RoleMapping")
        num_questions = int(request.data.get("num_questions", 10))

       
        questions_qs = DynamicTechQuestion.objects.filter(RoleMapping=role_mapping, isactive=True)
        if questions_qs.count() < num_questions:
            questions_qs = DynamicTechQuestion.objects.filter(isactive=True)

        selected_questions = random.sample(list(questions_qs), min(num_questions, questions_qs.count()))

        questions_data = []
        for q in selected_questions:
            qdict = {
                "text": q.questiontext,
                "option1": q.option1,
                "option2": q.option2,
                "option3": q.option3,
                "option4": q.option4,
                "option5": getattr(q, "option5", I_DONT_KNOW),
                "correct_option": q.correct_option,
                "skill": q.skill.strip(),
                "difficulty": q.difficulty,
                "RoleMapping": q.RoleMapping
            }
            questions_data.append(qdict)

        session = AssessmentSession.objects.create(
            user=user,
            questions=questions_data,
            current_question_index=0,
            answers=[],
            dont_know_per_skill={}
        )

        return Response({
            "message": "Assessment started",
            "session_id": session.id,
            "questions": session.questions
        })


# ---------------- Submit Answer ----------------
class SubmitAnswerAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


    def post(self, request):
        try:
            session_id = request.data.get("session_id")
            if not session_id:
                return Response({"error": "Missing session_id"}, status=400)
            session = AssessmentSession.objects.get(id=session_id, user=request.user)
            answer = request.data.get("answer")
            question_text = request.data.get("question_text")

            if not session_id or not answer or not question_text:
                return Response({"error": "Missing parameters"}, status=400)

            session = AssessmentSession.objects.get(id=session_id)

            prev_question = next((q for q in session.questions if q.get("text") == question_text), None)
            if not prev_question:
                return Response({"error": "Question not found in session"}, status=400)

            prev_skill = (prev_question.get("skill") or "").strip()
            prev_role = prev_question.get("RoleMapping")
            prev_difficulty = prev_question.get("difficulty")
            correct_opt_num = prev_question["correct_option"]
            correct_answer = prev_question[f"option{correct_opt_num}"].strip() if correct_opt_num else ""

            # Detect "I don't know" - treat as incorrect and track per skill
            user_said_i_dont_know = is_i_dont_know(answer)
            if user_said_i_dont_know:
                dont_know_counts = getattr(session, "dont_know_per_skill", None) or {}
                if not isinstance(dont_know_counts, dict):
                    dont_know_counts = {}
                dont_know_counts[prev_skill] = dont_know_counts.get(prev_skill, 0) + 1
                session.dont_know_per_skill = dont_know_counts
                is_correct = False
            else:
                is_correct = (answer.strip() == correct_answer)

            # Save answer
            session.answers.append({
                "text": question_text,
                "answer": answer,
                "correct": is_correct,
                "difficulty": prev_difficulty,
                "skill": prev_skill,
                "RoleMapping": prev_role,
            })

            # Skills to skip: user tapped "I don't know" >= 2 times on this topic
            dont_know_counts = getattr(session, "dont_know_per_skill", None) or {}
            skipped_skills = {s.lower() for s, c in dont_know_counts.items() if c >= 2}

            def is_skill_skipped(skill_name):
                return (skill_name or "").strip().lower() in skipped_skills

            if is_correct:
                next_skill = prev_skill
                next_difficulty = "hard" if prev_difficulty != "hard" else "hard"
            else:
                next_difficulty = "easy"
                skills_in_role = list(DynamicTechQuestion.objects.filter(
                    RoleMapping=prev_role, isactive=True
                ).values_list("skill", flat=True).distinct())
                skills_in_role = [s.strip() for s in skills_in_role if s]
                prev_skill_norm = prev_skill.lower()
                skills_in_role_norm = [s.lower() for s in skills_in_role]

                available_skills = [
                    skills_in_role[i] for i, s in enumerate(skills_in_role_norm)
                    if s != prev_skill_norm and s not in skipped_skills
                ]
                next_skill = random.choice(available_skills) if available_skills else prev_skill

            # If next_skill was chosen but is now skipped, pick another
            if is_skill_skipped(next_skill):
                skills_in_role = list(DynamicTechQuestion.objects.filter(
                    RoleMapping=prev_role, isactive=True
                ).values_list("skill", flat=True).distinct())
                skills_in_role = [s.strip() for s in skills_in_role if s and not is_skill_skipped(s)]
                next_skill = random.choice(skills_in_role) if skills_in_role else prev_skill

            answered_texts = [a["text"] for a in session.answers]
            next_qs = list(DynamicTechQuestion.objects.filter(
                RoleMapping=prev_role,
                skill=next_skill,
                difficulty=next_difficulty,
                isactive=True
            ).exclude(questiontext__in=answered_texts))

            # Exclude questions from skipped skills
            next_qs = [q for q in next_qs if not is_skill_skipped((q.skill or "").strip())]

            if not next_qs:
                next_qs = list(DynamicTechQuestion.objects.filter(
                    RoleMapping=prev_role,
                    isactive=True
                ).exclude(questiontext__in=answered_texts))
                next_qs = [q for q in next_qs if not is_skill_skipped((q.skill or "").strip())]

            next_question = None
            if next_qs:
                nq = random.choice(next_qs)
                next_question = {
                    "text": nq.questiontext,
                    "option1": nq.option1,
                    "option2": nq.option2,
                    "option3": nq.option3,
                    "option4": nq.option4,
                    "option5": getattr(nq, "option5", I_DONT_KNOW),
                    "correct_option": nq.correct_option,
                    "skill": nq.skill.strip(),
                    "difficulty": nq.difficulty,
                    "RoleMapping": nq.RoleMapping,
                }
                session.questions.append(next_question)

            session.current_question_index += 1
            session.save()

            # Tell frontend when a topic was just skipped (user tapped "I don't know" twice)
            topic_skipped = None
            if user_said_i_dont_know and prev_skill and (dont_know_counts.get(prev_skill) or 0) >= 2:
                topic_skipped = prev_skill

            return Response({
                "message": "Answer submitted",
                "correct": is_correct,
                "next_question": next_question,
                "topic_skipped": topic_skipped,
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)


# ---------------- Progress Metrics ----------------
class ProgressMetricsAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = User.objects.first()
        if not user:
            return Response({"error": "No demo user"}, status=404)

        assessments = Assessment.objects.filter(user=user)
        badges = Badge.objects.filter(user=user)

        return Response({
            "total_assessments": assessments.count(),
            "completed_assessments": assessments.filter(status='completed').count(),
            "in_progress_assessments": assessments.filter(status='in_progress').count(),
            "total_badges": badges.count()
        })



# ---------------- Finish Assessment ----------------


class FinishAssessmentAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            session_id = request.data.get("session_id")
            if not session_id:
                return Response({"error": "Missing session_id"}, status=400)
            session = AssessmentSession.objects.get(id=session_id, user=request.user)

            # Load answers
            answers = session.answers or []
            if isinstance(answers, str):
                try:
                    answers = json.loads(answers)
                except Exception:
                    answers = []

            skill_scores = {}
            skill_totals = {}

            # Calculate per-skill scores
            for ans in answers:
                if not isinstance(ans, dict):
                    continue
                question_text = (ans.get("text") or "").strip()
                user_answer = (ans.get("answer") or "").strip()
                if not question_text or not user_answer:
                    continue

                question = DynamicTechQuestion.objects.filter(questiontext__iexact=question_text).first()
                if not question:
                    continue

                skill_name = (question.skill or "").strip()
                correct_option = getattr(question, "correct_option", None)
                correct_answer = getattr(question, f"option{correct_option}", "").strip() if correct_option else ""

                skill_scores.setdefault(skill_name, 0)
                skill_totals.setdefault(skill_name, 0)
                skill_totals[skill_name] += 1
                if user_answer == correct_answer:
                    skill_scores[skill_name] += 1

            user = session.user
            results = {}
            threshold_strong = 70.0
            threshold_borderline = 60.0

            # Update UserSkill & SkillScore
            for skill_name, correct_count in skill_scores.items():
                total = skill_totals.get(skill_name, 0)
                if total == 0:
                    continue

                percentage = round((correct_count / total) * 100, 2)
                skill_obj, _ = Skill.objects.get_or_create(name=skill_name)
                user_skill, _ = UserSkill.objects.get_or_create(user=user, skill=skill_obj)
                user_skill.points += correct_count
                user_skill.save()

                SkillScore.objects.create(
                    user=user,
                    skill=skill_obj,
                    score=percentage,
                    threshold=threshold_strong
                )

                if percentage >= threshold_strong:
                    rec = "✅ Strong"
                elif percentage >= threshold_borderline:
                    rec = "⚠️ Borderline"
                else:
                    rec = "❌ Weak"

                results[skill_name] = {
                    "score": f"{correct_count}/{total}",
                    "percentage": f"{percentage}%",
                    "recommendation": rec
                }

            total_score = sum(skill_scores.values())
            total_questions = sum(skill_totals.values())
            score_per_skill = {skill: data["percentage"] for skill, data in results.items()}

            session.completed = True
            session.save()

            # ==== ML Prediction ====
            final_role = "N/A"
            try:
                all_skills = list(UserSkill.objects.filter(user=user).values_list("skill__name", flat=True))
                skill_vector = {skill: UserSkill.objects.filter(user=user, skill__name=skill).first().points for skill in all_skills}

                if skill_vector:
                    clf = joblib.load("app/ml/model.pkl")
                    X = pd.DataFrame([skill_vector])
                    predicted_role = clf.predict(X)[0]
                    final_role = predicted_role
            except Exception:
                pass

            # ==== Fallback Role Mapping ====
            if final_role == "N/A" and results:
                strongest_skill = max(results.items(), key=lambda item: float(item[1]['percentage'].replace('%', '')))[0].strip().lower()
                role_mapping = {
                    "react": "Frontend Developer",
                    "vue": "Frontend Developer",
                    "angular": "Frontend Developer",
                    "javascript": "Frontend Developer",
                    "typescript": "Frontend Developer",
                    "ios": "iOS Developer",
                    "android": "Android Developer",
                    "react native": "React Native Developer",
                    "ui/ux": "UI/UX Designer",
                    "graphic designer": "Graphic Designer",
                    "3d modeler": "3D Modeler",
                    "product designer": "Product Designer",
                    "python": "Backend Developer",
                    "django": "Backend Developer",
                    "flask": "Backend Developer",
                    "node.js": "Backend Developer",
                    "express.js": "Backend Developer",
                    "sql": "Data Analyst",
                    "mongodb": "Data Analyst",
                    "data analyst": "Data Analyst",
                    "content creator": "Content Creator",
                    "video editor": "Content Creator",
                    "copywriter": "Content Creator",
                    "devops": "DevOps Engineer",
                    "aws": "DevOps Engineer",
                    "docker": "DevOps Engineer",
                    "kubernetes": "DevOps Engineer",
                    "communication": "Team Player",
                    "teamwork": "Team Player",
                    "adaptability": "Problem Solver",
                    "task management": "Efficient Planner",
                    "time management": "Organized Worker",
                    "leadership": "Leader / Manager",
                    "project management": "Project Manager",
                    "learning ability": "Curious Learner",
                    "Time & Task Management": "Efficient Planner",
                    "Adaptability & Learning": "Proactive Learner",
                    "Communication & Teamwork": "Team Player",
                }
                normalized_role_mapping = {k.lower(): v for k, v in role_mapping.items()}
                final_role = normalized_role_mapping.get(strongest_skill, "N/A")

            return Response({
                "message": "Assessment finished successfully",
                "total_score": total_score,
                "total_questions": total_questions,
                "results": results,
                "score_per_skill": score_per_skill,
                "final_role": final_role
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)



class StartSoftAssessmentAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            num_questions = 10

            questions_qs = list(DynamicSoftSkillsQuestion.objects.filter(isactive=True))
            if not questions_qs:
                return Response({"error": "No soft skills questions available"}, status=400)

            selected_questions = random.sample(questions_qs, min(num_questions, len(questions_qs)))
            random.shuffle(selected_questions)

            questions_data = []
            for q in selected_questions:
                qdict = {
                    "questiontext": q.questiontext,
                    "option1": q.option1,
                    "option2": q.option2,
                    "option3": q.option3,
                    "option4": q.option4,
                    "option5": getattr(q, "option5", I_DONT_KNOW),
                    "correct_option": q.correct_option,
                    "skill": q.skill.strip(),
                    "difficulty": q.difficulty,
                    "RoleMapping": q.RoleMapping,
                    "type": "soft"
                }
                questions_data.append(qdict)

            session = AssessmentSession.objects.create(
                user=user,
                questions=questions_data,
                current_question_index=0,
                answers=[],
                dont_know_per_skill={}
            )

            first_question = session.questions[0] if session.questions else None

            return Response({
                "message": "Soft assessment started",
                "session_id": session.id,
                "first_question": first_question
            })

        except Exception as e:
            return Response({"error": str(e)}, status=500)
        

class SubmitSoftAnswerAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            session_id = request.data.get("session_id")
            if not session_id:
                return Response({"error": "Missing session_id"}, status=400)
            session = AssessmentSession.objects.get(id=session_id, user=request.user)
            answer = request.data.get("answer")
            question_text = request.data.get("question_text")

            if not session_id or not answer or not question_text:
                return Response({"error": "Missing parameters"}, status=400)

            session = AssessmentSession.objects.get(id=session_id)

            # Find current question to get skill for "I don't know" tracking
            current_idx = session.current_question_index
            if current_idx < len(session.questions):
                current_q = session.questions[current_idx]
                prev_skill = (current_q.get("skill") or "").strip()
                if is_i_dont_know(answer):
                    dont_know_counts = getattr(session, "dont_know_per_skill", None) or {}
                    if not isinstance(dont_know_counts, dict):
                        dont_know_counts = {}
                    dont_know_counts[prev_skill] = dont_know_counts.get(prev_skill, 0) + 1
                    session.dont_know_per_skill = dont_know_counts

            session.answers.append({"question_text": question_text, "answer": answer})
            session.current_question_index += 1
            session.save()

            # Skip questions from topics where user tapped "I don't know" twice
            dont_know_counts = getattr(session, "dont_know_per_skill", None) or {}
            skipped_skills = {s.lower() for s, c in dont_know_counts.items() if c >= 2}
            topics_skipped_this_round = []

            while session.current_question_index < len(session.questions):
                next_q = session.questions[session.current_question_index]
                next_skill = (next_q.get("skill") or "").strip()
                next_skill_lower = next_skill.lower()
                if next_skill_lower not in skipped_skills:
                    break
                topics_skipped_this_round.append(next_skill)
                session.current_question_index += 1
            session.save()

            if session.current_question_index >= len(session.questions):
                total_score = 0
                for a in session.answers:
                    qtext = a.get("question_text", "")
                    q = next((x for x in session.questions if (x.get("questiontext") or x.get("text")) == qtext), None)
                    if q and a.get("answer") == q.get(f"option{q.get('correct_option', 1)}"):
                        total_score += 1
                total_questions = len(session.answers)
                session.completed = True
                session.save()

                return Response({
                    "message": "Assessment finished",
                    "total_score": total_score,
                    "total_questions": total_questions
                })

            next_question = session.questions[session.current_question_index]
            return Response({
                "message": "Answer submitted",
                "next_question": next_question,
                "topics_skipped": topics_skipped_this_round,
            })

        except AssessmentSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        


class FinishSoftAssessmentAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            session_id = request.data.get("session_id")
            if not session_id:
                return Response({"error": "Missing session_id"}, status=400)

            session = AssessmentSession.objects.get(id=session_id, user=request.user)

            # Load answers safely
            answers = session.answers or []
            if isinstance(answers, str):
                try:
                    answers = json.loads(answers)
                except Exception:
                    answers = []

            skill_scores = {}
            skill_totals = {}

            # Calculate per-skill scores
            for ans in answers:
                if not isinstance(ans, dict):
                    continue
                question_text = (ans.get("question_text") or "").strip()
                user_answer = (ans.get("answer") or "").strip()
                if not question_text or not user_answer:
                    continue

                question = DynamicSoftSkillsQuestion.objects.filter(
                    questiontext__iexact=question_text
                ).first()
                if not question:
                    continue

                skill_name = (question.skill or "").strip()
                correct_option = getattr(question, "correct_option", None)
                correct_answer = getattr(question, f"option{correct_option}", "").strip() if correct_option else ""

                skill_scores.setdefault(skill_name, 0)
                skill_totals.setdefault(skill_name, 0)
                skill_totals[skill_name] += 1
                if user_answer == correct_answer:
                    skill_scores[skill_name] += 1

            user = session.user
            results = {}
            threshold_strong = 70.0
            threshold_borderline = 60.0

            # Update UserSkill & SkillScore safely
            for skill_name, correct_count in skill_scores.items():
                total = skill_totals.get(skill_name, 0)
                if total == 0:
                    continue

                percentage = round((correct_count / total) * 100, 2)

                skill_obj, _ = Skill.objects.get_or_create(name=skill_name)

                # ===== SAFETY FIX: avoid MultipleObjectsReturned =====
                user_skill = UserSkill.objects.filter(user=user, skill=skill_obj).first()
                if not user_skill:
                    user_skill = UserSkill.objects.create(user=user, skill=skill_obj, points=0)

                user_skill.points += correct_count
                user_skill.save()

                SkillScore.objects.create(
                    user=user,
                    skill=skill_obj,
                    score=percentage,
                    threshold=threshold_strong
                )

                if percentage >= threshold_strong:
                    rec = "✅ Strong"
                elif percentage >= threshold_borderline:
                    rec = "⚠️ Borderline"
                else:
                    rec = "❌ Weak"

                results[skill_name] = {
                    "score": f"{correct_count}/{total}",
                    "percentage": f"{percentage}%",
                    "recommendation": rec
                }

            total_score = sum(skill_scores.values())
            total_questions = sum(skill_totals.values())
            score_per_skill = {skill: data["percentage"] for skill, data in results.items()}

            # Mark session completed
            session.completed = True
            session.save()

            # ==== ML Prediction ====
            final_role = "N/A"
            try:
                all_skills = list(UserSkill.objects.filter(user=user).values_list("skill__name", flat=True))
                skill_vector = {skill: UserSkill.objects.filter(user=user, skill__name=skill).first().points for skill in all_skills}

                if skill_vector:
                    clf = joblib.load("app/ml/model.pkl") 
                    X = pd.DataFrame([skill_vector])
                    predicted_role = clf.predict(X)[0]
                    final_role = predicted_role
            except Exception:
                pass

            # ==== Fallback Role Mapping ====
            if final_role == "N/A" and results:
                cleaned_results = {k.strip().lower(): v for k, v in results.items()}
                strongest_skill = max(
                    cleaned_results.items(),
                    key=lambda item: float(item[1]['percentage'].replace('%', ''))
                )[0]

                role_mapping = {
                    "communication": "Team Player",
                    "teamwork": "Team Player",
                    "adaptability": "Problem Solver",
                    "task management": "Efficient Planner",
                    "time management": "Organized Worker",
                    "leadership": "Leader / Manager",
                    "project management": "Project Manager",
                    "learning ability": "Curious Learner",
                    "time & task management": "Efficient Planner",
                    "adaptability & learning": "Proactive Learner",
                    "communication & teamwork": "Team Player",
                    "react": "Frontend Developer",
                    "vue": "Frontend Developer",
                    "angular": "Frontend Developer",
                    "javascript": "Frontend Developer",
                    "typescript": "Frontend Developer",
                    "ios": "iOS Developer",
                    "android": "Android Developer",
                    "react native": "React Native Developer",
                    "ui/ux": "UI/UX Designer",
                    "graphic designer": "Graphic Designer",
                    "3d modeler": "3D Modeler",
                    "product designer": "Product Designer",
                    "python": "Backend Developer",
                    "django": "Backend Developer",
                    "flask": "Backend Developer",
                    "node.js": "Backend Developer",
                    "express.js": "Backend Developer",
                    "sql": "Data Analyst",
                    "mongodb": "Data Analyst",
                    "data analyst": "Data Analyst",
                    "content creator": "Content Creator",
                    "video editor": "Content Creator",
                    "copywriter": "Content Creator",
                    "devops": "DevOps Engineer",
                    "aws": "DevOps Engineer",
                    "docker": "DevOps Engineer",
                    "kubernetes": "DevOps Engineer"
                }
                normalized_role_mapping = {k.lower(): v for k, v in role_mapping.items()}
                final_role = normalized_role_mapping.get(strongest_skill, "N/A")

            return Response({
                "message": "Soft Skills Assessment finished successfully",
                "total_score": total_score,
                "total_questions": total_questions,
                "results": results or {},
                "score_per_skill": score_per_skill or {},
                "final_role": final_role
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)




@api_view(["POST"])
def finish_assessment(request):
    session_id = request.data.get("session_id")
    try:
        session = AssessmentSession.objects.get(id=session_id)
    except AssessmentSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)

    score = 0
    for ans in session.answers:
        try:
            q = DynamicTechQuestion.objects.get(questiontext=ans["questiontext"])
            if q.correct_option and ans["answer"] == getattr(q, f"option{q.correct_option}"):
                score += 1
        except DynamicTechQuestion.DoesNotExist:
            continue

    session.completed = True
    session.save()

    percentage = round((score / len(session.answers)) * 100, 2) if session.answers else 0

    return Response({
        "score": f"{score} / {len(session.answers)}",
        "percentage": percentage
    })





class RandomCareerQuestionsAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", 5))
            all_questions = list(CareerQuestion.objects.all())
            if not all_questions:
                return Response({"error": "No questions found"}, status=404)

            
            random.shuffle(all_questions)

            
            questions = all_questions[:min(limit, len(all_questions))]

            serializer = CareerQuestionSerializer(questions, many=True)
            data = serializer.data

            
            for q_idx, q in enumerate(questions):
                for o_idx, opt in enumerate(q.options.all()):
                    data[q_idx]['options'][o_idx]['RoleMapping'] = opt.RoleMapping

            return Response(data, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        



def get_top_role(answers):
    role_counts = {}
    for a in answers:
        role = a.get("RoleMapping")
        if role:
            role_counts[role] = role_counts.get(role, 0) + 1
    if not role_counts:
        return None
    return max(role_counts, key=role_counts.get)




class CareerRoadmapAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = User.objects.first()  # demo purposes
        if not user:
            return Response({"error": "No demo user"}, status=404)

        # -------- User Skills Snapshot --------
        user_skills_qs = UserSkill.objects.filter(user=user)
        skill_snapshot = {us.skill.name: us.points for us in user_skills_qs}

        # -------- Career Matches --------
        jobs_data = []
        for job in Job.objects.all():
            match = calculate_match(user_skills_qs, job)

            # Missing skills -> Recommended courses
            missing_skills = match.get("missing_skills", [])
            recommended_courses = Course.objects.filter(
                skills_taught__name__in=missing_skills
            ).values_list("title", flat=True)

            match["recommended_courses"] = list(set(recommended_courses))
            jobs_data.append(match)

        # -------- Identify top career (optional) --------
        top_career = max(jobs_data, key=lambda j: j["match_percentage"]) if jobs_data else None

        return Response({
            "user_skills": skill_snapshot,
            "career_matches": jobs_data,
            "top_career": top_career
        })



from .utils import fetch_salary_from_groq




# Save skill test results
THROTTLE_SECONDS = 30  # Ignore duplicate saves within this window


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_test_results(request):
    """
    API to save skill test results.
    - Update instead of create: replaces the user's most recent result (one row per user).
    - Throttling: ignores requests within 30s with same score/role (avoids double-submit).
    Expects JSON:
    {
        "final_role": "Developer",
        "obtained_score": 14,
        "total_questions": 25,
        "skills_json": { ... }
    }
    """
    data = request.data.copy()
    obtained = data.get("obtained_score", 0)
    total = data.get("total_questions", 0)
    total_score = f"{obtained} / {total}"
    data["total_score"] = total_score
    final_role = (data.get("final_role") or "").strip()
    skills_json = data.get("skills_json") or {}

    serializer = SkillTestResultSerializer(data=data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    user = request.user
    now = timezone.now()

    # Throttling: ignore if same score/role within last 30 seconds
    last = SkillTestResult.objects.filter(user=user).order_by("-created_at").first()
    if last:
        if last.total_score == total_score and last.final_role == final_role:
            age_seconds = (now - last.created_at).total_seconds()
            if age_seconds < THROTTLE_SECONDS:
                return Response(
                    SkillTestResultSerializer(last).data,
                    status=200,
                )

    # Update instead of create: replace most recent result (one row per user)
    if last:
        last.final_role = final_role
        last.total_score = total_score
        last.skills_json = skills_json
        last.save()
        update_profession_of_user_from_skill_test(user)
        return Response(SkillTestResultSerializer(last).data, status=200)

    # First result for user: create
    obj = serializer.save(user=user)
    update_profession_of_user_from_skill_test(user)
    return Response(serializer.data, status=201)
# Get logged-in user's skill test results
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_results(request):
    results = SkillTestResult.objects.filter(user=request.user).order_by('-created_at')
    serializer = SkillTestResultSerializer(results, many=True)
    return Response(serializer.data)

# --------------------------
# User Registration
# --------------------------

class RegisterView(generics.CreateAPIView):
    queryset = TemporaryUser.objects.all()
    serializer_class = RegisterSerializer

    def post(self, request):
        email = request.data.get("email")
        temp_user = TemporaryUser.objects.filter(email=email).first()

        if temp_user:
            temp_user.first_name = request.data.get("first_name")
            temp_user.last_name = request.data.get("last_name")
            temp_user.password = make_password(request.data.get("password"))
            temp_user.phone_number = request.data.get("phone_number")
        else:
            temp_user = TemporaryUser.objects.create(
                first_name=request.data.get("first_name"),
                last_name=request.data.get("last_name"),
                email=email,
                password=make_password(request.data.get("password")),
                phone_number=request.data.get("phone_number"),
            )

        temp_user.generate_verification_code()
        temp_user.save()

        # Render email templates
        html_message = render_to_string('emails/verification_code.html', {
            'verification_code': temp_user.verification_code,
            'first_name': temp_user.first_name,
            'logo_url': getattr(settings, 'BRENEO_LOGO_URL', ''),
        })
        text_message = render_to_string('emails/verification_code.txt', {
            'verification_code': temp_user.verification_code,
            'first_name': temp_user.first_name,
        })

        # Send email with HTML template
        success, error = send_email_safely(
            subject="Your Verification Code",
            text_message=text_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_email=email
        )
        
        if not success:
            return Response({
                "message": "Verification code created. Email delivery may be delayed.",
                "error": "Email sending failed"
            }, status=status.HTTP_202_ACCEPTED)

        return Response({"message": "Verification code sent to your email."}, status=200)




class VerifyCodeView(APIView):
    parser_classes = [JSONParser, FormParser]

    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")

        if not email or not code:
            return Response({"error": "Email and code are required"}, status=status.HTTP_400_BAD_REQUEST)

        
        temp_user = TemporaryUser.objects.filter(email=email).first()
        temp_academy = TemporaryAcademy.objects.filter(email=email).first()

        if not temp_user and not temp_academy:
            return Response({"error": "No temporary record found for this email"}, status=status.HTTP_404_NOT_FOUND)

        
        if temp_user:
            if temp_user.verification_code != code:
                return Response({"error": "Invalid verification code"}, status=status.HTTP_400_BAD_REQUEST)
            if temp_user.code_expires_at < timezone.now():
                temp_user.delete()
                return Response({"error": "Verification code expired"}, status=status.HTTP_400_BAD_REQUEST)
            
            
            if User.objects.filter(email=temp_user.email).exists():
                temp_user.delete()
                return Response({"error": "A user with this email already exists"}, status=status.HTTP_400_BAD_REQUEST)

            
            user = User.objects.create(
                username=temp_user.email,
                first_name=temp_user.first_name,
                last_name=temp_user.last_name,
                email=temp_user.email,
                password=temp_user.password,
                is_active=True
            )

            
            UserProfile.objects.create(
                user=user,
                phone_number=temp_user.phone_number
            )
            temp_user.delete()
            return Response({"message": "User registered successfully!"}, status=status.HTTP_201_CREATED)

        
        if temp_academy:
            if temp_academy.verification_code != code:
                return Response({"error": "Invalid verification code"}, status=status.HTTP_400_BAD_REQUEST)
            if temp_academy.code_expires_at < timezone.now():
                temp_academy.delete()
                return Response({"error": "Verification code expired"}, status=status.HTTP_400_BAD_REQUEST)
            
            
            if User.objects.filter(email=temp_academy.email).exists():
                temp_academy.delete()
                return Response({"error": "An academy with this email already exists"}, status=status.HTTP_400_BAD_REQUEST)

            user = User.objects.create(
                username=temp_academy.email,
                email=temp_academy.email,
                password=temp_academy.password,
                first_name=temp_academy.name,
                last_name="",
                is_active=True,
            )

            academy = Academy.objects.create(
                user=user,
                password=temp_academy.password,
                phone_number=temp_academy.phone_number or "",
                description=temp_academy.description or "No description provided",
                website=temp_academy.website,
                is_verified=True,
            )

            temp_academy.delete()
            return Response({"message": "Academy registered successfully!"}, status=status.HTTP_201_CREATED)


        
        
# --------------------------
# User Profile
# --------------------------



class UserProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def _reject_academy(self, request):
        return _reject_non_regular_user_profile(request)

    def get(self, request):
        if resp := self._reject_academy(request):
            return resp
        user = request.user
        profile, _ = UserProfile.objects.get_or_create(user=user)

        try:
            profile_image_url = (
                request.build_absolute_uri(profile.profile_image.url)
                if profile.profile_image else None
            )
        except Exception:
            profile_image_url = None

        
        social_links, _ = SocialLinks.objects.get_or_create(user=user)
        social_data = SocialLinksSerializer(social_links).data

       
        saved_courses = SavedCourse.objects.filter(user=user).values_list("course_id", flat=True)
        saved_jobs = SavedJob.objects.filter(user=user).values_list("job_id", flat=True)

        return Response({
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone_number": profile.phone_number,
            "country_region": getattr(profile, "country_region", "") or "",
            "city": getattr(profile, "city", "") or "",
            "about_me": profile.about_me,
            "profile_image": profile_image_url,
            "social_links": social_data,
            "saved_courses": list(saved_courses),
            "saved_jobs": list(saved_jobs),
        })

    def patch(self, request):
        if resp := self._reject_academy(request):
            return resp
        user = request.user
        profile, _ = UserProfile.objects.get_or_create(user=user)

       
        if "first_name" in request.data:
            user.first_name = request.data["first_name"]
        if "last_name" in request.data:
            user.last_name = request.data["last_name"]
        user.save()

        
        serializer = UserProfileSerializer(
            profile,
            data=request.data,
            partial=True,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        
        social_links, _ = SocialLinks.objects.get_or_create(user=user)
        social_data = request.data.get("social_links")

        if isinstance(social_data, dict):
            social_serializer = SocialLinksSerializer(
                social_links,
                data=social_data,
                partial=True
            )
            social_serializer.is_valid(raise_exception=True)
            social_serializer.save()

        try:
            profile_image_url = (
                request.build_absolute_uri(profile.profile_image.url)
                if profile.profile_image else None
            )
        except Exception:
            profile_image_url = None

        
        saved_courses = SavedCourse.objects.filter(user=user).values_list("course_id", flat=True)
        saved_jobs = SavedJob.objects.filter(user=user).values_list("job_id", flat=True)

        return Response({
            "message": "Profile updated successfully.",
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone_number": profile.phone_number,
            "country_region": getattr(profile, "country_region", "") or "",
            "city": getattr(profile, "city", "") or "",
            "about_me": profile.about_me,
            "profile_image": profile_image_url,
            "social_links": SocialLinksSerializer(social_links).data,
            "saved_courses": list(saved_courses),
            "saved_jobs": list(saved_jobs),
        }, status=status.HTTP_200_OK)

    def delete(self, request):
        if resp := self._reject_academy(request):
            return resp
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.profile_image:
            try:
                profile.profile_image.delete(save=True)
            except Exception:
                pass
            profile.profile_image = None
            profile.save()
            return Response({"message": "Profile image deleted successfully"}, status=status.HTTP_200_OK)
        return Response({"error": "No image to delete"}, status=status.HTTP_400_BAD_REQUEST)


# ---------------- /api/me/profile (Personal) ----------------
class PersonalProfileView(APIView):
    """GET/PUT /api/me/profile - User + UserProfile + social_links. Scoped to request.user. Requires JWT."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def _reject_academy(self, request):
        return _reject_non_regular_user_profile(request)

    def get(self, request):
        if resp := self._reject_academy(request):
            return resp
        user = request.user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        social_links, _ = SocialLinks.objects.get_or_create(user=user)
        try:
            profile_image_url = (
                request.build_absolute_uri(profile.profile_image.url)
                if profile.profile_image else None
            )
        except Exception:
            profile_image_url = None
        return Response({
            "email": user.email,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "phone_number": profile.phone_number or "",
            "country_region": getattr(profile, "country_region", "") or "",
            "city": getattr(profile, "city", "") or "",
            "about_me": profile.about_me or "",
            "profile_image": profile_image_url,
            "social_links": SocialLinksSerializer(social_links).data,
        })

    def put(self, request):
        if resp := self._reject_academy(request):
            return resp
        user = request.user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        data = request.data
        if "email" in data:
            user.email = data["email"]
        if "first_name" in data:
            user.first_name = data["first_name"]
        if "last_name" in data:
            user.last_name = data["last_name"]
        user.save()
        if "phone_number" in data:
            profile.phone_number = data["phone_number"]
        if "country_region" in data:
            profile.country_region = data["country_region"]
        if "city" in data:
            profile.city = data["city"]
        if "about_me" in data:
            profile.about_me = data["about_me"]
        if "profile_image" in data:
            profile.profile_image = data["profile_image"]
        profile.save()
        social_links, _ = SocialLinks.objects.get_or_create(user=user)
        try:
            profile_image_url = (
                request.build_absolute_uri(profile.profile_image.url)
                if profile.profile_image else None
            )
        except Exception:
            profile_image_url = None
        return Response({
            "email": user.email,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "phone_number": profile.phone_number or "",
            "country_region": getattr(profile, "country_region", "") or "",
            "city": getattr(profile, "city", "") or "",
            "about_me": profile.about_me or "",
            "profile_image": profile_image_url,
            "social_links": SocialLinksSerializer(social_links).data,
        }, status=status.HTTP_200_OK)


# ---------------- /api/me/social-links ----------------
class SocialLinksMeView(APIView):
    """GET/PUT/PATCH /api/me/social-links - CRUD scoped to request.user. Requires JWT."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def _reject_academy(self, request):
        return _reject_non_regular_user_profile(request)

    def get(self, request):
        if resp := self._reject_academy(request):
            return resp
        social_links, _ = SocialLinks.objects.get_or_create(user=request.user)
        return Response(SocialLinksSerializer(social_links).data)

    def put(self, request):
        if resp := self._reject_academy(request):
            return resp
        social_links, _ = SocialLinks.objects.get_or_create(user=request.user)
        serializer = SocialLinksSerializer(social_links, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        if resp := self._reject_academy(request):
            return resp
        social_links, _ = SocialLinks.objects.get_or_create(user=request.user)
        serializer = SocialLinksSerializer(social_links, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------- /api/me/industry-profile ----------------
class IndustryProfileView(APIView):
    """GET/PUT /api/me/industry-profile - Fetch or upsert industry years for request.user. Requires JWT."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            profile = UserIndustryProfile.objects.get(user=request.user)
            return Response({
                "industry_years_json": profile.industry_years_json,
                "updated_at": profile.updated_at.isoformat(),
            })
        except UserIndustryProfile.DoesNotExist:
            return Response({
                "industry_years_json": {},
                "updated_at": None,
            })

    def put(self, request):
        data = request.data
        if not isinstance(data, dict):
            return Response(
                {"detail": "Request body must be JSON object."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        industry_years_json = data.get("industry_years_json")
        if industry_years_json is None:
            industry_years_json = {}
        if not isinstance(industry_years_json, dict):
            return Response(
                {"detail": "industry_years_json must be an object."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_at_str = data.get("updated_at")
        if updated_at_str is not None:
            updated_at = parse_datetime(str(updated_at_str))
            if updated_at is None:
                return Response(
                    {"detail": "updated_at must be a valid ISO 8601 datetime string."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            updated_at = timezone.now()

        profile, created = UserIndustryProfile.objects.update_or_create(
            user=request.user,
            defaults={
                "industry_years_json": industry_years_json,
                "updated_at": updated_at,
            },
        )

        return Response(
            {
                "industry_years_json": profile.industry_years_json,
                "updated_at": profile.updated_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )


# ---------------- /api/educations ----------------
MAX_EDUCATIONS = 10
MAX_WORK_EXPERIENCES = 10


class EducationViewSet(viewsets.ModelViewSet):
    """CRUD for Education. Queryset filtered by request.user. Max 10 per user. Requires JWT."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EducationSerializer

    def get_queryset(self):
        return Education.objects.filter(user=self.request.user).order_by("-start_date")

    def _ensure_owner(self, instance):
        if instance.user_id != self.request.user.pk:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only modify your own education entries.")

    def perform_create(self, serializer):
        user = self.request.user
        if Education.objects.filter(user=user).count() >= MAX_EDUCATIONS:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                {"detail": f"Maximum {MAX_EDUCATIONS} education entries allowed per user."}
            )
        serializer.save(user=user)

    def perform_update(self, serializer):
        self._ensure_owner(serializer.instance)
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        self._ensure_owner(instance)
        instance.delete()


class WorkExperienceViewSet(viewsets.ModelViewSet):
    """CRUD for WorkExperience. Queryset filtered by request.user. Max 10 per user. Requires JWT."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WorkExperienceSerializer

    def get_queryset(self):
        return WorkExperience.objects.filter(user=self.request.user).order_by("-start_date")

    def _ensure_owner(self, instance):
        if instance.user_id != self.request.user.pk:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only modify your own work experience entries.")

    def perform_create(self, serializer):
        user = self.request.user
        if WorkExperience.objects.filter(user=user).count() >= MAX_WORK_EXPERIENCES:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                {"detail": f"Maximum {MAX_WORK_EXPERIENCES} work experience entries allowed per user."}
            )
        serializer.save(user=user)

    def perform_update(self, serializer):
        self._ensure_owner(serializer.instance)
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        self._ensure_owner(instance)
        instance.delete()


# ---------------- /api/skills?query= & /api/me/skills ----------------
class SkillSearchAPIView(APIView):
    """GET /api/skills?query=xxx - top 20 matches by name (icontains). Requires JWT."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = (request.query_params.get("query") or "").strip()
        if not query:
            qs = Skill.objects.all().order_by("name")[:20]
        else:
            qs = Skill.objects.filter(name__icontains=query).order_by("name")[:20]
        return Response(SkillSearchSerializer(qs, many=True).data)


class UserSkillListAttachView(APIView):
    """GET /api/me/skills - list current user's skills. POST - attach skill by name. Requires JWT."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get(self, request):
        """List all skills attached to the current user."""
        qs = UserSkill.objects.filter(user=request.user).select_related("skill").order_by("-created_at")
        return Response(UserSkillResponseSerializer(qs, many=True).data)

    def post(self, request):
        serializer = UserSkillAttachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = (serializer.validated_data["name"] or "").strip()
        if not name:
            return Response(
                {"detail": "Skill name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        normalized = " ".join(name.split())
        skill = Skill.objects.filter(name__iexact=normalized).first()
        if skill is None:
            skill = Skill.objects.create(name=normalized)
        user_skill, created = UserSkill.objects.get_or_create(
            user=request.user,
            skill=skill,
            defaults={"points": 1},
        )
        return Response(
            UserSkillResponseSerializer(user_skill).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class UserSkillDetachView(APIView):
    """DELETE /api/me/skills/<skill_id> - Removes UserSkill for request.user + skill_id. Requires JWT."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["delete", "head", "options"]

    def delete(self, request, skill_id):
        deleted, _ = UserSkill.objects.filter(user=request.user, skill_id=skill_id).delete()
        if not deleted:
            return Response(
                {"detail": "Skill not found on your profile."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)




class AcademyProfileUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_academy(self, request):
        return Academy.objects.filter(user=request.user).first()

    def get(self, request):
        academy = self.get_academy(request)
        if not academy:
            return Response({"error": "Academy not found"}, status=status.HTTP_404_NOT_FOUND)

        
        social_links, _ = SocialLinks.objects.get_or_create(academy=academy)
        social_data = SocialLinksSerializer(social_links).data

        try:
            profile_image_url = (
                request.build_absolute_uri(academy.profile_image.url)
                if academy.profile_image else None
            )
        except Exception:
            profile_image_url = None

        
        saved_courses = SavedCourse.objects.filter(academy=academy).values_list("course_id", flat=True)
        saved_jobs = SavedJob.objects.filter(academy=academy).values_list("job_id", flat=True)

        return Response({
            "id": academy.id,
            "name": academy.name,
            "email": academy.email,
            "phone_number": academy.phone_number,
            "description": academy.description,
            "website": academy.website,
            "is_verified": academy.is_verified,
            "created_at": academy.created_at,
            "profile_image": profile_image_url,
            "social_links": social_data,
            "saved_courses": list(saved_courses),
            "saved_jobs": list(saved_jobs),
        })

    def patch(self, request):
        academy = self.get_academy(request)
        if not academy:
            return Response({"error": "Academy not found"}, status=status.HTTP_404_NOT_FOUND)

       
        serializer = AcademyUpdateSerializer(
            academy,
            data=request.data,
            partial=True,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        social_links, _ = SocialLinks.objects.get_or_create(academy=academy)
        social_data = request.data.get("social_links", None)

        if isinstance(social_data, dict): 
            social_serializer = SocialLinksSerializer(
                social_links,
                data=social_data,
                partial=True
            )
            social_serializer.is_valid(raise_exception=True)
            social_serializer.save()

        try:
            profile_image_url = (
                request.build_absolute_uri(academy.profile_image.url)
                if academy.profile_image else None
            )
        except Exception:
            profile_image_url = None

       
        saved_courses = SavedCourse.objects.filter(academy=academy).values_list("course_id", flat=True)
        saved_jobs = SavedJob.objects.filter(academy=academy).values_list("job_id", flat=True)

        return Response({
            "message": "Academy profile updated successfully.",
            "academy": {
                "id": academy.id,
                "name": academy.name,
                "email": academy.email,
                "phone_number": academy.phone_number,
                "description": academy.description,
                "website": academy.website,
                "is_verified": academy.is_verified,
                "profile_image": profile_image_url,
            },
            "social_links": SocialLinksSerializer(social_links).data,
            "saved_courses": list(saved_courses),
            "saved_jobs": list(saved_jobs),
        }, status=status.HTTP_200_OK)


# ---------------- Employer (same pattern as Academy) ----------------


class IndustryListAPIView(APIView):
    """GET /api/industries/ — list industry catalog."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        qs = Industry.objects.all().order_by("name")
        return Response(IndustrySerializer(qs, many=True).data)


class EmployerProfileUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_employer(self, request):
        return Employer.objects.filter(user=request.user).first()

    def get(self, request):
        employer = self.get_employer(request)
        if not employer:
            return Response({"error": "Employer not found"}, status=status.HTTP_404_NOT_FOUND)

        social_links, _ = SocialLinks.objects.get_or_create(employer=employer)
        social_data = SocialLinksSerializer(social_links).data
        u = employer.user

        return Response(
            {
                "id": employer.id,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "email": employer.email,
                "role_in_company": employer.role_in_company,
                "is_verified": employer.is_verified,
                "created_at": employer.created_at,
                "social_links": social_data,
            }
        )

    def patch(self, request):
        employer = self.get_employer(request)
        if not employer:
            return Response({"error": "Employer not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = EmployerUpdateSerializer(
            employer,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        employer = self.get_employer(request)
        social_links, _ = SocialLinks.objects.get_or_create(employer=employer)
        social_data = request.data.get("social_links", None)

        if isinstance(social_data, dict):
            social_serializer = SocialLinksSerializer(
                social_links,
                data=social_data,
                partial=True,
            )
            social_serializer.is_valid(raise_exception=True)
            social_serializer.save()

        u = employer.user
        return Response(
            {
                "message": "Employer profile updated successfully.",
                "employer": {
                    "id": employer.id,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "email": employer.email,
                    "role_in_company": employer.role_in_company,
                    "is_verified": employer.is_verified,
                },
                "social_links": SocialLinksSerializer(social_links).data,
            },
            status=status.HTTP_200_OK,
        )


class EmployerLoginView(APIView):
    def post(self, request):
        identifier = (request.data.get("email") or "").strip()
        password = request.data.get("password")

        if not identifier or not password:
            return Response(
                {"error": "Email (or full name) and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        employer = Employer.objects.filter(user__email__iexact=identifier).first()
        if not employer and " " in identifier:
            first_name, last_name = identifier.split(" ", 1)
            employer = Employer.objects.filter(
                user__first_name__iexact=first_name.strip(),
                user__last_name__iexact=last_name.strip(),
            ).first()

        if not employer:
            return Response({"error": "Employer not found"}, status=status.HTTP_404_NOT_FOUND)

        if not employer.user.check_password(password):
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = RefreshToken.for_user(employer.user)
        access = refresh.access_token
        u = employer.user

        return Response(
            {
                "message": "Employer login successful",
                "access": str(access),
                "refresh": str(refresh),
                "user_type": "employer",
                "employer": {
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "email": employer.email,
                    "role_in_company": employer.role_in_company,
                },
            },
            status=status.HTTP_200_OK,
        )


class TemporaryEmployerRegisterView(generics.CreateAPIView):
    queryset = TemporaryEmployer.objects.all()
    serializer_class = TemporaryEmployerRegisterSerializer

    def post(self, request):
        serializer = TemporaryEmployerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        email = vd["email"]
        pw_hash = make_password(vd["password"])
        temp = TemporaryEmployer.objects.filter(email=email).first()

        if temp:
            temp.first_name = vd["first_name"]
            temp.last_name = vd["last_name"]
            temp.password = pw_hash
            temp.role_in_company = vd.get("role_in_company") or ""
        else:
            temp = TemporaryEmployer.objects.create(
                first_name=vd["first_name"],
                last_name=vd["last_name"],
                email=email,
                password=pw_hash,
                role_in_company=vd.get("role_in_company") or "",
            )

        temp.generate_verification_code()
        temp.save()

        html_message = render_to_string(
            "emails/academy_verification_code.html",
            {
                "verification_code": temp.verification_code,
                "logo_url": getattr(settings, "BRENEO_LOGO_URL", ""),
            },
        )
        text_message = render_to_string(
            "emails/academy_verification_code.txt",
            {
                "verification_code": temp.verification_code,
            },
        )

        success, error = send_email_safely(
            subject="Your Employer Verification Code",
            text_message=text_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_email=email,
        )

        if not success:
            return Response(
                {
                    "message": "Verification code created. Email delivery may be delayed.",
                    "error": "Email sending failed",
                },
                status=status.HTTP_202_ACCEPTED,
            )

        return Response({"message": "Verification code sent to your email."}, status=200)


class TemporaryEmployerVerifyView(APIView):
    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")

        if not email or not code:
            return Response({"error": "Email and code are required"}, status=400)

        try:
            temp = TemporaryEmployer.objects.get(email=email)
        except TemporaryEmployer.DoesNotExist:
            return Response({"error": "Temporary employer not found"}, status=404)

        if temp.verification_code != code:
            return Response({"error": "Invalid verification code"}, status=400)

        if temp.code_expires_at < timezone.now():
            temp.delete()
            return Response({"error": "Verification code expired"}, status=400)

        if User.objects.filter(email=email).exists():
            temp.delete()
            return Response({"error": "An account with this email already exists"}, status=400)

        user = User.objects.create(
            username=temp.email,
            email=temp.email,
            password=temp.password,
            first_name=temp.first_name,
            last_name=temp.last_name,
            is_active=True,
        )

        Employer.objects.create(
            user=user,
            role_in_company=temp.role_in_company or "",
            is_verified=True,
        )

        temp.delete()

        return Response({"message": "Employer registered successfully!"}, status=201)


class EmployerChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employer = Employer.objects.filter(user=request.user).first()
        if not employer:
            return Response({"error": "Employer not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = EmployerChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()

        if employer.user and employer.user.email:
            html_message = render_to_string(
                "emails/password_changed.html",
                {
                    "first_name": employer.user.first_name
                    or employer.user.username,
                    "changed_at": timezone.now().strftime("%B %d, %Y at %I:%M %p"),
                    "logo_url": getattr(settings, "BRENEO_LOGO_URL", ""),
                },
            )
            text_message = render_to_string(
                "emails/password_changed.txt",
                {
                    "first_name": employer.user.first_name
                    or employer.user.username,
                    "changed_at": timezone.now().strftime("%B %d, %Y at %I:%M %p"),
                },
            )
            send_email_safely(
                subject="Password Changed Successfully",
                text_message=text_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to_email=employer.user.email,
            )

        return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)


# --------------------------
# Token View
# --------------------------
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class SafeTokenRefreshView(TokenRefreshView):
    """Return 401 when refresh token references a deleted user instead of 500."""

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except get_user_model().DoesNotExist:
            return Response(
                {"detail": "User no longer exists. Please log in again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class AcademyLoginView(APIView):
    def post(self, request):
        identifier = request.data.get("email")  
        password = request.data.get("password")

        if not identifier or not password:
            return Response(
                {"error": "Email (or Name) and password are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        
        academy = (
            Academy.objects.filter(user__email__iexact=identifier).first()
            or Academy.objects.filter(user__first_name__iexact=identifier).first()
        )

        if not academy:
            return Response(
                {"error": "Academy not found"},
                status=status.HTTP_404_NOT_FOUND
            )

       
        if not check_password(password, academy.password):
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_400_BAD_REQUEST
            )

        refresh = RefreshToken.for_user(academy.user)
        access = refresh.access_token

        access["academy_email"] = academy.email
        access["academy_name"] = academy.name

        return Response({
            "message": "Academy login successful",
            "access": str(access),
            "refresh": str(refresh),
            "academy": {
                "name": academy.name,
                "email": academy.email,
                "phone_number": academy.phone_number,
                "website": academy.website,
                "description": academy.description,
            }
        }, status=status.HTTP_200_OK)


# --------------------------
# Academy Registration
# --------------------------


class TemporaryAcademyRegisterView(generics.CreateAPIView):
    queryset = TemporaryAcademy.objects.all()
    serializer_class = TemporaryAcademyRegisterSerializer

    def post(self, request):
        email = request.data.get("email")
        temp_academy = TemporaryAcademy.objects.filter(email=email).first()

        if temp_academy:
            temp_academy.name = request.data.get("name")
            temp_academy.password = make_password(request.data.get("password"))
            temp_academy.phone_number = request.data.get("phone_number")
            temp_academy.description = request.data.get("description")
            temp_academy.website = request.data.get("website")
        else:
            temp_academy = TemporaryAcademy.objects.create(
                name=request.data.get("name"),
                email=email,
                password=make_password(request.data.get("password")),
                phone_number=request.data.get("phone_number"),
                description=request.data.get("description"),
                website=request.data.get("website"),
            )

        temp_academy.generate_verification_code()
        temp_academy.save()

        # Render email templates
        html_message = render_to_string('emails/academy_verification_code.html', {
            'verification_code': temp_academy.verification_code,
            'logo_url': getattr(settings, 'BRENEO_LOGO_URL', ''),
        })
        text_message = render_to_string('emails/academy_verification_code.txt', {
            'verification_code': temp_academy.verification_code,
        })

        # Send email with HTML template
        success, error = send_email_safely(
            subject="Your Academy Verification Code",
            text_message=text_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_email=email
        )
        
        if not success:
            return Response({
                "message": "Verification code created. Email delivery may be delayed.",
                "error": "Email sending failed"
            }, status=status.HTTP_202_ACCEPTED)

        return Response({"message": "Verification code sent to your email."}, status=200)


class TemporaryAcademyVerifyView(APIView):
    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")

        if not email or not code:
            return Response({"error": "Email and code are required"}, status=400)

        try:
            temp_academy = TemporaryAcademy.objects.get(email=email)
        except TemporaryAcademy.DoesNotExist:
            return Response({"error": "Temporary academy not found"}, status=404)

        if temp_academy.verification_code != code:
            return Response({"error": "Invalid verification code"}, status=400)

        if temp_academy.code_expires_at < timezone.now():
            temp_academy.delete()
            return Response({"error": "Verification code expired"}, status=400)

        # აქ ვამოწმებთ უნიკალურობას
        if User.objects.filter(email=email).exists():
            temp_academy.delete()
            return Response({"error": "An academy with this email already exists"}, status=400)

        user = User.objects.create(
            username=temp_academy.email,
            email=temp_academy.email,
            password=temp_academy.password,
            first_name=temp_academy.name,
            last_name="",
            is_active=True,
        )

        academy = Academy.objects.create(
            user=user,
            password=temp_academy.password,
            phone_number=temp_academy.phone_number or "",
            description=temp_academy.description or "No description provided",
            website=temp_academy.website,
            is_verified=True,
        )

        temp_academy.delete()

        return Response({"message": "Academy registered successfully!"}, status=201)




# --------------------------
# Password Recovery
# --------------------------


class PasswordResetRequestView(APIView):
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User with this email does not exist"}, status=400)

        code = f"{randint(100000, 999999)}"
        PasswordResetCode.objects.create(user=user, code=code)

        # Render email templates
        html_message = render_to_string('emails/password_reset.html', {
            'reset_code': code,
            'logo_url': getattr(settings, 'BRENEO_LOGO_URL', ''),
        })
        text_message = render_to_string('emails/password_reset.txt', {
            'reset_code': code,
        })

        # Send email with HTML template
        success, error = send_email_safely(
            subject="Password Reset Code",
            text_message=text_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_email=email
        )
        
        if not success:
            return Response({
                "message": "Password reset code created. Email delivery may be delayed.",
                "error": "Email sending failed"
            }, status=status.HTTP_202_ACCEPTED)

        return Response({"message": "Password reset code sent to email"})

class PasswordResetVerifyView(APIView):
    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        try:
            reset_code = PasswordResetCode.objects.get(user=user, code=code)
        except PasswordResetCode.DoesNotExist:
            return Response({"error": "Invalid code"}, status=400)

        if reset_code.is_expired():
            return Response({"error": "Code expired"}, status=400)

        return Response({"message": "Code verified"})

class SetNewPasswordView(APIView):
    def post(self, request):
        serializer = SetNewPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        new_password = serializer.validated_data['new_password']

        try:
            user = User.objects.get(email=email)
            reset_code = PasswordResetCode.objects.filter(user=user, code=code).last()
            if not reset_code or reset_code.is_expired():
                return Response({"error": "Invalid or expired code"}, status=400)
        except User.DoesNotExist:
            return Response({"error": "Invalid email"}, status=400)

        user.set_password(new_password)
        user.save()
        return Response({"message": "Password updated successfully"})








#----------- User Change Password ----------------



class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user

        if not user.check_password(serializer.validated_data['old_password']):
            return Response({"error": "Old password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data['new_password'])
        user.save()

        # Send password changed confirmation email
        if user.email:
            html_message = render_to_string('emails/password_changed.html', {
                'first_name': user.first_name or user.username,
                'changed_at': timezone.now().strftime('%B %d, %Y at %I:%M %p'),
                'logo_url': getattr(settings, 'BRENEO_LOGO_URL', ''),
            })
            text_message = render_to_string('emails/password_changed.txt', {
                'first_name': user.first_name or user.username,
                'changed_at': timezone.now().strftime('%B %d, %Y at %I:%M %p'),
            })

            send_email_safely(
                subject="Password Changed Successfully",
                text_message=text_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to_email=user.email
            )

        return Response({"message": "Password changed successfully"})
    


#----------------- Academy Change Password ---------------



class AcademyChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AcademyChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            academy = request.user
            academy.password = make_password(serializer.validated_data['new_password'])
            academy.save()

            # Send password changed confirmation email
            if hasattr(academy, 'user') and academy.user and academy.user.email:
                html_message = render_to_string('emails/password_changed.html', {
                    'first_name': academy.user.first_name or academy.name or academy.user.username,
                    'changed_at': timezone.now().strftime('%B %d, %Y at %I:%M %p'),
                    'logo_url': getattr(settings, 'BRENEO_LOGO_URL', ''),
                })
                text_message = render_to_string('emails/password_changed.txt', {
                    'first_name': academy.user.first_name or academy.name or academy.user.username,
                    'changed_at': timezone.now().strftime('%B %d, %Y at %I:%M %p'),
                })

                send_email_safely(
                    subject="Password Changed Successfully",
                    text_message=text_message,
                    html_message=html_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to_email=academy.user.email
                )

            return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




# ----------------- Public user profile (no auth) ------------------


EMPTY_PUBLIC_SOCIAL_LINKS = {
    "github": None,
    "linkedin": None,
    "facebook": None,
    "instagram": None,
    "dribbble": None,
    "behance": None,
}


class ReadOnlyPublicAPIView(APIView):
    """GET-only, unauthenticated reads. Rejects POST/PUT/PATCH/DELETE with 405."""
    permission_classes = [permissions.AllowAny]
    http_method_names = ["get", "head", "options"]


def _absolute_profile_image_url(request, profile):
    if not profile or not profile.profile_image:
        return None
    try:
        return request.build_absolute_uri(profile.profile_image.url)
    except Exception:
        return None


def _get_regular_user_or_none(user_id):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return None
    if Academy.objects.filter(user=user).exists():
        return None
    if Employer.objects.filter(user=user).exists():
        return None
    return user


def _build_public_user_profile_payload(user, request):
    """Read-only aggregate; never creates or mutates profile rows."""
    profile = UserProfile.objects.filter(user=user).first()
    social_links = SocialLinks.objects.filter(user=user).first()

    educations = Education.objects.filter(user=user).order_by("-start_date")
    work_experiences = WorkExperience.objects.filter(user=user).order_by("-start_date")
    user_skills = UserSkill.objects.filter(user=user).select_related("skill").order_by("-created_at")

    try:
        industry_profile = UserIndustryProfile.objects.get(user=user)
        industry_data = {
            "industry_years_json": industry_profile.industry_years_json,
            "updated_at": industry_profile.updated_at.isoformat(),
        }
    except UserIndustryProfile.DoesNotExist:
        industry_data = {
            "industry_years_json": {},
            "updated_at": None,
        }

    last_result = SkillTestResult.objects.filter(user=user).order_by("-created_at").first()

    return {
        "id": user.id,
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "email": user.email,
        "phone_number": (profile.phone_number if profile else None) or "",
        "country_region": (getattr(profile, "country_region", "") if profile else "") or "",
        "city": (getattr(profile, "city", "") if profile else "") or "",
        "about_me": (profile.about_me if profile else None) or "",
        "profile_image": _absolute_profile_image_url(request, profile),
        "social_links": (
            PublicSocialLinksSerializer(social_links).data
            if social_links
            else EMPTY_PUBLIC_SOCIAL_LINKS
        ),
        "educations": EducationSerializer(educations, many=True).data,
        "work_experiences": WorkExperienceSerializer(work_experiences, many=True).data,
        "skills": UserSkillResponseSerializer(user_skills, many=True).data,
        "industry_profile": industry_data,
        "career": {
            "final_role": last_result.final_role if last_result else None,
            "total_score": last_result.total_score if last_result else None,
            "skills_json": last_result.skills_json if last_result else {},
        },
    }


class PublicUserProfileView(ReadOnlyPublicAPIView):
    """
    GET /api/users/<user_id>/profile/
    Full public profile for a regular user (no JWT required). Read-only.
    """

    def get(self, request, user_id):
        user = _get_regular_user_or_none(user_id)
        if user is None:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(_build_public_user_profile_payload(user, request))


# -----------------User Detail View ------------------


class UserProfileDetailView(ReadOnlyPublicAPIView):
    def get(self, request, user_id):
        try:
            profile = UserProfile.objects.get(id=user_id)
        except UserProfile.DoesNotExist:
            return Response({"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND)
        # User profiles are only for regular users, not academies or employers
        if Academy.objects.filter(user=profile.user).exists():
            return Response({"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND)
        if Employer.objects.filter(user=profile.user).exists():
            return Response({"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND)

        saved_courses = SavedCourse.objects.filter(user=profile.user).values_list("course__title", flat=True)
        saved_jobs = SavedJob.objects.filter(user=profile.user).values_list("job__title", flat=True)

        serializer = UserProfileSerializer(profile, context={"request": request})

        social_links = SocialLinks.objects.filter(user=profile.user).first()
        social_data = (
            PublicSocialLinksSerializer(social_links).data
            if social_links
            else EMPTY_PUBLIC_SOCIAL_LINKS
        )

        last_result = SkillTestResult.objects.filter(user=profile.user).order_by('-created_at').first()
        final_role = last_result.final_role if last_result else None
        skills_json = last_result.skills_json if last_result else {}

        user_skills = UserSkill.objects.filter(user=profile.user)

       
        user_missing_skills = []
        for job in Job.objects.all():
            match_data = calculate_match(user_skills, job)
            missing = match_data.get("missing_skills", [])
            user_missing_skills.extend(missing)

        
        user_missing_skills = list(set(user_missing_skills))
        

        
        courses_set = set()
        for job in Job.objects.all():
            match_data = calculate_match(user_skills, job)
            missing = match_data.get("missing_skills", [])
            courses = Course.objects.filter(skills_taught__name__in=missing).values_list("title", flat=True)
            courses_set.update(courses)

        recommended_courses = list(courses_set)

        recommended_jobs = []
        if final_role:
            jobs_qs = Job.objects.filter(title__icontains=final_role)
            for job in jobs_qs:
                recommended_jobs.append({
                    "id": job.id,
                    "title": job.title,
                    "description": job.description,
                    "salary_range": f"${job.salary_min:,} - ${job.salary_max:,}",
                    "time_to_ready": job.time_to_ready,
                })

        return Response({
            "profile_type": "user",
            "profile_data": serializer.data,
            "final_role": final_role,
            "recommended_courses": recommended_courses,
            "recommended_jobs": recommended_jobs,
            "saved_courses": list(saved_courses),
            "saved_jobs": list(saved_jobs),
            "social_links": social_data,
            "missing_skills": user_missing_skills,
        }, status=status.HTTP_200_OK)




# ----------------- Academy Detail View ------------------

class AcademyDetailView(ReadOnlyPublicAPIView):
    def get(self, request, academy_id):
        try:
            academy = Academy.objects.get(id=academy_id)
        except Academy.DoesNotExist:
            return Response({"error": "Academy not found"}, status=status.HTTP_404_NOT_FOUND)

       
        serializer = AcademyDetailSerializer(academy, context={"request": request})

        social_links = SocialLinks.objects.filter(academy=academy).first()
        social_data = (
            PublicSocialLinksSerializer(social_links).data
            if social_links
            else EMPTY_PUBLIC_SOCIAL_LINKS
        )

        
        academy_courses = Course.objects.filter(academy=academy)
        courses_list = list(academy_courses.values_list("title", flat=True))

        
        saved_courses = SavedCourse.objects.filter(academy=academy).values_list("course__title", flat=True)
        saved_jobs = SavedJob.objects.filter(academy=academy).values_list("job__title", flat=True)

        
        return Response({
            "profile_type": "academy",
            "profile_data": serializer.data,
            "recommended_courses": courses_list,   
            "recommended_jobs": [],                
            "saved_courses": list(saved_courses),
            "saved_jobs": list(saved_jobs),
            "social_links": social_data,
            "missing_skills": []                  
        }, status=status.HTTP_200_OK)



#-----------------Save Course/Job to User/Academy Profile ------------------

# ============================
#   USER TOGGLE SAVE COURSE
# ============================
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def toggle_save_course(request, course_id):
    user = request.user

    # Clean string ID (remove quotes)
    course_id = str(course_id).replace('"', '').replace("'", "")

    course_data = request.data

    course, _ = Course.objects.get_or_create(
        id=course_id,
        defaults={
            "title": course_data.get("title", "Unknown Course"),
        }
    )

    saved, created = SavedCourse.objects.get_or_create(
        user=user,
        course=course
    )

    if not created:
        saved.delete()
        return Response({"message": "Course removed from saved list.", "saved": False})

    return Response({"message": "Course saved successfully.", "saved": True})




# ============================
#   USER TOGGLE SAVE JOB
# ============================
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def toggle_save_job(request, job_id):
    user = request.user

    job_id = str(job_id).replace('"', '').replace("'", "")

    job_data = request.data

    job, _ = Job.objects.get_or_create(
        id=job_id,
        defaults={
            "title": job_data.get("title", "Unknown Job"),
            "description": job_data.get("description", ""),
            "salary_min": job_data.get("salary_min", 0),
            "salary_max": job_data.get("salary_max", 0),
            "time_to_ready": job_data.get("time_to_ready", ""),
        }
    )

    saved, created = SavedJob.objects.get_or_create(
        user=user,
        job=job
    )

    if not created:
        saved.delete()
        return Response({"message": "Job removed from saved list.", "saved": False})

    return Response({"message": "Job saved successfully.", "saved": True})


# ============================
#   ACADEMY TOGGLE SAVE COURSE
# ============================
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def toggle_save_course_academy(request, course_id):
    academy = Academy.objects.filter(user=request.user).first()
    if not academy:
        return Response({"error": "Academy not found"}, status=404)

    course_id = str(course_id).replace('"', '').replace("'", "")

    course_data = request.data

    course, _ = Course.objects.get_or_create(
        id=course_id,
        defaults={
            "title": course_data.get("title", "Unknown Course"),
        }
    )

    saved, created = SavedCourse.objects.get_or_create(
        academy=academy,
        course=course
    )

    if not created:
        saved.delete()
        return Response({"message": "Course removed from academy list.", "saved": False})

    return Response({"message": "Course saved to academy.", "saved": True})


# ============================
#   ACADEMY TOGGLE SAVE JOB
# ============================
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def toggle_save_job_academy(request, job_id):
    academy = Academy.objects.filter(user=request.user).first()
    if not academy:
        return Response({"error": "Academy not found"}, status=404)

    job_id = str(job_id).replace('"', '').replace("'", "")

    job_data = request.data

    job, _ = Job.objects.get_or_create(
        id=job_id,
        defaults={
            "title": job_data.get("title", "Unknown Job"),
            "description": job_data.get("description", ""),
            "salary_min": job_data.get("salary_min", 0),
            "salary_max": job_data.get("salary_max", 0),
            "time_to_ready": job_data.get("time_to_ready", ""),
        }
    )

    saved, created = SavedJob.objects.get_or_create(
        academy=academy,
        job=job
    )

    if not created:
        saved.delete()
        return Response({"message": "Job removed from academy list.", "saved": False})

    return Response({"message": "Job saved to academy profile.", "saved": True})





# ------------------ Bog Token Fetch ------------------

import base64, requests, json
from django.conf import settings

def get_bog_token():
    auth_string = f"{settings.BOG_CLIENT_ID}:{settings.BOG_CLIENT_SECRET}"
    b64 = base64.b64encode(auth_string.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {"grant_type": "client_credentials"}

    res = requests.post(settings.BOG_TOKEN_URL, headers=headers, data=data)

    if res.status_code != 200:
        logger.error(f"BOG TOKEN ERROR - Status: {res.status_code}")
        logger.error(f"BOG TOKEN ERROR - Response: {res.text}")
        logger.error(f"BOG TOKEN ERROR - URL: {settings.BOG_TOKEN_URL}")
        logger.error(f"BOG TOKEN ERROR - Client ID: {settings.BOG_CLIENT_ID}")
        return None

    return res.json().get("access_token")




# ------------------ Create Bog Order ------------------

class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = get_bog_token()
        if not token:
            return Response({"error": "Token error"}, status=400)

        # Get plan_id from request
        plan_id = request.data.get("plan_id")
        
        if not plan_id:
            return Response({"error": "plan_id is required"}, status=400)
        
        # Fetch the subscription plan for this account type only
        audience = _subscription_audience_for_user(request.user)
        try:
            plan = SubscriptionPlan.objects.get(
                id=plan_id,
                is_active=True,
                audience=audience,
            )
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {"error": "Invalid or inactive subscription plan for your account type"},
                status=404,
            )
        
        amount = float(plan.price)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept-Language": "ka",
        }

        # Use settings.BOG_CALLBACK_URL instead of hardcoded URL
        callback_url = getattr(settings, "BOG_CALLBACK_URL", "https://web-production-80ed8.up.railway.app/api/bog/callback/")

        payload = {
            "callback_url": callback_url,
            "external_order_id": f"user-{request.user.id}-{int(time.time())}",
            "purchase_units": {
                "currency": "GEL",
                "total_amount": amount,
                "basket": [
                    {
                        "quantity": 1,
                        "unit_price": amount,
                        "product_id": f"subscription_plan_{plan.id}"
                    }
                ]
            },
            "intent": "RECURRING",
            "redirect_urls": {
                "success": f"https://dashboard.breneo.app/success?plan_id={plan.id}",
                "fail": "https://dashboard.breneo.app/failure",
            }
        }

        try:
            res = requests.post(settings.BOG_ORDER_URL, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
            order_id = data["id"]

            # Create/update a pending subscription only. Paid access must wait for
            # BOG callback with order_status=completed — never activate here.
            existing = UserSubscription.objects.filter(user=request.user).first()
            if existing:
                if not existing.is_active:
                    existing.plan = plan
                    existing.parent_order_id = order_id
                    existing.next_payment_date = None
                    existing.save(update_fields=["plan", "parent_order_id", "next_payment_date"])
            else:
                UserSubscription.objects.create(
                    user=request.user,
                    plan=plan,
                    parent_order_id=order_id,
                    is_active=False,
                    next_payment_date=None,
                )

            return Response({
                "redirect_url": data["_links"]["redirect"]["href"],
                "order_id": order_id
            })
        except requests.exceptions.HTTPError as e:
            # Log the full response for debugging
            logger.error(f"BOG Create Order HTTP Error: {str(e)}")
            logger.error(f"BOG Response Status: {e.response.status_code}")
            logger.error(f"BOG Response Body: {e.response.text}")
            return Response({
                "error": "Failed to create BOG order",
                "details": e.response.text if hasattr(e, 'response') else str(e)
            }, status=500)
        except Exception as e:
            logger.error(f"BOG Create Order Error: {str(e)}")
            return Response({"error": f"Failed to create BOG order: {str(e)}"}, status=500)



# ------------------Save Card for Future Payments ------------------
import json
import uuid
from datetime import timedelta
from .models import UserSubscription

class SaveCardView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        token = get_bog_token()
        if not token:
            return Response({"error": "Token error"}, status=400)

        # Get plan_id from request
        plan_id = request.data.get("plan_id")
        plan = None
        
        if plan_id:
            try:
                audience = _subscription_audience_for_user(request.user)
                plan = SubscriptionPlan.objects.get(
                    id=plan_id,
                    is_active=True,
                    audience=audience,
                )
            except SubscriptionPlan.DoesNotExist:
                return Response({"error": "Invalid subscription plan for your account type"}, status=404)

        # Clean string ID (remove quotes/spaces)
        order_id = str(order_id).strip().replace('"', '').replace("'", "")
        
        # Try BOG endpoints for saving card
        # 1. First try /cards endpoint (Standard Save Card)
        # 2. Then try /subscription endpoint (Recurring Payment Activation)
        endpoints = ["cards", "subscription"] 
        last_error_details = ""
        success = False
        data = {}

        # Base URL construction - ensure strict /payments/v1/orders/ structure
        base_url = settings.BOG_ORDER_URL.replace("/ecommerce/orders", "/orders")
        if "api.bog.ge" in base_url and "/orders" not in base_url:
                base_url = "https://api.bog.ge/payments/v1/orders"

        for endpoint in endpoints:
            # Each request needs a unique Idempotency-Key
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Idempotency-Key": str(uuid.uuid4())
            }

            url = f"{base_url}/{order_id}/{endpoint}"
            logger.info(f"Attempting BOG Save Card: {url}")
            logger.info(f"Headers: {headers}")
            
            try:
                # BOG docs show PUT with NO body. 
                # However, for 'cards' endpoint specifically, we might need a body or different method if PUT fails.
                # We stick to PUT with empty JSON as per recent testing.
                res = requests.put(url, headers=headers, json={})
                
                logger.info(f"BOG Save Card Response ({endpoint}): {res.status_code} - {res.text}")

                if res.status_code in [200, 202, 201]:
                    try:
                        data = res.json()
                    except:
                        data = {}
                    success = True
                    logger.info(f"BOG Save Card Success: {endpoint} ({res.status_code})")
                    break
                else:
                    logger.warning(f"BOG Error {res.status_code} ({endpoint}): {res.text}")
                    last_error_details = res.text
                    
                    # If /cards fails with 400 or 404, we continue to try /subscription
                    # which is specifically for recurring payments.
            except Exception as e:
                logger.error(f"BOG Request failed ({endpoint}): {str(e)}")
                last_error_details = str(e)

        if not success:
            return Response({
                "error": "Failed to save card with BOG",
                "details": f"All endpoints failed. Last error: {last_error_details}"
            }, status=500)

        parent_order_id = data.get("parent_order_id") or order_id

        if not parent_order_id:
            return Response({"error": "No parent_order_id returned"}, status=400)

        # Store card/order linkage only. Never activate — payment confirmation
        # happens exclusively in BOGCallbackView when order_status is completed.
        existing = UserSubscription.objects.filter(user=request.user).first()
        if existing and existing.is_active:
            # Keep current paid access; only refresh recurring identifiers.
            update_fields = {"parent_order_id": parent_order_id}
            if plan:
                update_fields["plan"] = plan
            for field, value in update_fields.items():
                setattr(existing, field, value)
            existing.save(update_fields=list(update_fields.keys()))
        else:
            UserSubscription.objects.update_or_create(
                user=request.user,
                defaults={
                    "parent_order_id": parent_order_id,
                    "plan": plan or (existing.plan if existing else None),
                    "is_active": False,
                    "next_payment_date": None,
                }
            )

        return Response({
            "message": "Card saved for automatic payments", 
            "parent_order_id": parent_order_id
        })

class UserSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub = UserSubscription.objects.filter(user=request.user, is_active=True).first()
        if not sub:
            return Response({"is_active": False})
        
        # Fetch card details on-demand from BOG
        token = get_bog_token()
        card_mask = "N/A"
        card_type = "Card"
        
        if token and sub.parent_order_id:
            try:
                # GET /payments/v1/orders/{order_id}
                res = requests.get(f"{settings.BOG_ORDER_URL}/{sub.parent_order_id}", headers={
                    "Authorization": f"Bearer {token}"
                })
                if res.status_code == 200:
                    data = res.json()
                    detail = data.get("payment_detail", {})
                    card_mask = detail.get("payer_identifier", "N/A")
                    card_type = detail.get("card_type", "Card")
            except Exception as e:
                logger.error(f"Error fetching card details from BOG: {str(e)}")

        return Response({
            "is_active": sub.is_active,
            "plan_name": sub.plan.name if sub.plan else "N/A",
            "next_payment_date": sub.next_payment_date,
            "card_mask": card_mask,
            "card_type": card_type,
        })




# ------------------Automatic charge using saved card ------------------

def perform_automatic_charge(subscription):
    """
    Helper function to perform an automatic charge for a given subscription.
    Returns (success, data_or_error_message)
    """
    token = get_bog_token()
    if not token:
        return False, "Token error"

    # Get the subscription plan price
    if not subscription.plan:
        return False, "No subscription plan associated with this subscription"
    
    amount = float(subscription.plan.price)

    # BOG Offline Charge Endpoint: POST /ecommerce/orders/{parent_order_id}/subscribe
    base_url = settings.BOG_ORDER_URL.replace("/orders", "/ecommerce/orders")
    url = f"{base_url}/{subscription.parent_order_id}/subscribe"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    callback_url = getattr(settings, "BOG_CALLBACK_URL", "https://web-production-80ed8.up.railway.app/api/bog/callback/")

    payload = {
        "callback_url": callback_url,
        "purchase_units": {
            "total_amount": amount,
            "basket": [
                {
                    "quantity": 1,
                    "unit_price": amount,
                    "product_id": f"subscription_plan_{subscription.plan.id}"
                }
            ]
        }
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()
        return True, data
    except Exception as e:
        error_msg = f"BOG Automatic Charge Error: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

class AutomaticChargeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sub = UserSubscription.objects.filter(user=request.user, is_active=True).first()
        if not sub:
            return Response({"error": "No active subscription"}, status=404)

        success, result = perform_automatic_charge(sub)
        if success:
            # Record in Payment History
            PaymentHistory.objects.create(
                user=request.user,
                subscription=sub,
                order_id=result.get("id"),
                amount=sub.plan.price,
                status="completed",
                description=f"Automatic renewal for {sub.plan.name}"
            )
            return Response({"next_payment_order_id": result["id"]})
        else:
            # Record failure if possible
            PaymentHistory.objects.create(
                user=request.user,
                subscription=sub,
                order_id=f"fail-{timezone.now().timestamp()}",
                amount=sub.plan.price if sub.plan else 0,
                status="failed",
                description=f"Automatic renewal failed: {result}"
            )
            return Response({"error": result}, status=500)


class PaymentHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        history = PaymentHistory.objects.filter(user=request.user).order_by('-created_at')
        data = []
        for h in history:
            data.append({
                "id": h.id,
                "order_id": h.order_id,
                "amount": str(h.amount),
                "currency": h.currency,
                "status": h.status,
                "payment_method": h.payment_method,
                "card_mask": h.card_mask,
                "description": h.description,
                "date": h.created_at.isoformat(),
            })
        return Response(data)


# ------------------ BOG Callback Handler ------------------
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
import base64

class BOGCallbackView(APIView):
    authentication_classes = []
    permission_classes = []

    def verify_signature(self, request):
        signature_b64 = request.headers.get("Callback-Signature")
        if not signature_b64:
            return False

        public_key_str = getattr(settings, "BOG_CALLBACK_SECRET_PUBLIC_KEY", None)
        if not public_key_str:
            logger.warning("BOG_CALLBACK_SECRET_PUBLIC_KEY not configured. Skipping verification.")
            return True # Or False, depending on how strict we want to be during setup

        if "-----BEGIN PUBLIC KEY-----" not in public_key_str:
            # Wrap in PEM headers if missing
            clean_key = public_key_str.replace(" ", "").replace("\n", "").replace("\r", "")
            # Split into 64-character lines
            lines = [clean_key[i:i+64] for i in range(0, len(clean_key), 64)]
            public_key_str = "-----BEGIN PUBLIC KEY-----\n" + "\n".join(lines) + "\n-----END PUBLIC KEY-----"

        try:
            public_key = load_pem_public_key(public_key_str.encode())
            signature = base64.b64decode(signature_b64)
            # Documentation says: "Verification must happen before payload deserialization"
            # We use request.body (raw bytes) for verification
            public_key.verify(
                signature,
                request.body,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            return True
        except Exception as e:
            logger.error(f"BOG Callback Signature Verification Failed: {str(e)}")
            return False

    def post(self, request):
        if not self.verify_signature(request):
            return Response({"error": "Invalid signature"}, status=401)

        body = request.data
        logger.info(f"BOG Callback received: {json.dumps(body)}")

        order_status = body.get("order_status", {}).get("key")
        payment_detail = body.get("payment_detail", {})
        parent_order_id = payment_detail.get("parent_order_id")
        actual_order_id = body.get("id")
        external_order_id = body.get("external_order_id")

        def resolve_plan_from_body():
            """Parse plan id from basket product_id like subscription_plan_{id}."""
            try:
                basket = (
                    body.get("purchase_units", {}).get("basket")
                    or body.get("basket")
                    or []
                )
                for item in basket:
                    product_id = str(item.get("product_id", ""))
                    if product_id.startswith("subscription_plan_"):
                        plan_id = int(product_id.replace("subscription_plan_", "", 1))
                        return SubscriptionPlan.objects.filter(id=plan_id).first()
            except Exception as e:
                logger.error(f"Failed to resolve plan from callback body: {str(e)}")
            return None

        def resolve_user_from_external_order():
            if not external_order_id or "user-" not in str(external_order_id):
                return None
            try:
                parts = str(external_order_id).split("-")
                if len(parts) >= 2:
                    return User.objects.get(id=parts[1])
            except Exception as e:
                logger.error(f"Failed to resolve user from external_order_id: {str(e)}")
            return None

        # Try to find subscription by parent_order_id (Recurring) or current order id
        sub = None
        if parent_order_id:
            sub = UserSubscription.objects.filter(parent_order_id=parent_order_id).first()
        if not sub and actual_order_id:
            sub = UserSubscription.objects.filter(parent_order_id=actual_order_id).first()

        # Initial payment: find (or create) via external_order_id
        if not sub:
            user = resolve_user_from_external_order()
            if user:
                sub = UserSubscription.objects.filter(user=user).first()
                if not sub and order_status == "completed":
                    plan = resolve_plan_from_body()
                    sub = UserSubscription.objects.create(
                        user=user,
                        plan=plan,
                        parent_order_id=actual_order_id or parent_order_id,
                        is_active=False,
                    )
                    logger.info(f"Created subscription from callback for user {user.id}")
                elif sub and actual_order_id:
                    # LINK for future recurring charges
                    sub.parent_order_id = actual_order_id
                    sub.save(update_fields=["parent_order_id"])
                    logger.info(f"Linked initial subscription parent_order_id: {sub.parent_order_id}")

        if order_status == "completed" and sub:
            # Activate ONLY after confirmed payment
            if not sub.plan:
                resolved_plan = resolve_plan_from_body()
                if resolved_plan:
                    sub.plan = resolved_plan

            duration_days = sub.plan.duration_days if sub.plan and sub.plan.duration_days else 30
            if actual_order_id:
                sub.parent_order_id = actual_order_id
            sub.next_payment_date = timezone.now().date() + timedelta(days=duration_days)
            sub.is_active = True

            card_mask = payment_detail.get("payer_identifier")  # e.g. 1234****5678
            card_type = payment_detail.get("card_type")

            if card_mask:
                if "***" in card_mask:
                    sub.card_mask = card_mask[-4:]
                else:
                    sub.card_mask = card_mask
            if card_type:
                sub.card_type = card_type

            sub.save()
            logger.info(f"Subscription activated for order_id: {actual_order_id}")

            PaymentHistory.objects.update_or_create(
                order_id=actual_order_id,
                defaults={
                    "user": sub.user,
                    "subscription": sub,
                    "amount": sub.plan.price if sub.plan else 0,
                    "status": "completed",
                    "card_mask": card_mask,
                    "payment_method": card_type,
                    "description": f"Payment for {sub.plan.name}" if sub.plan else "Subscription Payment"
                }
            )

        elif order_status in ["failed", "rejected"]:
            if not sub:
                if parent_order_id:
                    sub = UserSubscription.objects.filter(parent_order_id=parent_order_id).first()
                if not sub and actual_order_id:
                    sub = UserSubscription.objects.filter(parent_order_id=actual_order_id).first()
                if not sub:
                    user = resolve_user_from_external_order()
                    if user:
                        sub = UserSubscription.objects.filter(user=user).first()

            if sub:
                # Only deactivate if this failed payment matches the pending/current order
                matching_order = (
                    (parent_order_id and sub.parent_order_id == parent_order_id)
                    or (actual_order_id and sub.parent_order_id == actual_order_id)
                )
                if matching_order or not sub.is_active:
                    sub.is_active = False
                    sub.save(update_fields=["is_active"])
                    logger.warning(f"Subscription deactivated due to failed payment: {order_status}")

                PaymentHistory.objects.update_or_create(
                    order_id=actual_order_id or f"fail-{timezone.now().timestamp()}",
                    defaults={
                        "user": sub.user,
                        "subscription": sub,
                        "amount": payment_detail.get("amount", 0),
                        "status": order_status,
                        "description": f"Payment {order_status}"
                    }
                )

        return Response({"status": "ok"})


# ==================== Subscription Plans ====================

class SubscriptionPlanListView(APIView):
    """List active subscription plans for the current account type."""

    def get(self, request):
        audience = _subscription_audience_for_user(request.user)
        plans = SubscriptionPlan.objects.filter(is_active=True, audience=audience)
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response(serializer.data)

@api_view(["GET", "POST"])
@permission_classes([]) # No auth for this public check
def bog_auth_placeholder(request):
    return Response({"status": "ok"})



