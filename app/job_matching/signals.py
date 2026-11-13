"""Drop a user's cached snapshot whenever a field that feeds it is saved or deleted."""

from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from app.models import (
    Skill,
    SkillTestResult,
    UserIndustryProfile,
    UserResume,
    UserSkill,
    WorkExperience,
)

from .snapshot import invalidate_user_snapshot

_PROFILE_MODELS = (UserSkill, SkillTestResult, WorkExperience, UserIndustryProfile, UserResume)


def _invalidate(user_id) -> None:
    if user_id is None:
        return
    invalidate_user_snapshot(user_id)
    # A rebuild between the write and its commit would cache the old rows; clear again once committed.
    transaction.on_commit(lambda: invalidate_user_snapshot(user_id))


def _on_profile_change(sender, instance, **kwargs):
    _invalidate(instance.user_id)


for _model in _PROFILE_MODELS:
    post_save.connect(_on_profile_change, sender=_model, dispatch_uid=f"job_match_snapshot_save_{_model.__name__}")
    post_delete.connect(_on_profile_change, sender=_model, dispatch_uid=f"job_match_snapshot_delete_{_model.__name__}")


@receiver(post_save, sender=Skill, dispatch_uid="job_match_snapshot_skill_rename")
def _on_skill_saved(sender, instance, created, **kwargs):
    if created:
        return
    for user_id in UserSkill.objects.filter(skill_id=instance.pk).values_list("user_id", flat=True):
        _invalidate(user_id)
