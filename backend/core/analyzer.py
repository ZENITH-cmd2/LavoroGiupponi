
import sqlite3
import pandas as pd
from core.database import Database
from core.reconciliation import riconcilia_giornata, riconcilia_contanti_multi_giorno

class Analyzer:
    def __init__(self, db_instance: Database):
        self.db = db_instance

    def run_analysis(self, progress_callback=None):
        """
        Runs analysis for all dates found in Fortech Master data.
        
        Two-pass approach:
        1. Standard per-day reconciliation for all categories
        2. Multi-day contanti reconciliation per impianto (overrides contanti results)
        """
        conn = self.db.get_connection()
        conn.row_factory = sqlite3.Row
        
        try:
            cur = conn.cursor()
            
            # 1. Identify what to analyze based on Fortech Master Data
            cur.execute("""
                SELECT DISTINCT data_contabile, impianto_id 
                FROM import_fortech_master 
                ORDER BY data_contabile DESC, impianto_id
            """)
            tasks = cur.fetchall()
            
            total_tasks = len(tasks)
            results = []
            
            # ── Pass 1: Standard per-day reconciliation ──
            for index, task in enumerate(tasks):
                date_str = task['data_contabile']
                impianto_id = task['impianto_id']
                
                if progress_callback:
                    cur.execute("SELECT nome_impianto FROM impianti WHERE id = ?", (impianto_id,))
                    plant_row = cur.fetchone()
                    plant_name = plant_row['nome_impianto'] if plant_row else f"ID {impianto_id}"
                    progress_callback(index, total_tasks, f"Riconciliazione {date_str} - {plant_name}...")
                
                # Fetch data
                fortech_data = self._fetch_fortech(conn, date_str, impianto_id)
                if not fortech_data:
                    continue

                as400_records = self._fetch_as400(conn, date_str, impianto_id)
                numia_records = self._fetch_numia(conn, date_str, impianto_id)
                ip_carte, ip_buoni = self._fetch_ip(conn, date_str, impianto_id)
                satispay_records = self._fetch_satispay(conn, date_str, impianto_id)
                crediti_records = self._fetch_crediti(conn, date_str, impianto_id)
                
                # Run logic
                res_dict = riconcilia_giornata(
                    fortech_data,
                    as400_records,
                    numia_records,
                    ip_carte,
                    ip_buoni,
                    satispay_records,
                    crediti_records
                )
                
                # Save to DB and commit immediately to release locks
                self._save_result(conn, res_dict, impianto_id)
                conn.commit()
                results.append(res_dict)

            # ── Pass 2: Multi-day contanti reconciliation per impianto ──
            self._run_contanti_multi_giorno(conn, progress_callback)
            conn.commit()
            
            if progress_callback:
                progress_callback(total_tasks, total_tasks, "Analisi completata.")
            
            return results

        except Exception as e:
            print(f"Errore durante l'analisi: {e}")
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _run_contanti_multi_giorno(self, conn, progress_callback=None):
        """
        Esegue la riconciliazione contanti multi-giorno per ogni impianto.
        Raggruppa tutti i giorni Fortech per impianto e li confronta con
        tutti i versamenti AS400 del periodo, sovrascrivendo i risultati
        contanti prodotti dalla Pass 1.
        """
        cur = conn.cursor()
        
        # Trova tutti gli impianti con dati Fortech
        cur.execute("SELECT DISTINCT impianto_id FROM import_fortech_master")
        impianti = [row['impianto_id'] for row in cur.fetchall()]
        
        for impianto_id in impianti:
            # Fetch tutti i giorni Fortech per questo impianto
            cur.execute("""
                SELECT data_contabile, incasso_contanti_teorico 
                FROM import_fortech_master 
                WHERE impianto_id = ?
                ORDER BY data_contabile
            """, (impianto_id,))
            fortech_rows = [dict(r) for r in cur.fetchall()]
            
            if not fortech_rows:
                continue
            
            # Determina il range date
            date_fortech = [r['data_contabile'] for r in fortech_rows if r['data_contabile']]
            if not date_fortech:
                continue
            data_min = min(date_fortech)
            data_max = max(date_fortech)
            
            # Fetch tutti i versamenti AS400 nel periodo allargato
            cur.execute("""
                SELECT * FROM verifica_contanti_as400 
                WHERE impianto_id = ?
                AND data_registrazione BETWEEN date(?, '-2 days') AND date(?, '+7 days')
                ORDER BY data_registrazione
            """, (impianto_id, data_min, data_max))
            as400_all = [dict(r) for r in cur.fetchall()]
            
            # Esegui riconciliazione multi-giorno
            risultati_multi = riconcilia_contanti_multi_giorno(
                fortech_rows, as400_all, impianto_id=str(impianto_id)
            )
            
            # Sovrascrivi i risultati contanti nella tabella report
            for ris in risultati_multi:
                cur.execute("""
                    DELETE FROM report_riconciliazioni 
                    WHERE impianto_id = ? AND data_riferimento = ? AND categoria = 'contanti'
                """, (impianto_id, ris.data))
                
                pct = 0.0
                if ris.valore_teorico != 0:
                    pct = (ris.differenza / ris.valore_teorico) * 100
                
                cur.execute("""
                    INSERT INTO report_riconciliazioni (
                        impianto_id, data_riferimento, categoria,
                        valore_fortech, valore_reale, differenza, percentuale_scostamento,
                        stato, tipo_anomalia, note, risolto
                    ) VALUES (?, ?, 'contanti', ?, ?, ?, ?, ?, ?, ?, 0)
                """, (
                    impianto_id, ris.data,
                    ris.valore_teorico, ris.valore_reale, ris.differenza,
                    round(pct, 2), ris.stato.value,
                    ris.match_info.get('tipo_match', '') if ris.match_info else None,
                    ris.note
                ))
            
            # Release DB lock after finishing an implant
            conn.commit()


    def _fetch_fortech(self, conn, date_str, impianto_id):
        cur = conn.cursor()
        cur.execute("SELECT * FROM import_fortech_master WHERE data_contabile = ? AND impianto_id = ?", (date_str, impianto_id))
        row = cur.fetchone()
        return dict(row) if row else {}

    def _fetch_as400(self, conn, date_str, impianto_id):
        # Window search for AS400 (cache logic handled in reconciliation.py, here we fetch candidates)
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM verifica_contanti_as400 
            WHERE data_registrazione BETWEEN date(?, '-5 days') AND date(?, '+5 days')
            AND impianto_id = ?
        """, (date_str, date_str, impianto_id))
        return [dict(row) for row in cur.fetchall()]

    def _fetch_numia(self, conn, date_str, impianto_id):
        # Match by date prefix (YYYY-MM-DD vs YYYY-MM-DD HH:MM:SS)
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM verifica_numia 
            WHERE data_ora_transazione LIKE ? 
            AND impianto_id = ?
        """, (f"{date_str}%", impianto_id))
        return [dict(row) for row in cur.fetchall()]

    def _fetch_ip(self, conn, date_str, impianto_id):
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM verifica_ip_portal 
            WHERE data_operazione LIKE ? 
            AND impianto_id = ?
        """, (f"{date_str}%", impianto_id))
        rows = [dict(row) for row in cur.fetchall()]
        
        carte = [r for r in rows if r['tipo_transazione'] == 'CARTA_PETROLIFERA']
        buoni = [r for r in rows if r['tipo_transazione'] == 'BUONO']
        return carte, buoni

    def _fetch_satispay(self, conn, date_str, impianto_id):
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM verifica_satispay 
            WHERE data_transazione LIKE ? 
            AND impianto_id = ?
        """, (f"{date_str}%", impianto_id))
        return [dict(row) for row in cur.fetchall()]

    def _fetch_crediti(self, conn, date_str, impianto_id):
        """Fetch Fattura1Click credit records for reconciliation."""
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM verifica_credito_clienti 
            WHERE data_erogazione = ? 
            AND impianto_id = ?
        """, (date_str, impianto_id))
        return [dict(row) for row in cur.fetchall()]

    def _save_result(self, conn, res, impianto_id):
        """
        Saves the reconciliation result dictionary to 'report_riconciliazioni'.
        Deletes existing records for that day/plant first to ensure clean state.
        """
        cur = conn.cursor()
        data_rif = res['data']
        
        # Clean old results for this day/plant
        cur.execute("DELETE FROM report_riconciliazioni WHERE data_riferimento = ? AND impianto_id = ?", (data_rif, impianto_id))
        
        insert_sql = """
            INSERT INTO report_riconciliazioni (
                impianto_id, data_riferimento, categoria, 
                valore_fortech, valore_reale, differenza, percentuale_scostamento,
                stato, tipo_anomalia, note, risolto
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """
        
        for cat, details in res['risultati'].items():
            # Calculate pct deviation if needed, else 0
            val_teorico = details['teorico']
            val_diff = details['differenza']
            pct = 0.0
            if val_teorico != 0:
                pct = (val_diff / val_teorico) * 100
            
            cur.execute(insert_sql, (
                impianto_id,
                data_rif,
                cat,
                val_teorico,
                details['reale'],
                val_diff,
                round(pct, 2),
                details['stato'],
                None, # Tipo anomalia (optional detail)
                details['note']
            ))
