@echo off
setlocal
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
where py >nul 2>nul
if errorlevel 1 goto python
py -3 "%~dp0player.py" %*
goto finished
:python
python "%~dp0player.py" %*
:finished
set "MV_EXIT=%ERRORLEVEL%"
if not "%MV_EXIT%"=="0" pause
exit /b %MV_EXIT%
