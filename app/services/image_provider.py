"""GigaChat text2image adapter with locally tracked async jobs.

The public GigaChat endpoint is synchronous, not a remote job-status API.
The adapter exposes submit/check/cancel so the orchestrator can poll safely.
"""
import asyncio
import base64
from contextlib import suppress
from dataclasses import dataclass
from html.parser import HTMLParser
import json
from pathlib import Path
import ssl
import time
import uuid

import httpx

from app.services.gigachat_settings import GigaChatSettings

IMAGE_SYSTEM_PROMPT = (Path(__file__).parent / "prompts/image_generation.txt").read_text(encoding="utf-8")


class ImageProviderError(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ImageBytes:
    content: bytes
    media_type: str


def checked_image(content: bytes) -> ImageBytes:
    if not 64 <= len(content) <= 10_000_000:
        raise ImageProviderError("invalid_image")
    if content.startswith(b"\xff\xd8\xff"):
        return ImageBytes(content, "image/jpeg")
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ImageBytes(content, "image/png")
    raise ImageProviderError("invalid_image")


class _ImageTag(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "img":
            try:
                identifier = uuid.UUID(dict(attrs).get("src", ""))
                if identifier.version == 4:
                    self.ids.append(str(identifier))
            except (ValueError, AttributeError):
                pass


def extract_image_id(content: str) -> str:
    parser = _ImageTag()
    parser.feed(content)
    if not parser.ids:
        raise ImageProviderError("provider_rejected_or_no_image")
    return parser.ids[0]


class GigaChatImageProvider:
    name = "gigachat_text2image"

    def __init__(self, settings: GigaChatSettings, *, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._transport = transport
        self._http: httpx.AsyncClient | None = None
        self._jobs: dict[str, asyncio.Task] = {}
        self._token: str | None = None
        self._expires_at = 0.0
        self._auth_lock = asyncio.Lock()

    def _http_client(self) -> httpx.AsyncClient:
        if self._http is None:
            try:
                tls = ssl.create_default_context()
                if self.settings.ca_bundle:
                    tls.load_verify_locations(cafile=str(self.settings.ca_bundle))
            except (OSError, ssl.SSLError):
                raise ImageProviderError("configuration_error") from None
            from urllib.parse import urlsplit
            for url in (self.settings.auth_url, self.settings.chat_url):
                parsed = urlsplit(url)
                if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                    raise ImageProviderError("configuration_error")
            # The orchestrator enforces the 15s interactive deadline. A longer
            # transport budget also permits explicit offline report preparation.
            self._http = httpx.AsyncClient(verify=tls, timeout=90.0, follow_redirects=False, transport=self._transport)
        return self._http

    async def _access_token(self) -> str:
        async with self._auth_lock:
            if self._token and self._expires_at > time.time() + 30:
                return self._token
            key = self.settings.auth_key.get_secret_value().strip() if self.settings.auth_key else ""
            if not key and self.settings.client_id and self.settings.client_secret:
                pair = f"{self.settings.client_id}:{self.settings.client_secret.get_secret_value()}"
                key = base64.b64encode(pair.encode()).decode()
            if not key or key.lower().startswith("basic "):
                raise ImageProviderError("configuration_error")
            result = await self._http_client().post(
                self.settings.auth_url,
                headers={"Authorization": "Basic " + key, "RqUID": str(uuid.uuid4())},
                data={"scope": self.settings.scope},
            )
            result.raise_for_status()
            payload = result.json()
            token = payload["access_token"]
            expires = payload["expires_at"]
            if not isinstance(token, str) or not token.strip() or type(expires) is not int or expires / 1000 <= time.time():
                raise ImageProviderError("authorization_error")
            self._token, self._expires_at = token, expires / 1000
            return token

    async def submit(self, prompt: str) -> str:
        job = str(uuid.uuid4())
        self._jobs[job] = asyncio.create_task(self._generate(prompt))
        return job

    async def check(self, job: str) -> ImageBytes | None:
        task = self._jobs.get(job)
        if task is None:
            raise ImageProviderError("unknown_job")
        return task.result() if task.done() else None

    async def cancel(self, job: str) -> None:
        task = self._jobs.pop(job, None)
        if task is not None:
            if not task.done():
                task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task

    async def aclose(self) -> None:
        for job in list(self._jobs):
            await self.cancel(job)
        if self._http is not None:
            await self._http.aclose()

    async def _generate(self, prompt: str) -> ImageBytes:
        try:
            token = await self._access_token()
            headers = {"Authorization": "Bearer " + token}
            response = await self._http_client().post(
                self.settings.chat_url, headers=headers,
                json={"model": self.settings.model, "messages": [
                    {"role": "system", "content": IMAGE_SYSTEM_PROMPT},
                    {"role": "user", "content": "Нарисуй книжную иллюстрацию: " + prompt},
                ], "function_call": "auto"},
            )
            response.raise_for_status()
            choice = response.json()["choices"][0]
            if choice.get("finish_reason") == "blacklist":
                raise ImageProviderError("provider_rejected")
            if choice.get("finish_reason") != "stop":
                raise ImageProviderError("incomplete_generation")
            identifier = extract_image_id(choice["message"]["content"])
            base = self.settings.chat_url.removesuffix("/chat/completions")
            downloaded = await self._http_client().get(
                f"{base}/files/{identifier}/content", headers={**headers, "Accept": "image/jpeg"},
            )
            downloaded.raise_for_status()
            return checked_image(downloaded.content)
        except httpx.TimeoutException:
            raise ImageProviderError("timeout") from None
        except httpx.HTTPStatusError as error:
            reason = "provider_rejected" if error.response.status_code in (400, 403) else "provider_http_error"
            raise ImageProviderError(reason) from None
        except httpx.RequestError:
            raise ImageProviderError("network_error") from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise ImageProviderError("invalid_provider_response") from None
