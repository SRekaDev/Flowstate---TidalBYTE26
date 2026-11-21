@echo off
setlocal
title Flowstate - Windows startup
echo Starting Flowstate...
pushd "%~dp0" || goto folder_error
if not exist "app.py" goto folder_error
if not exist "requirements.txt" goto folder_error
if exist ".venv\Scripts\python.exe" goto packages
echo [1/3] Checking for 64-bit Python 3.11...
py -3.11 -c "import sys,struct; sys.exit(sys.version_info[:2] != (3,11) or struct.calcsize('P') != 8)" >nul 2>&1
if errorlevel 1 goto python_fallback
echo Creating the local Python environment. This can take a minute.
py -3.11 -m venv .venv
if errorlevel 1 goto failed
goto packages
:python_fallback
python -c "import sys,struct; sys.exit(sys.version_info[:2] != (3,11) or struct.calcsize('P') != 8)" >nul 2>&1
if errorlevel 1 goto python_error
echo Creating the local Python environment. This can take a minute.
python -m venv .venv
if errorlevel 1 goto failed
:packages
if exist ".venv\flowstate-viewer-v1-ready" goto launch
echo [2/3] Installing packages. First setup needs internet and may take several minutes.
".venv\Scripts\python.exe" -m pip --disable-pip-version-check install -r requirements.txt
if errorlevel 1 goto failed
echo ready>".venv\flowstate-viewer-v1-ready"
:launch
echo [3/3] Opening the Flowstate window. Leave this console open during your session.
".venv\Scripts\python.exe" -u app.py
if errorlevel 1 goto failed
popd
exit /b 0
:folder_error
echo Extract the entire ZIP to a writable folder, then run Start-Flowstate.cmd inside it.
goto stop
:python_error
echo Could not find 64-bit Python 3.11. Install it with the Python launcher, then try again.
goto stop
:failed
echo Flowstate could not start. Copy the error above or take a screenshot.
:stop
pause
exit /b 1
