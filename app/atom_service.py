"""Business logic for the Atoms micro-learning feature."""

from django.utils import timezone

from .atom_schemas import QuizDataSchema, validate_quiz_data
from .models import Atom, Profession, UserProgress

PASS_THRESHOLD = UserProgress.PASS_THRESHOLD


def get_profession_or_none(profession_id: int) -> Profession | None:
    return Profession.objects.filter(pk=profession_id).first()


def get_atom_or_none(atom_id: int) -> Atom | None:
    return Atom.objects.select_related("profession").filter(pk=atom_id).first()


def _completed_atom_ids(user, profession: Profession) -> set[int]:
    return set(
        UserProgress.objects.filter(
            user=user,
            atom__profession=profession,
            is_completed=True,
        ).values_list("atom_id", flat=True)
    )


def _prerequisites_met(atom: Atom, completed_ids: set[int], profession_atoms: list[Atom]) -> bool:
    for previous in profession_atoms:
        if previous.sequence_order >= atom.sequence_order:
            break
        if previous.id not in completed_ids:
            return False
    return True


def get_next_atom_for_user(user, profession_id: int) -> tuple[Atom | None, str | None]:
    """
    Return the next Atom the user should work on for a profession.

    Users cannot skip ahead: every prior atom (by sequence_order) must be completed.
    Atoms that failed (requires_retake=True) are returned again until passed.
    """
    profession = get_profession_or_none(profession_id)
    if profession is None:
        return None, "profession_not_found"

    profession_atoms = list(
        Atom.objects.filter(profession=profession).order_by("sequence_order", "id")
    )
    if not profession_atoms:
        return None, "no_atoms"

    completed_ids = _completed_atom_ids(user, profession)
    progress_by_atom = {
        progress.atom_id: progress
        for progress in UserProgress.objects.filter(
            user=user,
            atom__in=profession_atoms,
        )
    }

    for atom in profession_atoms:
        if not _prerequisites_met(atom, completed_ids, profession_atoms):
            break

        progress = progress_by_atom.get(atom.id)
        if progress is None or not progress.is_completed or progress.requires_retake:
            return atom, None

    return None, "all_completed"


def user_can_access_atom(user, atom: Atom) -> bool:
    """True when all prerequisite atoms for the same profession are completed."""
    profession_atoms = list(
        Atom.objects.filter(profession=atom.profession).order_by("sequence_order", "id")
    )
    completed_ids = _completed_atom_ids(user, atom.profession)
    return _prerequisites_met(atom, completed_ids, profession_atoms)


def submit_atom_quiz(user, atom_id: int, selected_option_index: int) -> dict:
    """
    Grade a quiz submission and upsert UserProgress.

    Returns a result dict suitable for API serialization.
    Raises ValueError with an error code string for expected failures.
    """
    atom = Atom.objects.select_related("profession").filter(pk=atom_id).first()
    if atom is None:
        raise ValueError("atom_not_found")

    if not user_can_access_atom(user, atom):
        raise ValueError("prerequisites_not_met")

    try:
        quiz = validate_quiz_data(atom.quiz_data)
        quiz_model = QuizDataSchema.model_validate(quiz)
    except Exception as exc:
        raise ValueError("invalid_quiz_data") from exc

    if selected_option_index < 0 or selected_option_index >= len(quiz_model.options):
        raise ValueError("invalid_option_index")

    is_correct = selected_option_index == quiz_model.correct_index
    score_percentage = 100.0 if is_correct else 0.0
    passed = score_percentage >= PASS_THRESHOLD
    now = timezone.now()

    progress, _created = UserProgress.objects.update_or_create(
        user=user,
        atom=atom,
        defaults={
            "score_percentage": score_percentage,
            "is_completed": passed,
            "requires_retake": not passed,
            "last_attempted_at": now,
        },
    )

    return {
        "atom_id": atom.id,
        "profession_id": atom.profession_id,
        "score_percentage": score_percentage,
        "is_completed": progress.is_completed,
        "requires_retake": progress.requires_retake,
        "passed": passed,
        "is_correct": is_correct,
        "correct_index": quiz_model.correct_index,
        "explanation": quiz_model.explanation,
        "last_attempted_at": progress.last_attempted_at,
    }
