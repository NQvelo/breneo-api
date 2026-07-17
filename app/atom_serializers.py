from rest_framework import serializers

from .atom_service import build_path_atoms_preview, list_profession_atoms
from .models import Atom, UserProgress


class AtomQuizClientSerializer(serializers.Serializer):
    """Quiz payload for clients — options only (no answer key before submit)."""

    options = serializers.ListField(child=serializers.CharField())


class AtomPathItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    sequence_order = serializers.IntegerField()
    status = serializers.ChoiceField(choices=["locked", "available", "completed"])


class ProfessionAtomPathSerializer(serializers.Serializer):
    profession_id = serializers.IntegerField()
    profession_title = serializers.CharField()
    atoms = AtomPathItemSerializer(many=True)
    current_atom_id = serializers.IntegerField(allow_null=True)
    completed_count = serializers.IntegerField()
    total_count = serializers.IntegerField()


class AtomDetailSerializer(serializers.ModelSerializer):
    profession_id = serializers.IntegerField(source="profession.id", read_only=True)
    profession_title = serializers.CharField(source="profession.title", read_only=True)
    quiz = serializers.SerializerMethodField()
    total_atoms = serializers.SerializerMethodField()
    path_atoms = serializers.SerializerMethodField()

    class Meta:
        model = Atom
        fields = [
            "id",
            "profession_id",
            "profession_title",
            "title",
            "sequence_order",
            "content_cards",
            "quiz",
            "total_atoms",
            "path_atoms",
        ]

    def get_quiz(self, obj: Atom) -> dict:
        quiz_data = obj.quiz_data if isinstance(obj.quiz_data, dict) else {}
        options = quiz_data.get("options", [])
        return AtomQuizClientSerializer({"options": options}).data

    def get_total_atoms(self, obj: Atom) -> int:
        return Atom.objects.filter(profession_id=obj.profession_id).count()

    def get_path_atoms(self, obj: Atom) -> list[dict]:
        return build_path_atoms_preview(list_profession_atoms(obj.profession))


class AtomSubmitSerializer(serializers.Serializer):
    selected_option_index = serializers.IntegerField(min_value=0, max_value=2)


class AtomSubmitResultSerializer(serializers.Serializer):
    atom_id = serializers.IntegerField()
    profession_id = serializers.IntegerField()
    score_percentage = serializers.FloatField()
    is_completed = serializers.BooleanField()
    requires_retake = serializers.BooleanField()
    passed = serializers.BooleanField()
    is_correct = serializers.BooleanField()
    correct_index = serializers.IntegerField()
    explanation = serializers.CharField()
    last_attempted_at = serializers.DateTimeField()


class UserProgressSerializer(serializers.ModelSerializer):
    atom_id = serializers.IntegerField(source="atom.id", read_only=True)

    class Meta:
        model = UserProgress
        fields = [
            "atom_id",
            "score_percentage",
            "is_completed",
            "requires_retake",
            "last_attempted_at",
        ]
