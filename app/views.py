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
    TemporaryAcademy,
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
    EducationSerializer,
    WorkExperienceSerializer,
    SkillSearchSerializer,
    UserSkillAttachSerializer,
    UserSkillResponseSerializer,
    SubscriptionPlanSerializer,
)
from django.contrib.auth.models import User
import os, requests, random
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






GROQ_API_KEY = os.getenv("GROQ_API_KEY")

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

        session = AssessmentSession.objects.create(
            user=user,
            questions=[{
                "text": q.questiontext,
                "option1": q.option1,
                "option2": q.option2,
                "option3": q.option3,
                "option4": q.option4,
                "correct_option": q.correct_option,
                "skill": q.skill.strip(),
                "difficulty": q.difficulty,
                "RoleMapping": q.RoleMapping
            } for q in selected_questions],
            current_question_index=0,
            answers=[]
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

            correct_opt_num = prev_question["correct_option"]
            is_correct = (answer.strip() == prev_question[f"option{correct_opt_num}"].strip())

            prev_skill = (prev_question.get("skill") or "").strip()
            prev_role = prev_question.get("RoleMapping")
            prev_difficulty = prev_question.get("difficulty")

            # Save answer
            session.answers.append({
                "text": question_text,
                "answer": answer,
                "correct": is_correct,
                "difficulty": prev_difficulty,
                "skill": prev_skill,
                "RoleMapping": prev_role,
            })

            
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
                    skills_in_role[i] for i, s in enumerate(skills_in_role_norm) if s != prev_skill_norm
                ]
                next_skill = random.choice(available_skills) if available_skills else prev_skill

            
            answered_texts = [a["text"] for a in session.answers]
            next_qs = list(DynamicTechQuestion.objects.filter(
                RoleMapping=prev_role,
                skill=next_skill,
                difficulty=next_difficulty,
                isactive=True
            ).exclude(questiontext__in=answered_texts))

            if not next_qs:
               
                next_qs = list(DynamicTechQuestion.objects.filter(
                    RoleMapping=prev_role,
                    isactive=True
                ).exclude(questiontext__in=answered_texts))

            next_question = None
            if next_qs:
                nq = random.choice(next_qs)
                next_question = {
                    "text": nq.questiontext,
                    "option1": nq.option1,
                    "option2": nq.option2,
                    "option3": nq.option3,
                    "option4": nq.option4,
                    "correct_option": nq.correct_option,
                    "skill": nq.skill.strip(),
                    "difficulty": nq.difficulty,
                    "RoleMapping": nq.RoleMapping,
                }
                session.questions.append(next_question)

            session.current_question_index += 1
            session.save()

            return Response({
                "message": "Answer submitted",
                "correct": is_correct,
                "next_question": next_question
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

            session = AssessmentSession.objects.create(
                user=user,
                questions=[{
                    "questiontext": q.questiontext,
                    "option1": q.option1,
                    "option2": q.option2,
                    "option3": q.option3,
                    "option4": q.option4,
                    "correct_option": q.correct_option,
                    "skill": q.skill.strip(),
                    "difficulty": q.difficulty,
                    "RoleMapping": q.RoleMapping,
                    "type": "soft"
                } for q in selected_questions],
                current_question_index=0,
                answers=[]
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

            session.answers.append({"question_text": question_text, "answer": answer})
            session.current_question_index += 1
            session.save()

            if session.current_question_index >= len(session.questions):
                total_score = sum(
                    1 for q, a in zip(session.questions, session.answers)
                    if a["answer"] == q[f"option{q['correct_option']}"]
                )
                total_questions = len(session.questions)
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
                "next_question": next_question
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



def fetch_salary_from_groq(job_title: str, location: str = "global") -> str:
    """
    Ask Groq AI for an estimated salary range for a given job and location.
    Returns a clean string like '$70,000 - $120,000'
    """
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    
    prompt = (
        f"Provide a realistic yearly salary range in USD "
        f"for a {job_title} in {location} with mid-level experience. "
        f"Return ONLY the range like '$70,000 - $120,000'."
    )
    
    chat = client.chat.completions.create(
        model="llama-3.1-8b-instant", 
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    
    return chat.choices[0].message.content.strip()




# Save skill test results
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_test_results(request):
    """
    API to save skill test results.
    Expects JSON:
    {
        "final_role": "Developer",
        "obtained_score": 14,
        "total_questions": 25,
        "skills_json": { ... }
    }
    """
    data = request.data.copy()
    # ფორმატირება "14 / 25"
    obtained = data.get("obtained_score", 0)
    total = data.get("total_questions", 0)
    data["total_score"] = f"{obtained} / {total}"

    serializer = SkillTestResultSerializer(data=data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)
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
        """User profile is only for regular users, not academies."""
        if Academy.objects.filter(user=request.user).exists():
            return Response(
                {"error": "Academy accounts should use /api/academy/profile/"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

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
        if Academy.objects.filter(user=request.user).exists():
            return Response(
                {"error": "Academy accounts should use /api/academy/profile/"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

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
        if Academy.objects.filter(user=request.user).exists():
            return Response(
                {"error": "Academy accounts should use /api/academy/profile/ for social links."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

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

    def perform_create(self, serializer):
        user = self.request.user
        if Education.objects.filter(user=user).count() >= MAX_EDUCATIONS:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                {"detail": f"Maximum {MAX_EDUCATIONS} education entries allowed per user."}
            )
        serializer.save(user=user)


class WorkExperienceViewSet(viewsets.ModelViewSet):
    """CRUD for WorkExperience. Queryset filtered by request.user. Max 10 per user. Requires JWT."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WorkExperienceSerializer

    def get_queryset(self):
        return WorkExperience.objects.filter(user=self.request.user).order_by("-start_date")

    def perform_create(self, serializer):
        user = self.request.user
        if WorkExperience.objects.filter(user=user).count() >= MAX_WORK_EXPERIENCES:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                {"detail": f"Maximum {MAX_WORK_EXPERIENCES} work experience entries allowed per user."}
            )
        serializer.save(user=user)


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

    def delete(self, request, skill_id):
        deleted, _ = UserSkill.objects.filter(user=request.user, skill_id=skill_id).delete()
        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )




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




# -----------------User Detail View ------------------


class UserProfileDetailView(APIView):
    def get(self, request, user_id):
        try:
            profile = UserProfile.objects.get(id=user_id)
        except UserProfile.DoesNotExist:
            return Response({"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND)
        # User profiles are only for regular users, not academies
        if Academy.objects.filter(user=profile.user).exists():
            return Response({"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND)

        saved_courses = SavedCourse.objects.filter(user=profile.user).values_list("course__title", flat=True)
        saved_jobs = SavedJob.objects.filter(user=profile.user).values_list("job__title", flat=True)

        serializer = UserProfileSerializer(profile, context={"request": request})

        social_links, _ = SocialLinks.objects.get_or_create(user=profile.user)
        social_serializer = SocialLinksSerializer(social_links)

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
            "social_links": social_serializer.data,
            "missing_skills": user_missing_skills,
        }, status=status.HTTP_200_OK)




# ----------------- Academy Detail View ------------------

class AcademyDetailView(APIView):
    def get(self, request, academy_id):
        try:
            academy = Academy.objects.get(id=academy_id)
        except Academy.DoesNotExist:
            return Response({"error": "Academy not found"}, status=status.HTTP_404_NOT_FOUND)

       
        serializer = AcademyDetailSerializer(academy, context={"request": request})

        
        social_links, _ = SocialLinks.objects.get_or_create(academy=academy)
        social_serializer = SocialLinksSerializer(social_links)

        
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
            "social_links": social_serializer.data,
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
        
        # Fetch the subscription plan
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            return Response({"error": "Invalid or inactive subscription plan"}, status=404)
        
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
                "fail": "https://dashboard.breneo.app/fail",
            }
        }

        try:
            res = requests.post(settings.BOG_ORDER_URL, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
            return Response({
                "redirect_url": data["_links"]["redirect"]["href"],
                "order_id": data["id"]
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
                plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
            except SubscriptionPlan.DoesNotExist:
                return Response({"error": "Invalid subscription plan"}, status=404)

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

        # Save subscription info with plan (no local card data storage)
        UserSubscription.objects.update_or_create(
            user=request.user,
            defaults={
                "parent_order_id": parent_order_id,
                "plan": plan,
                "is_active": True,
                "next_payment_date": timezone.now().date() + timedelta(days=30)
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

        if not parent_order_id:
            # Might be a one-time payment or missing detail
            logger.info("BOG Callback: No parent_order_id, skipping subscription update.")
            return Response({"status": "ignored"})

        if order_status == "completed":
            sub = UserSubscription.objects.filter(parent_order_id=parent_order_id).first()
            if sub:
                sub.next_payment_date = timezone.now().date() + timedelta(days=30)
                sub.is_active = True
                sub.save()
                logger.info(f"Subscription updated for order_id: {body.get('id')}")
                
                # Record in Payment History
                PaymentHistory.objects.update_or_create(
                    order_id=body.get("id"),
                    defaults={
                        "user": sub.user,
                        "subscription": sub,
                        "amount": payment_detail.get("amount"),
                        "currency": payment_detail.get("currency", "GEL"),
                        "status": "completed",
                        "card_mask": payment_detail.get("payer_identifier"),
                        "description": f"Subscription payment: {sub.plan.name if sub.plan else 'N/A'}"
                    }
                )
            else:
                logger.warning(f"Callback success for unknown parent_order_id: {parent_order_id}")
                # Record payment history without subscription if possible (might fail if user lookup fails)
                PaymentHistory.objects.update_or_create(
                    order_id=body.get("id"),
                    defaults={
                        "amount": payment_detail.get("amount"),
                        "currency": payment_detail.get("currency", "GEL"),
                        "status": "completed",
                        "description": f"Completed payment for child order {body.get('id')}"
                    }
                )

        elif order_status in ["failed", "rejected"]:
            sub = UserSubscription.objects.filter(parent_order_id=parent_order_id).first()
            if sub:
                sub.is_active = False
                sub.save()
            
            # Record failed payment
            if sub:
                PaymentHistory.objects.update_or_create(
                    order_id=body.get("id"),
                    defaults={
                        "user": sub.user,
                        "subscription": sub,
                        "amount": payment_detail.get("amount", 0),
                        "status": order_status,
                        "description": f"Payment {order_status}"
                    }
                )
                sub.save()
                logger.warning(f"Subscription deactivated due to failed payment: {order_status}")

        return Response({"status": "ok"})


# ==================== Subscription Plans ====================

class SubscriptionPlanListView(APIView):
    """List all active subscription plans"""
    
    def get(self, request):
        plans = SubscriptionPlan.objects.filter(is_active=True)
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response(serializer.data)

@api_view(["GET", "POST"])
@permission_classes([]) # No auth for this public check
def bog_auth_placeholder(request):
    return Response({"status": "ok"})



