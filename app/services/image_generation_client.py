"""Submit -> poll at 1.5-second intervals -> ready bytes or a marked fallback."""
import asyncio
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Protocol

from app.services.image_prompts import prepare_image_prompt
from app.services.image_provider import ImageBytes, ImageProviderError

FALLBACK = (Path(__file__).resolve().parents[1] / "assets/fallback-cover.svg").read_bytes()


class ImageProvider(Protocol):
    name: str
    async def submit(self, prompt: str) -> str: ...
    async def check(self, job: str) -> ImageBytes | None: ...
    async def cancel(self, job: str) -> None: ...
    async def aclose(self) -> None: ...


@dataclass(frozen=True)
class GeneratedImage:
    content: bytes
    media_type: str
    is_fallback: bool
    reason: str | None
    effective_prompt: str
    provider: str
    polling_checks: int
    elapsed_seconds: float


class ImageGenerationClient:
    def __init__(self, provider: ImageProvider, *, poll_interval: float = 1.5, max_wait: float = 30.0):
        if not 1.5 <= poll_interval <= 2.0 or not 0 < max_wait <= 30.0:
            raise ValueError("Polling must be 1.5–2 s, total wait at most 15 s")
        self._provider = provider
        self._poll_interval = poll_interval
        self._max_wait = max_wait

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._provider.aclose()

    async def generate(self, image_prompt: str) -> GeneratedImage:
        start = time.monotonic()
        job = None
        effective = ""
        checks = 0

        def fallback(reason: str) -> GeneratedImage:
            return GeneratedImage(FALLBACK, "image/svg+xml", True, reason, effective,
                                  self._provider.name, checks, time.monotonic() - start)

        try:
            try:
                effective = prepare_image_prompt(image_prompt)
            except ValueError:
                return fallback("input_requires_review")
            async with asyncio.timeout(self._max_wait):
                job = await self._provider.submit(effective)
                while True:
                    checks += 1
                    result = await self._provider.check(job)
                    if result is not None:
                        return GeneratedImage(result.content, result.media_type, False, None,
                                              effective, self._provider.name, checks, time.monotonic() - start)
                    await asyncio.sleep(self._poll_interval)
        except TimeoutError:
            return fallback("timeout")
        except ImageProviderError as error:
            return fallback(error.reason)
        finally:
            if job is not None:
                await self._provider.cancel(job)
