"""Isolated async GigaChat client. No FastAPI imports or endpoint changes."""
import asyncio
import base64
import hashlib
import json
from pathlib import Path
import re
import ssl
import time
from urllib.parse import urlsplit
import uuid

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from app.schemas.ai_analysis import AIAnalysis, AnalysisInput
from app.services.gigachat_settings import GigaChatSettings
from app.services.analysis_cache import AnalysisCache, context_guard, request_hash

SYSTEM_PROMPT = (Path(__file__).parent / "prompts/literary_analysis.txt").read_text(encoding="utf-8")


LLM_TIMEOUT_SECONDS = 8.0
_RESULT_CACHE = AnalysisCache()


class GigaChatError(RuntimeError):
    """Safe public exception; contains no upstream response or credentials."""


class GigaChatConfigurationError(GigaChatError):
    pass


class GigaChatUnavailableError(GigaChatError):
    pass


class LLMTimeoutException(GigaChatUnavailableError):
    """The shared OAuth/generation/retry deadline or HTTP timeout expired."""


class GigaChatResponseError(GigaChatError):
    pass


class _InvalidOutput(ValueError):
    pass


class _Token(BaseModel):
    model_config = ConfigDict(strict=True)
    access_token: SecretStr
    expires_at: int  # Unix milliseconds, per the OAuth API.


def _unique_pairs(items: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in items:
        if key in result:
            raise _InvalidOutput("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise _InvalidOutput("Nonstandard JSON constant")


def parse_analysis(content: str) -> AIAnalysis:
    """Strip only a complete surrounding code fence, then validate strictly."""
    cleaned = content.strip()
    fence = re.fullmatch(r"```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```", cleaned, re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        value = json.loads(cleaned, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
        return AIAnalysis.model_validate(value, strict=True)
    except (ValueError, TypeError, ValidationError):
        # No raw text or Pydantic input_value in the exception chain.
        raise _InvalidOutput("Response is not a valid analysis object") from None


class GigaChatClient:
    def __init__(
        self, settings: GigaChatSettings | None = None, *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings if settings is not None else GigaChatSettings()
        for url in (self._settings.auth_url, self._settings.chat_url):
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise GigaChatConfigurationError("GigaChat endpoints must use HTTPS without embedded credentials")
        self._auth_key = self._credentials()
        try:
            tls = ssl.create_default_context()
            if self._settings.ca_bundle:
                tls.load_verify_locations(cafile=str(self._settings.ca_bundle))
        except (OSError, ssl.SSLError):
            raise GigaChatConfigurationError("Не удалось загрузить сертификат GigaChat") from None
        self._timeout = min(LLM_TIMEOUT_SECONDS, self._settings.timeout_seconds)
        # Separate credentials/models/providers without retaining a plaintext key
        # in cache identifiers. The request digest still uses the specified pair.
        namespace_input = (
            self._auth_key.get_secret_value(), self._settings.model, self._settings.scope,
            self._settings.auth_url, self._settings.chat_url, SYSTEM_PROMPT,
            self._settings.cache_ttl_seconds,
        )
        self._cache_namespace = hashlib.sha256(json.dumps(namespace_input).encode()).hexdigest()
        self._http = httpx.AsyncClient(
            verify=tls, timeout=self._timeout,
            follow_redirects=False, transport=transport,
        )
        self._token: _Token | None = None
        self._token_lock = asyncio.Lock()
        self._request_count = 0
        self._cache_hits = 0

    @property
    def request_count(self) -> int:
        """HTTP attempts sent by this instance, including OAuth."""
        return self._request_count

    @property
    def cache_hits(self) -> int:
        return self._cache_hits

    def _credentials(self) -> SecretStr:
        settings = self._settings
        key = settings.auth_key.get_secret_value().strip() if settings.auth_key else ""
        if not key and settings.client_id and settings.client_secret:
            pair = f"{settings.client_id}:{settings.client_secret.get_secret_value()}"
            key = base64.b64encode(pair.encode()).decode()
        if not key or key.lower().startswith("basic ") or any(char.isspace() for char in key):
            raise GigaChatConfigurationError("Укажите GIGACHAT_AUTH_KEY без Basic либо Client ID и Client Secret")
        return SecretStr(key)

    async def __aenter__(self) -> "GigaChatClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _post(self, url: str, **kwargs: object) -> httpx.Response:
        try:
            self._request_count += 1
            return await self._http.post(url, **kwargs)
        except httpx.TimeoutException:
            raise LLMTimeoutException("Нейросеть не ответила вовремя. Повторите запрос.") from None
        except httpx.RequestError:
            raise GigaChatUnavailableError("GigaChat недоступен или не ответил вовремя. Повторите позже.") from None

    async def _access_token(self) -> str:
        async with self._token_lock:
            if self._token is None or self._token.expires_at / 1000 <= time.time() + 30:
                response = await self._post(
                    self._settings.auth_url,
                    headers={"Authorization": f"Basic {self._auth_key.get_secret_value()}",
                             "RqUID": str(uuid.uuid4()), "Accept": "application/json"},
                    data={"scope": self._settings.scope},
                )
                if response.status_code != 200:
                    raise GigaChatUnavailableError(f"Не удалось авторизоваться в GigaChat (HTTP {response.status_code}).")
                try:
                    token = _Token.model_validate_json(response.content)
                    if not token.access_token.get_secret_value().strip() or token.expires_at / 1000 <= time.time():
                        raise ValueError("Empty/expired token")
                except (ValidationError, ValueError):
                    raise GigaChatUnavailableError("GigaChat вернул некорректный ответ авторизации.") from None
                self._token = token
            return self._token.access_token.get_secret_value()

    async def _completion(self, payload: dict) -> str:
        # Renew an unexpectedly revoked token once; never loop indefinitely.
        for auth_attempt in range(2):
            token = await self._access_token()
            response = await self._post(
                self._settings.chat_url, json=payload,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            if response.status_code == 401 and auth_attempt == 0:
                self._token = None
                continue
            if response.status_code != 200:
                raise GigaChatUnavailableError(f"Запрос GigaChat не выполнен (HTTP {response.status_code}).")
            try:
                choice = response.json()["choices"][0]
                content = choice["message"]["content"]
                if choice.get("finish_reason") != "stop" or not isinstance(content, str):
                    raise ValueError("Incomplete response")
                return content
            except (ValueError, KeyError, IndexError, TypeError):
                raise _InvalidOutput("Incomplete or malformed completion") from None
        raise GigaChatUnavailableError("GigaChat отклонил авторизацию.")

    async def analyze_text(
        self, selected_text: str, context: str, book_title: str | None = None,
    ) -> AIAnalysis:
        user_input = AnalysisInput(selected_text=selected_text, context=context, book_title=book_title)
        key = request_hash(user_input.selected_text, user_input.context)
        guard = context_guard(user_input.context, user_input.book_title)
        if self._settings.cache_ttl_seconds > 0:
            cached = _RESULT_CACHE.get(self._cache_namespace, key, guard)
            if cached is not None:
                self._cache_hits += 1
                return cached
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._timeout
        try:
            # One wall-clock budget across OAuth, token lock and all retries.
            async with asyncio.timeout(self._timeout):
                result = await self._analyze_uncached(user_input)
                if loop.time() >= deadline:
                    raise TimeoutError
        except TimeoutError:
            raise LLMTimeoutException("Нейросеть не ответила вовремя. Повторите запрос.") from None
        _RESULT_CACHE.put(self._cache_namespace, key, guard, result, self._settings.cache_ttl_seconds)
        return result

    async def _analyze_uncached(self, user_input: AnalysisInput) -> AIAnalysis:
        user_content = json.dumps(user_input.model_dump(exclude_none=True), ensure_ascii=False)
        for attempt in range(self._settings.max_attempts):
            prompt = SYSTEM_PROMPT
            if attempt:
                prompt += (
                    "\nПредыдущий ответ не прошёл проверку. Верни только полный JSON-объект "
                    "с четырьмя исходными полями и корректными типами, без лишних полей. "
                    "Не используй текстовые заглушки вместо null. image_prompt: конкретная сцена "
                    "на английском, максимум 150 символов, либо null. Анализируй исходный ввод."
                )
            payload = {
                "model": self._settings.model,
                "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": user_content}],
                "temperature": 0.1, "max_tokens": 1400, "stream": False,
                "response_format": {"type": "json_schema", "schema": AIAnalysis.model_json_schema(), "strict": True},
            }
            try:
                return parse_analysis(await self._completion(payload))
            except _InvalidOutput:
                pass
        raise GigaChatResponseError("GigaChat не вернул корректный разбор. Попробуйте ещё раз.") from None
