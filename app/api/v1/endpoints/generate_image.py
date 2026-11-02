from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from app.schemas.generate_image import GenerateImageRequest, GenerateImageResponse
from app.services.generate_image_service import generate_image
from app.services.image_provider import ImageProviderError

router = APIRouter(prefix="/generate-image", tags=["image"])


@router.post("", response_model=GenerateImageResponse)
async def generate(payload: GenerateImageRequest):
    try:
        return await generate_image(payload)
    except ImageProviderError as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"Генератор недоступен: {str(e)}"}
        )
    except Exception as e:
        logger.error(f"Ошибка при генерации: {type(e).__name__}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Внутренняя ошибка сервера при генерации изображения"}
        )