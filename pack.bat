@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "NAME=LocalKB"
set "OUTDIR=%~dp0release"

echo ========================================
echo   Packing %NAME% for distribution
echo ========================================

:: Clean output
if exist "%OUTDIR%" rmdir /s /q "%OUTDIR%"
mkdir "%OUTDIR%\%NAME%"

echo Copying files (skipping venv, caches, IDE files)...

:: Copy everything, then we'll delete unwanted dirs
robocopy "%~dp0" "%OUTDIR%\%NAME%" /E /XD venv .vscode .idea .claude release >nul

:: Remove __pycache__ directories
for /d /r "%OUTDIR%\%NAME%" %%d in (__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d"
)

:: Remove unwanted files
del /s /q "%OUTDIR%\%NAME%\*.pyc" 2>nul
del /q "%OUTDIR%\%NAME%\CONTINUE.md" 2>nul
del /q "%OUTDIR%\%NAME%\.gitignore" 2>nul
del /q "%OUTDIR%\%NAME%\.gitattributes" 2>nul
del /q "%OUTDIR%\%NAME%\pack.bat" 2>nul

:: Ensure data directory exists (empty, for runtime use)
mkdir "%OUTDIR%\%NAME%\data" 2>nul

:: Show what will be packaged
echo.
echo Files to be packaged:
powershell -Command ^
    "(Get-ChildItem '%OUTDIR%\%NAME%' -Recurse -File | Measure-Object -Property Length -Sum | ForEach-Object { ^
        Write-Host ('Total: {0:N0} KB ({1:N1} MB)' -f ($_.Sum/1KB), ($_.Sum/1MB)) ^
    })"

echo.
echo ========================================
echo   Creating zip archive...
echo ========================================

powershell -Command ^
    "Compress-Archive -Path '%OUTDIR%\%NAME%\*' -DestinationPath '%OUTDIR%\%NAME%.zip' -Force"

powershell -Command ^
    "\$zip = Get-Item '%OUTDIR%\%NAME%.zip'; Write-Host ('Archive: ' + \$zip.Name + ' (' + [math]::Round(\$zip.Length/1KB, 0).ToString() + ' KB)')"

echo.
echo ========================================
echo   Done! See release\ folder
echo ========================================
pause
