@echo off
setlocal

set PROJECT_DIR=C:\Users\SoftClansUser\Desktop\rechiro\Rechiro
set NGROK_CONFIG=%PROJECT_DIR%\logs\ngrok.yml
set NGROK_BIN=%PROJECT_DIR%\ngrok\ngrok.exe

if "%NGROK_AUTHTOKEN%"=="" (
    echo ERROR: NGROK_AUTHTOKEN environment variable is not set.
    echo Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
    pause
    exit /b 1
)

cd /d "%PROJECT_DIR%"

echo Starting Django server on port 8000...
start "Django Server" cmd /c "venv\Scripts\activate && python manage.py runserver 0.0.0.0:8000"

timeout /t 3 /nobreak >nul

echo Starting ngrok tunnel...
start "ngrok" cmd /c ""%NGROK_BIN%" start --config "%NGROK_CONFIG%" kuppetsiaya"

echo.
echo ==========================================
echo App should be available at:
echo https://albert-incult-superfluously.ngrok-free.dev
echo ==========================================

pause
