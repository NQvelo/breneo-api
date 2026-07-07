"""Pydantic schemas for Atom JSONB fields (content_cards, quiz_data)."""

from enum import Enum

from pydantic import BaseModel, Field, TypeAdapter, ValidationError, field_validator, model_validator


class ContentType(str, Enum):
    MARKDOWN = "markdown"
    CODE = "code"
    MATH_FORMULA = "math_formula"
    RICH_TEXT = "rich_text"


class ContentCardSchema(BaseModel):
    card_index: int = Field(ge=0)
    content_type: ContentType
    content_body: str = Field(min_length=1)


class QuizDataSchema(BaseModel):
    options: list[str] = Field(min_length=3, max_length=3)
    correct_index: int = Field(ge=0, le=2)
    explanation: str = Field(min_length=1)

    @field_validator("options")
    @classmethod
    def validate_options_not_empty(cls, options: list[str]) -> list[str]:
        if any(not option.strip() for option in options):
            raise ValueError("Each quiz option must be a non-empty string.")
        return options


class ContentCardsListSchema(BaseModel):
    cards: list[ContentCardSchema] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_card_indices(self) -> "ContentCardsListSchema":
        indices = [card.card_index for card in self.cards]
        if len(indices) != len(set(indices)):
            raise ValueError("content_cards must have unique card_index values.")
        expected = list(range(len(self.cards)))
        if sorted(indices) != expected:
            raise ValueError(
                "content_cards card_index values must be sequential starting at 0."
            )
        return self


_content_cards_adapter = TypeAdapter(list[ContentCardSchema])
_quiz_data_adapter = TypeAdapter(QuizDataSchema)


def validate_content_cards(data: object) -> list[dict]:
    """Validate and normalize content_cards JSONB payload."""
    if not isinstance(data, list):
        raise ValidationError.from_exception_data(
            "ContentCards",
            [{"type": "list_type", "loc": (), "input": data, "ctx": {"error": "Must be a list."}}],
        )
    parsed = ContentCardsListSchema(cards=_content_cards_adapter.validate_python(data))
    return [card.model_dump(mode="json") for card in parsed.cards]


def validate_quiz_data(data: object) -> dict:
    """Validate and normalize quiz_data JSONB payload."""
    if not isinstance(data, dict):
        raise ValidationError.from_exception_data(
            "QuizData",
            [{"type": "dict_type", "loc": (), "input": data, "ctx": {"error": "Must be an object."}}],
        )
    return _quiz_data_adapter.validate_python(data).model_dump(mode="json")


def format_pydantic_errors(exc: ValidationError) -> list[str]:
    """Convert Pydantic errors into human-readable strings for API responses."""
    messages = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", ()))
        msg = error.get("msg", "Invalid value.")
        messages.append(f"{loc}: {msg}" if loc else msg)
    return messages


def default_content_cards() -> list:
    """Callable default for Atom.content_cards (returns a new empty list)."""
    return []


def default_quiz_data() -> dict:
    """Callable default for Atom.quiz_data (returns a new empty dict)."""
    return {}
