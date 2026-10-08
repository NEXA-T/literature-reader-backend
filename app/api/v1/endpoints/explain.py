from fastapi import APIRouter
from app.schemas.explain import ExplainRequest, ExplainResponse
from app.services.explain_service import explain_text

router = APIRouter(prefix="/explain", tags=["explain"])


@router.post("", response_model=ExplainResponse)
async def explain(payload: ExplainRequest) -> ExplainResponse:
    return await explain_text(payload)