@echo off
setlocal
chcp 65001 >nul

echo Literature Reader - Demo Stand Launcher

REM 1. Проверка: Docker и ngrok доступны
where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker не найден в PATH. Установи Docker Desktop.
    pause
    exit /b 1
)
where ngrok >nul 2>&1
if errorlevel 1 (
    echo [ERROR] ngrok не найден в PATH. Установи: winget install ngrok.ngrok
    pause
    exit /b 1
)

REM 2. Запуск бэкенда
echo [1/3] Поднимаю контейнеры...
docker compose up -d --build
if errorlevel 1 (
    echo [ERROR] docker compose up завершился с ошибкой. Смотри лог выше.
    pause
    exit /b 1
)

echo [2/3] Ждём запуска бэкенда (10 секунд)...
timeout /t 10 /nobreak >nul

REM 3. Запуск ngrok в отдельном окне
echo [3/3] Запускаю ngrok-туннель...
start "ngrok tunnel" cmd /c "ngrok http 8000"

REM 4. Ждём, пока ngrok поднимется, и достаём URL из его локального API
echo Ожидаю ngrok API...
set PUBLIC_URL=
for /L %%i in (1,1,15) do (
    if not defined PUBLIC_URL (
        for /f "delims=" %%u in ('powershell -NoProfile -Command "try { (Invoke-RestMethod http://localhost:4040/api/tunnels).tunnels[0].public_url } catch { }"') do set PUBLIC_URL=%%u
        if not defined PUBLIC_URL timeout /t 1 /nobreak >nul
    )
)

if not defined PUBLIC_URL (
    echo [WARN] Не удалось автоматически получить публичный URL.
    echo        Открой в браузере http://localhost:4040 и скопируй ссылку оттуда.
    pause
    exit /b 0
)

REM 5. Красивый вывод ссылки
echo.
echo Swagger UI:        %PUBLIC_URL%/docs
echo Health check:      %PUBLIC_URL%/api/v1/health
echo Explain:           %PUBLIC_URL%/api/v1/explain
echo.
echo Логи бэкенда:   docker compose logs -f backend
echo Остановить:     docker compose down  +  закрыть окно ngrok
echo.

REM 6. Открыть Swagger в браузере
start "" "%PUBLIC_URL%/docs"

pause
endlocal