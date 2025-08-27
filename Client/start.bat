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
    powershell -Command "Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.12.5/python-3.12.5-amd64.exe -OutFile python_installer.exe"
    echo [*] Installing Python 3.12.5 silently...
    start /wait python_installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    del python_installer.exe
    color 0A
    echo [OK] Python installed successfully!
) else (
    echo [OK] Python already installed.
)

:: Check pip
echo.
echo [*] Checking for pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [!] Pip not found. Installing pip...
    powershell -Command "Invoke-WebRequest -Uri https://bootstrap.pypa.io/get-pip.py -OutFile get-pip.py"
    python get-pip.py
    del get-pip.py
    color 0A
    echo [OK] Pip installed successfully!
) else (
    echo [OK] Pip already installed.
)

:: Upgrade pip
echo.
echo [*] Upgrading pip...
python -m pip install --upgrade pip

:: Install requirements
if exist requirements.txt (
    echo.
    echo [*] Installing dependencies from requirements.txt...
    python -m pip install -r requirements.txt
    echo [OK] Dependencies installed!
) else (
    color 0E
    echo [!] requirements.txt not found. Skipping dependency installation.
    color 0A
)

:: Run client_agent.py as admin
echo.
echo ====================================================
echo         Launching Client Agent as Administrator
echo ====================================================
echo.
powershell -Command "Start-Process python 'client_agent.py' -Verb RunAs"

echo.
color 0B
echo [DONE] Setup complete. Client Agent is now running.
echo.
pause
