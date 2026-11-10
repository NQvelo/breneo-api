"""Structured resume extraction through the project's Groq client, or OpenAI."""

from __future__ import annotations

import json
import logging
import re

from pydantic import ValidationError

from app.ats.config import get_setting
from app.ats.exceptions import LlmExtractionFailed, LlmNotConfigured
from app.ats.schemas.resume import ResumeData

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You extract structured resume data for an applicant tracking system.
The resume may be English, Georgian (Mkhedruli), or a mix of both, and the text may come from columns, tables, sidebars, headers, footers, or OCR.
Return one JSON object and nothing else.
Rules:
- Copy facts only from the resume. Never invent an email, phone, employer, school, date, skill, link, or job.
- Read every section even when the heading is unusual. Keep each job and each school as its own entry. Do not merge two jobs.
- Company names, job titles, school names, and descriptions must be copied character for character from the resume. Do not translate, paraphrase, summarize, or correct them.
- Put that same original text in both "en" and "ka". Do not write a translation.
- For a job description, copy the original bullet lines in order, separated by newline. Do not rewrite them into a new paragraph.
- Copy dates exactly as printed, including the month name and the words Present, Current, or დღემდე. Do not reformat "Jan 2019" into "2019-01". Set is_current true when the resume says the role or study is current, and still keep the original end text.
- Put LinkedIn, GitHub, portfolio, Behance, Dribbble, and other URLs in links.
- Put projects, awards, volunteer work, publications, and other uncommon sections in projects, awards, or other_sections. Do not discard them.
- Leave lists empty when the resume does not contain that section.
- language is "en", "ka", or "mixed".
- extraction_method must be "llm".
"""

_SKELETON = {
    "full_name": {"en": "", "ka": ""},
    "headline": {"en": "", "ka": ""},
    "email": None,
    "phone": None,
    "location": {"en": "", "ka": ""},
    "summary": {"en": "", "ka": ""},
    "skills": [{"name_en": "", "name_ka": ""}],
    "languages": [{"name_en": "", "name_ka": ""}],
    "work_experience": [
        {
            "title": {"en": "", "ka": ""},
            "company": {"en": "", "ka": ""},
            "location": {"en": "", "ka": ""},
            "start_date": None,
            "end_date": None,
            "is_current": False,
            "employment_type": "",
            "description": {"en": "", "ka": ""},
        }
    ],
    "education": [
        {
            "school": {"en": "", "ka": ""},
            "degree": {"en": "", "ka": ""},
            "field_of_study": {"en": "", "ka": ""},
            "start_date": None,
            "end_date": None,
            "is_current": False,
        }
    ],
    "certifications": [{"en": "", "ka": ""}],
    "projects": [{"en": "", "ka": ""}],
    "awards": [{"en": "", "ka": ""}],
    "links": [],
    "other_sections": [{"title": {"en": "", "ka": ""}, "content": {"en": "", "ka": ""}}],
    "language": "unknown",
    "extraction_method": "llm",
}

_CHUNK_LIMIT = 12000


def extract_with_llm(text: str, *, missing: list[str] | None = None) -> ResumeData:
    client, models = _create_client()
    chunks = _chunks(text)
    parsed = [
        _extract_chunk(client, models, chunk, index, len(chunks), missing=missing)
        for index, chunk in enumerate(chunks)
    ]
    merged = parsed[0] if len(parsed) == 1 else _merge(parsed)
    if not _is_useful(merged):
        raise LlmExtractionFailed("The model returned an empty resume.")
    merged.extraction_method = "llm"
    return merged


def _create_client():
    provider = str(get_setting("ATS_LLM_PROVIDER", "groq") or "groq").strip().lower()
    groq_key = str(get_setting("GROQ_API_KEY", "") or "").strip()
    openai_key = str(get_setting("OPENAI_API_KEY", "") or "").strip()
    if provider == "openai" and openai_key:
        from openai import OpenAI

        return OpenAI(api_key=openai_key, timeout=45.0), [_openai_model()]
    if provider != "openai" and groq_key:
        from groq import Groq

        return Groq(api_key=groq_key, timeout=45.0), _groq_models()
    if openai_key:
        from openai import OpenAI

        return OpenAI(api_key=openai_key, timeout=45.0), [_openai_model()]
    if groq_key:
        from groq import Groq

        return Groq(api_key=groq_key, timeout=45.0), _groq_models()
    raise LlmNotConfigured()


# Groq shut these down for free and developer accounts on 16 Aug 2026.
_RETIRED_GROQ_MODELS = {
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "llama3-8b-8192": "openai/gpt-oss-20b",
    "llama3-70b-8192": "openai/gpt-oss-120b",
}


def _groq_models() -> list[str]:
    primary = str(get_setting("ATS_LLM_MODEL", "openai/gpt-oss-120b") or "openai/gpt-oss-120b")
    primary = _RETIRED_GROQ_MODELS.get(primary, primary)
    models = [primary]
    fallback = "openai/gpt-oss-20b"
    if fallback not in models:
        models.append(fallback)
    return models


def _openai_model() -> str:
    model = str(get_setting("ATS_LLM_MODEL", "gpt-4o-mini") or "gpt-4o-mini")
    if model.startswith(("llama", "mixtral", "gemma")):
        return "gpt-4o-mini"
    return model


def _chunks(text: str) -> list[str]:
    cleaned = (text or "").strip()
    if len(cleaned) <= _CHUNK_LIMIT:
        return [cleaned]
    head = cleaned[:_CHUNK_LIMIT]
    tail = cleaned[-_CHUNK_LIMIT:]
    if tail in head:
        return [head]
    return [head, tail]


def _extract_chunk(
    client,
    models: list[str],
    text: str,
    index: int,
    total: int,
    *,
    missing: list[str] | None = None,
) -> ResumeData:
    part = f"This is part {index + 1} of {total} of one resume.\n" if total > 1 else ""
    repair = ""
    if missing:
        repair = (
            "A previous parse left these fields empty. Fill each one in both languages "
            "when the fact exists anywhere in the resume. Do not invent contact details, "
            "employers, schools, or dates.\n"
            f"Empty fields: {', '.join(missing)}\n"
        )
    user_prompt = (
        f"{part}{repair}"
        "Fill this JSON shape from the resume. Copy company names, descriptions, and dates exactly as written. Leave a field empty when the resume does not contain it.\n"
        f"{json.dumps(_SKELETON, ensure_ascii=False)}\n\n"
        f"RESUME:\n{text}"
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    content, model_used = _complete(client, models, messages)
    try:
        return ResumeData.model_validate(_parse_json(content))
    except (ValidationError, LlmExtractionFailed, json.JSONDecodeError) as exc:
        logger.warning("Resume JSON failed validation on %s: %s", model_used, exc)
        repair = (
            "The previous JSON was rejected. Return only a corrected JSON object.\n"
            f"Problem: {exc}\n"
            f"Previous output:\n{content[:4000]}"
        )
        messages.append({"role": "assistant", "content": content[:4000]})
        messages.append({"role": "user", "content": repair})
        repaired, _model = _complete(client, [model_used], messages)
        try:
            return ResumeData.model_validate(_parse_json(repaired))
        except (ValidationError, LlmExtractionFailed, json.JSONDecodeError) as repair_exc:
            raise LlmExtractionFailed(str(repair_exc)) from repair_exc


def _complete(client, models: list[str], messages: list[dict]) -> tuple[str, str]:
    last_error: Exception | None = None
    for model in models:
        for json_mode in (True, False):
            try:
                kwargs = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": 4096,
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                response = client.chat.completions.create(**kwargs)
                content = (response.choices[0].message.content or "").strip()
                if not content:
                    raise LlmExtractionFailed("The model returned an empty response.")
                return content, model
            except Exception as exc:
                last_error = exc
                if json_mode and _json_mode_unsupported(exc):
                    logger.info("JSON mode is unsupported on %s; retrying plain text", model)
                    continue
                if _model_missing(exc):
                    logger.warning("ATS model %s is unavailable; trying the next model", model)
                    break
                logger.exception("ATS LLM call failed on model %s", model)
                raise LlmExtractionFailed("The language model could not extract this resume.") from exc
    raise LlmExtractionFailed(str(last_error or "No language model could extract this resume."))


def _parse_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise LlmExtractionFailed("The model did not return a JSON object.")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise LlmExtractionFailed("The model did not return a JSON object.")
    return payload


def _json_mode_unsupported(exc: Exception) -> bool:
    message = str(exc).lower()
    return "response_format" in message or "json_object" in message


def _model_missing(exc: Exception) -> bool:
    message = str(exc).lower()
    return "model" in message and any(token in message for token in ("not found", "does not exist", "unknown", "404"))


def _is_useful(resume: ResumeData) -> bool:
    return bool(
        resume.full_name.en
        or resume.full_name.ka
        or resume.summary.en
        or resume.summary.ka
        or resume.skills
        or resume.work_experience
        or resume.education
        or resume.email
    )


def _prefer(left: str, right: str) -> str:
    left = (left or "").strip()
    right = (right or "").strip()
    if not left:
        return right
    if not right:
        return left
    return left if len(left) >= len(right) else right


def _merge_bilingual(left, right):
    from app.ats.schemas.resume import BilingualText

    return BilingualText(en=_prefer(left.en, right.en), ka=_prefer(left.ka, right.ka))


def _merge(parts: list[ResumeData]) -> ResumeData:
    base = parts[0].model_copy(deep=True)
    for other in parts[1:]:
        base.full_name = _merge_bilingual(base.full_name, other.full_name)
        base.headline = _merge_bilingual(base.headline, other.headline)
        base.location = _merge_bilingual(base.location, other.location)
        base.summary = _merge_bilingual(base.summary, other.summary)
        base.email = base.email or other.email
        base.phone = base.phone or other.phone
        base.skills = _dedupe_skills([*base.skills, *other.skills])
        base.languages = _dedupe_skills([*base.languages, *other.languages])
        base.work_experience = _dedupe_roles([*base.work_experience, *other.work_experience])
        base.education = _dedupe_education([*base.education, *other.education])
        base.certifications = _dedupe_text([*base.certifications, *other.certifications])
        if base.language != other.language:
            base.language = "mixed"
        base.warnings = list(dict.fromkeys([*base.warnings, *other.warnings, "llm_chunked"]))
    return base


def _dedupe_skills(items):
    seen = set()
    kept = []
    for item in items:
        if item.is_empty():
            continue
        key = (item.name_en.casefold(), item.name_ka)
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return kept


def _dedupe_roles(items):
    seen = set()
    kept = []
    for item in items:
        key = (
            item.title.en.casefold(),
            item.title.ka,
            item.company.en.casefold(),
            item.company.ka,
            item.start_date or "",
        )
        if key in seen:
            continue
        if item.title.is_empty() and item.company.is_empty() and item.description.is_empty():
            continue
        seen.add(key)
        kept.append(item)
    return kept


def _dedupe_education(items):
    seen = set()
    kept = []
    for item in items:
        key = (item.school.en.casefold(), item.school.ka, item.degree.en.casefold(), item.degree.ka)
        if key in seen:
            continue
        if item.school.is_empty() and item.degree.is_empty():
            continue
        seen.add(key)
        kept.append(item)
    return kept


def _dedupe_text(items):
    seen = set()
    kept = []
    for item in items:
        key = (item.en.casefold(), item.ka)
        if key in seen or item.is_empty():
            continue
        seen.add(key)
        kept.append(item)
    return kept
