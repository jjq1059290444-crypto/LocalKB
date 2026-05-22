@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: ============================================
:: Find a working Python (3.10+)
:: ============================================
set "PYTHON="

:: 1) python / python3 on PATH
for %%c in (python python3) do (
    if "%PYTHON%"=="" (
        "%%c" --version >nul 2>&1
        if not errorlevel 1 set "PYTHON=%%c"
    )
)

:: 2) py launcher (ships with official Python)
if "%PYTHON%"=="" (
    py --version >nul 2>&1
    if not errorlevel 1 set "PYTHON=py"
)

:: 3) Check registry (both HKLM and HKCU) for Python installs
if "%PYTHON%"=="" (
    for /f "tokens=*" %%i in ('reg query "HKLM\SOFTWARE\Python\PythonCore" 2^>nul ^| findstr "PythonCore\\"') do set "REG_PY=%%i"
    if not "%REG_PY%"=="" (
        for /f "tokens=2,*" %%a in ('reg query "%REG_PY%\InstallPath" /ve 2^>nul ^| findstr "REG_SZ"') do (
            if exist "%%b\python.exe" set "PYTHON=%%b\python.exe"
        )
    )
)

if "%PYTHON%"=="" (
    for /f "tokens=*" %%i in ('reg query "HKCU\SOFTWARE\Python\PythonCore" 2^>nul ^| findstr "PythonCore\\"') do set "REG_PY=%%i"
    if not "%REG_PY%"=="" (
        for /f "tokens=2,*" %%a in ('reg query "%REG_PY%\InstallPath" /ve 2^>nul ^| findstr "REG_SZ"') do (
            if exist "%%b\python.exe" set "PYTHON=%%b\python.exe"
        )
    )
)

:: 4) Common install locations
if "%PYTHON%"=="" (
    for %%d in (
        "%LOCALAPPDATA%\Programs\Python"
        "C:\Program Files\Python"
        "C:\Python"
    ) do (
        if exist "%%~d" (
            for /f "delims=" %%p in ('dir "%%~d\Python3*" /b /ad 2^>nul ^| sort /r') do (
                if "%PYTHON%"=="" (
                    if exist "%%~d\%%p\python.exe" set "PYTHON=%%~d\%%p\python.exe"
                )
            )
        )
    )
)

:: 5) Nothing found
if "%PYTHON%"=="" (
    echo ========================================
    echo   Python 3.10+ is required
    echo ========================================
    echo.
    echo   Python was not found on this computer.
    echo.
    echo   Please install it from:
    echo   https://www.python.org/downloads/
    echo.
    echo   IMPORTANT: Check "Add Python to PATH"
    echo   during installation.
    echo ========================================
    pause
    exit /b 1
)

echo Python found: %PYTHON%

:: ============================================
:: Check if setup is complete
:: ============================================
set "NEED_SETUP="
if not exist "venv\" set "NEED_SETUP=1"
if "%NEED_SETUP%"=="" (
    venv\Scripts\python -c "import qdrant_client" >nul 2>&1
    if errorlevel 1 set "NEED_SETUP=1"
)

if "%NEED_SETUP%"=="1" (
    echo.
    echo ========================================
    echo   LocalKB - First Time Setup
    echo ========================================
    echo.

    if not exist "venv\" (
        echo [1/2] Creating virtual environment...
        "%PYTHON%" -m venv venv
        if errorlevel 1 (
            echo [ERROR] Failed to create virtual environment.
            pause
            exit /b 1
        )
    ) else (
        echo [1/2] Virtual environment exists, rechecking dependencies...
    )

    echo [2/2] Installing dependencies...
    venv\Scripts\python -m pip install --upgrade pip -q
    venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [WARN] Mirror failed, trying default source...
        venv\Scripts\pip install -r requirements.txt
        if errorlevel 1 (
            echo [ERROR] Failed to install dependencies.
            pause
            exit /b 1
        )
    )

    echo.
    echo Setup complete! Starting LocalKB...
    echo ========================================
)

:: ============================================
:: Launch
:: ============================================
start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0desktop_app\main.py"
