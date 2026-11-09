import asyncio
from types import SimpleNamespace

from app.schemas.generate_image import GenerateImageRequest
from app.services import generate_image_service as service
from app.services.gigachat_settings import GigaChatSettings
from app.services.image_cache import ImageCache


def test_image_cache_is_scoped_to_selected_model(monkeypatch, tmp_path):
    calls = []

    class FakeClient:
        def __init__(self, provider, *, max_wait):
            self.model = provider.model

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def generate(self, prompt):
            calls.append(self.model)
            return SimpleNamespace(
                content=b"image", is_fallback=False, reason=None,
                provider="fake", media_type="image/jpeg",
            )

    monkeypatch.setattr(service, "ImageGenerationClient", FakeClient)
    monkeypatch.setattr(service, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(service, "_IMAGE_CACHE", ImageCache())
    settings = GigaChatSettings(_env_file=None, image_model="GigaChat-2-Max")
    monkeypatch.setattr(service, "GigaChatSettings", lambda: settings)
    payload = GenerateImageRequest(prompt="A mouse at a woodland pond")

    baseline = asyncio.run(service.generate_image(payload))
    settings.image_model = "GigaChat-2"
    tuned = asyncio.run(service.generate_image(payload))
    cached = asyncio.run(service.generate_image(payload))

    assert calls == ["GigaChat-2-Max", "GigaChat-2"]
    assert baseline.image_url != tuned.image_url == cached.image_url
    assert tuned.prompt_used == cached.prompt_used == payload.prompt
