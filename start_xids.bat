@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\activate.bat" (
  echo Virtual environment missing. Run setup_windows.bat first.
  pause
  exit /b 1
)
if not exist "frontend\node_modules" (
  echo Frontend dependencies missing. Run setup_windows.bat first.
  pause
  exit /b 1
)
start "X-IDS Backend - Django" cmd /k "cd /d ""%~dp0"" && call ""%~dp0venv\Scripts\activate.bat"" && python manage.py runserver 127.0.0.1:8000"
start "X-IDS Frontend - React" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"
echo.
echo Backend:  http://127.0.0.1:8000/api/health/
echo Website:  http://127.0.0.1:5173/
echo.
echo For live packet capture or firewall blocking, run this launcher as Administrator.
echo Close both terminal windows to stop X-IDS.
pause
