"""
Calor Systems — Web Dashboard Server
Flask server che legge il database SQLite e serve una dashboard web.
Supporta caricamento file Excel per importazione e analisi.
Deployable su Vercel come serverless function.
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
from core.ai_report import generate_report, get_saved_api_key

from dotenv import load_dotenv
load_dotenv(".env.local")
load_dotenv()

# ── Vercel Environment Detection ──
IS_VERCEL = os.environ.get('VERCEL', '') == '1'

if IS_VERCEL:
    # Vercel serverless: use /tmp for writable SQLite
    DB_PATH = "/tmp/calor_systems.db"
    SCHEMA_SRC = os.path.join(PROJECT_ROOT, "db", "calor_systems_schema.sql")
    
    # Auto-initialize DB on cold start
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        try:
            if os.path.exists(SCHEMA_SRC):
                with open(SCHEMA_SRC, 'r', encoding='utf-8') as f:
                    conn.executescript(f.read())
                conn.commit()
                print(f"[Vercel] Database initialized at {DB_PATH}")
            else:
                print(f"[Vercel] Schema not found at {SCHEMA_SRC}")
        except Exception as e:
            print(f"[Vercel] DB init error: {e}")
        finally:
            conn.close()
else:
    # Local development
    DB_PATH = os.path.join(PROJECT_ROOT, "db", "calor_systems.db")

app = Flask(__name__, 
            template_folder="../frontend/templates",
            static_folder="../frontend/static")
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB max upload


def get_readonly_db():
    """Get a read-only database connection for queries."""
    if IS_VERCEL:
        conn = sqlite3.connect(DB_PATH)
    else:
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


@app.route("/api/impianti/<int:impianto_id>/andamento")
def api_andamento(impianto_id):
    """Andamento riconciliazione per un singolo impianto nel tempo."""
    conn = get_readonly_db()
    try:
        cur = conn.cursor()
        
        # Info impianto
        cur.execute("SELECT nome_impianto, codice_pv_fortech, tipo_gestione FROM impianti WHERE id = ?", (impianto_id,))
        imp = cur.fetchone()
        if not imp:
            return jsonify({"error": "Impianto non trovato"}), 404
        
        # Storico riconciliazioni
        cur.execute("""
            SELECT 
                r.data_riferimento,
                r.categoria,
                r.valore_fortech,
                r.valore_reale,
                r.differenza,
                r.stato,
                r.note
            FROM report_riconciliazioni r
            WHERE r.impianto_id = ?
            ORDER BY r.data_riferimento DESC, r.categoria
        """, (impianto_id,))
        
        rows = cur.fetchall()
        
        # Raggruppa per data
        giorni = {}
        for r in rows:
            data = r["data_riferimento"]
            if data not in giorni:
                giorni[data] = {
                    "data": data,
                    "categorie": {},
                    "totale_teorico": 0,
                    "totale_reale": 0,
                    "totale_diff": 0,
                    "stato_peggiore": "QUADRATO"
                }
            
            cat = r["categoria"]
            giorni[data]["categorie"][cat] = {
                "teorico": r["valore_fortech"],
                "reale": r["valore_reale"],
                "differenza": r["differenza"],
                "stato": r["stato"],
                "note": r["note"],
            }
            
            giorni[data]["totale_teorico"] += (r["valore_fortech"] or 0)
            giorni[data]["totale_reale"] += (r["valore_reale"] or 0)
            giorni[data]["totale_diff"] += (r["differenza"] or 0)
            
            # Track worst state per day
            priority = {"QUADRATO": 0, "QUADRATO_ARROT": 1, "ANOMALIA_LIEVE": 2, 
                        "IN_ATTESA": 3, "NON_TROVATO": 4, "ANOMALIA_GRAVE": 5}
            curr_p = priority.get(r["stato"], 4)
            worst_p = priority.get(giorni[data]["stato_peggiore"], 0)
            if curr_p > worst_p:
                giorni[data]["stato_peggiore"] = r["stato"]
        
        # Statistiche riepilogative
        stati_count = {}
        for g in giorni.values():
            for cat_det in g["categorie"].values():
                s = cat_det["stato"]
                stati_count[s] = stati_count.get(s, 0) + 1

        return jsonify({
            "impianto": {
                "id": impianto_id,
                "nome": imp["nome_impianto"],
                "codice_pv": imp["codice_pv_fortech"],
                "tipo": imp["tipo_gestione"],
            },
            "giorni": list(giorni.values()),
            "stats": stati_count,
            "totale_giorni": len(giorni),
        })
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
# API ENDPOINTS (WORKFLOW: Simona / Lidia / Taleggio)
# ============================================================================

@app.route("/api/contanti-banca")
def api_contanti_banca():
    """Vista Simona: stato dei versamenti contanti con matching banca.
    Mostra per ogni impianto/giornata il teorico Fortech vs il versato in banca (AS400).
    Include dettagli matching (tipo_match, giorni coperti) per conferma manuale.
    """
    conn = get_readonly_db()
    try:
        cur = conn.cursor()
        limit = request.args.get("limit", 100, type=int)
        
        cur.execute("""
            SELECT 
                r.id,
                r.data_riferimento,
                i.nome_impianto,
                i.codice_pv_fortech,
                r.valore_fortech as contanti_teorico,
                r.valore_reale as contanti_versato,
                r.differenza,
                r.stato,
                r.tipo_anomalia,
                r.note,
                r.risolto,
                r.verificato_da,
                r.data_verifica
            FROM report_riconciliazioni r
            JOIN impianti i ON r.impianto_id = i.id
            WHERE r.categoria = 'contanti'
            ORDER BY r.data_riferimento DESC, i.nome_impianto
            LIMIT ?
        """, (limit,))
        
        rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r["id"],
                "data": r["data_riferimento"],
                "impianto": r["nome_impianto"],
                "codice_pv": r["codice_pv_fortech"],
                "contanti_teorico": r["contanti_teorico"],
                "contanti_versato": r["contanti_versato"],
                "differenza": r["differenza"],
                "stato": r["stato"],
                "tipo_match": r["tipo_anomalia"] or "",
                "note": r["note"],
                "risolto": bool(r["risolto"]),
                "verificato_da": r["verificato_da"],
                "data_verifica": r["data_verifica"],
            })
        return jsonify(result)
    finally:
        conn.close()


@app.route("/api/contanti-conferma", methods=["POST"])
def api_contanti_conferma():
    """Simona conferma o segnala un risultato di matching contanti.
    Body JSON: { id: int, azione: "conferma"|"rifiuta", nota: string }
    """
    data = request.get_json()
    if not data or 'id' not in data:
        return jsonify({"error": "ID mancante"}), 400
    
    rec_id = data['id']
    azione = data.get('azione', 'conferma')
    nota_extra = data.get('nota', '')
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        
        if azione == 'conferma':
            cur.execute("""
                UPDATE report_riconciliazioni 
                SET risolto = 1,
                    verificato_da = 'Simona',
                    data_verifica = datetime('now'),
                    note = CASE 
                        WHEN ? != '' THEN note || ' | Confermato: ' || ?
                        ELSE note || ' | Confermato da Simona'
                    END
                WHERE id = ?
            """, (nota_extra, nota_extra, rec_id))
        elif azione == 'rifiuta':
            cur.execute("""
                UPDATE report_riconciliazioni 
                SET risolto = 0,
                    verificato_da = 'Simona',
                    data_verifica = datetime('now'),
                    stato = 'ANOMALIA_GRAVE',
                    note = CASE 
                        WHEN ? != '' THEN note || ' | SEGNALATO: ' || ?
                        ELSE note || ' | SEGNALATO da Simona'
                    END
                WHERE id = ?
            """, (nota_extra, nota_extra, rec_id))
        
        conn.commit()
        return jsonify({"ok": True, "azione": azione})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/stato-verifiche")
def api_stato_verifiche():
    """Vista riepilogo: stato riconciliazione per categoria.
    Per ogni impianto mostra lo stato di ogni tipo di verifica.
    """
    conn = get_readonly_db()
    try:
        cur = conn.cursor()
        
        # Ultima data disponibile per ogni impianto/categoria
        cur.execute("""
            SELECT 
                i.nome_impianto,
                i.codice_pv_fortech,
                i.tipo_gestione,
                r.categoria,
                r.data_riferimento,
                r.valore_fortech,
                r.valore_reale,
                r.differenza,
                r.stato,
                r.note
            FROM report_riconciliazioni r
            JOIN impianti i ON r.impianto_id = i.id
            WHERE r.data_riferimento = (
                SELECT MAX(r2.data_riferimento) 
                FROM report_riconciliazioni r2 
                WHERE r2.impianto_id = r.impianto_id AND r2.categoria = r.categoria
            )
            AND i.attivo = 1
            ORDER BY i.nome_impianto, r.categoria
        """)
        
        rows = cur.fetchall()
        impianti = {}
        for r in rows:
            nome = r["nome_impianto"]
            if nome not in impianti:
                impianti[nome] = {
                    "nome": nome,
                    "codice_pv": r["codice_pv_fortech"],
                    "tipo_gestione": r["tipo_gestione"],
                    "categorie": {}
                }
            impianti[nome]["categorie"][r["categoria"]] = {
                "data": r["data_riferimento"],
                "teorico": r["valore_fortech"],
                "reale": r["valore_reale"],
                "differenza": r["differenza"],
                "stato": r["stato"],
                "note": r["note"],
            }
        
        return jsonify(list(impianti.values()))
    finally:
        conn.close()


@app.route("/api/sicurezza")
def api_sicurezza():
    """Alert sicurezza casse (Taleggio e altri self-service).
    Mostra gli eventi di apertura cassaforte con verifica contante.
    """
    conn = get_readonly_db()
    try:
        cur = conn.cursor()
        limit = request.args.get("limit", 50, type=int)
        
        cur.execute("""
            SELECT 
                e.timestamp_apertura,
                e.giorno_settimana,
                i.nome_impianto,
                e.importo_rilevato_fortech,
                e.importo_atteso,
                e.differenza,
                e.apertura_autorizzata,
                e.alert_inviato,
                e.note
            FROM eventi_sicurezza_casse e
            JOIN impianti i ON e.impianto_id = i.id
            ORDER BY e.timestamp_apertura DESC
            LIMIT ?
        """, (limit,))
        
        rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                "timestamp": r["timestamp_apertura"],
                "giorno": r["giorno_settimana"],
                "impianto": r["nome_impianto"],
                "importo_fortech": r["importo_rilevato_fortech"],
                "importo_atteso": r["importo_atteso"],
                "differenza": r["differenza"],
                "autorizzata": bool(r["apertura_autorizzata"]) if r["apertura_autorizzata"] is not None else None,
                "alert_inviato": bool(r["alert_inviato"]),
                "note": r["note"],
            })
        return jsonify(result)
    finally:
        conn.close()


# ============================================================================
# API ENDPOINT: AI REPORT (OpenRouter)
# ============================================================================

@app.route("/api/ai-report", methods=["POST"])
def api_ai_report():
    """Genera un report AI basato sui risultati di riconciliazione.
    Usa OpenRouter (gpt-4o-mini) per analizzare le anomalie.
    """
    try:
        # Fetch all reconciliation results from DB
        conn = get_readonly_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                r.data_riferimento,
                i.nome_impianto,
                r.categoria,
                r.valore_fortech,
                r.valore_reale,
                r.differenza,
                r.stato,
                r.note
            FROM report_riconciliazioni r
            JOIN impianti i ON r.impianto_id = i.id
            ORDER BY r.data_riferimento DESC
            LIMIT 500
        """)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return jsonify({"report": "Nessun dato da analizzare. Carica prima i file Excel."})

        # Convert DB rows to the format expected by generate_report()
        days = {}
        for r in rows:
            date_key = r["data_riferimento"]
            if date_key not in days:
                days[date_key] = {"data": date_key, "risultati": {}}
            days[date_key]["risultati"][r["categoria"]] = {
                "stato": r["stato"],
                "differenza": r["differenza"],
                "note": r["note"] or "",
                "teorico": r["valore_fortech"],
                "reale": r["valore_reale"],
            }

        results_list = list(days.values())

        # Get API key
        api_key = get_saved_api_key("OpenRouter")
        if not api_key:
            return jsonify({"error": "Chiave API OpenRouter non configurata. Salva OPENROUTER_API_KEY in .env.local"}), 400

        # Generate report
        report_text = generate_report(results_list, "OpenRouter", api_key)
        return jsonify({"report": report_text})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


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
