@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [Ошибка] Не найдено .venv. Создайте окружение:
  echo   python -m venv .venv
  echo   .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py
pause
