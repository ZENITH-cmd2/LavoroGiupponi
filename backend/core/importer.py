import pandas as pd
import re
import os
from datetime import datetime
from core.database import Database
from core.file_classifier import FileClassifier

class DataImporter:
    def __init__(self, db_instance: Database):
        self.db = db_instance

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
        df = pd.read_excel(file_path)
        righe_importate = 0
        cur = conn.cursor()
        
        for _, row in df.iterrows():
            codice_pv = str(row.get('CodicePV', ''))
            impianto_id = self._ottieni_impianto_id(conn, codice_pv)
            if not impianto_id: continue
                
            cur.execute("""
                INSERT INTO import_fortech_master (
                    impianto_id, codice_pv, data_contabile, data_inizio, data_fine,
                    stato_giornata, corrispettivo_totale, corrispettivo_verde, corrispettivo_diesel,
                    volume_verde_prepay, importo_verde_prepay, prezzo_verde_prepay,
                    volume_diesel_prepay, importo_diesel_prepay, prezzo_diesel_prepay,
                    fatture_postpagate_totale, fatture_prepagate_totale, 
                    fatture_immediate_totale, fatture_differite_totale, buoni_totale,
                    file_origine
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                impianto_id, codice_pv, row.get('DataContabile'), row.get('DataInizio'),
                row.get('DataFine'), row.get('StatoGiornata'), row.get('Corrispettivo Totale', 0),
                row.get('CorrispettivoVerde', 0), row.get('CorrispettivoDiesel', 0),
                row.get('VolumeVerdePrepay', 0), row.get('ImportoVerdePrepay', 0), row.get('PrezzoVerdePrepay', 0),
                row.get('VolumeDieselPrepay', 0), row.get('ImportoDieselPrepay', 0), row.get('PrezzoDieselPrepay', 0),
                row.get('Fatture Postpagate Totale', 0), row.get('Fatture Prepagate Totale', 0),
                row.get('Fatture Immediate Totale', 0), row.get('Fatture Differite Totale', 0),
                row.get('Buoni Totale', 0), os.path.basename(file_path)
            ))
            righe_importate += 1
        conn.commit()

    def _import_as400(self, conn, file_path):
        df = pd.read_excel(file_path)
        righe_importate = 0
        # Default to Milano Repubblica (43809) if not specified, matching original script behavior
        impianto_id = self._ottieni_impianto_id(conn, "43809") 
        cur = conn.cursor()

        for _, row in df.iterrows():
            importo = row.get('Importo')
            if pd.isna(importo): continue
            
            cur.execute("""
                INSERT INTO verifica_contanti_as400 (
                    impianto_id, data_registrazione, data_documento, data_scadenza,
                    tipo_documento, numero_documento, tipo_registrazione, numero_registrazione,
                    importo_versato, segno, descrizione, centro_costo, stato, partita,
                    file_origine
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                impianto_id, row.get('Registrazione//Data'), row.get('Documento//Data'), row.get('Scadenza'),
                row.get('Documento//Tipo'), row.get('Documento//Numero'), row.get('Registrazione//Tipo'),
                row.get('Registrazione//Numero'), importo, row.get('Segno'), row.get('Descrizione'),
                row.get('Centro di Costo'), row.get('Stato'), row.get('Partita'), os.path.basename(file_path)
            ))
            righe_importate += 1
        conn.commit()

    def _import_numia(self, conn, file_path):
        df = pd.read_excel(file_path, header=1)
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
                impianto_id, row.get('Data e ora'), importo, row.get('Codice autorizzazione'),
                row.get('Numero carta'), row.get('Circuito'), row.get('Tipo transazione'),
                row.get('Stato operazione'), row.get('Punto vendita'), row.get('ID Punto vendita'),
                row.get('MID'), row.get('ID Terminale / TML'), row.get('Alias Terminale'),
                row.get('ID Transazione'), os.path.basename(file_path)
            ))
            righe_importate += 1
        conn.commit()

    def _import_ip_carte(self, conn, file_path):
        df = pd.read_excel(file_path, header=0)
        if len(df) > 0:
            df.columns = df.iloc[0]
            df = df.iloc[1:]
        
        cur = conn.cursor()
        for _, row in df.iterrows():
            pv = row.get('PV')
            if pd.isna(pv): continue
            impianto_id = self._ottieni_impianto_id(conn, str(pv))
            if not impianto_id: continue

            cur.execute("""
                INSERT INTO verifica_ip_portal (
                    impianto_id, tipo_transazione, codice_gestore, codice_pv,
                    data_operazione, ora_operazione, circuito,
                    codice_prodotto, prodotto, riferimento_scontrino,
                    quantita, prezzo, importo, segno,
                    numero_fattura, data_fattura, file_origine
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                impianto_id, 'CARTA_PETROLIFERA', row.get('Gestore'), pv,
                row.get('Data\noperazione'), row.get('Ora\noperazione'), row.get('Circuito'),
                row.get('Cod. Prod.'), row.get('Prodotto'), row.get('Riferimento\nScontrino'),
                row.get('Quantità'), row.get('Prezzo'), row.get('Importo'), row.get('Segno'),
                row.get('Numero Fattura'), row.get('Data Fattura'), os.path.basename(file_path)
            ))
        conn.commit()

    def _import_ip_buoni(self, conn, file_path):
        df = pd.read_excel(file_path, header=0)
        if len(df) > 0:
            df.columns = df.iloc[0]
            df = df.iloc[1:]
        
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
                impianto_id, 'BUONO', row.get('Gestore'), esercente,
                row.get('Descrizione esercente'), row.get('Punto vendita'), row.get('Data operazione'),
                row.get('Ora operazione'), row.get('Prodotto'), row.get('Quantita'),
                row.get('Prezzo unit.'), row.get('Importo'), row.get('Pan'),
                row.get('Serial number'), row.get('Terminale'), row.get('Auth code'),
                row.get('Flusso'), os.path.basename(file_path)
            ))
        conn.commit()

    def _import_satispay(self, conn, file_path):
        df = pd.read_excel(file_path)
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
                impianto_id, row.get('id transazione'), row.get('data transazione'),
                row.get('negozio'), codice_negozio, importo_totale, commissioni,
                importo_totale - commissioni, row.get('tipo transazione'),
                row.get('codice transazione'), row.get('id gruppo'), os.path.basename(file_path)
            ))
        conn.commit()
