-- ============================================================================
-- 🏛️ CALOR SYSTEMS - DATABASE SCHEMA
-- Sistema di Riconciliazione Carburanti
-- ============================================================================
-- Creato per: Calor Systems (circa 20 distributori di carburante)
-- Scopo: Riconciliazione tra dati teorici (Fortech) e dati reali (verifica)
-- Compatibile con: SQLite / MySQL / PostgreSQL
-- ============================================================================

-- Pulisci tabelle esistenti (ordine inverso per rispettare foreign keys)
DROP TABLE IF EXISTS report_riconciliazioni;
DROP TABLE IF EXISTS eventi_sicurezza_casse;
DROP TABLE IF EXISTS verifica_credito_clienti;
DROP TABLE IF EXISTS verifica_satispay;
DROP TABLE IF EXISTS verifica_ip_portal;
DROP TABLE IF EXISTS verifica_numia;
DROP TABLE IF EXISTS verifica_contanti_as400;
DROP TABLE IF EXISTS import_fortech_dettaglio;
DROP TABLE IF EXISTS import_fortech_master;
DROP TABLE IF EXISTS impianti;

-- ============================================================================
-- 1. 🏢 NODO CENTRALE: ANAGRAFICA IMPIANTI
-- ============================================================================
-- Serve a collegare i diversi flussi di dati che usano codici diversi 
-- per lo stesso distributore.

CREATE TABLE impianti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Identificativi
    nome_impianto VARCHAR(150) NOT NULL,           -- Es. "Milano Repubblica", "Bossol Giuseppina"
    codice_pv_fortech VARCHAR(50) UNIQUE,          -- Es. "43809" (per incrociare Fortech e iP Portal)
    codice_contabile_as400 VARCHAR(50),            -- Es. "17" (per incrociare con AS400)
    codice_negozio_satispay VARCHAR(100),          -- Es. "43809 - OPT1" (per Satispay)
    codice_gestore VARCHAR(50),                    -- Es. "181706" (da IP Portal)
    
    -- Configurazione
    tipo_gestione VARCHAR(50) DEFAULT 'PRESIDIATO', -- "PRESIDIATO", "SELF_SERVICE", "MISTO"
    giorno_ritiro_cassa VARCHAR(20),               -- Es. "Giovedi" (per impianti Self come Taleggio)
    email_alert VARCHAR(255),                      -- Destinatari per notifiche anomalie
    
    -- Indirizzi
    indirizzo VARCHAR(255),
    cap VARCHAR(10),
    citta VARCHAR(100),
    provincia VARCHAR(10),
    
    -- Metadata
    attivo BOOLEAN DEFAULT TRUE,
    data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    note TEXT
);

-- ============================================================================
-- 2. 📉 IMPORT FORTECH - DATI TEORICI (FILE MADRE)
-- ============================================================================
-- Il dato "teorico" che detta quanto si dovrebbe aver incassato.
-- Importato giornalmente dal portale Fortech.

CREATE TABLE import_fortech_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    impianto_id INTEGER NOT NULL,
    
    -- Riferimento temporale
    codice_pv VARCHAR(50) NOT NULL,                -- CodicePV dall'Excel
    data_contabile DATE NOT NULL,                  -- DataContabile
    data_inizio DATETIME,                          -- DataInizio
    data_fine DATETIME,                            -- DataFine
    stato_giornata VARCHAR(50),                    -- StatoGiornata (Rettificata, Creata, etc.)
    
    -- ===== TOTALI GENERALI =====
    corrispettivo_totale DECIMAL(15, 2),           -- Corrispettivo Totale
    
    -- ===== CARBURANTE VERDE =====
    corrispettivo_verde DECIMAL(15, 2),
    volume_verde_fai_da_te DECIMAL(15, 4),
    importo_verde_fai_da_te DECIMAL(15, 2),
    prezzo_verde_fai_da_te DECIMAL(10, 4),
    volume_verde_servito DECIMAL(15, 4),
    importo_verde_servito DECIMAL(15, 2),
    prezzo_verde_servito DECIMAL(10, 4),
    volume_verde_prepay DECIMAL(15, 4),
    importo_verde_prepay DECIMAL(15, 2),
    prezzo_verde_prepay DECIMAL(10, 4),
    
    -- ===== CARBURANTE DIESEL =====
    corrispettivo_diesel DECIMAL(15, 2),
    volume_diesel_fai_da_te DECIMAL(15, 4),
    importo_diesel_fai_da_te DECIMAL(15, 2),
    prezzo_diesel_fai_da_te DECIMAL(10, 4),
    volume_diesel_servito DECIMAL(15, 4),
    importo_diesel_servito DECIMAL(15, 2),
    prezzo_diesel_servito DECIMAL(10, 4),
    volume_diesel_prepay DECIMAL(15, 4),
    importo_diesel_prepay DECIMAL(15, 2),
    prezzo_diesel_prepay DECIMAL(10, 4),
    
    -- ===== PRODOTTI NON-OIL =====
    corrispettivo_adblue DECIMAL(15, 2),
    corrispettivo_adblue_confezione DECIMAL(15, 2),
    corrispettivo_liquido_radiatore DECIMAL(15, 2),
    corrispettivo_lubrificanti DECIMAL(15, 2),
    corrispettivo_lavavetri DECIMAL(15, 2),
    
    -- ===== FATTURE E PAGAMENTI =====
    fatture_postpagate_totale DECIMAL(15, 2),      -- Carte petrolifere (postpagate)
    fatture_prepagate_totale DECIMAL(15, 2),       -- Carte petrolifere (prepagate)
    fatture_immediate_totale DECIMAL(15, 2),
    fatture_differite_totale DECIMAL(15, 2),
    buoni_totale DECIMAL(15, 2),                   -- Buoni virtuali/cartacei
    
    -- ===== CALCOLATI (per riconciliazione) =====
    -- Questi valori vengono calcolati: Totale - Elettronico = Contanti
    incasso_carte_bancarie_teorico DECIMAL(15, 2),
    incasso_carte_petrolifere_teorico DECIMAL(15, 2),
    incasso_buoni_teorico DECIMAL(15, 2),
    incasso_satispay_teorico DECIMAL(15, 2),
    incasso_credito_finemese_teorico DECIMAL(15, 2),
    incasso_contanti_teorico DECIMAL(15, 2),       -- Residuo = Contanti in cassa
    
    -- Metadata
    data_importazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_origine VARCHAR(255),
    
    FOREIGN KEY (impianto_id) REFERENCES impianti(id)
);

-- Indice per ricerche veloci per data e impianto
CREATE INDEX idx_fortech_data_impianto ON import_fortech_master(data_contabile, impianto_id);
CREATE INDEX idx_fortech_codice_pv ON import_fortech_master(codice_pv);

-- ============================================================================
-- 3A. 💰 VERIFICA CONTANTI (Fonte: AS400/Contabilità) - GIALLO
-- ============================================================================
-- Il nodo più critico: manca spesso la data certa e i versamenti sono arrotondati.

CREATE TABLE verifica_contanti_as400 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    impianto_id INTEGER,
    
    -- Date (sfasamento temporale con la vendita!)
    data_registrazione DATE,                        -- Registrazione//Data
    data_documento DATE,                            -- Documento//Data
    data_scadenza DATE,                             -- Scadenza
    data_competenza DATE,                           -- Dedotta se possibile
    
    -- Identificativi documento
    tipo_documento VARCHAR(50),                     -- Documento//Tipo
    numero_documento VARCHAR(100),                  -- Documento//Numero
    tipo_registrazione VARCHAR(50),                 -- Registrazione//Tipo
    numero_registrazione VARCHAR(100),              -- Registrazione//Numero
    
    -- Importi
    importo_versato DECIMAL(15, 2),                 -- Importo (spesso arrotondato!)
    segno VARCHAR(5),                               -- Segno (A = Avere, D = Dare)
    importo_valuta DECIMAL(15, 2),                  -- Importo val.
    valuta VARCHAR(10),                             -- Val
    
    -- Descrizioni
    descrizione TEXT,                               -- Descrizione
    descrizione_2 TEXT,                             -- Descrizione 2
    
    -- Centri di costo
    centro_costo VARCHAR(50),                       -- Centro di Costo
    c_costo VARCHAR(50),                            -- C/Costo
    
    -- Altri campi AS400
    stato VARCHAR(50),                              -- Stato
    pagamento VARCHAR(50),                          -- Pagam.
    tipo_pagamento VARCHAR(50),                     -- Tipo pag.
    partita VARCHAR(100),                           -- Partita
    
    -- Metadata
    data_importazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_origine VARCHAR(255),
    
    FOREIGN KEY (impianto_id) REFERENCES impianti(id)
);

CREATE INDEX idx_as400_data ON verifica_contanti_as400(data_registrazione);
CREATE INDEX idx_as400_impianto ON verifica_contanti_as400(impianto_id);

-- ============================================================================
-- 3B. 💳 VERIFICA CARTE BANCARIE (Fonte: Numia) - VERDE
-- ============================================================================
-- Riconciliazione solitamente precisa al centesimo.

CREATE TABLE verifica_numia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    impianto_id INTEGER,
    
    -- Transazione
    data_ora_transazione DATETIME,                  -- Data e ora
    importo DECIMAL(15, 2),                         -- Importo
    
    -- Carta
    codice_autorizzazione VARCHAR(50),              -- Codice autorizzazione
    numero_carta VARCHAR(100),                      -- Numero carta (mascherato)
    circuito VARCHAR(50),                           -- Circuito (MASTERCARD, PAGOBANCOMAT, etc.)
    tipo_transazione VARCHAR(50),                   -- Tipo transazione (Acquisto)
    stato_operazione VARCHAR(100),                  -- Stato operazione
    
    -- Valuta
    importo_valuta_originale DECIMAL(15, 2),        -- Importo in valuta originale
    valuta_originale VARCHAR(10),                   -- Valuta originale
    importo_cashback DECIMAL(15, 2),                -- Importo Cashback
    
    -- Punto vendita
    punto_vendita VARCHAR(100),                     -- Punto vendita
    id_punto_vendita VARCHAR(50),                   -- ID Punto vendita
    mid VARCHAR(50),                                -- MID
    id_terminale VARCHAR(50),                       -- ID Terminale / TML
    alias_terminale VARCHAR(100),                   -- Alias Terminale
    id_transazione_numia VARCHAR(100),              -- ID Transazione
    codice_ordine VARCHAR(100),                     -- Codice ordine
    
    -- Metadata
    data_importazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_origine VARCHAR(255),
    
    FOREIGN KEY (impianto_id) REFERENCES impianti(id)
);

CREATE INDEX idx_numia_data ON verifica_numia(data_ora_transazione);
CREATE INDEX idx_numia_impianto ON verifica_numia(impianto_id);

-- ============================================================================
-- 3C. ⛽ VERIFICA CARTE PETROLIFERE E BUONI (Fonte: iP Portal) - AZZURRO/ROSSO
-- ============================================================================
-- Unica tabella per entrambi i tipi. Distinzione tramite tipo_transazione.

CREATE TABLE verifica_ip_portal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    impianto_id INTEGER,
    
    -- Tipo record
    tipo_transazione VARCHAR(50) NOT NULL,          -- 'CARTA_PETROLIFERA' o 'BUONO'
    
    -- Identificativi (diversi tra Carte e Buoni)
    codice_gestore VARCHAR(50),                     -- Gestore
    codice_pv VARCHAR(50),                          -- PV (Carte) o Punto vendita (Buoni)
    codice_esercente VARCHAR(50),                   -- Esercente (solo Buoni)
    descrizione_esercente VARCHAR(255),             -- Descrizione esercente (Buoni)
    
    -- Transazione
    data_operazione DATE,                           -- Data operazione
    ora_operazione TIME,                            -- Ora operazione
    circuito VARCHAR(50),                           -- Circuito (DKV, CM IPPLUS, etc.)
    
    -- Prodotto
    codice_prodotto VARCHAR(50),                    -- Cod. Prod.
    prodotto VARCHAR(100),                          -- Prodotto (SsPb self, Gasolio Self, etc.)
    riferimento_scontrino VARCHAR(100),             -- Riferimento Scontrino
    
    -- Importi
    quantita DECIMAL(15, 4),                        -- Quantità
    prezzo DECIMAL(10, 4),                          -- Prezzo
    importo DECIMAL(15, 2),                         -- Importo
    segno VARCHAR(5),                               -- Segno (+ / -)
    
    -- Fattura
    numero_fattura VARCHAR(100),                    -- Numero Fattura
    data_fattura DATE,                              -- Data Fattura
    
    -- Campi aggiuntivi Buoni
    numero_documento VARCHAR(100),                  -- Numero documento
    codice_cliente VARCHAR(50),                     -- Codice cliente
    ragione_sociale_cliente VARCHAR(255),           -- Ragione sociale cliente
    pan VARCHAR(100),                               -- PAN
    serial_number VARCHAR(100),                     -- Serial number
    terminale VARCHAR(50),                          -- Terminale
    auth_code VARCHAR(50),                          -- Auth code
    ambiente_operativo VARCHAR(50),                 -- Ambiente operativo
    stato_buono VARCHAR(50),                        -- Stato buono
    valuta VARCHAR(10),                             -- Valuta
    flusso VARCHAR(50),                             -- Flusso (NEXI, etc.)
    
    -- Metadata
    data_importazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_origine VARCHAR(255),
    
    FOREIGN KEY (impianto_id) REFERENCES impianti(id)
);

CREATE INDEX idx_ip_data ON verifica_ip_portal(data_operazione);
CREATE INDEX idx_ip_tipo ON verifica_ip_portal(tipo_transazione);
CREATE INDEX idx_ip_impianto ON verifica_ip_portal(impianto_id);

-- ============================================================================
-- 3D. 📱 VERIFICA SATISPAY (Fonte: Portale Satispay) - GRIGIO
-- ============================================================================

CREATE TABLE verifica_satispay (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    impianto_id INTEGER,
    
    -- Transazione
    id_transazione VARCHAR(100),                    -- id transazione
    data_transazione DATETIME,                      -- data transazione
    
    -- Negozio
    negozio VARCHAR(100),                           -- negozio
    codice_negozio VARCHAR(100),                    -- codice negozio (es. "43809 - OPT1")
    
    -- Importi
    importo_totale DECIMAL(15, 2),                  -- importo totale
    totale_commissioni DECIMAL(15, 4),              -- totale commissioni
    importo_netto DECIMAL(15, 2),                   -- Calcolato: totale - commissioni
    
    -- Tipo
    tipo_transazione VARCHAR(50),                   -- tipo transazione (TO_BUSINESS)
    codice_transazione VARCHAR(50),                 -- codice transazione
    id_gruppo VARCHAR(100),                         -- id gruppo
    
    -- Metadata
    data_importazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_origine VARCHAR(255),
    
    FOREIGN KEY (impianto_id) REFERENCES impianti(id)
);

CREATE INDEX idx_satispay_data ON verifica_satispay(data_transazione);
CREATE INDEX idx_satispay_impianto ON verifica_satispay(impianto_id);

-- ============================================================================
-- 3E. 📄 VERIFICA CREDITO CLIENTI (Fonte: Fattura1Click)
-- ============================================================================

CREATE TABLE verifica_credito_clienti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    impianto_id INTEGER,
    
    -- Cliente
    codice_cliente VARCHAR(100),
    nome_cliente VARCHAR(255),                      -- Es. "Luca D'Alessandro SRL"
    partita_iva VARCHAR(50),
    
    -- Erogazione
    data_erogazione DATE,
    importo_erogazione DECIMAL(15, 2),
    
    -- Fattura
    numero_fattura VARCHAR(100),
    data_fattura DATE,
    
    -- Metadata
    data_importazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_origine VARCHAR(255),
    
    FOREIGN KEY (impianto_id) REFERENCES impianti(id)
);

CREATE INDEX idx_credito_data ON verifica_credito_clienti(data_erogazione);
CREATE INDEX idx_credito_impianto ON verifica_credito_clienti(impianto_id);

-- ============================================================================
-- 4. 🔐 EVENTI SICUREZZA CASSE (Specifico per Taleggio/Self)
-- ============================================================================
-- Gestisce il controllo dell'apertura casseforti basato sui sensori IoT Fortech.

CREATE TABLE eventi_sicurezza_casse (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    impianto_id INTEGER NOT NULL,
    
    -- Evento
    timestamp_apertura DATETIME NOT NULL,
    giorno_settimana VARCHAR(20),                   -- Es. "Giovedi" (giorno previsto per Taleggio)
    
    -- Rilevazioni
    importo_rilevato_fortech DECIMAL(15, 2),        -- Contante presente al momento dell'apertura
    importo_atteso DECIMAL(15, 2),                  -- Somma vendite dal precedente prelievo
    differenza DECIMAL(15, 2),                      -- Scostamento
    
    -- Alert
    apertura_autorizzata BOOLEAN,                   -- TRUE se giorno corretto
    alert_inviato BOOLEAN DEFAULT FALSE,
    data_alert DATETIME,
    destinatari_alert TEXT,
    
    -- Note
    note TEXT,
    
    FOREIGN KEY (impianto_id) REFERENCES impianti(id)
);

CREATE INDEX idx_sicurezza_timestamp ON eventi_sicurezza_casse(timestamp_apertura);
CREATE INDEX idx_sicurezza_impianto ON eventi_sicurezza_casse(impianto_id);

-- ============================================================================
-- 5. 📊 REPORT RICONCILIAZIONI (Output Motore di Riconciliazione)
-- ============================================================================
-- Risultato dell'elaborazione AI/Script che confronta Fortech vs Verifica.

CREATE TABLE report_riconciliazioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    impianto_id INTEGER NOT NULL,
    
    -- Riferimento
    data_riferimento DATE NOT NULL,
    fortech_master_id INTEGER,                      -- Link al record Fortech
    
    -- Categoria analizzata
    categoria VARCHAR(50) NOT NULL,                 -- CONTANTI, CARTE_BANCARIE, CARTE_PETROLIFERE, BUONI, SATISPAY, CREDITO
    
    -- Confronto valori
    valore_fortech DECIMAL(15, 2),                  -- Dal Master teorico
    valore_reale DECIMAL(15, 2),                    -- Dalle tabelle verifica (somma)
    differenza DECIMAL(15, 2),                      -- (valore_fortech - valore_reale)
    percentuale_scostamento DECIMAL(8, 4),          -- % di scostamento
    
    -- Esito
    stato VARCHAR(50) DEFAULT 'IN_ATTESA',          -- QUADRATO, ANOMALIA_LIEVE, ANOMALIA_GRAVE, IN_ATTESA
    tipo_anomalia VARCHAR(100),                     -- Es. "Mancato Versamento", "Arrotondamento", "Scontrino Mancante"
    soglia_tolleranza DECIMAL(15, 2),               -- Tolleranza usata per il check
    
    -- Gestione anomalia
    verificato_da VARCHAR(100),
    data_verifica DATETIME,
    risolto BOOLEAN DEFAULT FALSE,
    data_risoluzione DATETIME,
    note TEXT,
    
    -- Metadata
    data_elaborazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    versione_algoritmo VARCHAR(50),
    
    FOREIGN KEY (impianto_id) REFERENCES impianti(id),
    FOREIGN KEY (fortech_master_id) REFERENCES import_fortech_master(id)
);

CREATE INDEX idx_report_data ON report_riconciliazioni(data_riferimento);
CREATE INDEX idx_report_stato ON report_riconciliazioni(stato);
CREATE INDEX idx_report_impianto ON report_riconciliazioni(impianto_id);
CREATE INDEX idx_report_categoria ON report_riconciliazioni(categoria);

-- ============================================================================
-- 6. 📝 TABELLA LOG IMPORT
-- ============================================================================
-- Traccia tutte le importazioni di file Excel.

CREATE TABLE log_importazioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- File
    nome_file VARCHAR(255),
    percorso_file TEXT,
    tipo_file VARCHAR(50),                          -- FORTECH, AS400, NUMIA, IP_CARTE, IP_BUONI, SATISPAY
    
    -- Esito
    data_importazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    righe_lette INTEGER,
    righe_importate INTEGER,
    righe_errore INTEGER,
    
    -- Note
    errori TEXT,
    note TEXT
);

-- ============================================================================
-- 📌 DATI INIZIALI: IMPIANTO DI ESEMPIO (Milano Repubblica)
-- ============================================================================

INSERT INTO impianti (
    nome_impianto, 
    codice_pv_fortech, 
    codice_contabile_as400, 
    codice_negozio_satispay,
    codice_gestore,
    tipo_gestione,
    indirizzo,
    citta
) VALUES (
    'Milano - Della Repubblica 5',
    '43809',
    'CP001',
    '43809 - OPT1',
    '181706',
    'PRESIDIATO',
    'Via della Repubblica 5',
    'Milano'
);

-- Secondo impianto menzionato nei dati
INSERT INTO impianti (
    nome_impianto, 
    codice_pv_fortech, 
    codice_gestore,
    tipo_gestione,
    indirizzo
) VALUES (
    'Bozzolo - Giuseppina 7/BIS',
    '43958',
    '181706',
    'PRESIDIATO',
    'Via Giuseppina 7/BIS'
);

-- Terzo impianto (Rovetta)
INSERT INTO impianti (
    nome_impianto, 
    codice_pv_fortech, 
    tipo_gestione,
    indirizzo
) VALUES (
    'Rovetta - Via Fantoni 53',
    '42840',
    'PRESIDIATO',
    'Via Fantoni 53'
);

-- ============================================================================
-- 📊 VISTA: RIEPILOGO RICONCILIAZIONE GIORNALIERA
-- ============================================================================

CREATE VIEW v_riconciliazione_giornaliera AS
SELECT 
    r.data_riferimento,
    i.nome_impianto,
    i.codice_pv_fortech,
    r.categoria,
    r.valore_fortech,
    r.valore_reale,
    r.differenza,
    r.stato,
    CASE 
        WHEN r.stato = 'QUADRATO' THEN '✅'
        WHEN r.stato = 'ANOMALIA_LIEVE' THEN '⚠️'
        WHEN r.stato = 'ANOMALIA_GRAVE' THEN '❌'
        ELSE '⏳'
    END AS icona_stato
FROM report_riconciliazioni r
JOIN impianti i ON r.impianto_id = i.id
ORDER BY r.data_riferimento DESC, i.nome_impianto, r.categoria;

-- ============================================================================
-- 📊 VISTA: TOTALI GIORNALIERI PER IMPIANTO
-- ============================================================================

CREATE VIEW v_totali_giornalieri AS
SELECT 
    f.data_contabile,
    i.nome_impianto,
    f.corrispettivo_totale,
    f.fatture_postpagate_totale + f.fatture_prepagate_totale AS totale_carte_petrolifere,
    f.buoni_totale,
    COALESCE(
        (SELECT SUM(vn.importo) FROM verifica_numia vn 
         WHERE vn.impianto_id = i.id 
         AND DATE(vn.data_ora_transazione) = f.data_contabile),
        0
    ) AS totale_numia,
    COALESCE(
        (SELECT SUM(vs.importo_totale) FROM verifica_satispay vs 
         WHERE vs.impianto_id = i.id 
         AND DATE(vs.data_transazione) = f.data_contabile),
        0
    ) AS totale_satispay
FROM import_fortech_master f
JOIN impianti i ON f.impianto_id = i.id
ORDER BY f.data_contabile DESC;

-- ============================================================================
-- ✅ SCHEMA COMPLETATO
-- ============================================================================
-- 
-- Tabelle create:
--   1. impianti                    - Anagrafica distributori (HUB)
--   2. import_fortech_master       - Dati teorici vendite (File Madre)
--   3. verifica_contanti_as400     - Versamenti contanti (GIALLO)
--   4. verifica_numia              - Carte bancarie POS (VERDE)
--   5. verifica_ip_portal          - Carte petrolifere + Buoni (AZZURRO/ROSSO)
--   6. verifica_satispay           - Pagamenti app (GRIGIO)
--   7. verifica_credito_clienti    - Clienti fine mese
--   8. eventi_sicurezza_casse      - Alert sicurezza (per Self)
--   9. report_riconciliazioni      - Output riconciliazione
--  10. log_importazioni            - Tracciamento import
--
-- Viste create:
--   - v_riconciliazione_giornaliera
--   - v_totali_giornalieri
--
-- ============================================================================
