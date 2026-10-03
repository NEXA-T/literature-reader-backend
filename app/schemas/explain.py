from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    selected_text: str = Field(..., description="Выделенный пользователем фрагмент")
    context: str | None = Field(None, description="Абзац/контекст вокруг выделения")
    book_id: str | None = None


class ExplainResponse(BaseModel):
    term: str
    definition: str
    explanation: str
    examples: list[str] = []