from app.schemas.explain import ExplainRequest, ExplainResponse


async def explain_text(payload: ExplainRequest) -> ExplainResponse:
    """Mock-реализация. В следующем спринте здесь будет вызов GigaChat"""
    return ExplainResponse(
        term=payload.selected_text[:64],
        definition="Mock-определение (будет заменено на ответ GigaChat)",
        explanation=(
            "заглушка для проверки контракта API "
            f"Контекст получен: {bool(payload.context)}"
        ),
        examples=["Пример 1", "Пример 2"],
    )