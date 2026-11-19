@echo off
rem SignBridge Phase 1 gate checks on a real Windows computer.
rem   1. installs what the checks need (Python packages, web packages, pose + face models, a test browser)
rem   2. runs every test suite and writes the results to reports\phase1_checks\
rem   3. opens the capture frame-rate benchmark in your browser
rem It needs internet access the first time (about 1 GB of downloads with the test browser).
rem Nothing is uploaded; the benchmark keeps camera frames in the browser tab.
setlocal
cd /d "%~dp0"
set "OUT=reports\phase1_checks"
if not exist "%OUT%" mkdir "%OUT%"

echo [1/6] Python environment
if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.13 -m venv .venv >nul 2>nul
    if errorlevel 1 py -3.12 -m venv .venv >nul 2>nul
    if errorlevel 1 py -3.14 -m venv .venv >nul 2>nul
    if errorlevel 1 py -3.11 -m venv .venv >nul 2>nul
    if errorlevel 1 py -3.10 -m venv .venv >nul 2>nul
  ) else (
    python -m venv .venv
  )
)
if not exist ".venv\Scripts\python.exe" (
  echo Python 3.10 to 3.14 was not found. Install Python 3.13 from python.org, then run this file again.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pip install --upgrade pip > "%OUT%\pip_log.txt" 2>&1
.venv\Scripts\python.exe -m pip install -r requirements.txt >> "%OUT%\pip_log.txt" 2>&1
if errorlevel 1 (
  echo Python package installation failed. See %OUT%\pip_log.txt
  pause
  exit /b 1
)
copy /y requirements.txt ".venv\requirements.installed.txt" >nul

echo [2/6] Web packages and test browser
where npm >nul 2>nul
if errorlevel 1 (
  echo Node.js with npm was not found. Install Node.js 22.12 or newer, then run this file again.
  pause
  exit /b 1
)
pushd web
call npm install > "..\%OUT%\npm_log.txt" 2>&1
if errorlevel 1 (
  popd
  echo Web package installation failed. See %OUT%\npm_log.txt
  pause
  exit /b 1
)
copy /y package.json "node_modules\.signbridge-package.json" >nul
call npm install --no-save playwright >> "..\%OUT%\npm_log.txt" 2>&1
call npx playwright install chromium >> "..\%OUT%\npm_log.txt" 2>&1
popd

echo [3/6] Model files (MediaPipe pose and face, ASL model), checked against their pinned SHA-256
.venv\Scripts\python.exe tools\fetch_assets.py > "%OUT%\models_log.txt" 2>&1
if errorlevel 1 echo Model download failed; the benchmark and ASL mode will not start. See %OUT%\models_log.txt

echo [4/6] Machine details
(
  echo Measured on:
  ver
  powershell -NoProfile -Command "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name; 'RAM GB: ' + [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1); Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"
  .venv\Scripts\python.exe --version
  .venv\Scripts\python.exe -c "import mediapipe, numpy, sklearn; print('mediapipe', mediapipe.__version__, 'numpy', numpy.__version__, 'scikit-learn', sklearn.__version__)"
  node --version
) > "%OUT%\machine.txt" 2>&1

echo [5/6] Test suites (this takes a few minutes)
where flutter >nul 2>nul
if not errorlevel 1 (
  pushd mobile
  call flutter pub get > "..\%OUT%\flutter_log.txt" 2>&1
  call flutter analyze >> "..\%OUT%\flutter_log.txt" 2>&1
  popd
)
.venv\Scripts\python.exe tools\run_all_tests.py --smoke > "%OUT%\tests_log.txt" 2>&1
set "TESTS_EXIT=%errorlevel%"
.venv\Scripts\python.exe tools\sync_vocabulary.py --check >> "%OUT%\tests_log.txt" 2>&1
echo.
echo ===== Test summary =====
.venv\Scripts\python.exe -c "import sys;t=open(sys.argv[1],encoding='utf-8',errors='replace').read();print(t[t.rfind('=== Summary ==='):])" "%OUT%\tests_log.txt"
echo Full log: %OUT%\tests_log.txt  (exit code %TESTS_EXIT%)
echo.

echo [6/6] Frame-rate benchmark
echo A new window starts the website. When the benchmark page opens:
echo   sit in front of the camera with your upper body and face in view, allow the camera,
echo   press Start benchmark, wait 30 seconds, press Copy result,
echo   then paste the result into %OUT%\bench_result.json (or into the chat).
start "SignBridge Web (close when done)" "%~dp0start_web.bat"
timeout /t 10 /nobreak >nul
start "" "http://localhost:5173/bench.html"
echo.
echo Done. Send the files in %OUT% back to Claude.
pause
endlocal
