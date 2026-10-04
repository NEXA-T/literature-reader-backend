# literature-reader-backend

## Проверка подключения к GigaChat API (#9)

Изолированный скрипт: `test_gigachat.py` (Python 3.10+, без зависимостей).
Регистрация, настройка ключа, сертификаты и запуск описаны в
[инструкции](docs/gigachat-setup.md).

Офлайн-проверки (не обращаются к API):

```powershell
py -3 -m unittest discover -s tests -v
```
