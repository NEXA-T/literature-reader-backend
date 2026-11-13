import time
import uuid
from pathlib import Path
from loguru import logger
from app.services.gigachat_settings import GigaChatSettings
from app.services.image_provider import GigaChatImageProvider
from app.services.image_generation_client import ImageGenerationClient
from app.schemas.generate_image import GenerateImageRequest, GenerateImageResponse
from app.services.image_cache import _IMAGE_CACHE


UPLOAD_DIR = Path("static/generated_images")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def generate_image(payload: GenerateImageRequest) -> GenerateImageResponse:
    settings = GigaChatSettings()
    provider = GigaChatImageProvider(settings)

    # Если пользователь передал style, добавляем его к промпту
    final_prompt = payload.prompt
    if payload.style:
        final_prompt += f", style: {payload.style}"

    cache_key = f"{provider.model}\0{final_prompt}"
    cached = _IMAGE_CACHE.get(cache_key)
    if cached:
        logger.info(f"Image generation: CACHE HIT | prompt='{final_prompt[:30]}...'")
        return GenerateImageResponse(
            image_url=cached.image_url,
            prompt_used=cached.prompt_used
        )

    start_time = time.perf_counter()
    logger.info(f"Starting GigaChat generation for prompt: '{final_prompt[:30]}...'")

    async with ImageGenerationClient(provider, max_wait=40.0) as client:
        result = await client.generate(final_prompt)

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        f"Image generation: {duration_ms:.1f}ms | "
        f"fallback={result.is_fallback} | "
        f"reason={result.reason} | "
        f"provider={result.provider}"
    )

    if result.is_fallback:
        # Если сработал таймаут или ошибка, возвращается SVG-заглушка
        extension = "svg"
    elif result.media_type == "image/jpeg":
        extension = "jpg"
    else:
        extension = "png"
    filename = f"img_{uuid.uuid4().hex}.{extension}"
    file_path = UPLOAD_DIR / filename
    file_path.write_bytes(result.content)

    image_url = f"/static/generated_images/{filename}"

    if not result.is_fallback:
        _IMAGE_CACHE.put(cache_key, image_url, final_prompt)

    return GenerateImageResponse(
        image_url=f"/static/generated_images/{filename}",
        prompt_used=final_prompt,
    )
