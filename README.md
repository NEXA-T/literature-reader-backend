# literature-reader-backend

## Проверка подключения к GigaChat API (#9)

Изолированный скрипт: `test_gigachat.py` (Python 3.10+, без зависимостей).
Регистрация, настройка ключа, сертификаты и запуск описаны в
[инструкции](docs/gigachat-setup.md).

Офлайн-проверки (не обращаются к API):

```powershell
py -3 -m unittest discover -s tests -v
```


## Внешний доступ к серверу через ngrok (№23

1. Установить ngrok: https://ngrok.com/download
2. Зарегистрироваться и получить authtoken в личном кабинете
3. Настроить один раз: ngrok config add-authtoken <твой-токен>
4. Запустить бэкенд: docker compose up --build
5. В отдельном терминале запустить туннель: ngrok http 8000
6. Скопировать публичную ссылку из вывода ngrok (вида https://abc123.ngrok-free.app).
7. Открыть Swagger: https://abc123.ngrok-free.app/docs

На бесплатном тарифе ссылка меняется при каждом перезапуске ngrok
## Литературный анализ: контракт задачи №11

Актуальный промпт: `prompts/literary-analysis-task11.txt`.
[Новые реальные ответы и оценка](docs/prompt-calibration-report.md).
[Пять JSON-тестов](calibration/five-tests.json).
[Передача для валидации](docs/prompt-handoff.md).

Поля ответа: `translation`, `context_meaning`, `slang_or_etymology`,
`image_prompt`. Старые материалы в `calibration/archive/pre-task11`
сохранены для истории и больше не задают контракт.
Изменения касаются калибровки; схемы mock в `app/` согласуются отдельно.
## Изолированный GigaChatClient (#25)

[Настройка, пример вызова, валидация и повтор](docs/gigachat-client.md).
[Лог реального успешного вызова](docs/gigachat-client-success.json).

Сервис возвращает строгий Pydantic-объект с полями контракта №11;
подключение к FastAPI выполняется отдельно.


## Запуск демо-стенда
Для запуска бэкенда и ngrok-туннеля одной командой используйте:
```cmd
run_demo.bat

## Надёжность LLM и кэш (#35)

[Общий таймаут 8 с, TTL-кэш, визуальный промпт и тесты](docs/llm-reliability-and-cache.md).
[Замер реального вызова и кэша](docs/llm-cache-measurement.json).
[Лог тестов](docs/llm-reliability-tests.txt).
