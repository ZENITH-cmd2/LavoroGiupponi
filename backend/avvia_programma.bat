@echo off
setlocal enabledelayedexpansion
title Calor Systems - Startup Script

echo =========================================
echo Calor Systems - Inizializzazione Ambiente
echo =========================================

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python non rilevato nel sistema.
    echo.
    echo E' necessario installare Python dal Microsoft Store...
    echo.
    echo Si aprira' lo Store. Clicca "Ottieni" o "Installa" e attendi il completamento.
    echo Una volta installato Python, chiudi questa finestra e riavvia lo script.
    echo.
    pause
    start ms-windows-store://pdp/?productid=9NCVDN91XZQP
    exit /b
)

:: Validate Python installation
for /f "delims=" %%i in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set pyver=%%i
echo [INFO] Rilevata versione Python: %pyver%

:: Setup Virtual Environment
set VENV_DIR=%~dp0.venv
if not exist "%VENV_DIR%" (
    echo [INFO] Creazione dell'ambiente virtuale...
    python -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo [ERRORE] Impossibile creare l'ambiente virtuale.
        pause
        exit /b
    )
)

:: Attivazione venv
call "%VENV_DIR%\Scripts\activate.bat"

:: Aggiornamento pip silenzioso
echo [INFO] Aggiornamento dei tool di base (pip)...
python -m pip install --upgrade pip >nul 2>&1

:: Installazione dipendenze
echo [INFO] Controllo e installazione delle dipendenze...
:: Utilizzo pip install in modo piu' silenzioso per non spammare la console
pip install -r "%~dp0requirements.txt" --quiet

if %errorlevel% neq 0 (
    echo [ERRORE] Problema durante l'installazione delle dipendenze!
    echo Prova a rieseguire il file come amministratore o disattiva temporaneamente i filtri di rete.
    pause
    exit /b
)

echo [OK] Tutte le dipendenze sono installate.

:: Avvio App
echo =========================================
echo Avvio in corso...
echo =========================================
:: Cambia la cartella di lavoro a quella dove si trova lo script backend
cd /d "%~dp0"

:: Facciamo partire pythonw così creiamo il processo in background e la console si può chiudere, oppure semplicemente python
:: Dal momento che l'app ha un server Flask e interfaccia CTK, conviene python ma facendolo partire e chiudendo il terminale
start "" python "main.py"

:: Attendere un secondo per evitare kill brutali iniziali
timeout /t 1 /nobreak >nul

exit
