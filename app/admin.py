from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django import forms
from django.utils.html import format_html
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.utils.http import unquote
from django.contrib.admin.options import TO_FIELD_VAR, IS_POPUP_VAR
from django.contrib.admin import helpers as admin_helpers
from django.forms.formsets import all_valid
import logging

from .models import (
    Assessment,
    AssessmentSession,
    Badge,
    Job,
    Profession,
    ProfessionOfUser,
    Skill,
    UserSkill,
    Course,
    DynamicTechQuestion,
    CareerCategory,
    CareerQuestion,
    CareerOption,
    DynamicSoftSkillsQuestion,
    SkillScore,
    Academy,
    UserProfile,
    TemporaryUser,
    TemporaryAcademy,
    SkillTestResult,
    SocialLinks,
    Education,
    WorkExperience,
    UserIndustryProfile,
    UserSubscription,
    SubscriptionPlan,
    PaymentHistory,
)


class SafeImageFileWrapper:
    """Wraps an ImageField file so .url never raises (avoids 500 in admin when storage fails)."""
    def __init__(self, file):
        self._file = file

    def __bool__(self):
        return bool(self._file)

    def __str__(self):
        return str(self._file) if self._file else ""

    @property
    def url(self):
        try:
            return self._file.url if self._file else ""
        except Exception:
            return ""

    def __getattr__(self, name):
        return getattr(self._file, name)


class ChangeFormSaveErrorMixin:
    """
    Mixin for ModelAdmin that catches save errors and re-displays the form
    with the error message instead of returning 500.
    Use for admin that has custom form save() or model save() that can raise.
    """
    def _changeform_view(self, request, object_id, form_url, extra_context):
        from django.contrib.admin.helpers import flatten_fieldsets
        from django.core.exceptions import PermissionDenied
        from django.contrib.admin.exceptions import DisallowedModelAdminToField
        from django.utils.translation import gettext as _

        to_field = request.POST.get(TO_FIELD_VAR, request.GET.get(TO_FIELD_VAR))
        if to_field and not self.to_field_allowed(request, to_field):
            raise DisallowedModelAdminToField("The field %s cannot be referenced." % to_field)
        if request.method == "POST" and "_saveasnew" in request.POST:
            object_id = None
        add = object_id is None
        if add:
            if not self.has_add_permission(request):
                raise PermissionDenied
            obj = None
        else:
            obj = self.get_object(request, unquote(object_id), to_field)
            if request.method == "POST" and not self.has_change_permission(request, obj):
                raise PermissionDenied
            elif request.method != "POST" and not self.has_view_or_change_permission(request, obj):
                raise PermissionDenied
            if obj is None:
                return self._get_obj_does_not_exist_redirect(request, self.model._meta, object_id)
        fieldsets = self.get_fieldsets(request, obj)
        ModelForm = self.get_form(request, obj, change=not add, fields=flatten_fieldsets(fieldsets))
        if request.method == "POST":
            form = ModelForm(request.POST, request.FILES, instance=obj)
            formsets, inline_instances = self._create_formsets(request, form.instance, change=not add)
            form_validated = form.is_valid()
            new_object = self.save_form(request, form, change=not add) if form_validated else form.instance
            if all_valid(formsets) and form_validated:
                try:
                    self.save_model(request, new_object, form, not add)
                    self.save_related(request, form, formsets, not add)
                    change_message = self.construct_change_message(request, form, formsets, add)
                    if add:
                        self.log_addition(request, new_object, change_message)
                        return self.response_add(request, new_object)
                    self.log_change(request, new_object, change_message)
                    return self.response_change(request, new_object)
                except Exception as e:
                    logging.getLogger("app.admin").exception("%s admin save failed", self.model.__name__)
                    messages.error(request, str(e))
                    form.add_error(None, str(e))
                    form_validated = False
            else:
                form_validated = False
        else:
            if add:
                form = ModelForm(initial=self.get_changeform_initial_data(request))
                formsets, inline_instances = self._create_formsets(request, form.instance, change=False)
            else:
                form = ModelForm(instance=obj)
                formsets, inline_instances = self._create_formsets(request, obj, change=True)
        if not add and not self.has_change_permission(request, obj):
            readonly_fields = flatten_fieldsets(fieldsets)
        else:
            readonly_fields = self.get_readonly_fields(request, obj)
        admin_form = admin_helpers.AdminForm(
            form, list(fieldsets),
            self.get_prepopulated_fields(request, obj) if add or self.has_change_permission(request, obj) else {},
            readonly_fields, model_admin=self,
        )
        media = self.media + admin_form.media
        inline_formsets = self.get_inline_formsets(request, formsets, inline_instances, obj)
        for ifs in inline_formsets:
            media += ifs.media
        title = _("Add %s") if add else _("Change %s") if self.has_change_permission(request, obj) else _("View %s")
        context = {
            **self.admin_site.each_context(request),
            "title": title % self.model._meta.verbose_name,
            "subtitle": str(obj) if obj else None,
            "adminform": admin_form,
            "object_id": object_id,
            "original": obj,
            "is_popup": IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET,
            "to_field": to_field or "",
            "media": media,
            "inline_admin_formsets": inline_formsets,
            "errors": admin_helpers.AdminErrorList(form, formsets),
            "preserved_filters": self.get_preserved_filters(request),
        }
        if request.method == "POST" and not form_validated and "_saveasnew" in request.POST:
            context["show_save"], context["show_save_and_continue"] = False, False
            add = False
        context.update(extra_context or {})
        return self.render_change_form(request, context, add=add, change=not add, obj=obj, form_url=form_url)


admin.site.register(Assessment)
admin.site.register(Badge)
@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(UserSkill)
class UserSkillAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "skill_name", "points", "created_at")
    list_filter = ("user",)
    search_fields = ("user__email", "skill__name")
    ordering = ("-created_at",)

    def skill_name(self, obj):
        return obj.skill.name if obj.skill_id else "—"
    skill_name.short_description = "Skill"
admin.site.register(TemporaryUser)
admin.site.register(TemporaryAcademy)





from django.contrib import admin
from .models import Job, Course


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "salary_min",
        "salary_max",
        "time_to_ready",
    )
    readonly_fields = ("id",) 
    search_fields = ("title",)
    list_filter = ("time_to_ready",)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "level",
        "language",
        "location",
        "price",
        "lessons_count",
        "academy",
        "user",
    )
    readonly_fields = ("id",)  
    search_fields = ("title", "lecturer_name", "description")
    list_filter = ("academy", "level", "language", "location")



@admin.register(DynamicTechQuestion)
class DynamicTechQuestionAdmin(admin.ModelAdmin):
    list_display = ('questiontext', 'skill', 'RoleMapping', 'difficulty')
    search_fields = ('questiontext', 'skill', 'RoleMapping')


@admin.register(CareerCategory)
class CareerCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'title')
    search_fields = ('code', 'title')


class CareerOptionInline(admin.TabularInline):
    model = CareerOption
    extra = 2


@admin.register(CareerQuestion)
class CareerQuestionAdmin(admin.ModelAdmin):
    list_display = ('category', 'text')
    search_fields = ('text',)
    list_filter = ('category',)
    inlines = [CareerOptionInline]


@admin.register(CareerOption)
class CareerOptionAdmin(admin.ModelAdmin):
    list_display = ('question', 'text', 'RoleMapping')
    search_fields = ('text', 'RoleMapping')
    list_filter = ('RoleMapping',)



@admin.register(DynamicSoftSkillsQuestion)
class DynamicSoftSkillsQuestionAdmin(admin.ModelAdmin):
    list_display = ('questiontext', 'skill', 'RoleMapping', 'difficulty')
    search_fields = ('questiontext', 'skill', 'RoleMapping')



@admin.register(Profession)
class ProfessionAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at")
    search_fields = ("title", "description")
    filter_horizontal = ("skills", "relevant_courses")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProfessionOfUser)
class ProfessionOfUserAdmin(admin.ModelAdmin):
    list_display = ("user", "profession", "match_score", "created_at")
    list_filter = ("profession",)
    search_fields = ("user__username", "user__email", "profession__title")
    ordering = ("-match_score",)
    readonly_fields = ("created_at",)


@admin.register(SkillScore)
class SkillScoreAdmin(admin.ModelAdmin):
    list_display = ("user", "skill", "score", "threshold", "created_at")
    list_filter = ("user", "skill")



@admin.register(SkillTestResult)
class SkillTestResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'final_role', 'total_score', 'created_at', 'updated_at')
    search_fields = ('user__username', 'final_role')
    list_filter = ('final_role', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    actions = ['remove_duplicate_results', 'remove_all_duplicate_results']

    @admin.action(description="Remove duplicates from selected (keep most recent per user)")
    def remove_duplicate_results(self, request, queryset):
        removed = 0
        user_ids = queryset.values_list("user_id", flat=True).distinct()
        for user_id in user_ids:
            results = SkillTestResult.objects.filter(user_id=user_id).order_by("-created_at")
            to_keep = results.first()
            if to_keep and results.count() > 1:
                deleted, _ = results.exclude(pk=to_keep.pk).delete()
                removed += deleted
        self.message_user(request, f"Removed {removed} duplicate result(s). Kept most recent per user.")

    @admin.action(description="Remove ALL duplicates (full table cleanup)")
    def remove_all_duplicate_results(self, request, queryset):
        removed = 0
        for user_id in SkillTestResult.objects.values_list("user_id", flat=True).distinct():
            results = SkillTestResult.objects.filter(user_id=user_id).order_by("-created_at")
            to_keep = results.first()
            if to_keep and results.count() > 1:
                deleted, _ = results.exclude(pk=to_keep.pk).delete()
                removed += deleted
        self.message_user(request, f"Removed {removed} duplicate result(s) from entire table.")

class UserProfileAdminForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get("user")
        if user and user.pk and Academy.objects.filter(user_id=user.pk).exists():
            raise forms.ValidationError(
                "UserProfile is only for regular users. This user is linked to an Academy; edit the Academy record instead."
            )
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.profile_image:
            self._real_profile_image = self.instance.profile_image
            # Only wrap for form display (initial); do not replace instance to avoid save issues
            self.initial["profile_image"] = SafeImageFileWrapper(self._real_profile_image)

    def save(self, commit=True):
        if hasattr(self, "_real_profile_image"):
            self.instance.profile_image = self._real_profile_image
        profile_image = self.cleaned_data.get("profile_image")
        if profile_image is not None and not isinstance(profile_image, SafeImageFileWrapper):
            self.instance.profile_image = profile_image if profile_image else None
        # Never persist the wrapper
        if isinstance(getattr(self.instance, "profile_image", None), SafeImageFileWrapper):
            self.instance.profile_image = getattr(self, "_real_profile_image", None)
        if commit:
            try:
                self.instance.save()
            except Exception as e:
                from django.core.exceptions import ValidationError
                raise ValidationError(f"Could not save profile image: {e}")
        else:
            # So admin's save_related() can call form.save_m2m()
            super().save(commit=False)
        return self.instance


@admin.register(UserProfile)
class UserProfileAdmin(ChangeFormSaveErrorMixin, admin.ModelAdmin):
    form = UserProfileAdminForm
    list_display = ('id', 'user', 'phone_number', 'country_region', 'city', 'has_profile_image', 'about_me')
    readonly_fields = ("id",)
    fields = ('id', 'user', 'phone_number', 'country_region', 'city', 'profile_image', 'about_me')

    @admin.display(boolean=True, description="Has image")
    def has_profile_image(self, obj):
        if not obj.profile_image:
            return False
        try:
            return bool(obj.profile_image.url)
        except Exception:
            return False


class AcademyAdminForm(forms.ModelForm):
    class Meta:
        model = Academy
        fields = "__all__"
        exclude = ["password"]  # Not in admin; keep when editing, set default when adding

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.profile_image:
            self._real_profile_image = self.instance.profile_image
            # Only wrap for form display (initial); do not replace instance to avoid save issues
            self.initial["profile_image"] = SafeImageFileWrapper(self._real_profile_image)

    def save(self, commit=True):
        if hasattr(self, "_real_profile_image"):
            self.instance.profile_image = self._real_profile_image
        profile_image = self.cleaned_data.get("profile_image")
        if profile_image is not None and not isinstance(profile_image, SafeImageFileWrapper):
            self.instance.profile_image = profile_image if profile_image else None
        # Never persist the wrapper
        if isinstance(getattr(self.instance, "profile_image", None), SafeImageFileWrapper):
            self.instance.profile_image = getattr(self, "_real_profile_image", None)
        # New Academy: set unusable password so DB constraint is satisfied
        if not self.instance.pk:
            self.instance.password = make_password(None)  # unusable
        if commit:
            try:
                self.instance.save()
            except Exception as e:
                from django.core.exceptions import ValidationError
                raise ValidationError(f"Could not save (e.g. profile image): {e}")
        else:
            # So admin's save_related() can call form.save_m2m()
            super().save(commit=False)
        return self.instance


@admin.register(Academy)
class AcademyAdmin(ChangeFormSaveErrorMixin, admin.ModelAdmin):
    form = AcademyAdminForm
    list_display = ('id', 'name', 'email', 'phone_number', 'has_profile_image', 'website', 'created_at')
    search_fields = ('user__first_name', 'user__email')
    readonly_fields = ('id', 'created_at')
    fields = ('id', 'user', 'phone_number', 'profile_image', 'website', 'description', 'is_verified')

    @admin.display(boolean=True, description="Has image")
    def has_profile_image(self, obj):
        if not obj.profile_image:
            return False
        try:
            return bool(obj.profile_image.url)
        except Exception:
            return False 


@admin.register(SocialLinks)
class SocialLinksAdmin(admin.ModelAdmin):
    list_display = ('user', 'academy')
    search_fields = ('user__username', 'user__email', 'academy__user__first_name', 'academy__user__email')


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ('user', 'school_name', 'major', 'degree_type', 'start_date', 'end_date', 'is_current')
    list_filter = ('is_current',)
    search_fields = ('user__email', 'school_name', 'major')


@admin.register(WorkExperience)
class WorkExperienceAdmin(admin.ModelAdmin):
    list_display = ('user', 'job_title', 'company', 'job_type', 'start_date', 'end_date', 'is_current')
    list_filter = ('is_current',)
    search_fields = ('user__email', 'job_title', 'company')


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "is_active", "next_payment_date", "parent_order_id")
    list_filter = ("is_active", "next_payment_date")
    search_fields = ("user__email", "parent_order_id")


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "duration_days", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    ordering = ("price",)

@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = ("order_id", "user", "amount", "currency", "status", "created_at")
    list_filter = ("status", "created_at", "currency")
    search_fields = ("order_id", "user__email", "card_mask")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


# Academy users: display name is User.first_name only (Academy.name); hide last_name in admin.
# Regular users: unchanged — full default User fieldsets from Django.
admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    def get_fieldsets(self, request, obj=None):
        if not obj:
            return super().get_fieldsets(request, obj)
        if Academy.objects.filter(user_id=obj.pk).exists():
            return (
                (None, {"fields": ("username", "password")}),
                (_("Personal info"), {"fields": ("first_name", "email")}),
                (
                    _("Permissions"),
                    {
                        "fields": (
                            "is_active",
                            "is_staff",
                            "is_superuser",
                            "groups",
                            "user_permissions",
                        ),
                    },
                ),
                (_("Important dates"), {"fields": ("last_login", "date_joined")}),
            )
        return super().get_fieldsets(request, obj)
