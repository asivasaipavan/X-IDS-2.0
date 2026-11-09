@echo off
setlocal
cd /d "%~dp0"
echo =====================================================
echo   X-IDS 2.0 - Windows setup
echo =====================================================
py -3.11 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.11 was not found. Install Python 3.11.x and enable Add Python to PATH.
  pause
  exit /b 1
)
if not exist "venv\Scripts\python.exe" py -3.11 -m venv venv
call "venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto :failed
pip install -r requirements.txt
if errorlevel 1 goto :failed
python manage.py migrate
if errorlevel 1 goto :failed
where npm >nul 2>&1
if errorlevel 1 (
  echo Node.js/npm not found. Install Node.js 20 or newer, then run: cd frontend ^&^& npm install
  goto :done
)
cd frontend
if not exist "node_modules" npm install
if errorlevel 1 goto :failed
cd ..
echo.
echo Setup completed. Run start_xids.bat to start the backend and frontend.
goto :done
:failed
echo.
echo Setup failed. Read the error above, correct it, and rerun this file.
:done
pause
