# GigaChatClient — задача №25

Изолированный асинхронный сервис `app/services/gigachat_client.py` выполняет
`analyze_text(selected_text: str, context: str, book_title: str | None = None)`
и возвращает **Pydantic-объект `AIAnalysis`**, а не строку или словарь.

## Контракт и границы изменения

`AIAnalysis` находится в `app/schemas/ai_analysis.py`:

- `translation: str` — контекстный перевод;
- `context_meaning: str` — смысл в абзаце;
- `slang_or_etymology: str | None` — сленг/культурная отсылка или null;
- `image_prompt: str | None` — английское описание конкретной сцены до 150 символов или null.

Все четыре ключа обязательны, включая nullable-поля. Типы строгие,
дополнительные и старые поля запрещены. Пустые основные строки и строковые
заглушки `"null"`/`"None"` вместо настоящего JSON null отклоняются.
Текст и контекст передаются отдельным user-сообщением в виде JSON, а промпт —
system-сообщением. Название книги передаётся только при наличии.
`context` должен быть строкой, но может быть пустым согласно контракту №11.

Клиент не меняет `ExplainRequest`, `ExplainResponse`, mock-сервис или HTTP-эндпоинт
коллеги. Подключение клиента к FastAPI и преобразование исключений в
`{"error":"..."}` — отдельная интеграционная задача. При объединении с веткой
контракта можно оставить `AIAnalysis` строгой моделью границы с LLM и
преобразовать её через `ExplainResponse(**result.model_dump())`.

Промпт перенесён из нашего исправления контракта №11 в
`app/services/prompts/literary_analysis.txt`: он попадает в существующий Docker
образ через `COPY app ./app`. Новых зависимостей нет: используются уже
зафиксированные Pydantic, pydantic-settings и httpx.

## Авторизация и время жизни

Получение OAuth-токена, UUID `RqUID`, scope, кэш до истечения срока и
обновление токена инкапсулированы в клиенте. Токен обновляется за 30 секунд до
истечения срока; при неожиданном HTTP 401 выполняется ровно одно повторное
получение токена. Используйте один экземпляр в пределах жизненного цикла
приложения/цикла asyncio, закрывая его через `async with` или `await aclose()`.

Проверка TLS включена всегда. `GIGACHAT_CA_BUNDLE` добавляется к системным
доверенным сертификатам. HTTP-перенаправления не выполняются. Ошибки клиента
не включают тела ответов, исходный текст модели или ключи.

## Валидация и повтор

1. Проверяется завершение генерации (`finish_reason=stop`).
2. Удаляется только полный внешний блок ```json или ``` без текста снаружи.
3. JSON строго разбирается: дубли ключей, NaN/Infinity и текст вокруг объекта
   отклоняются. Затем выполняется строгая Pydantic-валидация.
4. При неверном формате/схеме выполняется повтор с исходным пользовательским
   вводом и требованием исправить формат. По умолчанию максимум два запроса
   генерации. Ошибочный текст модели не становится новым входным заданием.
5. При исчерпании попыток — `GigaChatResponseError`. При сети, таймауте,
   проблемах OAuth или HTTP — `GigaChatUnavailableError` без автоматического
   повтора сетевых запросов. Ошибки конфигурации — `GigaChatConfigurationError`.
   Невалидные аргументы метода вызывают `pydantic.ValidationError` до обращения
   к сети. Эти ошибки не маскируются под успешный анализ.

Для генерации запрашивается JSON Schema, но локальная валидация обязательна.
Она проверяет структуру, а не истинность объяснения. В сохранённом примере
`image_prompt` добавляет кухню и возраст героини: это известное смысловое
ограничение модели, а не нарушение типов.

## Настройки

`GigaChatSettings` загружается при создании клиента, а не при импорте FastAPI.
Используются знакомые настройки задачи №9:

```dotenv
GIGACHAT_AUTH_KEY=
GIGACHAT_CLIENT_ID=
GIGACHAT_CLIENT_SECRET=
GIGACHAT_SCOPE=GIGACHAT_API_PERS
GIGACHAT_MODEL=GigaChat-2-Max
GIGACHAT_CA_BUNDLE=
GIGACHAT_TIMEOUT_SECONDS=8.0
GIGACHAT_MAX_ATTEMPTS=2
```

Задайте Authorization Key без `Basic` либо оба Client ID и Client Secret.
`GIGACHAT_API_KEY` из старого mock не используется. URL при необходимости
задаются через `GIGACHAT_AUTH_URL` и `GIGACHAT_CHAT_URL` (только HTTPS).
Максимальное количество попыток — от 1 до 3. По задаче №35 общий срок метода
ограничен 8 секундами, включая OAuth и повторы; меньшая настройка допускается.
Результаты кэшируются в памяти процесса с TTL 300 секунд.
Подробности: [таймаут и кэш](llm-reliability-and-cache.md).

При `GigaChatSettings.from_env_file(path)` относительный путь сертификата
считается от каталога указанного `.env`. Существующие переменные окружения
имеют приоритет, пустые настройки в `.env` игнорируются. `.env` не коммитится.

## Пример вызова

```python
import asyncio
from app.services.gigachat_client import GigaChatClient
from app.services.gigachat_settings import GigaChatSettings

async def main():
    settings = GigaChatSettings.from_env_file(".env")
    async with GigaChatClient(settings) as client:
        result = await client.analyze_text(
            selected_text="spill the beans",
            context="She promised to keep the engagement secret, but her sister asked her to spill the beans.",
            book_title=None,
        )
        print(type(result).__name__)  # AIAnalysis
        print(result.model_dump_json(indent=2))

asyncio.run(main())
```

## Проверки

Офлайн, Python с установленными `requirements.txt`:

```powershell
python -m pytest -q
```

Тесты используют httpx.MockTransport: реальных ключей и API-запросов нет.
Проверяются OAuth, кэш/обновление токена, TLS, валидация ввода и результата,
кодовые блоки, повтор и исчерпание попыток, повреждённый/обрезанный ответ,
таймауты, HTTP-ошибки, отсутствие секретов в сообщениях и закрытие соединения.

Реальный вызов выполняется явно и расходует API-токены:

```powershell
python scripts/check_gigachat_client.py --env-file "C:\lov3waste\NEXA-T\literature-reader-backend\.env" --log docs/gigachat-client-success.json
```

Скрипт по умолчанию выбирает GigaChat-2-Max; можно передать `--model`.
Результат успешного реального вызова от 17.10.2026 сохранён в
`docs/gigachat-client-success.json`: тип `AIAnalysis`, четыре поля, validation=passed.
Ни ключ, ни OAuth-токен в лог не записываются.

## Проверенная основа репозитория на 17.10.2026

Ветка `feature/gigachat-client` создана от `origin/develop` (`28857aa`),
в котором смержены каркас FastAPI/Docker (#12) и проверка подключения (#13).
На момент проверки `feature/api-contract` содержит новый mock-контракт,
`feature/with-sleep` — секундную задержку, `feature/tunneling` — инструкции
ngrok и необязательный env_file Compose. Калибровка №10 и её исправление
находятся в отдельных ветках и ещё не входят в develop. Их целиком не
переносили: для №25 взят только согласованный промпт.

Официальные справки:
- https://developers.sber.ru/docs/ru/gigachat/guides/structured-output
- https://pydantic.dev/docs/validation/latest/concepts/strict_mode/
