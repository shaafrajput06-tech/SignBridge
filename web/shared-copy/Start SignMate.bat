@echo off
rem Starts SignMate on this computer and opens it in your browser. Close the window that opens to stop it.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0serve.ps1"
