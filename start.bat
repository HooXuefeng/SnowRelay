@echo off
setlocal
cd /d "%~dp0"
if exist "dist\SnowRelay-v0.5.0\SnowRelay.exe" (
  start "" "dist\SnowRelay-v0.5.0\SnowRelay.exe"
  exit /b 0
)
if not exist ".venv\Scripts\pythonw.exe" call install.bat /nopause
if errorlevel 1 (
  echo SnowRelay could not prepare the source runtime.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "%~dp0main.py" --gui
exit /b 0
