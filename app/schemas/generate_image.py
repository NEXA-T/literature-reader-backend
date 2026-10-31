from pydantic import BaseModel, Field, field_validator


class GenerateImageRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Текст промпта для генерации (от 5 до 500 символов)",
        examples=["atmospheric oil painting of a Victorian street in fog"],
    )
    style: str | None = Field(
        None,
        max_length=100,
        description="Опциональный стиль (oil painting, watercolor, anime)",
    )

    @field_validator("prompt")
    @classmethod
    def prompt_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("prompt не должен состоять из пробелов")
        return v


class GenerateImageResponse(BaseModel):
    image_url: str = Field(
        ...,
        description="Прямая ссылка на сгенерированный файл",
        examples=["https://api.example.com/static/generated_123.jpg"],
    )
    prompt_used: str = Field(
        ...,
        description="Промпт, который фактически использован",
    )