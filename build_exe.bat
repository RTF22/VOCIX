@echo off
echo === VOCIX Build ===
echo.

:: Pruefen ob PyInstaller installiert ist
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller nicht gefunden. Installiere...
    pip install pyinstaller
)

echo.
echo Baue VOCIX.exe ...
pyinstaller vocix.spec --noconfirm

echo.
echo Kopiere .env.example ...
copy .env.example dist\VOCIX\.env.example >nul 2>&1

echo.
if exist dist\VOCIX\VOCIX.exe (
    echo === Build erfolgreich! ===
    echo.
    echo Portable App liegt in: dist\VOCIX\
    echo.
    echo Naechste Schritte:
    echo   1. dist\VOCIX\ an beliebigen Ort kopieren
    echo   2. .env.example zu .env umbenennen und API-Key eintragen
    echo   3. VOCIX.exe starten
    echo.
    echo Das Whisper-Modell wird beim ersten Start automatisch
    echo in den Unterordner "models\" heruntergeladen.
) else (
    echo === Build fehlgeschlagen! ===
)
pause
