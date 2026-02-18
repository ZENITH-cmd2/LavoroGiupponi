@echo off
cd /d "%~dp0"
echo ==============================
echo  Calor Systems Reconciler
echo ==============================
echo.
python backend\main.py
if errorlevel 1 (
    echo.
    echo Si e' verificato un errore. Controlla i messaggi sopra.
    pause
)
