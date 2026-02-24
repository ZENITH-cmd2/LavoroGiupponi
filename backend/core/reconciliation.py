"""
CALOR SYSTEMS - Modulo Riconciliazione
Logiche automatiche per confronto dati Fortech vs fonti reali
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from itertools import combinations


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


@dataclass
class MatchContanti:
    """Descrive un match trovato tra un versamento AS400 e uno o più giorni Fortech"""
    versamento_as400: Dict                              # Record AS400
    giorni_fortech_coperti: List[str] = field(default_factory=list)  # Date coperte
    totale_teorico: float = 0.0                         # Somma teorici Fortech
    importo_versato: float = 0.0                        # Importo AS400
    differenza: float = 0.0
    tipo_match: str = ""                                # '1:1', '1:1_arrotondato', 'cumulativo_2gg', etc.


# ============================================================================
# CONFIGURAZIONE TOLLERANZE
# ============================================================================

TOLLERANZE = {
    'contanti': {
        'arrotondamento': 5.0,      # €5 di tolleranza per arrotondamenti gestore
        'arrotondamento_per_giorno': 5.0,  # €5 × N giorni per versamenti cumulativi
        'lieve': 20.0,              # Fino a €20 = anomalia lieve
        'giorni_elastici': 3,       # Cerca versamento fino a +3 giorni
        'max_giorni_cumulativi': 4  # Max giorni raggruppabili in un versamento
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


def calcola_stato_contanti_cumulativo(differenza: float, n_giorni: int) -> StatoRiconciliazione:
    """
    Determina lo stato per versamenti cumulativi con tolleranza proporzionale.
    Tolleranza = ±5€ × N giorni cumulati.
    """
    diff_abs = abs(differenza)
    toll_per_giorno = TOLLERANZE['contanti']['arrotondamento_per_giorno']
    tolleranza_dinamica = toll_per_giorno * n_giorni
    lieve_dinamica = TOLLERANZE['contanti']['lieve'] * n_giorni
    
    if diff_abs == 0:
        return StatoRiconciliazione.QUADRATO
    elif diff_abs <= tolleranza_dinamica:
        return StatoRiconciliazione.QUADRATO_ARROTONDAMENTO
    elif diff_abs <= lieve_dinamica:
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
    Riconciliazione contanti SINGOLO GIORNO (legacy, backward-compatible).
    - Matching elastico sulle date (+1/+2/+3 giorni)
    - Gestione arrotondamenti (±5€)
    
    Per il matching multi-giorno (cumulativi), usare riconcilia_contanti_multi_giorno().
    
    Args:
        fortech_data: Dati teorici da Fortech per il giorno
        as400_records: Lista versamenti AS400
        data_riferimento: Data in formato YYYY-MM-DD
    
    Returns:
        RisultatoRiconciliazione con stato e dettagli
    """
    teorico = fortech_data.get('incasso_contanti_teorico', 0) or 0
    giorni_elastici = TOLLERANZE['contanti']['giorni_elastici']
    
    # Converti data riferimento
    try:
        data_ref = datetime.strptime(data_riferimento[:10], '%Y-%m-%d')
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
            importo = record.get('importo_versato', 0) or 0
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
# RICONCILIAZIONE CONTANTI MULTI-GIORNO (VERSAMENTI CUMULATIVI)
# ============================================================================

def riconcilia_contanti_multi_giorno(
    fortech_multi: List[Dict],
    as400_records: List[Dict],
    impianto_id: str = None
) -> List[RisultatoRiconciliazione]:
    """
    Riconciliazione contanti con matching intelligente many-to-one.
    
    Risolve le 3 criticità principali:
    1. ARROTONDAMENTI: tolleranza ±5€ per singolo giorno
    2. VERSAMENTI CUMULATIVI: cerca combinazioni N giorni → 1 versamento
    3. MANCANZA DATE: deduce le date tramite matching importi (subset-sum)
    
    Algoritmo in 4 fasi:
      Fase 1: Match esatto 1:1 (diff = 0)
      Fase 2: Match 1:1 con arrotondamento (±5€)
      Fase 3: Match cumulativo 2-4 giorni consecutivi (tolleranza ±5€×N)
      Fase 4: Giorni rimasti senza match → IN_ATTESA
    
    Args:
        fortech_multi: Lista di Dict Fortech, ognuno con almeno:
                       - data_contabile (str YYYY-MM-DD)
                       - incasso_contanti_teorico (float)
        as400_records: Tutti i versamenti AS400 nel periodo allargato
        impianto_id: ID impianto (opzionale, per logging)
    
    Returns:
        Lista di RisultatoRiconciliazione (uno per ogni giorno Fortech)
    """
    if not fortech_multi:
        return []
    
    toll_per_giorno = TOLLERANZE['contanti']['arrotondamento_per_giorno']
    max_combo = TOLLERANZE['contanti']['max_giorni_cumulativi']
    giorni_elastici = TOLLERANZE['contanti']['giorni_elastici']
    
    # ── Prepara dati Fortech ──
    # Ordina per data e crea struttura di lavoro
    giorni_fortech = []
    for ft in fortech_multi:
        data_str = ft.get('data_contabile', '')[:10]
        teorico = ft.get('incasso_contanti_teorico', 0) or 0
        if data_str and teorico > 0:  # Ignora giorni senza contanti
            giorni_fortech.append({
                'data': data_str,
                'teorico': teorico,
                'coperto': False,       # Flag matching
                'match': None           # MatchContanti assegnato
            })
    
    giorni_fortech.sort(key=lambda x: x['data'])
    
    # ── Prepara versamenti AS400 ──
    versamenti = []
    for rec in as400_records:
        importo = rec.get('importo_versato', 0) or 0
        data_reg = rec.get('data_registrazione', '')
        if importo > 0 and data_reg:
            versamenti.append({
                'record': rec,
                'importo': importo,
                'data': data_reg[:10],
                'usato': False
            })
    
    versamenti.sort(key=lambda x: x['data'])
    matches_trovati: List[MatchContanti] = []
    
    # ══════════════════════════════════════════════════════════════
    # FASE 1: Match esatto 1:1 (differenza = 0)
    # ══════════════════════════════════════════════════════════════
    for v in versamenti:
        if v['usato']:
            continue
        for g in giorni_fortech:
            if g['coperto']:
                continue
            # Verifica proximity temporale: versamento entro N giorni dal giorno Fortech
            if not _in_range_elastico(g['data'], v['data'], giorni_elastici):
                continue
            if abs(g['teorico'] - v['importo']) < 0.01:  # Match esatto
                match = MatchContanti(
                    versamento_as400=v['record'],
                    giorni_fortech_coperti=[g['data']],
                    totale_teorico=g['teorico'],
                    importo_versato=v['importo'],
                    differenza=0.0,
                    tipo_match='1:1_esatto'
                )
                g['coperto'] = True
                g['match'] = match
                v['usato'] = True
                matches_trovati.append(match)
                break
    
    # ══════════════════════════════════════════════════════════════
    # FASE 2: Match 1:1 con arrotondamento (±5€)
    # ══════════════════════════════════════════════════════════════
    for v in versamenti:
        if v['usato']:
            continue
        best_match = None
        best_diff = float('inf')
        best_giorno = None
        
        for g in giorni_fortech:
            if g['coperto']:
                continue
            if not _in_range_elastico(g['data'], v['data'], giorni_elastici):
                continue
            diff = abs(g['teorico'] - v['importo'])
            if diff <= toll_per_giorno and diff < best_diff:
                best_diff = diff
                best_match = g
        
        if best_match:
            differenza = round(best_match['teorico'] - v['importo'], 2)
            match = MatchContanti(
                versamento_as400=v['record'],
                giorni_fortech_coperti=[best_match['data']],
                totale_teorico=best_match['teorico'],
                importo_versato=v['importo'],
                differenza=differenza,
                tipo_match='1:1_arrotondato'
            )
            best_match['coperto'] = True
            best_match['match'] = match
            v['usato'] = True
            matches_trovati.append(match)
    
    # ══════════════════════════════════════════════════════════════
    # FASE 3: Match cumulativo (2, 3, 4 giorni consecutivi)
    # Es. Sabato + Domenica → Versamento Lunedì
    # Tolleranza dinamica: ±5€ × N giorni
    # ══════════════════════════════════════════════════════════════
    for v in versamenti:
        if v['usato']:
            continue
        
        # Prendi solo giorni non ancora coperti
        giorni_liberi = [g for g in giorni_fortech if not g['coperto']]
        if not giorni_liberi:
            break
        
        match_trovato = False
        
        # Prova combinazioni da 2 a max_combo giorni
        for n in range(2, min(max_combo + 1, len(giorni_liberi) + 1)):
            if match_trovato:
                break
            
            # Prova solo finestre contigue di n giorni liberi
            for i in range(len(giorni_liberi) - n + 1):
                giorni_combo = giorni_liberi[i : i+n]
                
                # Verifica che i giorni siano "ragionevolmente consecutivi"
                # (max 1 giorno di gap tra il primo e l'ultimo)
                date_combo = [g['data'] for g in giorni_combo]
                if not _sono_date_vicine(date_combo, max_gap=2):
                    continue
                
                # Verifica che il versamento sia successivo al primo giorno
                # (con margine elastico)
                if not _in_range_elastico(date_combo[0], v['data'], 
                                           giorni_elastici + n):
                    continue
                
                somma_teorici = sum(g['teorico'] for g in giorni_combo)
                diff = abs(somma_teorici - v['importo'])
                tolleranza_dinamica = toll_per_giorno * n
                
                if diff <= tolleranza_dinamica:
                    differenza = round(somma_teorici - v['importo'], 2)
                    match = MatchContanti(
                        versamento_as400=v['record'],
                        giorni_fortech_coperti=date_combo,
                        totale_teorico=round(somma_teorici, 2),
                        importo_versato=v['importo'],
                        differenza=differenza,
                        tipo_match=f'cumulativo_{n}gg'
                    )
                    for g in giorni_combo:
                        g['coperto'] = True
                        g['match'] = match
                    v['usato'] = True
                    matches_trovati.append(match)
                    match_trovato = True
                    break
    
    # ══════════════════════════════════════════════════════════════
    # FASE 4: Costruisci risultati per ogni giorno Fortech
    # ══════════════════════════════════════════════════════════════
    risultati = []
    
    for g in giorni_fortech:
        if g['coperto'] and g['match']:
            m = g['match']
            n_giorni = len(m.giorni_fortech_coperti)
            stato = calcola_stato_contanti_cumulativo(m.differenza, n_giorni)
            
            # Genera nota descrittiva
            if m.tipo_match == '1:1_esatto':
                nota = "✓ Match perfetto 1:1"
            elif m.tipo_match == '1:1_arrotondato':
                nota = f"Arrotondamento gestore (diff: €{m.differenza:+.2f})"
            else:
                date_coperte = ', '.join(m.giorni_fortech_coperti)
                nota = (f"Versamento cumulativo {n_giorni}gg "
                        f"({date_coperte}) → €{m.importo_versato:.2f} "
                        f"(diff: €{m.differenza:+.2f})")
            
            risultati.append(RisultatoRiconciliazione(
                categoria='contanti',
                data=g['data'],
                valore_teorico=g['teorico'],
                valore_reale=m.importo_versato if n_giorni == 1 else round(
                    m.importo_versato * (g['teorico'] / m.totale_teorico), 2
                ) if m.totale_teorico > 0 else 0,
                differenza=round(m.differenza, 2) if n_giorni == 1 else round(
                    m.differenza * (g['teorico'] / m.totale_teorico), 2
                ) if m.totale_teorico > 0 else 0,
                stato=stato,
                note=nota,
                match_info={
                    'tipo_match': m.tipo_match,
                    'giorni_coperti': m.giorni_fortech_coperti,
                    'importo_versato_totale': m.importo_versato,
                    'versamento_data': m.versamento_as400.get('data_registrazione', ''),
                }
            ))
        else:
            # Giorno non matchato → IN_ATTESA
            risultati.append(RisultatoRiconciliazione(
                categoria='contanti',
                data=g['data'],
                valore_teorico=g['teorico'],
                valore_reale=0,
                differenza=g['teorico'],
                stato=StatoRiconciliazione.IN_ATTESA,
                note=f"Nessun versamento trovato per questa giornata",
                match_info={'tipo_match': 'nessuno'}
            ))
    
    # Aggiungi anche i giorni Fortech con teorico = 0 (non inclusi nell'algoritmo)
    date_processate = {g['data'] for g in giorni_fortech}
    for ft in fortech_multi:
        data_str = ft.get('data_contabile', '')[:10]
        teorico = ft.get('incasso_contanti_teorico', 0) or 0
        if data_str and data_str not in date_processate:
            risultati.append(RisultatoRiconciliazione(
                categoria='contanti',
                data=data_str,
                valore_teorico=teorico,
                valore_reale=0,
                differenza=0,
                stato=StatoRiconciliazione.QUADRATO,
                note="Nessun contante teorico per questa giornata",
                match_info={'tipo_match': 'zero'}
            ))
    
    risultati.sort(key=lambda r: r.data)
    return risultati


# ── Helper functions per il matching multi-giorno ──

def _in_range_elastico(data_fortech: str, data_versamento: str, 
                        giorni_max: int) -> bool:
    """Verifica se il versamento è entro N giorni dal giorno Fortech."""
    try:
        d_ft = datetime.strptime(data_fortech[:10], '%Y-%m-%d')
        d_vs = datetime.strptime(data_versamento[:10], '%Y-%m-%d')
        delta = (d_vs - d_ft).days
        return 0 <= delta <= giorni_max
    except (ValueError, TypeError):
        return False


def _sono_date_vicine(date_ordinate: List[str], max_gap: int = 2) -> bool:
    """
    Verifica che una lista di date ordinate siano 'vicine' tra loro.
    max_gap: numero massimo di giorni tra la prima e l'ultima data
             rispetto a una sequenza perfettamente consecutiva.
    Es. ['2026-01-13', '2026-01-14', '2026-01-15'] → True (3 giorni consecutivi)
    Es. ['2026-01-13', '2026-01-16'] → gap di 3, se max_gap=2 → False
    """
    if len(date_ordinate) <= 1:
        return True
    try:
        first = datetime.strptime(date_ordinate[0][:10], '%Y-%m-%d')
        last = datetime.strptime(date_ordinate[-1][:10], '%Y-%m-%d')
        span = (last - first).days
        # I giorni dovrebbero coprire al massimo N-1 + max_gap giorni
        # Es. 3 date consecutive = span di 2 giorni; con gap 2 = max span 4
        n_date = len(date_ordinate)
        return span <= (n_date - 1) + max_gap
    except (ValueError, TypeError):
        return False


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
    if stato == StatoRiconciliazione.QUADRATO:
        note = "✓ Match perfetto"
    elif stato != StatoRiconciliazione.QUADRATO_ARROTONDAMENTO:
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
# RICONCILIAZIONE SATISPAY
# ============================================================================

def riconcilia_satispay(
    fortech_totale: float,
    satispay_totale: float
) -> RisultatoRiconciliazione:
    """
    Riconciliazione Satispay:
    - Confronto diretto Fortech vs portale Satispay
    - Identificazione impianto tramite codice negozio
    
    Args:
        fortech_totale: Totale Satispay da Fortech
        satispay_totale: Totale transazioni dal portale Satispay
    
    Returns:
        RisultatoRiconciliazione
    """
    differenza = fortech_totale - satispay_totale
    stato = calcola_stato(differenza, 'satispay')
    
    note = ""
    if stato == StatoRiconciliazione.QUADRATO:
        note = "✓ Match perfetto"
    elif differenza > 0:
        note = "Transazione Satispay mancante o non registrata"
    else:
        note = "Transazione extra su Satispay"
    
    return RisultatoRiconciliazione(
        categoria='satispay',
        data="",
        valore_teorico=fortech_totale,
        valore_reale=satispay_totale,
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
    Confronta il File Madre Fortech con tutte le fonti reali:
    - Contanti (AS400) - 🟡
    - Carte Bancarie (Numia) - 🟢
    - Carte Petrolifere + Buoni (iP Portal) - 🔵/🔴
    - Satispay - ⚫
    - Crediti Fine Mese (Fattura1Click) - 🟣
    
    Returns:
        Dict con risultati per ogni categoria e stato globale
    """
    data = fortech_data.get('data_contabile', '')[:10]
    
    # Calcola totali reali dalle fonti esterne
    numia_totale = sum(r.get('importo', 0) or 0 for r in numia_records)
    ip_carte_totale = sum(r.get('importo', 0) or 0 for r in ip_carte_records)
    ip_buoni_totale = sum(r.get('importo', 0) or 0 for r in ip_buoni_records)
    satispay_totale = sum(r.get('importo_totale', 0) or 0 for r in (satispay_records or []))
    fattura1click_totale = sum(r.get('importo_erogazione', 0) or 0 for r in (fattura1click_records or []))
    
    # ── Esegui riconciliazioni ──
    risultati = {}
    
    # 🟡 Contanti (AS400) — la più critica
    risultati['contanti'] = riconcilia_contanti(fortech_data, as400_records, data)
    
    # 🟢 Carte bancarie (Numia) — confronto diretto al centesimo
    carte_bancarie_teorico = fortech_data.get('incasso_carte_bancarie_teorico', 0) or 0
    risultati['carte_bancarie'] = riconcilia_carte_bancarie(carte_bancarie_teorico, numia_totale)
    risultati['carte_bancarie'].data = data
    
    # 🔵🔴 Carte petrolifere + Buoni (iP Portal) — aggregazione PV + Esercente
    fatture_tot = (fortech_data.get('fatture_postpagate_totale', 0) or 0) + \
                  (fortech_data.get('fatture_prepagate_totale', 0) or 0)
    risultati['carte_petrolifere'] = riconcilia_carte_petrolifere(
        fatture_tot, ip_carte_totale, ip_buoni_totale
    )
    risultati['carte_petrolifere'].data = data
    
    # ⚫ Satispay — confronto diretto tramite codice negozio
    satispay_teorico = fortech_data.get('incasso_satispay_teorico', 0) or 0
    risultati['satispay'] = riconcilia_satispay(satispay_teorico, satispay_totale)
    risultati['satispay'].data = data
    
    # 🟣 Crediti Fine Mese (Fattura1Click) — somma erogazioni vs Fortech
    credito_teorico = fortech_data.get('incasso_credito_finemese_teorico', 0) or 0
    risultati['crediti'] = riconcilia_crediti(credito_teorico, fattura1click_totale)
    risultati['crediti'].data = data
    
    # ── Stato globale ──
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
