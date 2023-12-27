@echo off
setlocal

:: Check for Python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python is not installed.
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b
)

:: Check for pip
python -m pip --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo pip is not installed.
    echo Attempting to install pip...
    python -m ensurepip
    if %ERRORLEVEL% NEQ 0 (
        echo Failed to install pip.
        pause
        exit /b
    )
)

:: Run the Python script in a minimized window
start /min python "mp3 tag editor.py"
