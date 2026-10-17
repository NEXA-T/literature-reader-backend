# literature-reader-backend

## Проверка подключения к GigaChat API (#9)

Изолированный скрипт: `test_gigachat.py` (Python 3.10+, без зависимостей).
Регистрация, настройка ключа, сертификаты и запуск описаны в
[инструкции](docs/gigachat-setup.md).

Офлайн-проверки (не обращаются к API):

```powershell
py -3 -m unittest discover -s tests -v
```

## Изолированный GigaChatClient (#25)

[Настройка, пример вызова, валидация и повтор](docs/gigachat-client.md).
[Лог реального успешного вызова](docs/gigachat-client-success.json).

Сервис возвращает строгий Pydantic-объект с полями контракта №11;
подключение к FastAPI выполняется отдельно.

## Литературный бенчмарк и иллюстрация (#26)

[Таблица качества 15 реальных литературных тестов](benchmarks/literary/report.md).
[Повторный запуск и методика](benchmarks/literary/README.md).
[Сгенерированная иллюстрация](benchmarks/literary/illustration/scene.jpg).
