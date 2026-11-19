@echo off
setlocal
cd /d "%~dp0"
where flutter >nul 2>nul
if errorlevel 1 (
  echo Flutter is not installed or is not on PATH.
  echo Install the Flutter SDK, reopen this window, then run this file again.
  exit /b 1
)
if not exist "android\gradle\wrapper\gradle-wrapper.jar" (
  echo Creating the standard Android and iOS Flutter runner folders...
  flutter create --platforms=android,ios --org=org.signbridge --project-name=signbridge_mobile .
  if errorlevel 1 exit /b 1
)
if not exist "android\app\src\main" mkdir "android\app\src\main"
copy /y "platform\AndroidManifest.xml" "android\app\src\main\AndroidManifest.xml" >nul
if errorlevel 1 exit /b 1
if not exist "ios\Runner" mkdir "ios\Runner"
copy /y "platform\Info.plist" "ios\Runner\Info.plist" >nul
if errorlevel 1 exit /b 1
flutter pub get
if errorlevel 1 exit /b 1
echo Mobile dependencies and platform runners are ready.
echo Run flutter run to launch the app on a connected phone or simulator.
endlocal
