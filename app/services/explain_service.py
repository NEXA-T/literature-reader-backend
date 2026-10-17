from app.schemas.explain import ExplainRequest, ExplainResponse
from app.services.gigachat_client import GigaChatClient, GigaChatError
from app.services.gigachat_settings import GigaChatSettings


async def explain_text(payload: ExplainRequest) -> ExplainResponse:
    """Вызывает GigaChat для анализа текста"""
    settings = GigaChatSettings()

    # Создаем клиент на время запроса
    async with GigaChatClient(settings) as client:
        # Метод analyze_text возвращает объект Pydantic (AIAnalysis)
        result = await client.analyze_text(
            selected_text=payload.selected_text,
            context=payload.context,
            book_title=payload.book_title
        )

        # Преобразуем AIAnalysis в ExplainResponse для API
        return ExplainResponse(
            translation=result.translation,
            context_meaning=result.context_meaning,
            slang_or_etymology=result.slang_or_etymology,
            image_prompt=result.image_prompt
        )