@echo off
setlocal
cd /d "%~dp0"
if exist ".env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do set "%%A=%%B"
)
if not defined SIGNBRIDGE_API_HOST set "SIGNBRIDGE_API_HOST=0.0.0.0"
if not defined SIGNBRIDGE_API_PORT set "SIGNBRIDGE_API_PORT=8000"
if not defined SIGNBRIDGE_WEB_PORT set "SIGNBRIDGE_WEB_PORT=5173"
if not exist ".venv\Scripts\python.exe" (
  echo Creating a project-local Python environment...
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.14 -m venv .venv >nul 2>nul
    if errorlevel 1 py -3.13 -m venv .venv >nul 2>nul
    if errorlevel 1 py -3.12 -m venv .venv >nul 2>nul
    if errorlevel 1 py -3.11 -m venv .venv >nul 2>nul
    if errorlevel 1 py -3.10 -m venv .venv >nul 2>nul
    if errorlevel 1 (
      echo Python 3.10 through 3.14 is required. Install Python 3.14 and select the Python launcher.
      pause
      exit /b 1
    )
  ) else (
    where python >nul 2>nul
    if errorlevel 1 (
      echo Python 3.10 or newer was not found. Install Python and select Add Python to PATH.
      pause
      exit /b 1
    )
    python -m venv .venv
  )
  if errorlevel 1 (
    echo Could not create the Python environment.
    pause
    exit /b 1
  )
)
.venv\Scripts\python.exe -c "import sys;raise SystemExit(0 if (3,10) <= sys.version_info[:2] < (3,15) else 1)"
if errorlevel 1 goto :python_version_error
rem Install (again) whenever requirements.txt differs from the copy saved after the last install.
fc /b requirements.txt ".venv\requirements.installed.txt" >nul 2>nul
if errorlevel 1 (
  echo Installing Python dependencies. This needs internet access.
  .venv\Scripts\python.exe -m pip install --upgrade pip
  if errorlevel 1 goto :python_error
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto :python_error
  copy /y requirements.txt ".venv\requirements.installed.txt" >nul
)
rem Model files that are downloaded once and checked against their pinned SHA-256 (pose, face, ASL).
.venv\Scripts\python.exe tools\fetch_assets.py
if errorlevel 1 echo Some model files could not be downloaded; the features that need them stay off until you connect to the internet and run this again.
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js was not found. Install Node.js 22.12 or newer, reopen this window, then run this file again.
  pause
  exit /b 1
)
node -e "const v=process.versions.node.split('.').map(Number);process.exit(v[0]>22 || (v[0]===22 && v[1]>=12) ? 0 : 1)"
if errorlevel 1 (
  echo Node.js 22.12 or newer is required. Update Node.js, reopen this window, then run this file again.
  pause
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo npm was not found. Reinstall Node.js with npm included, reopen this window, then run this file again.
  pause
  exit /b 1
)
rem Install (again) whenever web\package.json differs from the copy saved after the last install.
fc /b web\package.json "web\node_modules\.signbridge-package.json" >nul 2>nul
if errorlevel 1 (
  echo Installing website dependencies. This needs internet access.
  pushd web
  call npm install
  if errorlevel 1 (
    popd
    echo Website dependency installation failed.
    pause
    exit /b 1
  )
  copy /y package.json "node_modules\.signbridge-package.json" >nul
  popd
)
echo Starting SignBridge API and website...
start "SignBridge API" "%~dp0start_backend.bat"
start "SignBridge Web" "%~dp0start_web.bat"
timeout /t 8 /nobreak >nul
echo.
echo Local website: http://127.0.0.1:%SIGNBRIDGE_WEB_PORT%
echo Local API:     http://127.0.0.1:%SIGNBRIDGE_API_PORT%
echo Phone browsers need HTTPS for camera access; the Flutter app uses the local API directly.
echo Wi-Fi addresses on this computer:
ipconfig | findstr /i "IPv4"
start "" "http://127.0.0.1:%SIGNBRIDGE_WEB_PORT%"
exit /b 0

:python_error
echo Python dependencies could not be installed. Check internet access and the exact error above.
pause
exit /b 1

:python_version_error
echo Python 3.10 through 3.14 is required by the current MediaPipe package. Install Python 3.14 and run this file again.
echo If this project already has a .venv folder from Python 3.15, remove that project-local .venv folder before retrying.
pause
exit /b 1
