@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   LocalKB - Environment Setup
echo ========================================

:: Find Python
set "PYTHON="
for %%c in (python python3) do (
    if "%PYTHON%"=="" (
        "%%c" --version >nul 2>&1
        if not errorlevel 1 set "PYTHON=%%c"
    )
)
if "%PYTHON%"=="" (
    py --version >nul 2>&1
    if not errorlevel 1 set "PYTHON=py"
)
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
if "%PYTHON%"=="" (
    for %%d in ("%LOCALAPPDATA%\Programs\Python" "C:\Program Files\Python" "C:\Python") do (
        if exist "%%~d" (
            for /f "delims=" %%p in ('dir "%%~d\Python3*" /b /ad 2^>nul ^| sort /r') do (
                if "%PYTHON%"=="" (
                    if exist "%%~d\%%p\python.exe" set "PYTHON=%%~d\%%p\python.exe"
                )
            )
        )
    )
)
if "%PYTHON%"=="" (
    echo Python not found. Install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python: %PYTHON%

if not exist "venv\" (
    echo [1/2] Creating virtual environment...
    "%PYTHON%" -m venv venv
)

echo [2/2] Installing dependencies...
venv\Scripts\python -m pip install --upgrade pip -q
venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [RETRY] Mirror failed, trying default source...
    venv\Scripts\pip install -r requirements.txt
)

echo ========================================
echo   Setup complete! Run 启动.bat to start.
echo ========================================
pause
