
@echo off
cd /d "%~dp0"
echo Installazione dipendenze in corso...
pip install -r requirements.txt
if errorlevel 1 (
    echo Errore durante l'installazione delle dipendenze.
    pause
    exit /b
)
echo Installazione completata con successo!
pause
