"""
Match users to professions based on SkillScore (only score > 0) or SkillTestResult.skills_json.
Updates ProfessionOfUser table.
"""
from django.db import transaction
from django.contrib.auth import get_user_model

from app.models import Profession, ProfessionOfUser, Skill, SkillScore

User = get_user_model()


def _parse_percentage(value):
    """Parse '0.0%' or '75.0%' to float. Returns 0.0 if invalid."""
    if value is None:
        return 0.0
    s = str(value).strip().replace("%", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def skill_ids_from_skills_json(skills_json):
    """
    Parse skills_json from SkillTestResult.
    Expected: {"soft": {"Teamwork": "0.0%", ...}, "tech": {"Python": "0.0%"}}.
    Also supports flat: {"Python": "75%", "Teamwork": "50%"}.
    Returns set of Skill IDs for which the user has score > 0.
    Matches Skill by name (case-insensitive); only includes skills that exist in DB.
    """
    if not skills_json or not isinstance(skills_json, dict):
        return set()
    user_skill_ids = set()
    blocks = []
    if "soft" in skills_json or "tech" in skills_json:
        for category in ("soft", "tech"):
            block = skills_json.get(category)
            if isinstance(block, dict):
                blocks.append(block.items())
    else:
        blocks.append(skills_json.items())
    for block_items in blocks:
        for skill_name, raw_value in block_items:
            if not (skill_name and isinstance(skill_name, str)):
                continue
            score = _parse_percentage(raw_value)
            if score <= 0:
                continue
            skill = Skill.objects.filter(name__iexact=skill_name.strip()).first()
            if skill:
                user_skill_ids.add(skill.id)
    return user_skill_ids


def compute_profession_scores_from_skill_ids(user_skill_ids):
    """
    Given a set of user skill IDs (score > 0), compute match_score for each profession.
    Returns list of (profession, match_score) with match_score > 0.
    """
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


def compute_user_profession_scores(user):
    """
    For a user, compute match_score with each profession.
    Only skills with SkillScore.score > 0 are considered.
    Returns list of (profession, match_score) with match_score > 0.
    """
    user_skill_ids = set(
        SkillScore.objects.filter(user=user, score__gt=0).values_list("skill_id", flat=True)
    )
    return compute_profession_scores_from_skill_ids(user_skill_ids)


def _save_profession_assignments(user, scores):
    """Replace user's ProfessionOfUser rows with the given (profession, match_score) list."""
    with transaction.atomic():
        ProfessionOfUser.objects.filter(user=user).delete()
        for profession, match_score in scores:
            ProfessionOfUser.objects.create(
                user=user,
                profession=profession,
                match_score=match_score,
            )


def update_profession_of_user(user):
    """
    Update ProfessionOfUser for one user from SkillScore (score > 0).
    Creates/updates rows and removes professions that no longer match.
    """
    scores = compute_user_profession_scores(user)
    _save_profession_assignments(user, scores)


def update_profession_of_user_from_skill_test(user):
    """
    Update ProfessionOfUser for one user from their latest SkillTestResult.skills_json.
    skills_json format: {"soft": {"Teamwork": "0.0%", ...}, "tech": {"Python": "0.0%"}}.
    Only skills with percentage > 0 are considered; skill names matched to Skill (case-insensitive).
    """
    from app.models import SkillTestResult

    last = SkillTestResult.objects.filter(user=user).order_by("-created_at").first()
    if not last or not getattr(last, "skills_json", None):
        _save_profession_assignments(user, [])
        return
    user_skill_ids = skill_ids_from_skills_json(last.skills_json)
    scores = compute_profession_scores_from_skill_ids(user_skill_ids)
    _save_profession_assignments(user, scores)


def update_all_profession_assignments():
    """
    Update ProfessionOfUser for all users that have at least one SkillScore with score > 0.
    """
    user_ids = SkillScore.objects.filter(score__gt=0).values_list("user_id", flat=True).distinct()
    for user_id in user_ids:
        user = User.objects.filter(pk=user_id).first()
        if user:
            update_profession_of_user(user)


def update_all_profession_assignments_from_skill_test():
    """
    Update ProfessionOfUser for all users that have at least one SkillTestResult,
    using each user's latest skills_json (soft + tech, percentage > 0).
    """
    from app.models import SkillTestResult

    user_ids = SkillTestResult.objects.values_list("user_id", flat=True).distinct()
    for user_id in user_ids:
        user = User.objects.filter(pk=user_id).first()
        if user:
            update_profession_of_user_from_skill_test(user)
