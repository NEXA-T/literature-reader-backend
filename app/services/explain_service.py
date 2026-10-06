import asyncio

from app.schemas.explain import ExplainRequest, ExplainResponse


async def explain_text(payload: ExplainRequest) -> ExplainResponse:
    await asyncio.sleep(1)
    return ExplainResponse(
        translation=f"[mock] Перевод: {payload.selected_text}",
        context_meaning=(
            "Это заглушка для проверки контракта API"
            f"Контекст получен: {bool(payload.context)}"
            f"Книга: {payload.book_title or 'не указана'}"
        ),
        slang_or_etymology=None,
        image_prompt="A mock scene placeholder in English",
    )