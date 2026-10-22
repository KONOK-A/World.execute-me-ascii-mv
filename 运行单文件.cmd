@echo off
setlocal
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
if not exist "%~dp0world-execute-mv.pyz" (
    echo Keep this launcher beside world-execute-mv.pyz.
    pause
    exit /b 1
)
where py >nul 2>nul
if errorlevel 1 goto python
py -3 "%~dp0world-execute-mv.pyz" %*
goto finished
:python
python "%~dp0world-execute-mv.pyz" %*
:finished
set "MV_EXIT=%ERRORLEVEL%"
if not "%MV_EXIT%"=="0" pause
exit /b %MV_EXIT%
