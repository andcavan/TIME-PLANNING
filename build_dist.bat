@echo off
setlocal enabledelayedexpansion
title Build — APP Timesheet

echo ============================================
echo  BUILD DISTRIBUZIONE — APP Timesheet
echo ============================================
echo.

:: Leggi versione dal file VERSION
set "VERSION="
if exist "VERSION" (
    set /p VERSION=<VERSION
    set "VERSION=!VERSION: =!"
) else (
    echo [ERRORE] File VERSION non trovato.
    pause
    exit /b 1
)
echo [INFO] Versione: !VERSION!
echo.

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato nel PATH.
    pause
    exit /b 1
)

:: Verifica/installa PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installazione PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERRORE] Impossibile installare PyInstaller.
        pause
        exit /b 1
    )
)

:: Verifica dipendenze app
echo [INFO] Verifica dipendenze...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERRORE] Installazione dipendenze fallita.
    pause
    exit /b 1
)

:: Verifica spec file
set "SPEC_FILE=APP-Timesheet-v!VERSION!.spec"
if not exist "!SPEC_FILE!" (
    echo [ERRORE] File spec non trovato: !SPEC_FILE!
    echo         Assicurarsi che il file spec corrisponda alla versione in VERSION.
    pause
    exit /b 1
)

:: Pulizia build precedente
echo [INFO] Pulizia cartelle build precedenti...
if exist "build" rmdir /s /q "build"
if exist "dist"  rmdir /s /q "dist"

:: Build con PyInstaller
echo.
echo [INFO] Avvio build PyInstaller con !SPEC_FILE!...
echo.
pyinstaller "!SPEC_FILE!" --noconfirm

if errorlevel 1 (
    echo.
    echo [ERRORE] Build fallita. Controlla i messaggi sopra.
    pause
    exit /b 1
)

:: Verifica output
set "EXE_NAME=APP-Timesheet-v!VERSION!"
if not exist "dist\!EXE_NAME!\!EXE_NAME!.exe" (
    echo [ERRORE] Eseguibile non trovato dopo la build.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  BUILD COMPLETATA CON SUCCESSO
echo ============================================
echo.
echo  Output: dist\!EXE_NAME!\
echo.
echo  Per distribuire: copiare l'intera cartella
echo  dist\!EXE_NAME!\ sul PC di destinazione.
echo.

:: Apri cartella output
explorer "dist\!EXE_NAME!"

pause
