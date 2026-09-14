@echo off
setlocal
cd /d "%~dp0"
echo SnowRelay is preparing the source runtime...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-runtime.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo Runtime installation completed.
) else (
  echo Runtime installation failed. Review the error shown above.
)
if /I not "%~1"=="/nopause" pause
exit /b %RESULT%
