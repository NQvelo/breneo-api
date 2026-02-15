"""
Match users to professions based on SkillScore (only score > 0).
Updates ProfessionOfUser table.
"""
from django.db import transaction
from django.contrib.auth import get_user_model

from app.models import Profession, ProfessionOfUser, SkillScore

User = get_user_model()


def compute_user_profession_scores(user):
    """
    For a user, compute match_score with each profession.
    Only skills with SkillScore.score > 0 are considered.
    Returns list of (profession, match_score) with match_score > 0.
    """
    # User's skill IDs that have score > 0
    user_skill_ids = set(
        SkillScore.objects.filter(user=user, score__gt=0).values_list("skill_id", flat=True)
    )
    if not user_skill_ids:
        return []

    result = []
    for profession in Profession.objects.prefetch_related("skills").all():
        profession_skill_ids = set(profession.skills.values_list("id", flat=True))
        if not profession_skill_ids:
            continue
        overlap = len(user_skill_ids & profession_skill_ids)
        match_score = round((overlap / len(profession_skill_ids)) * 100.0, 2)
        if match_score > 0:
            result.append((profession, match_score))
    return result


def update_profession_of_user(user):
    """
    Update ProfessionOfUser for one user from SkillScore (score > 0).
    Creates/updates rows and removes professions that no longer match.
    """
    scores = compute_user_profession_scores(user)
    with transaction.atomic():
        ProfessionOfUser.objects.filter(user=user).delete()
        for profession, match_score in scores:
            ProfessionOfUser.objects.create(
                user=user,
                profession=profession,
                match_score=match_score,
            )


def update_all_profession_assignments():
    """
    Update ProfessionOfUser for all users that have at least one SkillScore with score > 0.
    """
    user_ids = SkillScore.objects.filter(score__gt=0).values_list("user_id", flat=True).distinct()
    for user_id in user_ids:
        user = User.objects.filter(pk=user_id).first()
        if user:
            update_profession_of_user(user)
