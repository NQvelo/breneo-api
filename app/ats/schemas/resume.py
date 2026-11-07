"""Pydantic models for bilingual resume extraction."""

from __future__ import annotations

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


def _clean_date(value):
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _EMPTY_DATES or text.lower() in _ONGOING_MARKERS:
        return None
    return text


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
    language: Literal["en", "ka", "mixed", "unknown"] = "unknown"
    extraction_method: Literal["llm", "heuristic"] = "heuristic"
    parser_method: str = ""
    source_filename: str = ""
    warnings: list[str] = Field(default_factory=list)

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

    @field_validator("certifications", mode="before")
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

    @field_validator("warnings", mode="before")
    @classmethod
    def _warnings(cls, value):
        if not value:
            return []
        return [str(item) for item in value if str(item).strip()]

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
        for cert in self.certifications:
            parts.append(cert.combined())
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


def format_validation_error(exc) -> str:
    """Short, client-safe summary of a Pydantic validation error."""
    parts = []
    for error in exc.errors():
        loc = ".".join(str(piece) for piece in error.get("loc", ()))
        message = error.get("msg", "Invalid value.")
        parts.append(f"{loc}: {message}" if loc else message)
    return "; ".join(parts[:8]) or "Invalid resume payload."
