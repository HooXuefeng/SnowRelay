@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo SnowRelay is preparing an isolated build environment...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build-exe.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo Build completed: dist\SnowRelay-v0.5.0\SnowRelay.exe
) else (
  echo Build failed. Review the error shown above.
)
if /I not "%~1"=="/nopause" pause
exit /b %RESULT%
