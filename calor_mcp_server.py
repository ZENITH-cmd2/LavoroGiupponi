"""
MCP Server - Calor Smart Recon
================================
Model Context Protocol server per accesso Claude al database di riconciliazione.

Risorse disponibili:
- calor://impianti - Lista impianti
- calor://anomalie - Anomalie attive
- calor://stats - Statistiche globali

Tools disponibili:
- query_database - Query SQL (sola lettura)
- get_riconciliazione - Stato riconciliazione impianto
- get_anomalie_giornata - Anomalie per data
"""

import asyncio
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    INTERNAL_ERROR,
    INVALID_PARAMS
)

# Configurazione
DB_PATH = Path(__file__).parent / "calor_systems.db"
SERVER_NAME = "calor-systems"
SERVER_VERSION = "1.0.0"

# Crea il server MCP
app = Server(SERVER_NAME)


def get_db():
    """Connessione al database SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_list(rows):
    """Converte righe SQLite in lista di dizionari."""
    return [dict(row) for row in rows]


# =============================================================================
# RESOURCES - Dati esposti a Claude
# =============================================================================

@app.list_resources()
async def list_resources():
    """Lista delle risorse disponibili."""
    return [
        Resource(
            uri="calor://impianti",
            name="Lista Impianti",
            description="Anagrafica di tutti gli impianti/distributori registrati",
            mimeType="application/json"
        ),
        Resource(
            uri="calor://anomalie",
            name="Anomalie Attive",
            description="Lista delle anomalie di riconciliazione da verificare",
            mimeType="application/json"
        ),
        Resource(
            uri="calor://stats",
            name="Statistiche Globali",
            description="Riepilogo statistico del sistema",
            mimeType="application/json"
        ),
        Resource(
            uri="calor://schema",
            name="Schema Database",
            description="Struttura delle tabelle del database",
            mimeType="text/plain"
        )
    ]


@app.read_resource()
async def read_resource(uri: str):
    """Legge una risorsa specifica."""
    
    if uri == "calor://impianti":
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                id, nome_impianto, codice_pv_fortech, 
                tipo_gestione, citta, attivo,
                (SELECT COUNT(*) FROM import_fortech_master f WHERE f.impianto_id = impianti.id) as record_count
            FROM impianti
            WHERE attivo = 1
            ORDER BY nome_impianto
        """)
        data = rows_to_list(cur.fetchall())
        conn.close()
        return TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))
    
    elif uri == "calor://anomalie":
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                r.id, i.nome_impianto, r.data_riferimento, r.categoria,
                r.valore_fortech, r.valore_reale, r.differenza, r.stato
            FROM report_riconciliazioni r
            JOIN impianti i ON r.impianto_id = i.id
            WHERE r.stato IN ('ANOMALIA_LIEVE', 'ANOMALIA_GRAVE')
            AND r.risolto = 0
            ORDER BY r.data_riferimento DESC
            LIMIT 50
        """)
        data = rows_to_list(cur.fetchall())
        conn.close()
        return TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))
    
    elif uri == "calor://stats":
        conn = get_db()
        cur = conn.cursor()
        
        # Conta impianti
        cur.execute("SELECT COUNT(*) FROM impianti WHERE attivo = 1")
        n_impianti = cur.fetchone()[0]
        
        # Conta giornate Fortech
        cur.execute("SELECT COUNT(*) FROM import_fortech_master")
        n_giornate = cur.fetchone()[0]
        
        # Conta anomalie aperte
        cur.execute("SELECT COUNT(*) FROM report_riconciliazioni WHERE stato LIKE 'ANOMALIA%' AND risolto = 0")
        n_anomalie = cur.fetchone()[0]
        
        # Totale corrispettivo
        cur.execute("SELECT COALESCE(SUM(corrispettivo_totale), 0) FROM import_fortech_master")
        totale_corr = cur.fetchone()[0]
        
        conn.close()
        
        stats = {
            "impianti_attivi": n_impianti,
            "giornate_analizzate": n_giornate,
            "anomalie_aperte": n_anomalie,
            "corrispettivo_totale": round(totale_corr, 2),
            "ultimo_aggiornamento": datetime.now().isoformat()
        }
        return TextContent(type="text", text=json.dumps(stats, indent=2, ensure_ascii=False))
    
    elif uri == "calor://schema":
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cur.fetchall()
        conn.close()
        
        schema_text = "# Schema Database Calor Systems\n\n"
        for table in tables:
            schema_text += f"## Tabella: {table[0]}\n```sql\n{table[1]}\n```\n\n"
        
        return TextContent(type="text", text=schema_text)
    
    else:
        raise ValueError(f"Risorsa sconosciuta: {uri}")


# =============================================================================
# TOOLS - Azioni disponibili per Claude
# =============================================================================

@app.list_tools()
async def list_tools():
    """Lista degli strumenti disponibili."""
    return [
        Tool(
            name="query_database",
            description="Esegue una query SQL SELECT sul database (solo lettura). Utile per analisi personalizzate.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Query SQL SELECT da eseguire. Solo SELECT permessi."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Numero massimo di righe (default 100)",
                        "default": 100
                    }
                },
                "required": ["sql"]
            }
        ),
        Tool(
            name="get_riconciliazione",
            description="Ottiene lo stato di riconciliazione completo per un impianto specifico.",
            inputSchema={
                "type": "object",
                "properties": {
                    "impianto_id": {
                        "type": "integer",
                        "description": "ID dell'impianto"
                    },
                    "giorni": {
                        "type": "integer",
                        "description": "Numero di giorni da analizzare (default 7)",
                        "default": 7
                    }
                },
                "required": ["impianto_id"]
            }
        ),
        Tool(
            name="get_anomalie_giornata",
            description="Ottiene tutte le anomalie per una data specifica.",
            inputSchema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "Data in formato YYYY-MM-DD"
                    }
                },
                "required": ["data"]
            }
        ),
        Tool(
            name="cerca_impianto",
            description="Cerca un impianto per nome o codice.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Nome parziale o codice dell'impianto"
                    }
                },
                "required": ["query"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    """Esegue uno strumento."""
    
    if name == "query_database":
        sql = arguments.get("sql", "").strip()
        limit = min(arguments.get("limit", 100), 500)  # Max 500 righe
        
        # Sicurezza: solo SELECT permessi
        if not sql.upper().startswith("SELECT"):
            return TextContent(
                type="text",
                text="❌ Errore: Solo query SELECT sono permesse."
            )
        
        # Blocca parole chiave pericolose
        forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE"]
        for word in forbidden:
            if word in sql.upper():
                return TextContent(
                    type="text",
                    text=f"❌ Errore: Parola chiave '{word}' non permessa."
                )
        
        try:
            conn = get_db()
            cur = conn.cursor()
            # Aggiungi LIMIT se non presente
            if "LIMIT" not in sql.upper():
                sql = f"{sql} LIMIT {limit}"
            cur.execute(sql)
            data = rows_to_list(cur.fetchall())
            conn.close()
            
            result = {
                "success": True,
                "row_count": len(data),
                "data": data
            }
            return TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False, default=str))
            
        except Exception as e:
            return TextContent(type="text", text=f"❌ Errore SQL: {str(e)}")
    
    elif name == "get_riconciliazione":
        impianto_id = arguments.get("impianto_id")
        giorni = arguments.get("giorni", 7)
        
        conn = get_db()
        cur = conn.cursor()
        
        # Info impianto
        cur.execute("SELECT nome_impianto FROM impianti WHERE id = ?", (impianto_id,))
        imp = cur.fetchone()
        if not imp:
            conn.close()
            return TextContent(type="text", text=f"❌ Impianto ID {impianto_id} non trovato.")
        
        # Dati Fortech ultimi N giorni
        cur.execute("""
            SELECT 
                data_contabile, corrispettivo_totale, 
                incasso_contanti_teorico, buoni_totale,
                fatture_postpagate_totale, fatture_prepagate_totale
            FROM import_fortech_master
            WHERE impianto_id = ?
            ORDER BY data_contabile DESC
            LIMIT ?
        """, (impianto_id, giorni))
        fortech_data = rows_to_list(cur.fetchall())
        
        # Anomalie
        cur.execute("""
            SELECT categoria, differenza, stato
            FROM report_riconciliazioni
            WHERE impianto_id = ? AND risolto = 0
            ORDER BY data_riferimento DESC
            LIMIT 10
        """, (impianto_id,))
        anomalie = rows_to_list(cur.fetchall())
        
        conn.close()
        
        result = {
            "impianto": imp[0],
            "impianto_id": impianto_id,
            "giorni_analizzati": len(fortech_data),
            "dati_fortech": fortech_data,
            "anomalie_aperte": anomalie
        }
        return TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False, default=str))
    
    elif name == "get_anomalie_giornata":
        data = arguments.get("data")
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                i.nome_impianto, r.categoria, r.valore_fortech, 
                r.valore_reale, r.differenza, r.stato
            FROM report_riconciliazioni r
            JOIN impianti i ON r.impianto_id = i.id
            WHERE r.data_riferimento = ?
            ORDER BY r.differenza DESC
        """, (data,))
        anomalie = rows_to_list(cur.fetchall())
        conn.close()
        
        result = {
            "data": data,
            "n_anomalie": len(anomalie),
            "dettaglio": anomalie
        }
        return TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False, default=str))
    
    elif name == "cerca_impianto":
        query = arguments.get("query", "")
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, nome_impianto, codice_pv_fortech, citta, tipo_gestione
            FROM impianti
            WHERE nome_impianto LIKE ? OR codice_pv_fortech LIKE ?
            ORDER BY nome_impianto
        """, (f"%{query}%", f"%{query}%"))
        impianti = rows_to_list(cur.fetchall())
        conn.close()
        
        return TextContent(type="text", text=json.dumps(impianti, indent=2, ensure_ascii=False))
    
    else:
        return TextContent(type="text", text=f"❌ Tool sconosciuto: {name}")


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Avvia il server MCP."""
    print(f"🚀 Avvio MCP Server: {SERVER_NAME} v{SERVER_VERSION}", flush=True)
    print(f"📁 Database: {DB_PATH}", flush=True)
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
