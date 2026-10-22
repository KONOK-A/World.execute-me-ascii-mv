@echo off
setlocal DisableDelayedExpansion
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
if not exist "%~dp0world-execute-mv.pyz" (
    echo Keep this launcher beside world-execute-mv.pyz.
    pause
    exit /b 1
)
set "PYTHON_MANAGER_AUTOMATIC_INSTALL=false"
set "MV_BOOTSTRAP=%~dp0ensure-runtime.ps1"
set "MV_RUNTIME_MANIFEST=%~dp0python-runtime.json"
set "MV_RUNTIME_ROOT=%LOCALAPPDATA%\world-execute-mv"
set "MV_PYTHON_ARGS="
set "MV_HAVE_PYTHON=1"
py -3 -I -B -c "import sys,ctypes,json,zipfile,unicodedata,msvcrt; raise SystemExit(sys.version_info < (3,9))" >nul 2>nul
if errorlevel 1 goto check_python
set "MV_PYTHON=py"
set "MV_PYTHON_ARGS=-3"
goto prerequisites
:check_python
python -I -B -c "import sys,ctypes,json,zipfile,unicodedata,msvcrt; raise SystemExit(sys.version_info < (3,9))" >nul 2>nul
if errorlevel 1 goto check_cache
set "MV_PYTHON=python"
goto prerequisites
:check_cache
set "MV_PYTHON=%MV_RUNTIME_ROOT%\runtime\python.exe"
if not exist "%MV_PYTHON%" goto download
"%MV_PYTHON%" -I -B -c "import sys,ctypes,json,zipfile,unicodedata,msvcrt; raise SystemExit(sys.version_info < (3,9))" >nul 2>nul
if not errorlevel 1 goto prerequisites
:download
set "MV_HAVE_PYTHON=0"
:prerequisites
if not exist "%MV_BOOTSTRAP%" goto missing_setup
if not exist "%MV_RUNTIME_MANIFEST%" goto missing_setup
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -Command "try { & ([scriptblock]::Create([IO.File]::ReadAllText($env:MV_BOOTSTRAP,[Text.Encoding]::UTF8))) } catch { [Console]::Error.WriteLine('MV setup failed: '+$_.Exception.Message); exit 1 }"
if errorlevel 1 goto finished
rem Keep original arguments outside IF blocks; runpy also supports isolated embedded Python.
"%MV_PYTHON%" %MV_PYTHON_ARGS% -I -B -c "import pathlib,runpy,sys;p=sys.argv.pop(1);sys.argv[0]=p;sys.path.insert(0,str(pathlib.Path(p).resolve().parent));runpy.run_path(p,run_name='__main__')" "%~dp0world-execute-mv.pyz" %*
goto finished
:missing_setup
echo Runtime setup files are missing. Re-extract the complete release ZIP.
set "MV_EXIT=1"
goto failed
:finished
set "MV_EXIT=%ERRORLEVEL%"
:failed
if not "%MV_EXIT%"=="0" pause
exit /b %MV_EXIT%
