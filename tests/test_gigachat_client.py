import asyncio
import base64
import json
import ssl
import time
import uuid

import httpx
from pydantic import SecretStr, ValidationError
import pytest

from app.schemas.ai_analysis import AIAnalysis
from app.services.gigachat_client import (
    GigaChatClient, GigaChatConfigurationError, GigaChatResponseError,
    GigaChatUnavailableError, parse_analysis,
)
from app.services.gigachat_settings import GigaChatSettings

VALID = {
    "translation": "раскрыть секрет", "context_meaning": "Сестра просит рассказать о помолвке.",
    "slang_or_etymology": None, "image_prompt": "Two sisters talking quietly.",
}


def settings(**overrides):
    return GigaChatSettings(_env_file=None, auth_key=SecretStr("test-auth-secret"), **overrides)


def token_response():
    return httpx.Response(200, json={"access_token": "test-access-secret", "expires_at": int((time.time() + 1800) * 1000)})


def completion(content=None, finish="stop"):
    if content is None:
        content = json.dumps(VALID, ensure_ascii=False)
    return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": finish}]})


def run_client(handler, **kwargs):
    async def run():
        async with GigaChatClient(settings(), transport=httpx.MockTransport(handler)) as client:
            return await client.analyze_text("spill the beans", "A secret.", **kwargs)
    return asyncio.run(run())


def test_returns_pydantic_object_and_sends_exact_input():
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.path.endswith("oauth"):
            assert request.headers["Authorization"] == "Basic test-auth-secret"
            assert uuid.UUID(request.headers["RqUID"]).version == 4
            assert request.content == b"scope=GIGACHAT_API_PERS"
            return token_response()
        payload = json.loads(request.content)
        assert request.headers["Authorization"] == "Bearer test-access-secret"
        assert payload["messages"][0]["role"] == "system"
        assert json.loads(payload["messages"][1]["content"]) == {
            "selected_text": "spill the beans", "context": "A secret.", "book_title": "A Book",
        }
        assert payload["response_format"]["schema"]["additionalProperties"] is False
        assert set(payload["response_format"]["schema"]["required"]) == set(VALID)
        return completion()
    result = run_client(handler, book_title="A Book")
    assert isinstance(result, AIAnalysis)
    assert result.model_dump() == VALID
    assert len(calls) == 2


@pytest.mark.parametrize("wrapper", ["{}", "  ```json\n{}\n```  ", "```\n{}\n```", "```JSON\r\n{}\r\n```"])
def test_accepts_plain_json_or_complete_surrounding_fence(wrapper):
    content = wrapper.format(json.dumps(VALID))
    assert parse_analysis(content).model_dump() == VALID


@pytest.mark.parametrize("bad", [
    {**VALID, "translation": 42}, {**VALID, "context_meaning": False},
    {**VALID, "image_prompt": []}, {**VALID, "slang_or_etymology": {}},
    {k: v for k, v in VALID.items() if k != "slang_or_etymology"},
    {**VALID, "term": "obsolete"}, {"term": "x", "definition": "y", "explanation": "z", "examples": []},
    {**VALID, "translation": " "}, {**VALID, "slang_or_etymology": "null"},
    {**VALID, "image_prompt": "None"},
])
def test_strict_schema_rejects_invalid_model_objects(bad):
    with pytest.raises(ValueError):
        parse_analysis(json.dumps(bad))


@pytest.mark.parametrize("content", [
    "Here is JSON: {}", "{} trailing", "```json\n{}\n``` extra",
    '{"translation":"a","translation":"b"}', '{"x":NaN}', '"a string"', "[]", "not JSON",
])
def test_rejects_malformed_ambiguous_or_non_object_json(content):
    with pytest.raises(ValueError):
        parse_analysis(content)


def test_allows_real_null_and_real_etymology_strings():
    assert parse_analysis(json.dumps({**VALID, "image_prompt": None})).image_prompt is None
    assert parse_analysis(json.dumps({**VALID, "slang_or_etymology": "A cultural reference."})).slang_or_etymology


def test_invalid_output_retries_once_without_losing_original_input():
    chat = []
    def handler(request):
        if request.url.path.endswith("oauth"):
            return token_response()
        chat.append(json.loads(request.content))
        return completion("not JSON") if len(chat) == 1 else completion()
    assert run_client(handler).translation == VALID["translation"]
    assert len(chat) == 2
    assert chat[0]["messages"][1] == chat[1]["messages"][1]
    assert chat[0]["messages"][0] != chat[1]["messages"][0]


@pytest.mark.parametrize("first", [completion(finish="length"), httpx.Response(200, json={"choices": []})])
def test_truncated_or_malformed_envelope_retries(first):
    chat = []
    def handler(request):
        if request.url.path.endswith("oauth"):
            return token_response()
        chat.append(request)
        return first if len(chat) == 1 else completion()
    assert isinstance(run_client(handler), AIAnalysis)
    assert len(chat) == 2


def test_retry_exhaustion_is_bounded_and_hides_raw_model_output():
    calls = []
    def handler(request):
        calls.append(request)
        return token_response() if request.url.path.endswith("oauth") else completion("private model text")
    with pytest.raises(GigaChatResponseError) as error:
        run_client(handler)
    assert len(calls) == 3
    assert "private model text" not in str(error.value)


def test_token_cached_between_method_calls_and_connection_closed():
    auth = []
    holder = []
    def handler(request):
        if request.url.path.endswith("oauth"):
            auth.append(request)
            return token_response()
        return completion()
    async def run():
        async with GigaChatClient(settings(), transport=httpx.MockTransport(handler)) as client:
            holder.append(client)
            await client.analyze_text("x", "a")
            await client.analyze_text("y", "b")
    asyncio.run(run())
    assert len(auth) == 1
    assert holder[0]._http.is_closed


def test_token_refresh_when_chat_returns_401():
    auth, chat = [], []
    def handler(request):
        if request.url.path.endswith("oauth"):
            auth.append(request)
            return token_response()
        chat.append(request)
        return httpx.Response(401) if len(chat) == 1 else completion()
    assert isinstance(run_client(handler), AIAnalysis)
    assert len(auth) == len(chat) == 2


def test_repeated_401_stops_without_infinite_refresh():
    chat = []
    def handler(request):
        if request.url.path.endswith("oauth"):
            return token_response()
        chat.append(request)
        return httpx.Response(401)
    with pytest.raises(GigaChatUnavailableError):
        run_client(handler)
    assert len(chat) == 2


@pytest.mark.parametrize("status", [400, 403, 429, 500])
def test_http_failures_are_safe_and_not_json_retried(status):
    chat = []
    def handler(request):
        if request.url.path.endswith("oauth"):
            return token_response()
        chat.append(request)
        return httpx.Response(status, text="private-upstream-token")
    with pytest.raises(GigaChatUnavailableError) as error:
        run_client(handler)
    assert str(status) in str(error.value)
    assert "private-upstream-token" not in str(error.value)
    assert len(chat) == 1


def test_network_timeout_is_safe():
    def handler(request):
        raise httpx.ReadTimeout("private detail", request=request)
    with pytest.raises(GigaChatUnavailableError) as error:
        run_client(handler)
    assert "private detail" not in str(error.value)


@pytest.mark.parametrize("payload", [
    {"access_token": "x"}, {"access_token": "", "expires_at": 123},
    {"access_token": "x", "expires_at": 0}, {"access_token": 123, "expires_at": 99},
])
def test_invalid_oauth_data_is_rejected(payload):
    def handler(request):
        return httpx.Response(200, json=payload)
    with pytest.raises(GigaChatUnavailableError):
        run_client(handler)


def test_expiring_token_is_renewed():
    auth = []
    def handler(request):
        if request.url.path.endswith("oauth"):
            auth.append(request)
            return httpx.Response(200, json={"access_token":"x", "expires_at":int((time.time()+10)*1000)})
        return completion()
    async def run():
        async with GigaChatClient(settings(), transport=httpx.MockTransport(handler)) as client:
            await client.analyze_text("x", "a")
            await client.analyze_text("x", "a")
    asyncio.run(run())
    assert len(auth) == 2


@pytest.mark.parametrize("selection,context,title", [(123,"a",None),("x",None,None),(" ","a",None),("x","a",7)])
def test_invalid_input_is_rejected_before_network(selection,context,title):
    calls = []
    async def run():
        async with GigaChatClient(settings(),transport=httpx.MockTransport(lambda r: calls.append(r))) as client:
            await client.analyze_text(selection,context,title)
    with pytest.raises(ValidationError):
        asyncio.run(run())
    assert calls == []


def test_optional_book_title_omitted_and_empty_context_preserved():
    bodies = []
    def handler(request):
        if request.url.path.endswith("oauth"):
            return token_response()
        bodies.append(json.loads(request.content))
        return completion()
    async def run():
        async with GigaChatClient(settings(),transport=httpx.MockTransport(handler)) as client:
            await client.analyze_text("x", "")
    asyncio.run(run())
    assert json.loads(bodies[0]["messages"][1]["content"]) == {"selected_text":"x","context":""}


def test_settings_use_existing_client_id_secret_and_hide_secrets():
    cfg = GigaChatSettings(_env_file=None, client_id="test-id", client_secret="test-password")
    async def run():
        async with GigaChatClient(cfg,transport=httpx.MockTransport(lambda r: token_response())) as client:
            assert client._auth_key.get_secret_value() == base64.b64encode(b"test-id:test-password").decode()
    asyncio.run(run())
    assert "test-password" not in repr(cfg)
    assert "test-id" not in repr(cfg)


def test_env_file_resolves_relative_ca_path_and_ignores_empty_settings(tmp_path):
    path = tmp_path / ".env"
    path.write_text("GIGACHAT_AUTH_KEY=test-key\nGIGACHAT_CA_BUNDLE=certs/root.crt\n", encoding="utf-8")
    assert GigaChatSettings.from_env_file(path).ca_bundle == tmp_path / "certs/root.crt"
    path.write_text("GIGACHAT_AUTH_KEY=test-key\nGIGACHAT_CA_BUNDLE=\n", encoding="utf-8")
    assert GigaChatSettings.from_env_file(path).ca_bundle is None


def test_certificate_loading_errors_are_safe(tmp_path):
    with pytest.raises(GigaChatConfigurationError):
        GigaChatClient(settings(ca_bundle=tmp_path / "missing.crt"))


def test_tls_verification_stays_enabled(monkeypatch):
    import app.services.gigachat_client as module
    original = module.httpx.AsyncClient
    contexts = []
    def factory(**kwargs):
        contexts.append(kwargs["verify"])
        return original(**kwargs)
    monkeypatch.setattr(module.httpx,"AsyncClient",factory)
    async def run():
        async with GigaChatClient(settings(),transport=httpx.MockTransport(lambda r: completion())):
            pass
    asyncio.run(run())
    assert contexts[0].verify_mode == ssl.CERT_REQUIRED
    assert contexts[0].check_hostname


@pytest.mark.parametrize("overrides", [{"auth_key":None}, {"auth_key":"Basic secret"}, {"chat_url":"http://unsafe.example"}])
def test_configuration_errors(overrides):
    cfg = GigaChatSettings(_env_file=None,**{"auth_key":"test-key",**overrides})
    with pytest.raises(GigaChatConfigurationError):
        GigaChatClient(cfg)
