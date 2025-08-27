@echo off
title Client Agent Installer
color 0A
setlocal ENABLEDELAYEDEXPANSION

:: Go to script's folder
cd /d %~dp0

:: Stylized Header
echo.
echo ====================================================
echo              CLIENT AGENT INSTALLER
echo ====================================================
echo.

:: Check Python
echo [*] Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [!] Python not found. Installing latest version...
    powershell -Command "Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.13.7/python-3.13.7-amd64.exe -OutFile python_installer.exe"
    echo [*] Installing Python 3.13.7 silently...
    start /wait python_installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    del python_installer.exe
    color 0A
    echo [OK] Python installed successfully!
) else (
    echo [OK] Python already installed.
)

:: =============================================
:: Create/Check virtual environment (.venv)
:: =============================================
echo.
echo [*] Checking for virtual environment (.venv)...
if not exist ".venv" (
    echo [!] No venv found. Creating one...
    python -m venv .venv
    if errorlevel 1 (
        color 0C
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

:: Activate venv
echo.
echo [*] Activating virtual environment...
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    color 0C
    echo [ERROR] Failed to activate virtual environment!
    pause
    exit /b 1
)
echo [OK] Virtual environment activated.

:: =============================================
:: Ensure pip inside venv
:: =============================================
echo.
echo [*] Ensuring pip in venv...
python -m ensurepip --upgrade >nul 2>&1
python -m pip install --upgrade pip

:: =============================================
:: Install requirements inside venv
:: =============================================
if exist requirements.txt (
    echo.
    echo [*] Installing dependencies from requirements.txt into venv...
    python -m pip install -r requirements.txt
    echo [OK] Dependencies installed in venv!
) else (
    color 0E
    echo [!] requirements.txt not found. Skipping dependency installation.
    color 0A
)

:: =============================================
:: Run client_agent_v2.py inside venv as Admin
:: =============================================
echo.
echo ====================================================
echo     Launching Client Agent (inside .venv) as Admin
echo ====================================================
echo.

powershell -Command "Start-Process '.venv\Scripts\python.exe' 'client_agent.py' -Verb RunAs"

echo.
color 0B
echo [DONE] Setup complete. Client Agent is now running in its own venv.
echo.
pause
