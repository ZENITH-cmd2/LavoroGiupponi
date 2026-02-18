
import sqlite3
import pandas as pd
from core.database import Database
from core.reconciliation import riconcilia_giornata

class Analyzer:
    def __init__(self, db_instance: Database):
        self.db = db_instance

    def run_analysis(self, progress_callback=None):
        """
        Runs analysis for all dates found in Fortech Master data.
        Iterates through each plant and date combination.
        Saves results to 'report_riconciliazioni' table.
        """
        conn = self.db.get_connection()
        conn.row_factory = sqlite3.Row
        
        try:
            cur = conn.cursor()
            
            # 1. Identify what to analyze based on Fortech Master Data
            # This drives the process. If we have theoretical data, we reconcile.
            cur.execute("""
                SELECT DISTINCT data_contabile, impianto_id 
                FROM import_fortech_master 
                ORDER BY data_contabile DESC, impianto_id
            """)
            tasks = cur.fetchall()
            
            total_tasks = len(tasks)
            results = []
            
            for index, task in enumerate(tasks):
                date_str = task['data_contabile']
                impianto_id = task['impianto_id']
                
                if progress_callback:
                    # Fetch plant name for better log
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
                
                # Run logic
                res_dict = riconcilia_giornata(
                    fortech_data,
                    as400_records,
                    numia_records,
                    ip_carte,
                    ip_buoni,
                    satispay_records
                )
                
                # Save to DB
                self._save_result(conn, res_dict, impianto_id)
                results.append(res_dict)

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
