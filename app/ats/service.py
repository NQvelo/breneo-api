"""Service layer used by the ATS API and by other app code."""

from __future__ import annotations

import logging

from app.ats.config import get_int_setting
from app.ats.exceptions import (
    EmptyResumeError,
    JobDescriptionMissing,
    JobNotFound,
    ResumeTooLarge,
)
from app.ats.extractor.engine import extract_resume
from app.ats.matcher.engine import score_resume
from app.ats.parsers import read_resume
from app.ats.schemas.match import MatchResult
from app.ats.schemas.resume import ResumeData

logger = logging.getLogger(__name__)

_DEFAULT_MAX_BYTES = 10 * 1024 * 1024


def parse_uploaded_resume(uploaded_file) -> tuple[ResumeData, str]:
    """Read an uploaded resume and return structured data plus cleaned source text."""
    data, filename = read_upload(uploaded_file)
    document = read_resume(data, filename)
    resume = extract_resume(document.text, filename=document.filename)
    resume.parser_method = document.method
    resume.warnings = list(dict.fromkeys([*document.warnings, *resume.warnings]))
    logger.info(
        "Parsed resume file=%s method=%s pages=%s chars=%s extraction=%s",
        document.filename,
        document.method,
        document.page_count,
        len(document.text),
        resume.extraction_method,
    )
    return resume, document.text


def match_resume(
    resume: ResumeData,
    *,
    job_id: str | None = None,
    job_description: str = "",
    job_title: str = "",
    source_text: str = "",
) -> MatchResult:
    """Score ``resume`` against a free-text job description and/or a Job row."""
    text, title, skills = resolve_job_context(job_id, job_description, job_title)
    return score_resume(
        resume,
        text,
        job_title=title,
        required_skills=skills,
        source_text=source_text,
    )


def resolve_job_context(
    job_id: str | None,
    job_description: str,
    job_title: str,
) -> tuple[str, str, list[str]]:
    """Build matcher input from ``Job`` plus any description supplied by the client."""
    parts: list[str] = []
    skills: list[str] = []
    title = (job_title or "").strip()
    if job_id:
        from app.models import Job

        job = Job.objects.filter(pk=str(job_id)).prefetch_related("required_skills").first()
        if job is None:
            raise JobNotFound("Job not found.")
        title = title or (job.title or "")
        if job.title:
            parts.append(job.title)
        description = (job.description or "").strip()
        if description and description != "No description":
            parts.append(description)
        skills = [name for name in job.required_skills.values_list("name", flat=True) if name]
        if skills:
            parts.append("Required skills: " + ", ".join(skills))
    extra = (job_description or "").strip()
    if extra:
        parts.append(extra)
    text = "\n".join(part for part in parts if part).strip()
    if not text:
        raise JobDescriptionMissing("Provide a job_description or a job_id that has a description.")
    return text, title, skills


def read_upload(uploaded_file) -> tuple[bytes, str]:
    max_bytes = get_int_setting("ATS_MAX_UPLOAD_BYTES", _DEFAULT_MAX_BYTES)
    filename = getattr(uploaded_file, "name", "") or "resume"
    size = getattr(uploaded_file, "size", None)
    if size is not None and int(size) > max_bytes:
        raise ResumeTooLarge(_too_large_message(max_bytes))
    data = uploaded_file.read()
    if len(data) > max_bytes:
        raise ResumeTooLarge(_too_large_message(max_bytes))
    if not data:
        raise EmptyResumeError("The uploaded file is empty.")
    return data, filename


def _too_large_message(max_bytes: int) -> str:
    megabytes = max(1, max_bytes // (1024 * 1024))
    return f"Resume files must be {megabytes} MB or smaller."
