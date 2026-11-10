"""ATS HTTP API.

POST /api/ats/parse/
    multipart field ``file``: a .pdf or .docx resume.
    Returns ``ResumeData``.

POST /api/ats/match/
    Either the same ``file`` upload, or JSON ``resume`` (a ResumeData object),
    plus ``job_description`` and/or ``job_id`` (a Job primary key).
    Optional ``job_title`` overrides the stored job title.
    Returns ``{"resume": ResumeData, "match": MatchResult}``.

GET /api/me/resume/
    The signed-in user's saved CV, for the profile page to render on reload.
"""

from __future__ import annotations

import logging

from pydantic import ValidationError
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from app.ats.exceptions import ResumeReaderError
from app.ats.persist import save_parsed_resume
from app.ats.schemas.resume import ResumeData, format_validation_error
from app.ats.service import match_resume, parse_uploaded_resume
from app.models import UserResume

logger = logging.getLogger(__name__)


class _AtsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _failure(self, exc: Exception):
        if isinstance(exc, ResumeReaderError):
            logger.warning("ATS request failed: %s", exc.code)
            body = {"detail": exc.message, "code": exc.code}
            missing = getattr(exc, "missing", None)
            if missing:
                body["missing"] = missing
            return Response(body, status=exc.status_code)
        if isinstance(exc, ValidationError):
            return Response(
                {"detail": format_validation_error(exc), "code": "invalid_resume"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        logger.exception("Unexpected ATS failure")
        return Response(
            {"detail": "The resume could not be processed.", "code": "internal_error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ResumeParseView(_AtsView):
    """Parse a PDF or DOCX resume into bilingual structured data."""

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"detail": "Upload a resume in the file field.", "code": "file_missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            resume, _source = parse_uploaded_resume(upload)
            save_parsed_resume(request.user, resume)
        except Exception as exc:
            return self._failure(exc)
        return Response(resume.model_dump(mode="json"))


class ResumeMatchView(_AtsView):
    """Parse a resume if needed and score it against a job description."""

    def post(self, request):
        upload = request.FILES.get("file")
        job_id = str(request.data.get("job_id") or "").strip() or None
        job_description = request.data.get("job_description") or ""
        job_title = request.data.get("job_title") or ""
        try:
            if upload is not None:
                resume, source_text = parse_uploaded_resume(upload)
            elif request.data.get("resume"):
                resume = ResumeData.model_validate(request.data.get("resume"))
                source_text = ""
            else:
                return Response(
                    {
                        "detail": "Upload a file or send a resume object.",
                        "code": "resume_missing",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            result = match_resume(
                resume,
                job_id=job_id,
                job_description=job_description,
                job_title=job_title,
                source_text=source_text,
            )
            save_parsed_resume(request.user, resume)
        except Exception as exc:
            return self._failure(exc)
        return Response(
            {
                "resume": resume.model_dump(mode="json"),
                "match": result.model_dump(mode="json"),
            }
        )


class MyResumeView(_AtsView):
    """GET /api/me/resume/ — formatted CV for the signed-in user."""

    def get(self, request):
        record = UserResume.objects.filter(user=request.user).first()
        if record is None:
            return Response({"resume": None, "source_filename": "", "updated_at": None})
        return Response(
            {
                "resume": record.data,
                "source_filename": record.source_filename,
                "updated_at": record.updated_at.isoformat(),
            }
        )
