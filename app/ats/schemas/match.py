"""Pydantic models for ATS match results."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ScoreBreakdown(BaseModel):
    model_config = ConfigDict(extra="ignore")

    keyword_overlap: float = 0.0
    experience: float = 0.0
    semantic_similarity: float = 0.0
    overall: float = 0.0


class MatchWeights(BaseModel):
    model_config = ConfigDict(extra="ignore")

    keyword_overlap: float = 0.45
    experience: float = 0.25
    semantic_similarity: float = 0.30


class MatchResult(BaseModel):
    """Score of one resume against one job description."""

    model_config = ConfigDict(extra="ignore")

    scores: ScoreBreakdown
    weights: MatchWeights = Field(default_factory=MatchWeights)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    candidate_years_experience: float = 0.0
    required_years_experience: float | None = None
    resume_language: str = "unknown"
    job_language: str = "unknown"
    recommendations: list[str] = Field(default_factory=list)
    method: str = "tfidf+keywords+experience"
