from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
from datetime import timedelta, datetime
import random
from cloudinary_storage.storage import MediaCloudinaryStorage




class Assessment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed')
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.status})"

class Badge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    achieved_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.name}"




class AssessmentSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    current_question_index = models.IntegerField(default=0)
    questions = models.JSONField(default=list)
    answers = models.JSONField(default=list)
    completed = models.BooleanField(default=False)
    final_role = models.CharField(max_length=100, null=True, blank=True)
    dont_know_per_skill = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.user.username} - Session {self.id} - Completed: {self.completed}"
    


class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class UserSkill(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_skills",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="user_skills",
    )
    points = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "skill"],
                name="unique_user_skill",
            )
        ]

class Job(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    title = models.CharField(max_length=200)
    description = models.TextField(null=False, default="No description")
    salary_min = models.IntegerField(null=False, default=0)
    salary_max = models.IntegerField(null=False, default=0)
    time_to_ready = models.CharField(max_length=50, default="Not specified")
    required_skills = models.ManyToManyField(Skill, related_name="jobs")


class Profession(models.Model):
    """
    Career profession based on skills. Populated via fetch_profession_data command.
    - market_popularity: JSON for charts e.g. [{"year": "2020", "value": 75}, ...]
    """
    title = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, default="")
    skills = models.ManyToManyField(Skill, related_name="professions", blank=True)
    market_popularity = models.JSONField(
        default=list,
        help_text='[{"year": "2020", "value": 75}, {"year": "2021", "value": 80}, ...] for charts'
    )
    relevant_courses = models.ManyToManyField(
        "Course", related_name="professions", blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class ProfessionOfUser(models.Model):
    """
    Assigns a user to a matched profession based on SkillScore (only skills with score > 0).
    match_score = percentage of the profession's skills that the user has with score > 0.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profession_assignments",
    )
    profession = models.ForeignKey(
        Profession,
        on_delete=models.CASCADE,
        related_name="user_assignments",
    )
    match_score = models.FloatField(
        default=0.0,
        help_text="Percentage (0-100) of profession skills the user has with SkillScore > 0",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "profession"],
                name="unique_user_profession",
            )
        ]
        ordering = ["-match_score"]

    def __str__(self):
        return f"{self.user.username} → {self.profession.title} ({self.match_score:.1f}%)"


class Course(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    academy = models.ForeignKey(
        'Academy', on_delete=models.CASCADE, related_name="courses", null=True, blank=True
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="user_courses", null=True, blank=True
    )
    title = models.CharField(max_length=200)
    cover_image = models.ImageField(
        storage=MediaCloudinaryStorage(),
        upload_to="course_covers/",
        blank=True,
        null=True,
    )
    description = models.TextField(blank=True, default="")
    level = models.CharField(max_length=100, blank=True, default="")
    language = models.CharField(max_length=100, blank=True, default="")
    location = models.CharField(max_length=255, blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    lessons_count = models.PositiveIntegerField(default=0)
    total_duration = models.CharField(max_length=100, blank=True, default="")
    required_skills = models.ManyToManyField(Skill, related_name="required_for_courses", blank=True)
    enrolled_users = models.ManyToManyField(User, related_name="enrolled_courses", blank=True)
    registration_link = models.URLField(blank=True, null=True)
    lecturer_name = models.CharField(max_length=255, blank=True, default="")
    lecturer_photo = models.ImageField(
        storage=MediaCloudinaryStorage(),
        upload_to="lecturer_photos/",
        blank=True,
        null=True,
    )
    skills_taught = models.ManyToManyField(Skill, related_name="courses")

    def __str__(self):
        owner = self.academy.name if self.academy else (self.user.get_full_name() if self.user else "Unknown")
        return f"{self.title} by {owner}"



class DynamicTechQuestion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    questionid = models.CharField(max_length=50, unique=True)
    skill = models.CharField(max_length=100,default='')
    RoleMapping = models.CharField(max_length=100)
    difficulty = models.CharField(max_length=10,default='easy')
    questiontext = models.TextField()
    option1 = models.CharField(max_length=255)
    option2 = models.CharField(max_length=255)
    option3 = models.CharField(max_length=255)
    option4 = models.CharField(max_length=255)
    option5 = models.CharField(max_length=255, default="I don't know")
    correct_option = models.IntegerField(default=1)
    isactive = models.BooleanField(default=True)
    createdat = models.DateTimeField(auto_now_add=True)
    updatedat = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.skill} - {self.questiontext[:50]}"



class CareerCategory(models.Model):
    code = models.CharField(max_length=5, unique=True) 
    title = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.code} - {self.title}"


class CareerQuestion(models.Model):
    category = models.ForeignKey(CareerCategory, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()

    def __str__(self):
        return f"{self.category.code}{self.id}: {self.text[:50]}"


class CareerOption(models.Model):
    question = models.ForeignKey(CareerQuestion, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=255)
    RoleMapping = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.text} → {self.RoleMapping}"
    


class DynamicSoftSkillsQuestion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    questionid = models.CharField(max_length=50, unique=True)
    skill = models.CharField(max_length=100,default='')
    RoleMapping = models.CharField(max_length=100)
    difficulty = models.CharField(max_length=10,default='easy')
    questiontext = models.TextField()
    option1 = models.CharField(max_length=255)
    option2 = models.CharField(max_length=255)
    option3 = models.CharField(max_length=255)
    option4 = models.CharField(max_length=255)
    option5 = models.CharField(max_length=255, default="I don't know")
    correct_option = models.IntegerField(default=1)
    isactive = models.BooleanField(default=True)
    createdat = models.DateTimeField(auto_now_add=True)
    updatedat = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.skill} - {self.questiontext[:50]}"
    



class SkillScore(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    score = models.FloatField(default=0.0) 
    threshold = models.FloatField(default=70.0) 
    created_at = models.DateTimeField(auto_now_add=True)

    def is_strong(self):
        return self.score >= self.threshold

    def __str__(self):
        status = "✅ Strong" if self.is_strong() else "❌ Weak"
        return f"{self.user.username} - {self.skill.name}: {self.score}% ({status})"
    



class SkillTestResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    final_role = models.CharField(max_length=255)
    total_score = models.CharField(max_length=20)
    skills_json = models.JSONField()               
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.final_role} ({self.total_score})"
    




class Industry(models.Model):
    """Industry catalog (optional; not linked to Employer profiles)."""

    name = models.CharField(max_length=200, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Academy(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="academy")
    phone_number = models.CharField(max_length=20)
    password = models.CharField(max_length=128)
    description = models.TextField(default="No description provided")
    website = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    profile_image = models.ImageField(
        storage=MediaCloudinaryStorage(),
        upload_to="academy_pics/",
        blank=True,
        null=True
    )

    @property
    def name(self):
        return self.user.first_name if self.user else "Unknown Academy"

    @property
    def email(self):
        return self.user.email if self.user else ""

    def __str__(self):
        return self.name


class Employer(models.Model):
    """
    Employer account: personal name on User (first_name, last_name); role at work on Employer.
    Authentication uses the linked User password (no separate Employer.password field).
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employer")
    role_in_company = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Job title or role (e.g. HR Manager, Founder).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    @property
    def email(self):
        return self.user.email if self.user else ""

    @property
    def full_name(self):
        if not self.user_id:
            return ""
        return (self.user.get_full_name() or "").strip()

    def __str__(self):
        if self.user_id:
            name = self.full_name
            return name or self.user.email or str(self.pk)
        return f"Employer #{self.pk}"





class UserProfile(models.Model):
    """Profile for regular users only. Academies use Academy; employers use Employer — not UserProfile."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    country_region = models.CharField(max_length=100, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    profile_image = models.ImageField(
        storage=MediaCloudinaryStorage(),
        upload_to='profile_pics/',
        blank=True,
        null=True
    )
    about_me = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.user_id and Academy.objects.filter(user_id=self.user_id).exists():
            raise ValueError(
                "UserProfile is only for regular users. Academy profiles belong in the Academy table."
            )
        if self.user_id and Employer.objects.filter(user_id=self.user_id).exists():
            raise ValueError(
                "UserProfile is only for regular users. Employer profiles belong in the Employer table."
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} Profile"



class TemporaryUser(models.Model):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    code_expires_at = models.DateTimeField(blank=True, null=True)   

    def generate_verification_code(self):
        code = str(random.randint(100000, 999999))
        self.verification_code = code
        self.code_expires_at = timezone.now() + timedelta(minutes=10)
        self.save()
        return code

    def __str__(self):
        return f"{self.email} (Temporary)"
    


class TemporaryEmployer(models.Model):
    """Pre-verification employer signup: personal name + email + optional role."""
    first_name = models.CharField(max_length=150, default="")
    last_name = models.CharField(max_length=150, default="")
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    role_in_company = models.CharField(max_length=255, blank=True, default="")
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    code_expires_at = models.DateTimeField(blank=True, null=True)

    def generate_verification_code(self):
        code = str(random.randint(100000, 999999))
        self.verification_code = code
        self.code_expires_at = timezone.now() + timedelta(minutes=10)
        self.save()
        return code

    def __str__(self):
        return f"{self.email} (Temporary Employer)"


class TemporaryAcademy(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    code_expires_at = models.DateTimeField(blank=True, null=True)

    def generate_verification_code(self):
        code = str(random.randint(100000, 999999))
        self.verification_code = code
        self.code_expires_at = timezone.now() + timedelta(minutes=10)
        self.save()
        return code
    
    def __str__(self):
        return f"{self.email} (Temporary)"
    
    
    




class PasswordResetCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=15)
    







class SocialLinks(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="social_links",
    )
    academy = models.OneToOneField(
        Academy,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="social_links",
    )
    employer = models.OneToOneField(
        "Employer",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="social_links",
    )

    github = models.URLField(blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    facebook = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    dribbble = models.URLField(blank=True, null=True)
    behance = models.URLField(blank=True, null=True)

    def __str__(self):
        if self.user:
            return f"{self.user.username}'s Social Links"
        elif self.academy:
            return f"{self.academy.name}'s Social Links"
        elif self.employer_id and self.employer.user_id:
            name = self.employer.user.get_full_name().strip() or self.employer.user.email
            return f"{name}'s Social Links"
        return "Unknown Social Links"


class Education(models.Model):
    """Education entries for a user. Max 10 per user enforced in API."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="educations",
    )
    school_name = models.CharField(max_length=255)
    major = models.CharField(max_length=255, blank=True, default="")
    degree_type = models.CharField(max_length=100, blank=True, default="")
    gpa = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.is_current and self.end_date is not None:
            raise ValidationError(
                {"end_date": "end_date must be NULL when is_current is True."}
            )
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(
                {"end_date": "end_date must be on or after start_date."}
            )

    def __str__(self):
        return f"{self.user_id} - {self.school_name}"


class UserIndustryProfile(models.Model):
    """One row per user: industry years computed by frontend from work experience. Stored for job match later."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="industry_profile",
    )
    industry_years_json = models.JSONField(default=dict)  # e.g. {"fintech": 2.5, "e-commerce": 0.8}; can be {}
    updated_at = models.DateTimeField()  # Set from request body or server time

    def __str__(self):
        return f"{self.user.username} Industry Profile"


class WorkExperience(models.Model):
    """Work experience entries for a user. Max 10 per user enforced in API."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="work_experiences",
    )
    job_title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    job_type = models.CharField(max_length=100, blank=True, default="")
    location = models.CharField(max_length=255, blank=True, default="")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.is_current and self.end_date is not None:
            raise ValidationError(
                {"end_date": "end_date must be NULL when is_current is True."}
            )
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(
                {"end_date": "end_date must be on or after start_date."}
            )

    def __str__(self):
        return f"{self.user_id} - {self.job_title} at {self.company}"


class SavedCourse(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="saved_courses")
    academy = models.ForeignKey('Academy', on_delete=models.CASCADE, null=True, blank=True, related_name="saved_courses")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="saved_by")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('user', 'course'), ('academy', 'course'))

    def __str__(self):
        if self.user:
            return f"{self.user.username} saved {self.course.title}"
        return f"{self.academy.name} saved {self.course.title}"


class SavedJob(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="saved_jobs")
    academy = models.ForeignKey('Academy', on_delete=models.CASCADE, null=True, blank=True, related_name="saved_jobs")
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="saved_by")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('user', 'job'), ('academy', 'job'))

    def __str__(self):
        if self.user:
            return f"{self.user.username} saved {self.job.title}"
        return f"{self.academy.name} saved {self.job.title}"




# Subscription Models

class SubscriptionPlan(models.Model):
    AUDIENCE_USER = "user"
    AUDIENCE_ACADEMY = "academy"
    AUDIENCE_COMPANY = "company"
    AUDIENCE_CHOICES = [
        (AUDIENCE_USER, "User"),
        (AUDIENCE_ACADEMY, "Academy"),
        (AUDIENCE_COMPANY, "Company"),
    ]

    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(default=30)
    is_active = models.BooleanField(default=True)
    audience = models.CharField(
        max_length=20,
        choices=AUDIENCE_CHOICES,
        default=AUDIENCE_USER,
        db_index=True,
        help_text="Who this plan is for: User, Academy, or Company.",
    )
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_audience_display()}) - {self.price} GEL"

    class Meta:
        ordering = ['price']


class UserSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True)
    parent_order_id = models.CharField(max_length=200, null=True, blank=True)
    is_active = models.BooleanField(default=False)
    next_payment_date = models.DateField(null=True, blank=True)
    card_mask = models.CharField(max_length=20, null=True, blank=True)
    card_type = models.CharField(max_length=20, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} subscription"


class PaymentHistory(models.Model):
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payment_history")
    subscription = models.ForeignKey(UserSubscription, on_delete=models.SET_NULL, null=True, blank=True)
    order_id = models.CharField(max_length=200, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="GEL")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=50, default="Card")
    card_mask = models.CharField(max_length=50, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.order_id} - {self.status}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ("info", "Info"),
        ("success", "Success"),
        ("warning", "Warning"),
        ("error", "Error"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="info")
    is_read = models.BooleanField(default=False)
    kind = models.CharField(max_length=64, blank=True, default="", db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "-created_at"]),
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["recipient", "kind", "-created_at"]),
        ]

    def __str__(self):
        target = self.recipient_id or "broadcast"
        return f"Notification {self.pk} → {target}: {self.title[:40]}"


class JobNotification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="job_notifications",
    )
    job_id = models.CharField(max_length=128)
    notified_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "job_id")]
        indexes = [models.Index(fields=["user"])]

    def __str__(self):
        return f"{self.user_id} notified for job {self.job_id}"


class Atom(models.Model):
    """A single ~3-minute micro-lesson made of story-like cards ending in a quiz."""

    profession = models.ForeignKey(
        Profession,
        on_delete=models.CASCADE,
        related_name="atoms",
    )
    title = models.CharField(max_length=255)
    sequence_order = models.PositiveIntegerField(
        help_text="Strict ordering within the profession path (1 = first atom).",
    )
    content_cards = models.JSONField(default=list, blank=True)
    quiz_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["profession", "sequence_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["profession", "sequence_order"],
                name="unique_atom_sequence_per_profession",
            ),
        ]
        indexes = [
            models.Index(fields=["profession", "sequence_order"]),
        ]

    def __str__(self):
        return f"{self.profession.title} — #{self.sequence_order}: {self.title}"


class UserProgress(models.Model):
    """Tracks a user's completion state for a single Atom."""

    PASS_THRESHOLD = 80.0

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="atom_progress",
    )
    atom = models.ForeignKey(
        Atom,
        on_delete=models.CASCADE,
        related_name="user_progress",
    )
    score_percentage = models.FloatField(default=0.0)
    is_completed = models.BooleanField(default=False)
    requires_retake = models.BooleanField(default=False)
    last_attempted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "atom"],
                name="unique_user_atom_progress",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "atom"]),
            models.Index(fields=["user", "is_completed"]),
        ]

    def __str__(self):
        return f"User {self.user_id} — Atom {self.atom_id}: {self.score_percentage}%"
