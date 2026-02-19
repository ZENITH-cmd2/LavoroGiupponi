# Guida al Deploy su Render.com

Questa guida spiega come mettere online l'applicazione utilizzando **Render.com** (servizio cloud moderno e semplice).

## Prerequisiti
1. Hai già caricato il codice su GitHub: [https://github.com/ZENITH-cmd2/LavoroGiupponi](https://github.com/ZENITH-cmd2/LavoroGiupponi)
2. Crea un account su [Render.com](https://render.com/).

## Procedura Passo-Passo

1. **Nuovo Servizio Web**
   - Dalla dashboard di Render, clicca su **New +** e seleziona **Web Service**.
   - Connetti il tuo account GitHub e seleziona il repository `LavoroGiupponi`.

2. **Configurazione**
   Immetti i seguenti parametri:
   - **Name**: Scegli un nome (es. `calor-dashboard`).
   - **Region**: `Frankfurt (EU Central)` (migliore latenza per l'Italia).
   - **Branch**: `main`.
   - **Root Directory**: Lascia vuoto (default `.`).
   - **Runtime**: `Python 3`.
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `gunicorn --chdir backend server:app`
   - **Plan**: `Free` (per test) o `Starter` (per produzione).

3. **Deploy**
   - Clicca su **Create Web Service**.
   - Render inizierà a scaricare il codice, installare le dipendenze e avviare il server.
   - Una volta finito, vedrai un bollino verde **Live** e un URL (es. `https://calor-dashboard.onrender.com`).

## ⚠️ ATTENZIONE: Il Database SQLite

Il database `calor_systems.db` è un file su disco.
Su servizi cloud come Render (versione Free), il disco è **effimero**: ogni volta che aggiorni il sito (nuovo deploy) o che il server si riavvia, **i file creati o modificati vengono persi** e il database torna allo stato iniziale (vuoto o quello di GitHub).

### Soluzione per la persistenza (Dati Reali)
Per salvare i dati in modo permanente hai due opzioni:

1. **Render Disk (Semplice, A Pagamento)**
   - Richiede il piano "Starter" ($7/mese).
   - Vai nella tab **Disks** del servizio.
   - Crea un disco chiamato `calor_db_data`.
   - Mount Path: `/opt/render/project/src/db`.
   - In questo modo la cartella `db` sarà persistente.

2. **Database Esterno (Avanzato)**
   - Usare un database PostgreSQL gestito (es. Render PostgreSQL).
   - Richiede modifiche al codice (`backend/core/database.py`) per usare SQLAlchemy o driver Postgres invece di SQLite.

## Note Aggiuntive
- L'upload dei file Excel funzionerà, ma i file temporanei verranno cancellati subito dopo l'elaborazione (corretto comportamento).
- I log dell'applicazione sono visibili nella dashboard di Render sezione "Logs".
