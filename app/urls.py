from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView
from .views import (
    home,
    DashboardProgressAPI,
    StartAssessmentAPI,
    ProgressMetricsAPI,
    SubmitAnswerAPI,
    CareerPathAPI,
    DynamictestquestionsAPI,
    finish_assessment,
    RecommendedJobsAPI,
    RecommendedCoursesAPI,
    FinishAssessmentAPI,
    CareerCategoryListAPIView,
    RandomCareerQuestionsAPI,
    DynamicSoftSkillsquestionsAPI,
    StartSoftAssessmentAPI,
    SubmitSoftAnswerAPI,
    FinishSoftAssessmentAPI,
    CareerRoadmapAPI,
    save_test_results,
    get_user_results,
    RegisterView,
    CustomTokenObtainPairView,
    SafeTokenRefreshView,
    TemporaryAcademyRegisterView,
    TemporaryAcademyVerifyView,
    VerifyCodeView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    SetNewPasswordView,
    AcademyProfileUpdateView,
    ChangePasswordView,
    AcademyChangePasswordView,
    UserProfileView,
    AcademyLoginView,
    AcademyDetailView,
    UserProfileDetailView,
    toggle_save_course,
    toggle_save_job,
    toggle_save_course_academy,
    toggle_save_job_academy,
    CreateOrderView,
    SaveCardView,
    AutomaticChargeView,
    BOGCallbackView,
    SubscriptionPlanListView,
    PersonalProfileView,
    SocialLinksMeView,
    IndustryProfileView,
    EducationViewSet,
    WorkExperienceViewSet,
    SkillSearchAPIView,
    UserSkillListAttachView,
    UserSkillDetachView,
    UserSubscriptionView,
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', home, name='home'),
    path('api/dashboard/', DashboardProgressAPI.as_view(), name='dashboard-api'),
    path('api/jobs/recommended/', RecommendedJobsAPI.as_view(), name='recommended-jobs'),
    path('api/courses/recommended/', RecommendedCoursesAPI.as_view(), name='recommended-courses'),
    path('api/start-assessment/', StartAssessmentAPI.as_view(), name='start-assessment'),
    path('api/submit-answer/', SubmitAnswerAPI.as_view(), name='submit-answer'),
    path("api/finish-assessment/", FinishAssessmentAPI.as_view(), name="finish-assessment"),
    path('api/progress/', ProgressMetricsAPI.as_view(), name='progress-metrics'),
    path('api/careerpath/', CareerPathAPI.as_view(), name='career-path'),
    path('api/techquestions/', DynamictestquestionsAPI.as_view(), name='tech_questions'),
    path("api/finish-assessment-simple/", finish_assessment, name="finish-assessment-simple"),
    path('api/career-categories/', CareerCategoryListAPIView.as_view(), name='career-categories'),
    path("api/career-questions-random/", RandomCareerQuestionsAPI.as_view(), name="career-questions-random"),

    # ---------------- Soft Skills Assessment ----------------
    path('api/softskillsquestions/', DynamicSoftSkillsquestionsAPI.as_view(), name='SoftSkills_questions'),
    path("api/soft/start/", StartSoftAssessmentAPI.as_view(), name="start-soft-assessment"),
    path("api/soft/submit/", SubmitSoftAnswerAPI.as_view(), name="submit-soft-answer"),
    path("api/soft/finish/", FinishSoftAssessmentAPI.as_view(), name="finish-soft-assessment"),
    path("api/career-roadmap/", CareerRoadmapAPI.as_view(), name="career-roadmap"),
    path('api/skilltest/save/', save_test_results, name='save_test_results'),
    path('api/skilltest/results/', get_user_results, name='get_user_results'),

    # ---------------- Authentication ----------------
    path("api/register/", RegisterView.as_view(), name="register"),
    path("api/register", RegisterView.as_view(), name="register-no-slash"),
    path("api/login/", CustomTokenObtainPairView.as_view(), name="login"),
    path("api/verify-code/", VerifyCodeView.as_view(), name="verify-code"),
    path("api/refresh/", SafeTokenRefreshView.as_view(), name="refresh"),
    path("api/academy/login/", AcademyLoginView.as_view(), name="academy-login"),
    path("api/academy/login", AcademyLoginView.as_view(), name="academy-login-no-slash"),
    path("api/academy/register/", TemporaryAcademyRegisterView.as_view(), name="academy-register"),
    path('api/verify-academy-email/', TemporaryAcademyVerifyView.as_view(),name='verify-academy-email'),

    #------------- recovery password ---------------
    path('password-reset/request/', PasswordResetRequestView.as_view()),
    path('password-reset/verify/', PasswordResetVerifyView.as_view()),
    path('password-reset/set-new/', SetNewPasswordView.as_view()),

    #-------------- Change Password ----------------
    path("api/change-password/", ChangePasswordView.as_view(), name="change-password"),   
    path('api/academy/change-password/', AcademyChangePasswordView.as_view(), name='academy-change-password'),
    
     #-------------- Profile ----------------
    path("api/profile/", UserProfileView.as_view(), name="user-profile"),
    path("api/me/profile/", PersonalProfileView.as_view(), name="personal-profile"),
    path("api/me/social-links/", SocialLinksMeView.as_view(), name="me-social-links"),
    path("api/me/industry-profile/", IndustryProfileView.as_view(), name="industry-profile"),
    path("api/academy/profile/", AcademyProfileUpdateView.as_view(), name="academy-profile"),

    # -------------- New tables API (all require JWT: Authorization: Bearer <token>) ----------------
    path("api/educations/", EducationViewSet.as_view({"get": "list", "post": "create"}), name="education-list"),
    path("api/educations/<int:pk>/", EducationViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="education-detail"),
    path("api/work-experiences/", WorkExperienceViewSet.as_view({"get": "list", "post": "create"}), name="workexperience-list"),
    path("api/work-experiences/<int:pk>/", WorkExperienceViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="workexperience-detail"),

    # Skills: search catalog; list my skills (GET) / attach (POST) at api/me/skills/; detach at api/me/skills/<id>/
    path("api/skills/", SkillSearchAPIView.as_view(), name="skill-search"),
    path("api/me/skills/", UserSkillListAttachView.as_view(), name="me-skills-list-attach"),
    path("api/me/skills/<int:skill_id>/", UserSkillDetachView.as_view(), name="me-skills-detach"),

    # -------------Details --------------
    path('api/user/<int:user_id>/', UserProfileDetailView.as_view(), name='user-public-profile'),
    path("api/academy/<int:academy_id>/", AcademyDetailView.as_view(), name="academy-detail"),

    # ----------- saved courses and jobs -----------

    path("api/save-job/<path:job_id>/", toggle_save_job),
    path("api/save-course/<path:course_id>/", toggle_save_course),
    path("api/save-job-academy/<path:job_id>/", toggle_save_job_academy),
    path("api/save-course-academy/<path:course_id>/", toggle_save_course_academy),




    # ----------- BOG Payment Integration -----------
    path("api/bog/create-order/", CreateOrderView.as_view()),
    path("api/bog/save-card/<str:order_id>/", SaveCardView.as_view()),
    path("api/bog/subscribe/", AutomaticChargeView.as_view()),
    path("api/bog/callback/", BOGCallbackView.as_view()),
    
    # ----------- Subscription Plans -----------
    path("api/subscription-plans/", SubscriptionPlanListView.as_view()),
    path("api/me/subscription/", UserSubscriptionView.as_view()),
] 


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

