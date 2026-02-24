import pandas as pd
import re
import os
from datetime import datetime
from core.database import Database
from core.file_classifier import FileClassifier

class DataImporter:
    def __init__(self, db_instance: Database):
        self.db = db_instance

    @staticmethod
    def _safe_val(val):
        """Convert pandas NaT/NaN/None to Python None for SQLite."""
        if val is None:
            return None
        if isinstance(val, float) and pd.isna(val):
            return None
        if pd.isna(val):
            return None
        # Convert Timestamp to ISO string
        if isinstance(val, pd.Timestamp):
            return val.isoformat()
        return val

    def import_files(self, file_paths, progress_callback=None):
        """
        Imports a list of files.
        progress_callback: function(current, total, message)
        """
        conn = self.db.get_connection()
        classified = FileClassifier.classify_files(file_paths)
        total_files = len(file_paths)
        processed = 0

        try:
            # Map types to import functions
            import_functions = {
                "FORTECH": self._import_fortech,
                "AS400": self._import_as400,
                "NUMIA": self._import_numia,
                "IP_CARTE": self._import_ip_carte,
                "IP_BUONI": self._import_ip_buoni,
                "SATISPAY": self._import_satispay
            }

            for f_type, paths in classified.items():
                if f_type == "UNKNOWN":
                    processed += len(paths)
                    continue
                
                if f_type in import_functions:
                    func = import_functions[f_type]
                    for path in paths:
                        if progress_callback:
                            progress_callback(processed, total_files, f"Importing {f_type}: {os.path.basename(path)}")
                        
                        try:
                            # Pass 'conn' to keep transaction open or manage inside? 
                            # Used passed conn for batch commit capability if needed, or simple commit per file.
                            # The original functions committed internally.
                            func(conn, path)
                        except Exception as e:
                            print(f"Error importing {path}: {e}")
                            if progress_callback:
                                progress_callback(processed, total_files, f"Error: {e}")
                        
                        processed += 1
            
            if progress_callback:
                progress_callback(total_files, total_files, "Import complete.")

        finally:
            conn.close()

    # --- Helper Methods from original script ---
    
    def _estrai_codice_pv(self, testo):
        if pd.isna(testo):
            return None
        match = re.match(r'(\d+)', str(testo))
        return match.group(1) if match else str(testo)

    def _ottieni_impianto_id(self, conn, codice_pv):
        codice = self._estrai_codice_pv(codice_pv)
        if not codice:
            return None
        
        cur = conn.cursor()
        cur.execute("SELECT id FROM impianti WHERE codice_pv_fortech = ?", (codice,))
        result = cur.fetchone()
        
        if result:
            return result[0]
        else:
            cur.execute("""
                INSERT INTO impianti (nome_impianto, codice_pv_fortech, tipo_gestione)
                VALUES (?, ?, 'PRESIDIATO')
            """, (f"Impianto {codice}", codice))
            conn.commit()
            return cur.lastrowid

    # --- Import Functions (Adapted) ---

    def _import_fortech(self, conn, file_path):
        # ── Read both sheets from the Fortech Excel ──
        xls = pd.ExcelFile(file_path)
        sheet_names = [s.lower() for s in xls.sheet_names]
        
        # Sheet "Vendite" (or first sheet) = corrispettivi, volumi, fatture
        df_vendite = pd.read_excel(xls, sheet_name=0)
        df_vendite = df_vendite.where(pd.notna(df_vendite), None)
        
        # Sheet "Incassi" = suddivisione per metodo di pagamento
        df_incassi = None
        incassi_map = {}  # key: (codice_pv, data_contabile) → incassi row
        
        if len(xls.sheet_names) > 1:
            for idx, sn in enumerate(xls.sheet_names):
                if sn.lower() in ('incassi', 'incasso', 'pagamenti'):
                    df_incassi = pd.read_excel(xls, sheet_name=idx)
                    df_incassi = df_incassi.where(pd.notna(df_incassi), None)
                    break
            if df_incassi is None:
                # Fallback: try second sheet
                df_incassi = pd.read_excel(xls, sheet_name=1)
                df_incassi = df_incassi.where(pd.notna(df_incassi), None)
        
        # Build lookup map from Incassi sheet
        if df_incassi is not None:
            for _, row in df_incassi.iterrows():
                key = (str(row.get('CodicePV', '')), str(row.get('DataContabile', '')))
                
                # Carte bancarie = somma di tutti i pagamenti elettronici bancari
                carte_bancarie = sum(filter(None, [
                    row.get('CARTA CREDITO GENERICA', 0) or 0,
                    row.get('PAGOBANCOMAT', 0) or 0,
                    row.get('AMEX', 0) or 0,
                    row.get('BANCOMAT GESTORE', 0) or 0,
                    row.get('CARTA CREDITO GESTORE', 0) or 0,
                ]))
                
                # Carte petrolifere = somma di tutti i network petroliferi
                carte_petrolifere = sum(filter(None, [
                    row.get('CARTAPETROLIFERA', 0) or 0,
                    row.get('DKV', 0) or 0,
                    row.get('UTA', 0) or 0,
                    row.get('CARTAMAXIMA', 0) or 0,
                ]))
                
                incassi_map[key] = {
                    'contanti': row.get('CONTANTI', 0) or 0,
                    'carte_bancarie': carte_bancarie,
                    'carte_petrolifere': carte_petrolifere,
                    'satispay': row.get('PAGAMENTIINNOVATIVI', 0) or 0,
                    'credito_finemese': row.get('CLIENTI CON FATTURA FINE MESE', 0) or 0,
                    'buoni': row.get('BUONI', 0) or 0,
                }
        
        # ── Import rows ──
        righe_importate = 0
        cur = conn.cursor()
        
        for _, row in df_vendite.iterrows():
            codice_pv = str(row.get('CodicePV', ''))
            impianto_id = self._ottieni_impianto_id(conn, codice_pv)
            if not impianto_id: continue
                
            # Valori dal foglio Vendite
            corrispettivo_totale = row.get('Corrispettivo Totale', 0) or 0
            fatture_post = row.get('Fatture Postpagate Totale', 0) or 0
            fatture_pre = row.get('Fatture Prepagate Totale', 0) or 0
            buoni_tot = row.get('Buoni Totale', 0) or 0
            
            # Valori teorici dal foglio Incassi (se disponibile)
            data_contabile = str(row.get('DataContabile', ''))
            key = (codice_pv, data_contabile)
            inc = incassi_map.get(key, {})
            
            incasso_contanti = inc.get('contanti', 0)
            incasso_carte_bancarie = inc.get('carte_bancarie', 0)
            incasso_carte_petrolifere = inc.get('carte_petrolifere', None)
            incasso_satispay = inc.get('satispay', 0)
            incasso_credito = inc.get('credito_finemese', 0)
            
            # Se il foglio Incassi non è disponibile, fallback al calcolo
            if not inc and corrispettivo_totale > 0:
                incasso_contanti = corrispettivo_totale - fatture_post - fatture_pre - buoni_tot
            
            cur.execute("""
                INSERT INTO import_fortech_master (
                    impianto_id, codice_pv, data_contabile, data_inizio, data_fine,
                    stato_giornata, corrispettivo_totale, corrispettivo_verde, corrispettivo_diesel,
                    volume_verde_prepay, importo_verde_prepay, prezzo_verde_prepay,
                    volume_diesel_prepay, importo_diesel_prepay, prezzo_diesel_prepay,
                    fatture_postpagate_totale, fatture_prepagate_totale, 
                    fatture_immediate_totale, fatture_differite_totale, buoni_totale,
                    incasso_carte_bancarie_teorico, incasso_carte_petrolifere_teorico,
                    incasso_satispay_teorico, incasso_credito_finemese_teorico,
                    incasso_contanti_teorico,
                    file_origine
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                impianto_id, codice_pv, row.get('DataContabile'), row.get('DataInizio'),
                row.get('DataFine'), row.get('StatoGiornata'), corrispettivo_totale,
                row.get('CorrispettivoVerde', 0), row.get('CorrispettivoDiesel', 0),
                row.get('VolumeVerdePrepay', 0), row.get('ImportoVerdePrepay', 0), row.get('PrezzoVerdePrepay', 0),
                row.get('VolumeDieselPrepay', 0), row.get('ImportoDieselPrepay', 0), row.get('PrezzoDieselPrepay', 0),
                fatture_post, fatture_pre,
                row.get('Fatture Immediate Totale', 0), row.get('Fatture Differite Totale', 0),
                buoni_tot,
                incasso_carte_bancarie, incasso_carte_petrolifere,
                incasso_satispay, incasso_credito,
                incasso_contanti,
                os.path.basename(file_path)
            ))
            righe_importate += 1
        conn.commit()

    def _import_as400(self, conn, file_path):
        df = pd.read_excel(file_path)
        df = df.where(pd.notna(df), None)
        righe_importate = 0
        # Default to Milano Repubblica (43809) if not specified, matching original script behavior
        impianto_id = self._ottieni_impianto_id(conn, "43809") 
        cur = conn.cursor()

        for _, row in df.iterrows():
            importo = row.get('Importo')
            reg_data = row.get('Registrazione//Data')
            
            # Skip empty rows or detail lines (which have no Registration Date)
            if pd.isna(importo) or pd.isna(reg_data): 
                continue
            
            cur.execute("""
                INSERT INTO verifica_contanti_as400 (
                    impianto_id, data_registrazione, data_documento, data_scadenza,
                    tipo_documento, numero_documento, tipo_registrazione, numero_registrazione,
                    importo_versato, segno, descrizione, centro_costo, stato, partita,
                    file_origine
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                impianto_id,
                self._safe_val(row.get('Registrazione//Data')),
                self._safe_val(row.get('Documento//Data')),
                self._safe_val(row.get('Scadenza')),
                self._safe_val(row.get('Documento//Tipo')),
                self._safe_val(row.get('Documento//Numero')),
                self._safe_val(row.get('Registrazione//Tipo')),
                self._safe_val(row.get('Registrazione//Numero')),
                importo,
                self._safe_val(row.get('Segno')),
                self._safe_val(row.get('Descrizione')),
                self._safe_val(row.get('Centro di Costo')),
                self._safe_val(row.get('Stato')),
                self._safe_val(row.get('Partita')),
                os.path.basename(file_path)
            ))
            righe_importate += 1
        conn.commit()

    def _import_numia(self, conn, file_path):
        # Numia file: row 0 = empty, row 1 = title text, row 2 = actual headers
        df = pd.read_excel(file_path, header=2)
        df = df.where(pd.notna(df), None)
        righe_importate = 0
        impianto_id = self._ottieni_impianto_id(conn, "43809")
        cur = conn.cursor()

        for _, row in df.iterrows():
            importo = row.get('Importo')
            if pd.isna(importo): continue

            cur.execute("""
                INSERT INTO verifica_numia (
                    impianto_id, data_ora_transazione, importo,
                    codice_autorizzazione, numero_carta, circuito,
                    tipo_transazione, stato_operazione, punto_vendita,
                    id_punto_vendita, mid, id_terminale, alias_terminale,
                    id_transazione_numia, file_origine
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                impianto_id,
                self._safe_val(row.get('Data e ora')),
                importo,
                self._safe_val(row.get('Codice autorizzazione')),
                self._safe_val(row.get('Numero carta')),
                self._safe_val(row.get('Circuito')),
                self._safe_val(row.get('Tipo transazione')),
                self._safe_val(row.get('Stato operazione')),
                self._safe_val(row.get('Punto vendita')),
                self._safe_val(row.get('ID Punto vendita')),
                self._safe_val(row.get('MID')),
                self._safe_val(row.get('ID Terminale / TML')),
                self._safe_val(row.get('Alias Terminale')),
                self._safe_val(row.get('ID Transazione')),
                os.path.basename(file_path)
            ))
            righe_importate += 1
        conn.commit()

    def _import_ip_carte(self, conn, file_path):
        df = pd.read_excel(file_path, header=1)
        df = df.where(pd.notna(df), None)
        
        cur = conn.cursor()
        for _, row in df.iterrows():
            pv = row.get('PV')
            if pd.isna(pv): continue
            
            pv_code = str(pv).strip()

            impianto_id = self._ottieni_impianto_id(conn, pv_code)
            if not impianto_id: continue

            quantita = row.get('Quantità', row.get('QuantitÓ'))

            cur.execute("""
                INSERT INTO verifica_ip_portal (
                    impianto_id, tipo_transazione, codice_gestore, codice_pv,
                    data_operazione, ora_operazione, circuito,
                    codice_prodotto, prodotto, riferimento_scontrino,
                    quantita, prezzo, importo, segno,
                    numero_fattura, data_fattura, file_origine
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                impianto_id, 'CARTA_PETROLIFERA', self._safe_val(row.get('Gestore')), pv_code,
                self._safe_val(row.get('Data\noperazione')), self._safe_val(row.get('Ora\noperazione')), self._safe_val(row.get('Circuito')),
                self._safe_val(row.get('Cod. Prod.')), self._safe_val(row.get('Prodotto')), self._safe_val(row.get('Riferimento\nScontrino')),
                self._safe_val(quantita), self._safe_val(row.get('Prezzo')), self._safe_val(row.get('Importo')), self._safe_val(row.get('Segno')),
                self._safe_val(row.get('Numero Fattura')), self._safe_val(row.get('Data Fattura')), os.path.basename(file_path)
            ))
        conn.commit()

    def _import_ip_buoni(self, conn, file_path):
        df = pd.read_excel(file_path, header=1)
        df = df.where(pd.notna(df), None)
        
        cur = conn.cursor()
        for _, row in df.iterrows():
            esercente = row.get('Esercente')
            if pd.isna(esercente): continue
            
            codice_pv = self._estrai_codice_pv(esercente)
            impianto_id = self._ottieni_impianto_id(conn, codice_pv)
            if not impianto_id: continue

            cur.execute("""
                INSERT INTO verifica_ip_portal (
                    impianto_id, tipo_transazione, codice_gestore, codice_esercente,
                    descrizione_esercente, codice_pv, data_operazione, ora_operazione,
                    prodotto, quantita, prezzo, importo, pan, serial_number,
                    terminale, auth_code, flusso, file_origine
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                impianto_id, 'BUONO', self._safe_val(row.get('Gestore')), self._safe_val(esercente),
                self._safe_val(row.get('Descrizione esercente')), self._safe_val(row.get('Punto vendita')), self._safe_val(row.get('Data operazione')),
                self._safe_val(row.get('Ora operazione')), self._safe_val(row.get('Prodotto')), self._safe_val(row.get('Quantita')),
                self._safe_val(row.get('Prezzo unit.')), self._safe_val(row.get('Importo')), self._safe_val(row.get('Pan')),
                self._safe_val(row.get('Serial number')), self._safe_val(row.get('Terminale')), self._safe_val(row.get('Auth code')),
                self._safe_val(row.get('Flusso')), os.path.basename(file_path)
            ))
        conn.commit()

    def _import_satispay(self, conn, file_path):
        df = pd.read_excel(file_path)
        df = df.where(pd.notna(df), None)
        cur = conn.cursor()
        
        for _, row in df.iterrows():
            codice_negozio = row.get('codice negozio')
            if pd.isna(codice_negozio): continue
            
            codice_pv = self._estrai_codice_pv(codice_negozio)
            impianto_id = self._ottieni_impianto_id(conn, codice_pv)
            if not impianto_id: continue
            
            importo_totale = row.get('importo totale', 0) or 0
            commissioni = row.get('totale commissioni', 0) or 0

            cur.execute("""
                INSERT INTO verifica_satispay (
                    impianto_id, id_transazione, data_transazione,
                    negozio, codice_negozio, importo_totale, totale_commissioni,
                    importo_netto, tipo_transazione, codice_transazione, id_gruppo,
                    file_origine
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                impianto_id, self._safe_val(row.get('id transazione')), self._safe_val(row.get('data transazione')),
                self._safe_val(row.get('negozio')), self._safe_val(codice_negozio), importo_totale, commissioni,
                importo_totale - commissioni, self._safe_val(row.get('tipo transazione')),
                self._safe_val(row.get('codice transazione')), self._safe_val(row.get('id gruppo')), os.path.basename(file_path)
            ))
        conn.commit()
