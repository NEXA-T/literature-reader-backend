"""Independent GigaChat OAuth smoke test (Python 3.10+, no dependencies)."""

import base64
import getpass
import json
import os
from pathlib import Path
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parent
AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT_URL = "https://api.giga.chat/v1/chat/completions"
PROMPT = "Привет, ответь одним словом: работает?"


def load_env():
    """Read simple KEY=value settings; existing environment takes precedence."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator:
            raise ValueError("Некорректная строка в .env: ожидается KEY=value.")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def credentials():
    key = os.getenv("GIGACHAT_AUTH_KEY", "").strip()
    if not key:
        client_id = os.getenv("GIGACHAT_CLIENT_ID", "").strip()
        secret = os.getenv("GIGACHAT_CLIENT_SECRET", "").strip()
        if client_id and secret:
            key = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
        elif client_id or secret:
            raise ValueError("Укажите оба значения: Client ID и Client Secret.")
        else:
            key = getpass.getpass("Authorization Key (ввод скрыт): ").strip()
    if not key or key.lower().startswith("basic "):
        raise ValueError("Укажите Authorization Key без префикса Basic.")
    return key


def tls_context():
    context = ssl.create_default_context()
    bundle = os.getenv("GIGACHAT_CA_BUNDLE", "").strip()
    if bundle:
        path = Path(bundle)
        if not path.is_absolute():
            path = ROOT / path
        context.load_verify_locations(cafile=str(path))
    return context


def post_json(url, headers, body, context):
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, context=context, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # Do not print response bodies, headers or credentials.
        hints = {
            400: "Проверьте scope и параметры запроса.",
            401: "Проверьте ключ авторизации.",
            403: "Проверьте права проекта и доступ к модели.",
            402: "Проверьте доступные токены и тариф.",
            429: "Достигнут лимит запросов; повторите позже.",
        }
        raise RuntimeError(
            f"HTTP {error.code}. {hints.get(error.code, 'Проверьте состояние сервиса и тариф.')}"
        ) from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, ssl.SSLError):
            raise RuntimeError(
                "Ошибка TLS. Установите сертификаты Минцифры или задайте "
                "GIGACHAT_CA_BUNDLE с путём к PEM-файлу."
            ) from None
        raise RuntimeError("Сетевая ошибка: проверьте интернет, прокси и доступность API.") from None


def run():
    load_env()
    key = credentials()
    context = tls_context()
    token = post_json(
        AUTH_URL,
        {"Authorization": f"Basic {key}", "RqUID": str(uuid.uuid4()),
         "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        urllib.parse.urlencode({"scope": os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")}).encode(),
        context,
    ).get("access_token")
    if not isinstance(token, str) or not token.strip():
        raise RuntimeError("OAuth-ответ не содержит access_token.")
    print("OAuth: успешно (токен не выводится)")
    model = os.getenv("GIGACHAT_MODEL", "GigaChat")
    result = post_json(
        os.getenv("GIGACHAT_CHAT_URL", CHAT_URL),
        {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
         "Accept": "application/json"},
        json.dumps({"model": model, "messages": [{"role": "user", "content": PROMPT}],
                    "max_tokens": 32, "stream": False}).encode(),
        context,
    )
    try:
        answer = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Неожиданный формат ответа модели.") from None
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("Модель вернула пустой ответ.")
    print(f"Модель: {model}")
    print(f"Запрос: {PROMPT}")
    print(f"Ответ модели: {answer.strip()}")
    print("Проверка подключения: успешно")


if __name__ == "__main__":
    try:
        run()
    except (ValueError, RuntimeError, OSError, EOFError):
        # Known errors are safe to display; OS errors may contain private paths.
        error = sys.exc_info()[1]
        message = str(error) if isinstance(error, (ValueError, RuntimeError)) else "Не удалось прочитать настройки или сертификат."
        print(f"Ошибка: {message}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nПроверка отменена.", file=sys.stderr)
        sys.exit(130)
