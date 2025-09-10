@echo off
echo ===============================
echo Updating Client files...
echo ===============================

:: Enable ANSI escape sequences
for /F "tokens=2 delims=:." %%i in ('ver') do if %%i GEQ 10 ( >nul 2>&1 reg query HKCU\Console || reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f )

:: Navigate to script directory
cd /d "%~dp0"

:: Define variables
set REPO_URL=https://github.com/mr-velosofy/Chat-Controls-Streamer/archive/refs/heads/master.zip
set TMP_DIR=tmp_repo
set ZIP_FILE=repo.zip

:: Cleanup old temp files
if exist %ZIP_FILE% del /f /q %ZIP_FILE%
if exist %TMP_DIR% rmdir /s /q %TMP_DIR%

:: Download latest repo ZIP
echo Downloading latest repo...
powershell -Command "Invoke-WebRequest -Uri '%REPO_URL%' -OutFile '%ZIP_FILE%'"

:: Extract ZIP
echo Extracting files...
powershell -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%TMP_DIR%'"

:: Find extracted folder name (first subfolder inside tmp_repo)
for /d %%i in (%TMP_DIR%\*) do set EXTRACTED=%%i

:: Copy only new/updated files, leave others intact
echo Copying updated Client files from %EXTRACTED%\Client ...

:: Make sure target folder exists so xcopy doesn't ask F/D question
if not exist "Client" mkdir "Client"

xcopy "%EXTRACTED%\Client" "Client" /E /D /Y /EXCLUDE:config.json .venv\




:: Cleanup
del /f /q %ZIP_FILE%
rmdir /s /q %TMP_DIR%

echo ===============================
echo Update complete!
echo ===============================

:: Check if config.json exists
if exist "Client\config.json" (
    echo Found config.json, starting Client\start_v2.bat ...
    call "Client\start_v2.bat"
) else (
    echo.
    echo [91m===============================
    echo   ERROR: CONFIG.JSON NOT FOUND!
    echo   PLEASE CREATE AND SET UP YOUR CONFIG.JSON FILE.
    echo ===============================[0m
    echo.
    pause
    exit /b
)

exit
