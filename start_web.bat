@echo off
setlocal
cd /d "%~dp0web"
rem Install (again) whenever package.json differs from the copy saved after the last install.
fc /b package.json "node_modules\.signbridge-package.json" >nul 2>nul
if errorlevel 1 (
  echo Installing web dependencies...
  call npm install
  if errorlevel 1 exit /b 1
  copy /y package.json "node_modules\.signbridge-package.json" >nul
)
npm run dev
