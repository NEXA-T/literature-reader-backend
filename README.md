# literature-reader-backend

## Проверка подключения к GigaChat API (#9)

Изолированный скрипт: `test_gigachat.py` (Python 3.10+, без зависимостей).
Регистрация, настройка ключа, сертификаты и запуск описаны в
[инструкции](docs/gigachat-setup.md).

Офлайн-проверки (не обращаются к API):

```powershell
py -3 -m unittest discover -s tests -v
```

## Литературный анализ: контракт задачи №11

Актуальный промпт: `prompts/literary-analysis-task11.txt`.
[Новые реальные ответы и оценка](docs/prompt-calibration-report.md).
[Пять JSON-тестов](calibration/five-tests.json).
[Передача для валидации](docs/prompt-handoff.md).

Поля ответа: `translation`, `context_meaning`, `slang_or_etymology`,
`image_prompt`. Старые материалы в `calibration/archive/pre-task11`
сохранены для истории и больше не задают контракт.
Изменения касаются калибровки; схемы mock в `app/` согласуются отдельно.
