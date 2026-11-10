"""Pydantic models for bilingual resume extraction."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ats.textutil import detect_language


class BilingualText(BaseModel):
    """One fact stored in Latin (``en``) and Mkhedruli (``ka``)."""

    model_config = ConfigDict(extra="ignore")

    en: str = ""
    ka: str = ""

    @field_validator("en", "ka", mode="before")
    @classmethod
    def _blank(cls, value):
        if value is None:
            return ""
        return str(value).strip()

    def is_empty(self) -> bool:
        return not self.en and not self.ka

    def combined(self) -> str:
        parts = [self.en, self.ka]
        return "\n".join(part for part in parts if part)


class SkillItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name_en: str = ""
    name_ka: str = ""

    @field_validator("name_en", "name_ka", mode="before")
    @classmethod
    def _blank(cls, value):
        if value is None:
            return ""
        return str(value).strip()

    def is_empty(self) -> bool:
        return not self.name_en and not self.name_ka


_ONGOING_MARKERS = {
    "present",
    "current",
    "now",
    "ongoing",
    "დღემდე",
    "მიმდინარე",
    "დღეს",
}
_EMPTY_DATES = {"", "null", "none", "n/a", "na", "-"}


def _mark_ongoing(data):
    if not isinstance(data, dict):
        return data
    end = data.get("end_date")
    if isinstance(end, str) and end.strip().lower() in _ONGOING_MARKERS:
        data = dict(data)
        data["end_date"] = None
        data["is_current"] = True
    return data


_MONTHS = {
    "jan": "01",
    "january": "01",
    "feb": "02",
    "february": "02",
    "mar": "03",
    "march": "03",
    "apr": "04",
    "april": "04",
    "may": "05",
    "jun": "06",
    "june": "06",
    "jul": "07",
    "july": "07",
    "aug": "08",
    "august": "08",
    "sep": "09",
    "sept": "09",
    "september": "09",
    "oct": "10",
    "october": "10",
    "nov": "11",
    "november": "11",
    "dec": "12",
    "december": "12",
}


def _clean_date(value):
    if value is None:
        return None
    text = str(value).strip().replace("—", "-").replace("–", "-").replace(".", "/")
    if text.lower() in _EMPTY_DATES or text.lower() in _ONGOING_MARKERS:
        return None
    text = _fix_ocr_date(text)
    normalized = _normalize_date(text)
    return normalized or text


def _fix_ocr_date(text: str) -> str:
    """Turn obvious OCR digit mistakes inside a date into digits."""
    if not re.search(r"\d", text):
        return text
    chars: list[str] = []
    for char in text:
        previous = chars[-1] if chars else ""
        if char in "Oo" and previous.isdigit():
            chars.append("0")
        elif char in "Il|" and previous.isdigit():
            chars.append("1")
        else:
            chars.append(char)
    return "".join(chars)


def _normalize_date(text: str) -> str | None:
    month_name = re.fullmatch(r"([A-Za-z]{3,9})\s+(\d{4})", text)
    if month_name and month_name.group(1).lower() in _MONTHS:
        return f"{month_name.group(2)}-{_MONTHS[month_name.group(1).lower()]}"
    month_first = re.fullmatch(r"(\d{1,2})/(\d{4})", text)
    if month_first:
        month = int(month_first.group(1))
        if 1 <= month <= 12:
            return f"{month_first.group(2)}-{month:02d}"
    year_first = re.fullmatch(r"(\d{4})/(\d{1,2})", text)
    if year_first:
        month = int(year_first.group(2))
        if 1 <= month <= 12:
            return f"{year_first.group(1)}-{month:02d}"
    year_only = re.fullmatch(r"(?:19|20)\d{2}", text)
    if year_only:
        return text
    year_month = re.fullmatch(r"((?:19|20)\d{2})-(\d{1,2})(?:-\d{1,2})?", text)
    if year_month:
        month = int(year_month.group(2))
        if 1 <= month <= 12:
            return f"{year_month.group(1)}-{month:02d}"
    return None


def _clean_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


class WorkExperienceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: BilingualText = Field(default_factory=BilingualText)
    company: BilingualText = Field(default_factory=BilingualText)
    location: BilingualText = Field(default_factory=BilingualText)
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    employment_type: str = ""
    description: BilingualText = Field(default_factory=BilingualText)

    @model_validator(mode="before")
    @classmethod
    def _ongoing(cls, data):
        return _mark_ongoing(data)

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _dates(cls, value):
        return _clean_date(value)

    @field_validator("is_current", mode="before")
    @classmethod
    def _bool(cls, value):
        return _clean_bool(value)

    @field_validator("employment_type", mode="before")
    @classmethod
    def _employment_type(cls, value):
        if value is None:
            return ""
        return str(value).strip()


class EducationItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    school: BilingualText = Field(default_factory=BilingualText)
    degree: BilingualText = Field(default_factory=BilingualText)
    field_of_study: BilingualText = Field(default_factory=BilingualText)
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False

    @model_validator(mode="before")
    @classmethod
    def _ongoing(cls, data):
        return _mark_ongoing(data)

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _dates(cls, value):
        return _clean_date(value)

    @field_validator("is_current", mode="before")
    @classmethod
    def _bool(cls, value):
        return _clean_bool(value)


class OtherSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: BilingualText = Field(default_factory=BilingualText)
    content: BilingualText = Field(default_factory=BilingualText)


class ResumeData(BaseModel):
    """Structured resume. Bilingual fields keep Latin and Mkhedruli side by side."""

    model_config = ConfigDict(extra="ignore")

    full_name: BilingualText = Field(default_factory=BilingualText)
    headline: BilingualText = Field(default_factory=BilingualText)
    email: str | None = None
    phone: str | None = None
    location: BilingualText = Field(default_factory=BilingualText)
    summary: BilingualText = Field(default_factory=BilingualText)
    skills: list[SkillItem] = Field(default_factory=list)
    languages: list[SkillItem] = Field(default_factory=list)
    work_experience: list[WorkExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certifications: list[BilingualText] = Field(default_factory=list)
    projects: list[BilingualText] = Field(default_factory=list)
    awards: list[BilingualText] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    other_sections: list[OtherSection] = Field(default_factory=list)
    language: Literal["en", "ka", "mixed", "unknown"] = "unknown"
    extraction_method: Literal["llm", "heuristic"] = "heuristic"
    parser_method: str = ""
    source_filename: str = ""
    warnings: list[str] = Field(default_factory=list)
    parsing_metadata: dict = Field(default_factory=dict)

    @field_validator("email", "phone", mode="before")
    @classmethod
    def _optional_text(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        if text.lower() in {"", "null", "none", "n/a"}:
            return None
        return text

    @field_validator("language", mode="before")
    @classmethod
    def _language(cls, value):
        if value is None:
            return "unknown"
        text = str(value).strip().lower()
        aliases = {
            "english": "en",
            "georgian": "ka",
            "geo": "ka",
            "kat": "ka",
            "mkhedruli": "ka",
            "mix": "mixed",
            "bilingual": "mixed",
        }
        text = aliases.get(text, text)
        if text not in {"en", "ka", "mixed", "unknown"}:
            return "unknown"
        return text

    @field_validator("extraction_method", mode="before")
    @classmethod
    def _method(cls, value):
        text = str(value or "heuristic").strip().lower()
        return text if text in {"llm", "heuristic"} else "heuristic"

    @field_validator("skills", "languages", mode="before")
    @classmethod
    def _skill_list(cls, value):
        if not value:
            return []
        items = []
        for item in value:
            if isinstance(item, str):
                items.append(_skill_dict_from_string(item))
            elif isinstance(item, dict) or isinstance(item, SkillItem):
                items.append(item)
        return items

    @field_validator("certifications", "projects", "awards", mode="before")
    @classmethod
    def _certifications(cls, value):
        if not value:
            return []
        items = []
        for item in value:
            if isinstance(item, str):
                items.append(_bilingual_dict_from_string(item))
            elif isinstance(item, dict) or isinstance(item, BilingualText):
                items.append(item)
        return items

    @field_validator("links", mode="before")
    @classmethod
    def _links(cls, value):
        if not value:
            return []
        links = []
        for item in value:
            text = str(item or "").strip().rstrip(".,);")
            if text and text not in links:
                links.append(text)
        return links

    @field_validator("other_sections", mode="before")
    @classmethod
    def _other_sections(cls, value):
        if not value:
            return []
        items = []
        for item in value:
            if isinstance(item, str):
                items.append({"content": _bilingual_dict_from_string(item)})
            elif isinstance(item, dict) or isinstance(item, OtherSection):
                items.append(item)
        return items

    @field_validator("warnings", mode="before")
    @classmethod
    def _warnings(cls, value):
        if not value:
            return []
        return [str(item) for item in value if str(item).strip()]

    @field_validator("parsing_metadata", mode="before")
    @classmethod
    def _metadata(cls, value):
        return value if isinstance(value, dict) else {}

    def to_match_text(self) -> str:
        """Flat text used by keyword and TF-IDF scoring."""
        parts: list[str] = [
            self.full_name.combined(),
            self.headline.combined(),
            self.summary.combined(),
            self.location.combined(),
        ]
        for skill in [*self.skills, *self.languages]:
            parts.extend([skill.name_en, skill.name_ka])
        for role in self.work_experience:
            parts.extend(
                [
                    role.title.combined(),
                    role.company.combined(),
                    role.location.combined(),
                    role.description.combined(),
                    role.start_date or "",
                    role.end_date or "",
                ]
            )
        for school in self.education:
            parts.extend(
                [
                    school.school.combined(),
                    school.degree.combined(),
                    school.field_of_study.combined(),
                ]
            )
        for cert in [*self.certifications, *self.projects, *self.awards]:
            parts.append(cert.combined())
        parts.extend(self.links)
        for section in self.other_sections:
            parts.extend([section.title.combined(), section.content.combined()])
        return "\n".join(part for part in parts if part and part.strip())


def _bilingual_dict_from_string(text: str) -> dict:
    cleaned = text.strip()
    if detect_language(cleaned) == "ka":
        return {"en": "", "ka": cleaned}
    return {"en": cleaned, "ka": ""}


def _skill_dict_from_string(text: str) -> dict:
    cleaned = text.strip()
    if detect_language(cleaned) == "ka":
        return {"name_en": "", "name_ka": cleaned}
    return {"name_en": cleaned, "name_ka": ""}


def missing_fields(resume: ResumeData) -> list[str]:
    """Paths that a complete bilingual CV must contain."""
    missing: list[str] = []

    def require_text(path: str, value: BilingualText) -> None:
        if not (value.en or "").strip():
            missing.append(f"{path}.en")
        if not (value.ka or "").strip():
            missing.append(f"{path}.ka")

    def require_dates(path: str, start: str | None, end: str | None, is_current: bool) -> None:
        if not (start or "").strip():
            missing.append(f"{path}.start_date")
        if not is_current and not (end or "").strip():
            missing.append(f"{path}.end_date")

    require_text("full_name", resume.full_name)
    require_text("headline", resume.headline)
    if not (resume.email or "").strip():
        missing.append("email")
    if not (resume.phone or "").strip():
        missing.append("phone")
    require_text("location", resume.location)
    require_text("summary", resume.summary)

    if not resume.skills:
        missing.append("skills")
    for index, skill in enumerate(resume.skills):
        if not skill.name_en.strip():
            missing.append(f"skills[{index}].name_en")
        if not skill.name_ka.strip():
            missing.append(f"skills[{index}].name_ka")

    for index, language in enumerate(resume.languages):
        if not language.name_en.strip():
            missing.append(f"languages[{index}].name_en")
        if not language.name_ka.strip():
            missing.append(f"languages[{index}].name_ka")

    if not resume.work_experience:
        missing.append("work_experience")
    for index, role in enumerate(resume.work_experience):
        prefix = f"work_experience[{index}]"
        require_text(f"{prefix}.title", role.title)
        require_text(f"{prefix}.company", role.company)
        require_text(f"{prefix}.description", role.description)
        require_dates(prefix, role.start_date, role.end_date, role.is_current)

    if not resume.education:
        missing.append("education")
    for index, school in enumerate(resume.education):
        prefix = f"education[{index}]"
        require_text(f"{prefix}.school", school.school)
        require_text(f"{prefix}.degree", school.degree)
        require_dates(prefix, school.start_date, school.end_date, school.is_current)

    for index, item in enumerate(resume.certifications):
        require_text(f"certifications[{index}]", item)

    if resume.language not in {"en", "ka", "mixed"}:
        missing.append("language")
    return missing


def _copy_blank(en: str, ka: str) -> tuple[str, str]:
    en = (en or "").strip()
    ka = (ka or "").strip()
    if en and not ka:
        return en, en
    if ka and not en:
        return ka, ka
    return en, ka


def fill_blank_translations(resume: ResumeData) -> ResumeData:
    """Copy a filled language into the empty one so a one-language fact still counts."""
    resume.full_name.en, resume.full_name.ka = _copy_blank(resume.full_name.en, resume.full_name.ka)
    resume.headline.en, resume.headline.ka = _copy_blank(resume.headline.en, resume.headline.ka)
    resume.location.en, resume.location.ka = _copy_blank(resume.location.en, resume.location.ka)
    resume.summary.en, resume.summary.ka = _copy_blank(resume.summary.en, resume.summary.ka)
    for skill in resume.skills:
        skill.name_en, skill.name_ka = _copy_blank(skill.name_en, skill.name_ka)
    for language in resume.languages:
        language.name_en, language.name_ka = _copy_blank(language.name_en, language.name_ka)
    for role in resume.work_experience:
        role.title.en, role.title.ka = _copy_blank(role.title.en, role.title.ka)
        role.company.en, role.company.ka = _copy_blank(role.company.en, role.company.ka)
        role.location.en, role.location.ka = _copy_blank(role.location.en, role.location.ka)
        role.description.en, role.description.ka = _copy_blank(role.description.en, role.description.ka)
    for school in resume.education:
        school.school.en, school.school.ka = _copy_blank(school.school.en, school.school.ka)
        school.degree.en, school.degree.ka = _copy_blank(school.degree.en, school.degree.ka)
        school.field_of_study.en, school.field_of_study.ka = _copy_blank(
            school.field_of_study.en, school.field_of_study.ka
        )
    for item in [*resume.certifications, *resume.projects, *resume.awards]:
        item.en, item.ka = _copy_blank(item.en, item.ka)
    for section in resume.other_sections:
        section.title.en, section.title.ka = _copy_blank(section.title.en, section.title.ka)
        section.content.en, section.content.ka = _copy_blank(section.content.en, section.content.ka)
    return resume


def format_validation_error(exc) -> str:
    """Short, client-safe summary of a Pydantic validation error."""
    parts = []
    for error in exc.errors():
        loc = ".".join(str(piece) for piece in error.get("loc", ()))
        message = error.get("msg", "Invalid value.")
        parts.append(f"{loc}: {message}" if loc else message)
    return "; ".join(parts[:8]) or "Invalid resume payload."
