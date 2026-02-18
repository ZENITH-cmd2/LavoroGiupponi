"""
Calor Systems — Web Dashboard Server
Flask server che legge il database SQLite e serve una dashboard web.
Supporta caricamento file Excel per importazione e analisi.
"""

import sqlite3
import os
import sys
import webbrowser
import threading
import tempfile
import shutil
import time
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from werkzeug.utils import secure_filename

# Ensure we can find the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT) # Ensure core can be imported

from core.database import Database
from core.importer import DataImporter
from core.analyzer import Analyzer

DB_PATH = os.path.join(PROJECT_ROOT, "db", "calor_systems.db")

app = Flask(__name__, 
            template_folder="../frontend/templates",
            static_folder="../frontend/static")
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB max upload

def get_readonly_db():
    """Get a read-only database connection for queries."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================================
# PAGES
# ============================================================================

@app.route("/")
def index():
    return render_template("index.html")


# ============================================================================
# API ENDPOINTS (READ)
# ============================================================================

@app.route("/api/stats")
def api_stats():
    """Global statistics for the dashboard header."""
    conn = get_readonly_db()
    try:
        cur = conn.cursor()

        # Total impianti
        cur.execute("SELECT COUNT(*) FROM impianti WHERE attivo = 1")
        total_impianti = cur.fetchone()[0]

        # Total giornate analizzate
        cur.execute("SELECT COUNT(DISTINCT data_riferimento) FROM report_riconciliazioni")
        total_giornate = cur.fetchone()[0]

        # Anomalies
        cur.execute("""
            SELECT COUNT(*) FROM report_riconciliazioni 
            WHERE stato IN ('ANOMALIA_LIEVE', 'ANOMALIA_GRAVE') AND risolto = 0
        """)
        anomalie_aperte = cur.fetchone()[0]

        # Quadrate
        cur.execute("SELECT COUNT(*) FROM report_riconciliazioni WHERE stato = 'QUADRATO'")
        quadrate = cur.fetchone()[0]

        # Anomalie gravi
        cur.execute("""
            SELECT COUNT(*) FROM report_riconciliazioni 
            WHERE stato = 'ANOMALIA_GRAVE' AND risolto = 0
        """)
        anomalie_gravi = cur.fetchone()[0]

        # Total records imported
        cur.execute("SELECT COUNT(*) FROM import_fortech_master")
        fortech_records = cur.fetchone()[0]
        
        # Last import date
        cur.execute("""
            SELECT MAX(data_importazione) FROM (
                SELECT data_importazione FROM import_fortech_master
                UNION ALL
                SELECT data_importazione FROM verifica_numia
            )
        """)
        row = cur.fetchone()
        last_import = row[0] if row else None

        return jsonify({
            "total_impianti": total_impianti,
            "total_giornate": total_giornate,
            "anomalie_aperte": anomalie_aperte,
            "anomalie_gravi": anomalie_gravi,
            "quadrate": quadrate,
            "fortech_records": fortech_records,
            "last_import": last_import,
        })
    finally:
        conn.close()


@app.route("/api/impianti")
def api_impianti():
    """List all impianti with their latest reconciliation status."""
    conn = get_readonly_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                i.id,
                i.nome_impianto,
                i.codice_pv_fortech,
                i.tipo_gestione,
                i.citta,
                i.attivo,
                (SELECT COUNT(*) FROM report_riconciliazioni r 
                 WHERE r.impianto_id = i.id AND r.stato = 'QUADRATO') as cnt_ok,
                (SELECT COUNT(*) FROM report_riconciliazioni r 
                 WHERE r.impianto_id = i.id AND r.stato = 'ANOMALIA_LIEVE') as cnt_warn,
                (SELECT COUNT(*) FROM report_riconciliazioni r 
                 WHERE r.impianto_id = i.id AND r.stato = 'ANOMALIA_GRAVE' AND r.risolto = 0) as cnt_grave,
                (SELECT MAX(r.data_riferimento) FROM report_riconciliazioni r 
                 WHERE r.impianto_id = i.id) as last_date
            FROM impianti i
            WHERE i.attivo = 1
            ORDER BY i.nome_impianto
        """)
        rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r["id"],
                "nome": r["nome_impianto"],
                "codice_pv": r["codice_pv_fortech"],
                "tipo": r["tipo_gestione"],
                "citta": r["citta"],
                "cnt_ok": r["cnt_ok"],
                "cnt_warn": r["cnt_warn"],
                "cnt_grave": r["cnt_grave"],
                "last_date": r["last_date"],
            })
        return jsonify(result)
    finally:
        conn.close()


@app.route("/api/riconciliazioni")
def api_riconciliazioni():
    """Reconciliation results with optional filters."""
    conn = get_readonly_db()
    try:
        cur = conn.cursor()

        # Query params
        data_da = request.args.get("data_da")
        data_a = request.args.get("data_a")
        limit = request.args.get("limit", 200, type=int)

        query = """
            SELECT 
                r.id,
                r.data_riferimento,
                i.nome_impianto,
                r.categoria,
                r.valore_fortech,
                r.valore_reale,
                r.differenza,
                r.stato,
                r.tipo_anomalia,
                r.note
            FROM report_riconciliazioni r
            JOIN impianti i ON r.impianto_id = i.id
            WHERE 1=1
        """
        params = []

        if data_da:
            query += " AND r.data_riferimento >= ?"
            params.append(data_da)
        if data_a:
            query += " AND r.data_riferimento <= ?"
            params.append(data_a)

        query += " ORDER BY r.data_riferimento DESC, i.nome_impianto LIMIT ?"
        params.append(limit)

        cur.execute(query, params)
        rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r["id"],
                "data": r["data_riferimento"],
                "impianto": r["nome_impianto"],
                "categoria": r["categoria"],
                "valore_fortech": r["valore_fortech"],
                "valore_reale": r["valore_reale"],
                "differenza": r["differenza"],
                "stato": r["stato"],
                "tipo_anomalia": r["tipo_anomalia"],
                "note": r["note"]
            })
        return jsonify(result)
    finally:
        conn.close()


# ============================================================================
# API ENDPOINTS (WRITE / ACTION)
# ============================================================================

@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Handle file upload, import, and analysis."""
    if 'files[]' not in request.files:
        return jsonify({"error": "Nessun file caricato"}), 400
    
    files = request.files.getlist('files[]')
    if not files or all(f.filename == '' for f in files):
        return jsonify({"error": "Nessun file selezionato"}), 400

    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix="calor_upload_")
    saved_paths = []

    try:
        # 1. Save files
        for f in files:
            if f.filename:
                safe_name = secure_filename(f.filename)
                path = os.path.join(temp_dir, safe_name)
                f.save(path)
                saved_paths.append(path)
        
        if not saved_paths:
             return jsonify({"error": "Nessun file valido"}), 400

        # 2. Init Core
        # Use PROJECT_ROOT to ensure DB is found correctly
        db_instance = Database(PROJECT_ROOT) 
        
        # Ensure DB init (safeguard) - ONLY IF NOT EXISTS
        if not os.path.exists(DB_PATH):
            if not db_instance.initialize():
                 return jsonify({"error": "Errore inizializzazione database"}), 500

        # Define a no-op progress callback since we can't stream progress easily in one HTTP request
        # (Alternatively, we could use Server-Sent Events, but let's keep it simple for now)
        logs = []
        def progress_cb(cur, tot, msg):
            logs.append(msg)
            # print(f"[Processing] {msg}") 

        # 3. Import
        importer = DataImporter(db_instance)
        importer.import_files(saved_paths, progress_callback=progress_cb)

        # 4. Analyze
        analyzer = Analyzer(db_instance)
        results = analyzer.run_analysis(progress_callback=progress_cb)

        return jsonify({
            "message": "Elaborazione completata",
            "files_imported": len(saved_paths),
            "days_analyzed": len(results),
            "logs": logs
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"⚠  Database non trovato: {DB_PATH}")

    port = 5000
    print(f"\n🌐  Calor Systems Web Dashboard")
    print(f"   http://localhost:{port}")
    print(f"   Database: {DB_PATH}\n")

    def open_browser():
        time.sleep(1.2)
        webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=open_browser, daemon=True).start()

    app.run(host="0.0.0.0", port=port, debug=False)
