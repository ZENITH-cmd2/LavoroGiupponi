# Guida al Deploy su Vercel

Questa guida spiega come deployare l'app su **Vercel**.

## ⚠️ ATTENZIONE CRITICA: DATABASE SQLITE

Vercel è una piattaforma "Serverless".
Questo significa che il file system è **Read-Only** (sola lettura) e **Effimero**.
**Il database `calor_systems.db` NON funzionerà correttamente:**
1. Ogni volta che l'app si riavvia (o ad ogni richiesta), il DB torna allo stato iniziale.
2. I tentativi di scrittura (Upload file, salvataggio analisi) falliranno o verranno persi immediatamente.

**SOLUZIONE CONSIGLIATA**: Usare **Render.com** (vedi `DEPLOY.md`) che supporta dischi persistenti, oppure migrare a un database esterno (PostgreSQL/Supabase).

Se vuoi procedere comunque per testare l'interfaccia (in sola lettura):

## Configurazione

Il file `vercel.json` è già incluso nel repository.

## Procedura

1. Vai su [Vercel](https://vercel.com) e fai Login con GitHub.
2. Clicca su **Add New Project**.
3. Importa il repository `LavoroGiupponi`.
4. Vercel rileverà automaticamente la configurazione Python.
5. Clicca **Deploy**.

## Limiti noti su Vercel
- **Nessuna persistenza**: I dati caricati vanno persi subito.
- **Timeout**: Le funzioni serverless hanno un timeout breve (10-60 secondi), l'analisi di file grossi potrebbe fallire.
