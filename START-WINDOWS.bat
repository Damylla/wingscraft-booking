@echo off
cd /d "%~dp0"
py -3 run.py
if errorlevel 1 (
  echo.
  echo Python launch failed. Make sure Python 3.10+ is installed.
  pause
)
