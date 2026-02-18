# MCP Server Calor Systems - Guida Installazione

## 📦 Cosa è stato creato

| File | Descrizione |
|------|-------------|
| `calor_mcp_server.py` | Server MCP Python |
| `mcp_config.json` | Configurazione per Claude Desktop |

---

## 🔧 Installazione Claude Desktop

### 1. Trova il file di configurazione Claude

Apri questa cartella:
```
%APPDATA%\Claude\
```
(Incolla questo percorso nella barra degli indirizzi di Esplora File)

### 2. Modifica `claude_desktop_config.json`

Se il file NON esiste, crealo. Se esiste, aggiungi la sezione `mcpServers`:

```json
{
    "mcpServers": {
        "calor-systems": {
            "command": "python",
            "args": ["calor_mcp_server.py"],
            "cwd": "c:/Users/Utente/Desktop/Lavoro_Giupponi"
        }
    }
}
```

### 3. Riavvia Claude Desktop

Chiudi completamente Claude Desktop e riavvialo.

---

## 🎯 Risorse Disponibili

Una volta connesso, Claude può accedere a:

| Risorsa | URI | Descrizione |
|---------|-----|-------------|
| Impianti | `calor://impianti` | Lista tutti gli impianti |
| Anomalie | `calor://anomalie` | Anomalie da verificare |
| Statistiche | `calor://stats` | Riepilogo sistema |
| Schema | `calor://schema` | Struttura database |

---

## 🔨 Tools Disponibili

| Tool | Uso |
|------|-----|
| `query_database` | Query SQL personalizzate (solo SELECT) |
| `get_riconciliazione` | Stato riconciliazione impianto |
| `get_anomalie_giornata` | Anomalie per data specifica |
| `cerca_impianto` | Cerca impianto per nome/codice |

---

## 💬 Esempi di Domande per Claude

Una volta configurato, puoi chiedere a Claude:

- "Mostrami le anomalie di oggi"
- "Quali impianti hanno più problemi?"
- "Dammi il riepilogo di Milano Repubblica"
- "Esegui SELECT * FROM impianti"
- "Cerca l'impianto Rovetta"

---

## 🔐 Sicurezza

- ✅ Il server gira SOLO in locale (localhost)
- ✅ Nessuna porta esposta su internet
- ✅ Solo query SELECT permesse
- ✅ Parole chiave pericolose bloccate (DROP, DELETE, etc.)
