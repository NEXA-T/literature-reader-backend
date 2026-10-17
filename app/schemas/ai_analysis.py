"""Strict AI boundary models for the four-field contract in issue #11."""
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnalysisInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    selected_text: str = Field(min_length=1)
    context: str
    book_title: str | None = None

    @field_validator("selected_text")
    @classmethod
    def selection_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("selected_text must not be blank")
        return value


class AIAnalysis(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    translation: str = Field(min_length=1)
    context_meaning: str = Field(min_length=1)
    # Required keys; JSON null is a valid value, absence is not.
    slang_or_etymology: str | None
    image_prompt: str | None

    @field_validator("translation", "context_meaning")
    @classmethod
    def analysis_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("analysis must not be blank")
        return value

    @field_validator("slang_or_etymology", "image_prompt")
    @classmethod
    def actual_null_not_placeholder(cls, value: str | None) -> str | None:
        if value is not None and value.strip().lower() in ("", "null", "none"):
            raise ValueError("use JSON null rather than a placeholder string")
        return value
