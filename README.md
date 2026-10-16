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