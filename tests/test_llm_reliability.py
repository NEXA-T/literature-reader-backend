import asyncio
import json
import time

from fastapi.testclient import TestClient
import httpx
import pytest

from app.schemas.ai_analysis import AIAnalysis
from app.services.analysis_cache import AnalysisCache, request_hash
import app.services.gigachat_client as llm
from app.services.gigachat_settings import GigaChatSettings

VALID = {
    "translation": "решиться на неприятный разговор",
    "context_meaning": "Дочь решается сообщить отцу плохую новость.",
    "slang_or_etymology": None,
    "image_prompt": "A woman speaks to her father at breakfast.",
}


def settings(**extra):
    return GigaChatSettings(_env_file=None, auth_key="reliability-test-key", **extra)


def token():
    return httpx.Response(200, json={"access_token": "test-token", "expires_at": int((time.time() + 1800) * 1000)})


def response(value=VALID):
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(value)}, "finish_reason": "stop"}]})


def test_eight_second_deadline_cancels_slow_api_and_covers_oauth(monkeypatch):
    monkeypatch.setattr(llm, "_RESULT_CACHE", AnalysisCache())
    state = {"slow": True, "cancelled": False}

    async def handler(request):
        if request.url.path.endswith("oauth"):
            return token()
        if state["slow"]:
            try:
                await asyncio.sleep(9)
            except asyncio.CancelledError:
                state["cancelled"] = True
                raise
        return response()

    async def run():
        # Old .env value 60 cannot enlarge the hard 8-second limit.
        async with llm.GigaChatClient(settings(timeout_seconds=60), transport=httpx.MockTransport(handler)) as client:
            start = time.perf_counter()
            with pytest.raises(llm.LLMTimeoutException):
                await client.analyze_text("deadline", "A scene.")
            elapsed = time.perf_counter() - start
            assert 7.9 <= elapsed < 9.5
            print(f"Artificial API delay 9s -> LLMTimeoutException in {elapsed:.3f}s; request cancelled")
            assert state["cancelled"]
            state["slow"] = False
            # A timeout is not cached; the same input can succeed on retry.
            assert isinstance(await client.analyze_text("deadline", "A scene."), AIAnalysis)

        async def oauth_and_chat(request):
            await asyncio.sleep(0.035)
            return token() if request.url.path.endswith("oauth") else response()

        # Each stage is shorter than .05, but their sum exceeds the one budget.
        async with llm.GigaChatClient(settings(timeout_seconds=0.05), transport=httpx.MockTransport(oauth_and_chat)) as client:
            with pytest.raises(llm.LLMTimeoutException):
                await client.analyze_text("shared budget", "Another scene.")

        def http_timeout(request):
            raise httpx.ReadTimeout("private transport detail", request=request)

        async with llm.GigaChatClient(settings(), transport=httpx.MockTransport(http_timeout)) as client:
            with pytest.raises(llm.LLMTimeoutException) as caught:
                await client.analyze_text("transport timeout", "Scene.")
            assert "private" not in str(caught.value)

    asyncio.run(run())


def test_cache_survives_client_recreation_and_checks_ttl_collisions_and_copies(monkeypatch):
    clock = [0.0]
    cache = AnalysisCache(max_entries=2, clock=lambda: clock[0])
    monkeypatch.setattr(llm, "_RESULT_CACHE", cache)
    calls = []

    def handler(request):
        calls.append(request)
        return token() if request.url.path.endswith("oauth") else response()

    async def analyze(text="Bite the bullet", context="A scene.", title=None, auth="reliability-test-key"):
        cfg = GigaChatSettings(_env_file=None, auth_key=auth)
        async with llm.GigaChatClient(cfg, transport=httpx.MockTransport(handler)) as client:
            return await client.analyze_text(text, context, title)

    async def run():
        first = await analyze()
        first.translation = "caller changed its copy"
        before = len(calls)
        cached = await analyze(text="bite the bullet")
        assert len(calls) == before
        assert cached.model_dump() == VALID
        assert request_hash("BITE", "x" * 101) == request_hash("bite", "x" * 100 + "y")
        # Hash required by the task collides, but full-context guard prevents reuse.
        await analyze(context="x" * 100 + "a")
        before = len(calls)
        await analyze(context="x" * 100 + "b")
        assert len(calls) > before
        before = len(calls)
        await analyze(context="x" * 100 + "b", title="A different book")
        assert len(calls) > before
        before = len(calls)
        await analyze(context="x" * 100 + "b", title="A different book", auth="another-project-key")
        assert len(calls) > before
        clock[0] += 301
        before = len(calls)
        await analyze(context="x" * 100 + "b", title="A different book", auth="another-project-key")
        assert len(calls) > before
        await analyze(text="entry two")
        await analyze(text="entry three")
        assert len(cache._entries) == 2  # Bounded, not an unbounded memory leak.

    asyncio.run(run())


def test_null_parsing_and_scene_constraints_trigger_retry(monkeypatch):
    monkeypatch.setattr(llm, "_RESULT_CACHE", AnalysisCache())
    assert llm.parse_analysis(json.dumps({**VALID, "image_prompt": None})).image_prompt is None
    assert llm.parse_analysis(json.dumps(VALID)).slang_or_etymology is None
    assert len(llm.parse_analysis(json.dumps({**VALID, "image_prompt": "A" * 150})).image_prompt) == 150
    for prompt in ("A" * 151, "Дочь разговаривает с отцом.", "12345"):
        with pytest.raises(ValueError):
            llm.parse_analysis(json.dumps({**VALID, "image_prompt": prompt}))
    chats = []

    def handler(request):
        if request.url.path.endswith("oauth"):
            return token()
        chats.append(json.loads(request.content))
        return response({**VALID, "image_prompt": "A" * 151}) if len(chats) == 1 else response()

    async def run():
        async with llm.GigaChatClient(settings(), transport=httpx.MockTransport(handler)) as client:
            assert (await client.analyze_text("scene validation", "Breakfast.")).model_dump() == VALID
    asyncio.run(run())
    assert len(chats) == 2
    assert chats[0]["messages"][1] == chats[1]["messages"][1]


def test_endpoint_reuses_cache_and_returns_controlled_504(monkeypatch):
    from app.main import app
    import app.services.explain_service as service
    import app.api.v1.endpoints.explain as endpoint

    monkeypatch.setattr(llm, "_RESULT_CACHE", AnalysisCache())
    calls = []

    def handler(request):
        calls.append(request)
        return token() if request.url.path.endswith("oauth") else response()

    def factory(config):
        return llm.GigaChatClient(config, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(service, "GigaChatSettings", settings)
    monkeypatch.setattr(service, "GigaChatClient", factory)
    with TestClient(app) as client:
        payload = {"selected_text": "same HTTP request", "context": "Breakfast."}
        assert client.post("/api/v1/explain", json=payload).json() == VALID
        before = len(calls)
        assert client.post("/api/v1/explain", json=payload).json() == VALID
        assert len(calls) == before

        async def fail(payload):
            raise llm.LLMTimeoutException("provider timeout")

        monkeypatch.setattr(endpoint, "explain_text", fail)
        result = client.post("/api/v1/explain", json=payload)
        assert result.status_code == 504
        assert set(result.json()) == {"error"}
        assert "provider timeout" not in result.json()["error"]
