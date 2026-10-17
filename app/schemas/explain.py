from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    selected_text: str = Field(
        ...,
        description="Выделенный фрагмент: слово, фраза или идиома",
        examples=["горе от ума"],
    )
    context: str = Field(
        ...,
        description="Текст абзаца, в котором встретилась фраза",
        examples=["Чацкий произносит монолог о том, что горе от ума..."],
    )
    book_title: str | None = Field(
        None,
        description="Название книги для понимания сеттинга и эпохи",
        examples=["Горе от ума"],
    )


class ExplainResponse(BaseModel):
    translation: str = Field(
        ...,
        description="Контекстный перевод фразы на русский язык",
        examples=["Горе от ума"],
    )
    context_meaning: str = Field(
        ...,
        description="Объяснение скрытого смысла, метафоры или подтекста",
        examples=["Идиома означает, что чрезмерный ум приносит страдания..."],
    )
    slang_or_etymology: str | None = Field(
        None,
        description="Этимология, сленг или культурная отсылка (если применимо)",
    )
    image_prompt: str | None = Field(
        None,
        description="Краткое описание визуальной сцены на английском (задел под генерацию картинки)",
        examples=["A melancholic Russian nobleman in 19th century attire..."],
    )


class ErrorResponse(BaseModel):
    error: str = Field(
        ...,
        description="Текст ошибки для пользователя",
        examples=["Сервис AI-анализа временно недоступен"],
    )