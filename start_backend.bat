@echo off
setlocal
cd /d "%~dp0"
if exist ".env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do set "%%A=%%B"
)
if not defined SIGNBRIDGE_API_HOST set "SIGNBRIDGE_API_HOST=0.0.0.0"
if not defined SIGNBRIDGE_API_PORT set "SIGNBRIDGE_API_PORT=8000"
if not exist ".venv\Scripts\python.exe" (
  echo Run start_signbridge.bat once to install the project dependencies first.
  exit /b 1
)
.venv\Scripts\python.exe -m uvicorn backend.app:app --host %SIGNBRIDGE_API_HOST% --port %SIGNBRIDGE_API_PORT%
