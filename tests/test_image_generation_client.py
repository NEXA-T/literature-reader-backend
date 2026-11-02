import asyncio
import json
import hashlib
from pathlib import Path
import time
import uuid

import httpx
import pytest

from app.services.gigachat_settings import GigaChatSettings
from app.services.image_generation_client import ImageGenerationClient
from app.services.image_prompts import prepare_image_prompt
from app.services.image_provider import (
    GigaChatImageProvider, ImageBytes, ImageProviderError, extract_image_id,
)

JPEG = b"\xff\xd8\xff" + b"image-test" * 20


class FakeProvider:
    name = "fake"

    def __init__(self, statuses):
        self.statuses = iter(statuses)
        self.cancelled = []
        self.check_times = []
        self.closed = False
        self.prompts = []

    async def submit(self, prompt):
        self.prompts.append(prompt)
        return "test-job"

    async def check(self, job):
        self.check_times.append(time.monotonic())
        value = next(self.statuses, None)
        if isinstance(value, Exception):
            raise value
        return value

    async def cancel(self, job):
        self.cancelled.append(job)

    async def aclose(self):
        self.closed = True


def run(provider, prompt="A woman reads beside a window.", **options):
    async def call():
        async with ImageGenerationClient(provider, **options) as client:
            return await client.generate(prompt)
    return asyncio.run(call())


def test_submit_poll_done_returns_bytes_and_applies_style():
    provider = FakeProvider([None, ImageBytes(JPEG, "image/jpeg")])
    result = run(provider)
    assert not result.is_fallback and result.content == JPEG
    assert 1.45 <= provider.check_times[1] - provider.check_times[0] <= 2.2
    assert "book illustration style" in provider.prompts[0]
    assert "no text, no letters" in provider.prompts[0]
    assert result.polling_checks == 2
    assert provider.cancelled == ["test-job"] and provider.closed


def test_timeout_returns_a_real_cover_and_stops_job():
    provider = FakeProvider([])
    result = run(provider, max_wait=0.03)
    assert result.is_fallback and result.reason == "timeout"
    assert result.media_type == "image/svg+xml" and b"<svg" in result.content
    assert b"<text" not in result.content
    assert result.elapsed_seconds < 0.5
    assert provider.cancelled == ["test-job"]


@pytest.mark.parametrize("reason", ["network_error", "provider_rejected", "invalid_image"])
def test_provider_failures_return_marked_fallback_without_retry(reason):
    provider = FakeProvider([ImageProviderError(reason)])
    result = run(provider)
    assert result.is_fallback and result.reason == reason
    assert len(provider.prompts) == 1


@pytest.mark.parametrize("options", [{"max_wait":16}, {"poll_interval":1}, {"poll_interval":3}])
def test_wait_limit_and_polling_range_are_enforced(options):
    with pytest.raises(ValueError):
        ImageGenerationClient(FakeProvider([]), **options)


def test_literary_disambiguation_does_not_disguise_unsafe_requests():
    prompt = prepare_image_prompt("as dead as a door-nail")
    assert "counting-house" in prompt and "door-nail" not in prompt
    provider = FakeProvider([])
    result = run(provider, prompt="graphic gore")
    assert result.is_fallback and result.reason == "input_requires_review"
    assert provider.prompts == []
    assert run(FakeProvider([]), prompt="").is_fallback


def test_image_uuid_is_not_a_remote_url_or_path():
    identifier = str(uuid.uuid4())
    assert extract_image_id(f'<img src="{identifier}"/>') == identifier
    for value in ("https://unsafe.invalid/image.jpg", "../secret", "invalid"):
        with pytest.raises(ImageProviderError):
            extract_image_id(f'<img src="{value}"/>')


def test_gigachat_adapter_real_request_shapes_and_binary_download():
    calls = []
    identifier = str(uuid.uuid4())

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("oauth"):
            return httpx.Response(200, json={"access_token":"test-token", "expires_at":int((time.time()+1800)*1000)})
        if request.method == "GET":
            assert request.url.path.endswith(f"files/{identifier}/content")
            return httpx.Response(200, content=JPEG)
        payload = json.loads(request.content)
        assert payload["function_call"] == "auto"
        assert "no text" in payload["messages"][1]["content"]
        return httpx.Response(200, json={"choices":[{"finish_reason":"stop","message":{"content":f'<img src="{identifier}"/>'}}]})

    provider = GigaChatImageProvider(GigaChatSettings(_env_file=None,auth_key="test-key"),transport=httpx.MockTransport(handler))
    result = run(provider)
    assert not result.is_fallback
    assert len(calls) == 3 and provider._jobs == {} and provider._http.is_closed


@pytest.mark.parametrize("mode", ["network", "refusal", "broken", "not_image"])
def test_gigachat_adapter_handles_external_failures(mode):
    identifier = str(uuid.uuid4())
    def handler(request):
        if mode == "network":
            raise httpx.ConnectError("private information",request=request)
        if request.url.path.endswith("oauth"):
            return httpx.Response(200,json={"access_token":"x","expires_at":int((time.time()+1800)*1000)})
        if mode == "refusal":
            return httpx.Response(200,json={"choices":[{"finish_reason":"blacklist","message":{"content":"rejected"}}]})
        if mode == "broken":
            return httpx.Response(200,json={"choices":[]})
        if request.method == "GET":
            return httpx.Response(200,content=b'{"error":"not image"}')
        return httpx.Response(200,json={"choices":[{"finish_reason":"stop","message":{"content":f'<img src="{identifier}"/>'}}]})
    provider = GigaChatImageProvider(GigaChatSettings(_env_file=None,auth_key="test-key"),transport=httpx.MockTransport(handler))
    assert run(provider).is_fallback
    assert provider._jobs == {}


def test_slow_gigachat_task_is_cancelled_without_leaking_background_work():
    cancelled = []
    async def handler(request):
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
    provider = GigaChatImageProvider(GigaChatSettings(_env_file=None,auth_key="test-key"),transport=httpx.MockTransport(handler))
    result = run(provider,max_wait=0.03)
    assert result.is_fallback and result.reason == "timeout"
    assert cancelled and provider._jobs == {}


def test_demo_files_are_real_generated_images_and_offline_mode_is_explicit():
    root = Path(__file__).resolve().parents[1]
    folder = root / "docs/demo-assets"
    log = json.loads((folder / "generation-log.json").read_text(encoding="utf-8"))
    interactive = json.loads((folder / "interactive-timeout-log.json").read_text(encoding="utf-8"))
    scenes = json.loads((folder / "scenes.json").read_text(encoding="utf-8"))
    assert log["mode"] == "offline_asset_preparation"
    assert log["max_wait_per_attempt_seconds"] == 90
    assert log["interactive_client_max_wait_seconds"] == 15
    assert log["generated_count"] == 5
    assert {case["id"] for case in log["cases"]} == {scene["id"] for scene in scenes}
    for case in log["cases"]:
        content = (folder / case["image_file"]).read_bytes()
        assert not case["is_fallback"] and content.startswith(b"\xff\xd8\xff")
        assert hashlib.sha256(content).hexdigest() == case["sha256"]
    fallback_hash = hashlib.sha256((root / "app/assets/fallback-cover.svg").read_bytes()).hexdigest()
    # The first interactive run predates the explicit mode metadata field.
    assert interactive["max_wait_per_attempt_seconds"] == 15 and interactive["generated_count"] == 0
    assert all(case["is_fallback"] and case["sha256"] == fallback_hash for case in interactive["cases"])
