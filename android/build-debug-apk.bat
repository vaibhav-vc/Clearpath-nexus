@echo off
setlocal
cd /d %~dp0
if "%ANDROID_HOME%"=="" if "%ANDROID_SDK_ROOT%"=="" (
  echo Set ANDROID_HOME or ANDROID_SDK_ROOT to your Android SDK path.
  exit /b 1
)
call gradlew.bat --no-daemon clean assembleDebug
if errorlevel 1 exit /b %errorlevel%
if not exist "app\build\outputs\apk\debug\app-debug.apk" (
  echo APK not found.
  exit /b 1
)
copy /Y "app\build\outputs\apk\debug\app-debug.apk" "..\ClearPathNexus-debug.apk" >nul
echo Built: %CD%\..\ClearPathNexus-debug.apk
endlocal
