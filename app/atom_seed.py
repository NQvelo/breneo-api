"""Idempotent seed for Atoms micro-learning content (shared by command + migration)."""

from django.db import transaction

from app.atom_schemas import validate_content_cards, validate_quiz_data
from app.data.atoms_seed_data import ATOMS_SEED
from app.models import Atom, Profession


def seed_atoms(*, clear: bool = False, stdout=None) -> dict:
    """
    Create or update professions and atoms from ATOMS_SEED.

    Matches professions by title so it works across environments with different IDs.
    Returns counts: created_professions, created_atoms, updated_atoms.
    """
    write = stdout.write if stdout else print
    titles = [entry["title"] for entry in ATOMS_SEED]
    created_professions = 0
    created_atoms = 0
    updated_atoms = 0

    with transaction.atomic():
        if clear:
            deleted, _ = Atom.objects.filter(profession__title__in=titles).delete()
            write(f"Cleared {deleted} atom-related objects.")

        for entry in ATOMS_SEED:
            profession, prof_created = Profession.objects.get_or_create(
                title=entry["title"],
                defaults={"description": entry["description"]},
            )
            if prof_created:
                created_professions += 1
                write(f"Created profession: {profession.title}")
            elif entry["description"] and profession.description != entry["description"]:
                profession.description = entry["description"]
                profession.save(update_fields=["description", "updated_at"])

            for atom_data in entry["atoms"]:
                content_cards = validate_content_cards(atom_data["content_cards"])
                quiz_data = validate_quiz_data(atom_data["quiz_data"])

                atom, atom_created = Atom.objects.update_or_create(
                    profession=profession,
                    sequence_order=atom_data["sequence_order"],
                    defaults={
                        "title": atom_data["title"],
                        "content_cards": content_cards,
                        "quiz_data": quiz_data,
                    },
                )
                if atom_created:
                    created_atoms += 1
                else:
                    updated_atoms += 1

    return {
        "created_professions": created_professions,
        "created_atoms": created_atoms,
        "updated_atoms": updated_atoms,
    }
