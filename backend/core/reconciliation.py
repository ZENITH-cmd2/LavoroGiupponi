"""
CALOR SYSTEMS - Modulo Riconciliazione
Logiche automatiche per confronto dati Fortech vs fonti reali
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum


class StatoRiconciliazione(Enum):
    """Stati possibili della riconciliazione"""
    QUADRATO = "QUADRATO"                          # Differenza = 0
    QUADRATO_ARROTONDAMENTO = "QUADRATO_ARROT"     # Diff ≤ tolleranza
    ANOMALIA_LIEVE = "ANOMALIA_LIEVE"              # Piccola discrepanza
    ANOMALIA_GRAVE = "ANOMALIA_GRAVE"              # Grande discrepanza
    NON_TROVATO = "NON_TROVATO"                    # Dato mancante
    IN_ATTESA = "IN_ATTESA"                        # Attesa versamento (contanti)


@dataclass
class RisultatoRiconciliazione:
    """Risultato di una singola riconciliazione"""
    categoria: str
    data: str
    valore_teorico: float
    valore_reale: float
    differenza: float
    stato: StatoRiconciliazione
    note: str = ""
    match_info: Dict = None


# ============================================================================
# CONFIGURAZIONE TOLLERANZE
# ============================================================================

TOLLERANZE = {
    'contanti': {
        'arrotondamento': 5.0,      # €5 di tolleranza per arrotondamenti gestore
        'lieve': 20.0,              # Fino a €20 = anomalia lieve
        'giorni_elastici': 3        # Cerca versamento fino a +3 giorni
    },
    'carte_bancarie': {
        'arrotondamento': 1.0,      # €1 di tolleranza
        'lieve': 10.0
    },
    'carte_petrolifere': {
        'arrotondamento': 1.0,
        'lieve': 10.0
    },
    'buoni': {
        'arrotondamento': 0.5,
        'lieve': 5.0
    },
    'satispay': {
        'arrotondamento': 0.1,
        'lieve': 1.0
    }
}


def calcola_stato(differenza: float, categoria: str) -> StatoRiconciliazione:
    """
    Determina lo stato della riconciliazione in base alla differenza.
    """
    tolleranze = TOLLERANZE.get(categoria, TOLLERANZE['carte_bancarie'])
    diff_abs = abs(differenza)
    
    if diff_abs == 0:
        return StatoRiconciliazione.QUADRATO
    elif diff_abs <= tolleranze['arrotondamento']:
        return StatoRiconciliazione.QUADRATO_ARROTONDAMENTO
    elif diff_abs <= tolleranze['lieve']:
        return StatoRiconciliazione.ANOMALIA_LIEVE
    else:
        return StatoRiconciliazione.ANOMALIA_GRAVE


# ============================================================================
# RICONCILIAZIONE CONTANTI (CRITICITÀ ALTA)
# ============================================================================

def riconcilia_contanti(
    fortech_data: Dict,
    as400_records: List[Dict],
    data_riferimento: str
) -> RisultatoRiconciliazione:
    """
    Riconciliazione contanti con:
    - Matching elastico sulle date (+1/+2/+3 giorni)
    - Gestione arrotondamenti (±5€)
    
    Args:
        fortech_data: Dati teorici da Fortech per il giorno
        as400_records: Lista versamenti AS400
        data_riferimento: Data in formato YYYY-MM-DD
    
    Returns:
        RisultatoRiconciliazione con stato e dettagli
    """
    teorico = fortech_data.get('contanti_teorico', 0) or 0
    giorni_elastici = TOLLERANZE['contanti']['giorni_elastici']
    
    # Converti data riferimento
    try:
        data_ref = datetime.strptime(data_riferimento, '%Y-%m-%d')
    except ValueError:
        return RisultatoRiconciliazione(
            categoria='contanti',
            data=data_riferimento,
            valore_teorico=teorico,
            valore_reale=0,
            differenza=teorico,
            stato=StatoRiconciliazione.NON_TROVATO,
            note='Data non valida'
        )
    
    # Cerca versamenti nel range elastico [data, data+giorni_elastici]
    versamenti_trovati = []
    totale_versato = 0
    
    for record in as400_records:
        data_vers_str = record.get('data_registrazione')
        if not data_vers_str:
            continue
            
        try:
            data_vers = datetime.strptime(data_vers_str[:10], '%Y-%m-%d')
        except ValueError:
            continue
        
        # Verifica se nel range elastico
        if data_ref <= data_vers <= data_ref + timedelta(days=giorni_elastici):
            importo = record.get('importo', 0) or 0
            versamenti_trovati.append({
                'data': data_vers_str,
                'importo': importo,
                'giorni_dopo': (data_vers - data_ref).days
            })
            totale_versato += importo
    
    # Calcola differenza
    differenza = teorico - totale_versato
    
    # Determina stato
    if not versamenti_trovati and teorico > 0:
        stato = StatoRiconciliazione.IN_ATTESA
        note = f"Attesa versamento (cercato fino a +{giorni_elastici}gg)"
    else:
        stato = calcola_stato(differenza, 'contanti')
        if stato == StatoRiconciliazione.QUADRATO_ARROTONDAMENTO:
            note = f"Quadrato con arrotondamento gestore (diff: €{differenza:.2f})"
        elif versamenti_trovati and versamenti_trovati[0]['giorni_dopo'] > 0:
            note = f"Versamento trovato dopo {versamenti_trovati[0]['giorni_dopo']} giorni"
        else:
            note = ""
    
    return RisultatoRiconciliazione(
        categoria='contanti',
        data=data_riferimento,
        valore_teorico=teorico,
        valore_reale=totale_versato,
        differenza=round(differenza, 2),
        stato=stato,
        note=note,
        match_info={'versamenti': versamenti_trovati}
    )


# ============================================================================
# RICONCILIAZIONE CARTE PETROLIFERE (AGGREGAZIONE)
# ============================================================================

def riconcilia_carte_petrolifere(
    fortech_fatture: float,
    ip_carte_totale: float,
    ip_buoni_totale: float
) -> RisultatoRiconciliazione:
    """
    Riconciliazione carte petrolifere:
    - Somma IP Carte (Azzurro) + IP Buoni (Rosso)
    - Confronta con Fortech Fatture Postpagate + Prepagate
    
    Args:
        fortech_fatture: Totale fatture da Fortech
        ip_carte_totale: Totale carte petrolifere da iP Portal
        ip_buoni_totale: Totale buoni da iP Portal
    
    Returns:
        RisultatoRiconciliazione
    """
    reale = ip_carte_totale + ip_buoni_totale
    differenza = fortech_fatture - reale
    stato = calcola_stato(differenza, 'carte_petrolifere')
    
    note = ""
    if stato != StatoRiconciliazione.QUADRATO:
        if ip_buoni_totale == 0 and differenza > 0:
            note = "Possibili buoni mancanti nel file iP Portal"
        elif ip_carte_totale == 0 and differenza > 0:
            note = "Possibili carte mancanti nel file iP Portal"
    
    return RisultatoRiconciliazione(
        categoria='carte_petrolifere',
        data="",  # Da impostare dal chiamante
        valore_teorico=fortech_fatture,
        valore_reale=reale,
        differenza=round(differenza, 2),
        stato=stato,
        note=note,
        match_info={
            'ip_carte': ip_carte_totale,
            'ip_buoni': ip_buoni_totale
        }
    )


# ============================================================================
# RICONCILIAZIONE CARTE BANCARIE (NUMIA)
# ============================================================================

def riconcilia_carte_bancarie(
    fortech_totale: float,
    numia_totale: float
) -> RisultatoRiconciliazione:
    """
    Riconciliazione carte bancarie:
    - Confronto diretto 1:1 Fortech vs Numia
    - Deve essere ESATTO (differenza = 0 per verde)
    
    Args:
        fortech_totale: Totale incassi carte da Fortech
        numia_totale: Totale transazioni POS da Numia
    
    Returns:
        RisultatoRiconciliazione
    """
    differenza = fortech_totale - numia_totale
    stato = calcola_stato(differenza, 'carte_bancarie')
    
    note = ""
    if stato == StatoRiconciliazione.QUADRATO:
        note = "✓ Match perfetto"
    elif differenza > 0:
        note = "Transazione Numia mancante o non registrata"
    else:
        note = "Transazione extra su Numia (doppio addebito?)"
    
    return RisultatoRiconciliazione(
        categoria='carte_bancarie',
        data="",
        valore_teorico=fortech_totale,
        valore_reale=numia_totale,
        differenza=round(differenza, 2),
        stato=stato,
        note=note
    )


# ============================================================================
# RICONCILIAZIONE CREDITI (FATTURA1CLICK)
# ============================================================================

def riconcilia_crediti(
    fortech_crediti: float,
    fattura1click_totale: float
) -> RisultatoRiconciliazione:
    """
    Riconciliazione crediti:
    - Verifica somma erogazioni Fattura1Click vs Fortech
    
    Args:
        fortech_crediti: Totale vendite a credito da Fortech
        fattura1click_totale: Totale inserito su Fattura1Click
    
    Returns:
        RisultatoRiconciliazione
    """
    differenza = fortech_crediti - fattura1click_totale
    stato = calcola_stato(differenza, 'carte_bancarie')  # Usa stesse tolleranze
    
    note = ""
    if stato != StatoRiconciliazione.QUADRATO:
        note = "Verifica inserimenti manuali su Fattura1Click"
    
    return RisultatoRiconciliazione(
        categoria='crediti',
        data="",
        valore_teorico=fortech_crediti,
        valore_reale=fattura1click_totale,
        differenza=round(differenza, 2),
        stato=stato,
        note=note
    )


# ============================================================================
# RICONCILIAZIONE COMPLETA GIORNATA
# ============================================================================

def riconcilia_giornata(
    fortech_data: Dict,
    as400_records: List[Dict],
    numia_records: List[Dict],
    ip_carte_records: List[Dict],
    ip_buoni_records: List[Dict],
    satispay_records: List[Dict] = None,
    fattura1click_records: List[Dict] = None
) -> Dict:
    """
    Esegue riconciliazione completa per una giornata.
    
    Returns:
        Dict con risultati per ogni categoria e stato globale
    """
    data = fortech_data.get('data_contabile', '')
    
    # Calcola totali reali
    numia_totale = sum(r.get('importo', 0) for r in numia_records)
    ip_carte_totale = sum(r.get('importo', 0) for r in ip_carte_records)
    ip_buoni_totale = sum(r.get('importo', 0) for r in ip_buoni_records)
    satispay_totale = sum(r.get('importo', 0) for r in (satispay_records or []))
    
    # Esegui riconciliazioni
    risultati = {}
    
    # Contanti
    risultati['contanti'] = riconcilia_contanti(fortech_data, as400_records, data)
    
    # Carte bancarie
    # Stima teorico carte = corrispettivo - fatture - buoni - contanti
    corrispettivo = fortech_data.get('corrispettivo_totale', 0) or 0
    fatture_tot = (fortech_data.get('fatture_postpagate', 0) or 0) + \
                  (fortech_data.get('fatture_prepagate', 0) or 0)
    buoni_tot = fortech_data.get('buoni_totale', 0) or 0
    contanti_teorico = fortech_data.get('contanti_teorico', 0) or 0
    
    carte_bancarie_teorico = corrispettivo - fatture_tot - buoni_tot - contanti_teorico
    if carte_bancarie_teorico < 0:
        carte_bancarie_teorico = 0
        
    risultati['carte_bancarie'] = riconcilia_carte_bancarie(carte_bancarie_teorico, numia_totale)
    risultati['carte_bancarie'].data = data
    
    # Carte petrolifere (aggregazione)
    risultati['carte_petrolifere'] = riconcilia_carte_petrolifere(
        fatture_tot, ip_carte_totale, ip_buoni_totale
    )
    risultati['carte_petrolifere'].data = data
    
    # Stato globale
    stati = [r.stato for r in risultati.values()]
    if StatoRiconciliazione.ANOMALIA_GRAVE in stati:
        stato_globale = 'ANOMALIA_GRAVE'
    elif StatoRiconciliazione.ANOMALIA_LIEVE in stati:
        stato_globale = 'ANOMALIA_LIEVE'
    elif StatoRiconciliazione.IN_ATTESA in stati:
        stato_globale = 'IN_ATTESA'
    elif StatoRiconciliazione.NON_TROVATO in stati:
        stato_globale = 'INCOMPLETO'
    else:
        stato_globale = 'QUADRATO'
    
    return {
        'data': data,
        'stato_globale': stato_globale,
        'risultati': {k: {
            'stato': v.stato.value,
            'teorico': v.valore_teorico,
            'reale': v.valore_reale,
            'differenza': v.differenza,
            'note': v.note
        } for k, v in risultati.items()}
    }


# ============================================================================
# ANALISI ANOMALIE RICORRENTI
# ============================================================================

def analizza_anomalie_ricorrenti(
    storico_riconciliazioni: List[Dict],
    soglia_ricorrenza: int = 3
) -> List[Dict]:
    """
    Analizza lo storico per identificare pattern di anomalie ricorrenti.
    
    Args:
        storico_riconciliazioni: Lista risultati storici
        soglia_ricorrenza: Numero minimo occorrenze per segnalare
    
    Returns:
        Lista di pattern identificati
    """
    # Conta anomalie per categoria e impianto
    conteggi = {}
    
    for ric in storico_riconciliazioni:
        impianto = ric.get('impianto_id')
        for cat, risultato in ric.get('risultati', {}).items():
            if risultato['stato'] in ('ANOMALIA_LIEVE', 'ANOMALIA_GRAVE'):
                key = (impianto, cat)
                if key not in conteggi:
                    conteggi[key] = {
                        'count': 0,
                        'totale_diff': 0,
                        'date': []
                    }
                conteggi[key]['count'] += 1
                conteggi[key]['totale_diff'] += abs(risultato['differenza'])
                conteggi[key]['date'].append(ric.get('data'))
    
    # Filtra per soglia
    patterns = []
    for (impianto, categoria), info in conteggi.items():
        if info['count'] >= soglia_ricorrenza:
            patterns.append({
                'impianto_id': impianto,
                'categoria': categoria,
                'occorrenze': info['count'],
                'diff_media': round(info['totale_diff'] / info['count'], 2),
                'ultime_date': info['date'][-5:],
                'severita': 'ALTA' if info['count'] >= soglia_ricorrenza * 2 else 'MEDIA'
            })
    
    return sorted(patterns, key=lambda x: x['occorrenze'], reverse=True)
