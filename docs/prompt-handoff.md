# Передача задачи №10: контракт задачи №11

Актуальный промпт: `prompts/literary-analysis-task11.txt`, модель `GigaChat-2-Max`.
Основные пять результатов: `calibration/five-tests.json`.
Все восемь реальных ответов: `calibration/results-task11.json`.
Документ с входами, промптом, результатами и оценкой: `docs/prompt-calibration-report.md`.

## Схемы

- Запрос: `calibration/request.schema.json` — обязательные строки selected_text и context; опциональная строка book_title.
- Успех: `calibration/backend-response.schema.json` — translation и context_meaning (строки), slang_or_etymology и image_prompt (строки или null). Все четыре ключа обязательны.
- Ошибка сервера: `calibration/error.schema.json` — единственный ключ error со строкой сообщения.
- Примеры трёх форматов: `calibration/contract-examples.json`.

Схемы намеренно отвергают дополнительные поля, чтобы старый контракт не принимался молча. Отсутствие context и context=null невалидны; пустая строка допустима по предоставленному ТЗ. Локальная политика приёма также отклоняет пустые translation/context_meaning, строки-заглушки "null"/"none" и image_prompt при пустом контексте. Это дополнительные проверки качества, не новые требования текста задачи №11.

## Приём ответа

Передавать промпт отдельным system-сообщением, вход — сериализованным JSON в user. Запрашивать response_format json_schema и strict=true, но всегда локально проверять finish_reason, JSON и типы полей. Отвергать дубли ключей, NaN/Infinity, Markdown, текст вокруг JSON и старые поля. При ошибке — одна попытка исправления с исходным вводом, затем контролируемая ошибка сервера. Недоступность нейросети и некорректный Request обрабатывает сервер через {"error":"..."}; модельный успешный Response не должен содержать error.

Никакой валидатор формы не гарантирует смысловую точность. В новых результатах смысл распознан, но image_prompt иногда добавляет возраст и позы персонажей. Во всех примерах slang_or_etymology=null; нужен отдельный набор для оценки сленга/этимологии с непустыми значениями.

Это исправление материалов задачи №10. Изменения Pydantic-схем и mock-эндпоинта в app/ нужно взять из согласованной работы Данила по задаче №11. В этой основе app/ всё ещё использует старый контракт.

## Запуск в PowerShell

Из `C:\lov3waste\NEXA-T\gigachat-json-contract`:

```powershell
& "C:\Users\vladi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -X utf8 .\calibration\run_calibration.py --env-file "C:\lov3waste\NEXA-T\literature-reader-backend\.env" --structured
```

Новый прогон сохраняется в results-task11-new.json. Ключи не копируются в папку и не записываются в результаты. Можно использовать любой Python 3.10+. Запросы расходуют API-токены.

Для всех тестов проекта нужен Python с зависимостями requirements.txt:

```powershell
python -m pytest -q
```

Старые материалы сохранены в calibration/archive/pre-task11 и не являются актуальной спецификацией.
