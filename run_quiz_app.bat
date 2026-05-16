@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%quiz-generator-rag-python\backend"
set "VENV_DIR=%ROOT_DIR%.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "ACTIVATE_BAT=%VENV_DIR%\Scripts\activate.bat"

echo.
echo === AI Quiz App Launcher ===
echo.

if not exist "%BACKEND_DIR%\main.py" (
    echo Could not find backend app at:
    echo %BACKEND_DIR%\main.py
    echo.
    pause
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    echo Virtual environment not found. Creating it now...
    py -3 -m venv "%VENV_DIR%"
    if errorlevel 1 (
        python -m venv "%VENV_DIR%"
    )
    if errorlevel 1 (
        echo.
        echo Failed to create virtual environment.
        echo Install Python, make sure it is available in PATH, then run this file again.
        echo.
        pause
        exit /b 1
    )
)

echo Activating virtual environment...
call "%ACTIVATE_BAT%"
if errorlevel 1 (
    echo.
    echo Failed to activate virtual environment:
    echo %ACTIVATE_BAT%
    echo.
    pause
    exit /b 1
)

echo.
echo Checking required libraries...
python -c "import fastapi, uvicorn, dotenv, openai, httpx, truststore" >nul 2>nul
if errorlevel 1 (
    echo Some libraries are missing. Installing required libraries...
    python -m pip install --upgrade pip
    if errorlevel 1 (
        echo.
        echo Could not upgrade pip. Continuing with requirements install...
    )

    python -m pip install -r "%BACKEND_DIR%\requirements.txt"
    if errorlevel 1 (
        echo.
        echo Failed to install requirements from PyPI.
        echo Check your internet connection, then run this file again.
        echo.
        pause
        exit /b 1
    )
) else (
    echo Required libraries already installed. Skipping internet install.
)

netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul
if not errorlevel 1 (
    echo.
    echo App is already running.
    echo Open this URL in your browser:
    echo http://127.0.0.1:8000
    echo.
    pause
    exit /b 0
)

echo.
echo Starting app...
echo Open this URL in your browser:
echo http://127.0.0.1:8000
echo.

cd /d "%BACKEND_DIR%"
python main.py

echo.
echo App stopped.
pause
