from rest_framework import serializers
from .models import (
    Assessment,
    Badge,
    DynamicTechQuestion,
    CareerCategory,
    CareerQuestion,
    CareerOption,
    DynamicSoftSkillsQuestion,
    SkillTestResult,
    TemporaryAcademy,
    SocialLinks,
    Academy,
    UserProfile,
    TemporaryUser,
    Course,
    SavedCourse,
    SavedJob,
    Education,
    WorkExperience,
    Skill,
    UserSkill,
    SubscriptionPlan,
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import authenticate,get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.models import User
from .models import Academy,UserProfile,TemporaryUser
from django.contrib.auth.hashers import make_password, check_password
User = get_user_model()



# --------------------------
# Assessment & Badge
# --------------------------
class AssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assessment
        fields = ['id', 'name', 'status', 'completed_at']


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ['id', 'name', 'achieved_at']


# --------------------------
# Technical Questions
# --------------------------
class QuestionTechSerializer(serializers.ModelSerializer):
    class Meta:
        model = DynamicTechQuestion
        fields = [
            "id",
            "questionid",
            "questiontext",
            "RoleMapping",
            "skill",
            "difficulty",
            "option1",
            "option2",
            "option3",
            "option4",
            "option5",
            "correct_option",
            "isactive",
            "createdat",
            "updatedat",
        ]


# --------------------------
# Career Questions
# --------------------------
class CareerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CareerOption
        fields = ['id', 'text', 'RoleMapping']


class CareerQuestionSerializer(serializers.ModelSerializer):
    options = CareerOptionSerializer(many=True, read_only=True)

    class Meta:
        model = CareerQuestion
        fields = ['id', 'text', 'options']


class CareerCategorySerializer(serializers.ModelSerializer):
    questions = CareerQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = CareerCategory
        fields = ['id', 'code', 'title', 'questions']


# --------------------------
# Soft Skills Questions
# --------------------------
class QuestionSoftSkillsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DynamicSoftSkillsQuestion
        fields = [
            "id",
            "questionid",
            "questiontext",
            "RoleMapping",
            "skill",
            "difficulty",
            "option1",
            "option2",
            "option3",
            "option4",
            "option5",
            "correct_option",
            "isactive",
            "createdat",
            "updatedat",
        ]


class SkillTestResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillTestResult
        fields = ['id', 'user', 'final_role', 'total_score', 'skills_json', 'created_at']
        read_only_fields = ['user', 'created_at']



# ---------- User Detail ---------------------

class UserCourseMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "title"]


class UserDetailSerializer(serializers.ModelSerializer):
    courses = UserCourseMiniSerializer(many=True, read_only=True, source="user_courses")
    social_links = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()
    about_me = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "about_me",
            "profile_image_url",
            "courses",
            "social_links",
        ]

    def get_profile_image_url(self, obj):
        """აბრუნებს იუზერის პროფილის ფოტოს URL-ს."""
        profile = getattr(obj, "profile", None)
        if profile and profile.profile_image:
            try:
                request = self.context.get("request")
                return (
                    request.build_absolute_uri(profile.profile_image.url)
                    if request
                    else profile.profile_image.url
                )
            except:
                return None
        return None

    def get_social_links(self, obj):
        if hasattr(obj, "social_links"):
            return {
                "github": obj.social_links.github,
                "linkedin": obj.social_links.linkedin,
                "facebook": obj.social_links.facebook,
                "instagram": obj.social_links.instagram,
                "dribbble": obj.social_links.dribbble,
                "behance": obj.social_links.behance,
            }
        return {}

    def get_about_me(self, obj):
        profile = getattr(obj, "profile", None)
        return getattr(profile, "about_me", None)


#--------- Academy Detail ---------------------



class CourseMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "title"]

class AcademyDetailSerializer(serializers.ModelSerializer):
    courses = CourseMiniSerializer(many=True, read_only=True)
    social_links = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Academy
        fields = [
            "id",
            "name",
            "email",
            "phone_number",
            "description",
            "website",
            "profile_image_url",
            "courses",
            "social_links",
        ]

    def get_profile_image_url(self, obj):
        if obj.profile_image:
            try:
                request = self.context.get("request")
                return request.build_absolute_uri(obj.profile_image.url) if request else obj.profile_image.url
            except:
                return None
        return None

    def get_social_links(self, obj):
        if hasattr(obj, "social_links"):
            return {
                "github": obj.social_links.github,
                "linkedin": obj.social_links.linkedin,
                "facebook": obj.social_links.facebook,
                "instagram": obj.social_links.instagram,
            }
        return {}
    
# ------- User Registration ---------------------


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemporaryUser
        fields = ["first_name", "last_name", "email", "password", "phone_number"]
        extra_kwargs = {"password": {"write_only": True}}
        validators = []

    def create(self, validated_data):
        validated_data["password"] = make_password(validated_data["password"])
        temp_user = TemporaryUser.objects.create(**validated_data)
        temp_user.generate_verification_code()
        return temp_user

# --------------------------
# Academy Registration
# --------------------------
class TemporaryAcademyRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemporaryAcademy
        fields = ["name", "email", "password", "phone_number", "description", "website"]
        extra_kwargs = {"password": {"write_only": True}}
        validators = []

    def create(self, validated_data):
        validated_data["password"] = make_password(validated_data["password"])
        temp_academy = TemporaryAcademy.objects.create(**validated_data)
        temp_academy.generate_verification_code()
        return temp_academy







# --------------------------
# Token Serializer
# --------------------------

User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        identifier = attrs.get("username")
        password = attrs.get("password")

        user = None
        user = User.objects.filter(email__iexact=identifier).first()

        if not user and " " in identifier:
            first_name, last_name = identifier.split(" ", 1)
            user = User.objects.filter(
                first_name__iexact=first_name.strip(),
                last_name__iexact=last_name.strip()
            ).first()

        # ======================= USER LOGIN ==========================
        if user and user.check_password(password):
            attrs["username"] = user.email
            data = super().validate(attrs)

            refresh = self.get_token(user)
            access = refresh.access_token

            profile = getattr(user, "profile", None)
            phone_number = getattr(profile, "phone_number", None)
            profile_image_url = profile.profile_image.url if profile and profile.profile_image else None

            data.update({
                "access": str(access),
                "refresh": str(refresh),
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone_number": phone_number,
                "profile_image": profile_image_url,
                "user_type": "user"
            })
            return data

        # ====================== ACADEMY LOGIN =========================
        academy = (
            Academy.objects.filter(user__email__iexact=identifier).first()
            or Academy.objects.filter(user__first_name__iexact=identifier).first()
        )

        if academy and check_password(password, academy.password):
            refresh = RefreshToken.for_user(academy.user)
            access = refresh.access_token

            profile_image_url = getattr(academy, "profile_image", None)
            if profile_image_url and hasattr(profile_image_url, "url"):
                profile_image_url = profile_image_url.url

            return {
                "access": str(access),
                "refresh": str(refresh),
                "user_type": "academy",
                "name": academy.name,
                "email": academy.email,
                "phone_number": academy.phone_number,
                "profile_image": profile_image_url,
            }

        # ====================== INVALID LOGIN =========================
        raise AuthenticationFailed("Invalid email/full name or password.")



class VerifyCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)





class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

class SetNewPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return data









class UserProfileUpdateSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source="profile.phone_number", allow_blank=True, required=False)
    profile_image = serializers.ImageField(source="profile.profile_image", allow_null=True, required=False)
    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ["id","first_name", "last_name", "email", "phone_number", "profile_image"]
        extra_kwargs = {
            "first_name": {"required": False},
            "last_name": {"required": False},
            "email": {"required": False},
        }

    def validate_email(self, value):
        user = self.context["request"].user
        if User.objects.exclude(pk=user.pk).filter(email__iexact=value).exists():
            raise serializers.ValidationError("this mail already taken")
        return value

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})

        # update user fields
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()

        # Only create/update UserProfile for regular users, not academies
        if not Academy.objects.filter(user=instance).exists():
            profile, _ = UserProfile.objects.get_or_create(user=instance)
            if "phone_number" in profile_data:
                profile.phone_number = profile_data.get("phone_number")
            if "profile_image" in profile_data:
                profile.profile_image = profile_data.get("profile_image")
            profile.save()
        return instance


class AcademyUpdateSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(required=False, source="user.first_name")
    email = serializers.EmailField(required=False, source="user.email")

    class Meta:
        model = Academy
        fields = ["id", "name", "email", "phone_number", "description", "website", "profile_image"]
        extra_kwargs = {
            "phone_number": {"required": False},
            "description": {"required": False},
            "website": {"required": False},
            "profile_image": {"required": False, "allow_null": True},
        }

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if user_data:
            for attr, value in user_data.items():
                setattr(instance.user, attr, value)
            instance.user.save()
        return instance

    def validate_email(self, value):
        instance = getattr(self, "instance", None)
        if instance and instance.user_id:
            if User.objects.exclude(pk=instance.user_id).filter(email__iexact=value).exists():
                raise serializers.ValidationError("this mail already taken")
        elif User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("this mail already taken")
        return value





#------------ User Change Password -------------------


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return data
    


#------------ Academy Change Password -----------------



class AcademyChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return data

    def validate_old_password(self, value):
        academy = self.context['request'].user
        if not check_password(value, academy.password):
            raise serializers.ValidationError("Old password is incorrect")
        return value
    




#------------------- person information -----------------

class UserProfileSerializer(serializers.ModelSerializer):
    profile_image_url = serializers.SerializerMethodField(read_only=True)
    about_me = serializers.CharField(allow_blank=True, allow_null=True, required=False)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "phone_number",
            "country_region",
            "city",
            "profile_image",
            "profile_image_url",
            "about_me",
        ]

    def get_profile_image_url(self, obj):
        if obj.profile_image:
            try:
                return obj.profile_image.url
            except Exception:
                return None
        return None

    def get_about_me(self, obj):
        return obj.about_me or ""

    def update(self, instance, validated_data):
        instance.phone_number = validated_data.get("phone_number", instance.phone_number)
        instance.country_region = validated_data.get("country_region", instance.country_region)
        instance.city = validated_data.get("city", instance.city)
        instance.about_me = validated_data.get("about_me", instance.about_me)
        if "profile_image" in validated_data:
            instance.profile_image = validated_data["profile_image"] or None
        instance.save()
        return instance


class SocialLinksSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialLinks
        fields = "__all__"
        read_only_fields = ["user", "academy"]


# --------------------------
# Personal profile (User + UserProfile + social_links)
# --------------------------
class PersonalProfileSerializer(serializers.Serializer):
    """For GET/PUT /api/me/profile: User + UserProfile fields."""
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    country_region = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    about_me = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    profile_image = serializers.ImageField(required=False, allow_null=True)
    social_links = SocialLinksSerializer(required=False, read_only=True)


# --------------------------
# Education & WorkExperience
# --------------------------
class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = [
            "id",
            "school_name",
            "major",
            "degree_type",
            "gpa",
            "start_date",
            "end_date",
            "is_current",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, data):
        if data.get("is_current") and data.get("end_date") is not None:
            raise serializers.ValidationError(
                {"end_date": "end_date must be null when is_current is True."}
            )
        start = data.get("start_date")
        end = data.get("end_date")
        if start and end and start > end:
            raise serializers.ValidationError(
                {"end_date": "end_date must be on or after start_date."}
            )
        return data


class WorkExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkExperience
        fields = [
            "id",
            "job_title",
            "company",
            "job_type",
            "location",
            "start_date",
            "end_date",
            "is_current",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, data):
        if data.get("is_current") and data.get("end_date") is not None:
            raise serializers.ValidationError(
                {"end_date": "end_date must be null when is_current is True."}
            )
        start = data.get("start_date")
        end = data.get("end_date")
        if start and end and start > end:
            raise serializers.ValidationError(
                {"end_date": "end_date must be on or after start_date."}
            )
        return data


# --------------------------
# Skills: search + attach/detach
# --------------------------
class SkillSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name"]


class UserSkillAttachSerializer(serializers.Serializer):
    """Body: { \"name\": \"React\" } - attach existing skill or create + attach."""
    name = serializers.CharField(max_length=100)


class UserSkillResponseSerializer(serializers.ModelSerializer):
    """Attached skill with id and name for POST /api/me/skills response."""
    skill_id = serializers.IntegerField(source="skill.id")
    skill_name = serializers.CharField(source="skill.name")

    class Meta:
        model = UserSkill
        fields = ["id", "skill_id", "skill_name", "created_at"]


#---------------- Saved Courses and Jobs ----------------


class SavedJobSerializer(serializers.ModelSerializer):
    job = serializers.IntegerField(write_only=True)
    job_title = serializers.CharField(source="job.title", read_only=True)

    class Meta:
        model = SavedJob
        fields = ["id", "job", "job_title", "saved_at"]

    def create(self, validated_data):
        job_id = validated_data.pop("job")
        return SavedJob.objects.create(
            user=self.context["request"].user,
            job_id=job_id,
            **validated_data
        )



class SavedCourseSerializer(serializers.ModelSerializer):
    course = serializers.IntegerField(write_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)

    class Meta:
        model = SavedCourse
        fields = ["id", "course", "course_title", "saved_at"]

    def create(self, validated_data):
        course_id = validated_data.pop("course")
        return SavedCourse.objects.create(
            user=self.context["request"].user,
            course_id=course_id,
            **validated_data
        )


#---------------- Subscription Plans ----------------

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ["id", "name", "price", "duration_days", "description"]

