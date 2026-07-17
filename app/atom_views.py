from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .atom_serializers import (
    AtomDetailSerializer,
    AtomSubmitResultSerializer,
    AtomSubmitSerializer,
    ProfessionAtomPathSerializer,
)
from .atom_service import (
    get_atom_or_none,
    get_next_atom_for_user,
    get_profession_atom_path_for_user,
    submit_atom_quiz,
    user_can_access_atom,
)


class ProfessionAtomsListView(APIView):
    """
    GET /api/v1/professions/{profession_id}/atoms/

    Returns the full atom path for a profession with per-user progress status.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, profession_id: int):
        path, error_code = get_profession_atom_path_for_user(request.user, profession_id)

        if error_code == "profession_not_found":
            return Response(
                {"detail": "Profession not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if error_code == "no_atoms":
            return Response(
                {"detail": "This profession has no atoms yet."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(ProfessionAtomPathSerializer(path).data)


class ProfessionNextAtomView(APIView):
    """
    GET /api/v1/professions/{profession_id}/next-atom/

    Returns the next Atom the authenticated user should complete for the profession.
    Prerequisite atoms (lower sequence_order) must be completed first.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, profession_id: int):
        atom, error_code = get_next_atom_for_user(request.user, profession_id)

        if error_code == "profession_not_found":
            return Response(
                {"detail": "Profession not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if error_code == "no_atoms":
            return Response(
                {"detail": "This profession has no atoms yet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if error_code == "all_completed":
            return Response(
                {"detail": "You have completed all atoms for this profession."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(AtomDetailSerializer(atom).data)


class AtomDetailView(APIView):
    """
    GET /api/v1/atoms/{atom_id}/

    Returns a playable atom when the user has completed all prerequisites.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, atom_id: int):
        atom = get_atom_or_none(atom_id)
        if atom is None:
            return Response(
                {"detail": "Atom not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_atom(request.user, atom):
            return Response(
                {"detail": "Complete prerequisite atoms before opening this lesson."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(AtomDetailSerializer(atom).data)


class AtomSubmitView(APIView):
    """
    POST /api/v1/atoms/{atom_id}/submit/

    Accepts the user's quiz answer, grades it, and upserts UserProgress.
    Score >= 80% marks the atom completed; below 80% requires a retake.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    _ERROR_STATUS = {
        "atom_not_found": (status.HTTP_404_NOT_FOUND, "Atom not found."),
        "prerequisites_not_met": (
            status.HTTP_403_FORBIDDEN,
            "Complete prerequisite atoms before submitting this quiz.",
        ),
        "invalid_quiz_data": (
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Atom quiz data is misconfigured.",
        ),
        "invalid_option_index": (
            status.HTTP_400_BAD_REQUEST,
            "selected_option_index must match a quiz option (0–2).",
        ),
    }

    def post(self, request, atom_id: int):
        serializer = AtomSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = submit_atom_quiz(
                user=request.user,
                atom_id=atom_id,
                selected_option_index=serializer.validated_data["selected_option_index"],
            )
        except ValueError as exc:
            error_code = str(exc)
            http_status, detail = self._ERROR_STATUS.get(
                error_code,
                (status.HTTP_400_BAD_REQUEST, "Unable to submit quiz."),
            )
            return Response({"detail": detail}, status=http_status)

        return Response(AtomSubmitResultSerializer(result).data)
