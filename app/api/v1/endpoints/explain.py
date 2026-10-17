from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.explain import ExplainRequest, ExplainResponse
from app.services.explain_service import explain_text
from app.services.gigachat_client import (
    GigaChatUnavailableError,
    GigaChatResponseError,
    GigaChatConfigurationError
)

router = APIRouter(prefix="/explain", tags=["explain"])


@router.post("", response_model=ExplainResponse)
async def explain(payload: ExplainRequest):
    try:
        return await explain_text(payload)
    except GigaChatConfigurationError as e:
        return JSONResponse(
            status_code=503,
            content={"error": f"Ошибка конфигурации сервера: {str(e)}"}
        )
    except GigaChatUnavailableError as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"Нейросеть недоступна: {str(e)}"}
        )
    except GigaChatResponseError as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"Ошибка ответа нейросети: {str(e)}"}
        )