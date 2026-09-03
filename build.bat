@echo off
setlocal
cd /d "%~dp0"

set "OUT=%~1"
if "%OUT%"=="" set "OUT=dist"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo ERROR: %PY% not found. Create the venv and install requirements first.
    exit /b 1
)

echo Building ADHDFeedbackServer.exe ...
"%PY%" -m PyInstaller main.spec --distpath "%OUT%" --workpath build --noconfirm
if errorlevel 1 exit /b 1

echo.
echo Done. Built ADHDFeedbackServer.exe into: %OUT%
echo Attach it to the GitHub release as the exe asset, or copy it
echo (with a .env) into a folder and run it.
endlocal
