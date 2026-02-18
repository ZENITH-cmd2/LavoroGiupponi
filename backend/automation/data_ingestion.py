"""
CALOR SYSTEMS - Modulo Ingestione Dati
Parser intelligente per riconoscimento automatico fonte Excel
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import re
from typing import Dict, Optional, Tuple, List

# Mapping colonne per identificazione fonte
FONTE_SIGNATURES = {
    'FORTECH': ['CodicePV', 'Corrispettivo Totale', 'DataContabile', 'StatoGiornata'],
    'AS400': ['Registrazione//Data', 'Documento//Tipo', 'Importo', 'Segno'],
    'NUMIA': ['Circuito', 'MID', 'ID Terminale / TML', 'Codice autorizzazione'],
    'IP_CARTE': ['PV', 'Gestore', 'Circuito', 'Cod. Prod.'],
    'IP_BUONI': ['Esercente', 'Descrizione esercente', 'Pan', 'Serial number'],
    'SATISPAY': ['id transazione', 'codice negozio', 'totale commissioni']
}


def identifica_fonte(df: pd.DataFrame) -> Tuple[str, float]:
    """
    Analizza le colonne di un DataFrame per determinare la fonte.
    
    Returns:
        Tuple[str, float]: (nome_fonte, confidence_score 0-1)
    """
    colonne = set(df.columns.tolist())
    
    best_match = ('UNKNOWN', 0.0)
    
    for fonte, signature_cols in FONTE_SIGNATURES.items():
        # Conta quante colonne della signature sono presenti
        matches = sum(1 for col in signature_cols if col in colonne)
        score = matches / len(signature_cols)
        
        if score > best_match[1]:
            best_match = (fonte, score)
    
    # Se score troppo basso, prova pattern matching sui nomi colonne
    if best_match[1] < 0.5:
        col_str = ' '.join(str(c).lower() for c in colonne)
        
        if 'esercente' in col_str and 'pan' in col_str:
            return ('IP_BUONI', 0.7)
        elif 'circuito' in col_str and 'mid' in col_str:
            return ('NUMIA', 0.7)
        elif 'codicepv' in col_str or 'corrispettivo' in col_str:
            return ('FORTECH', 0.7)
        elif 'registrazione' in col_str and 'importo' in col_str:
            return ('AS400', 0.7)
        elif 'satispay' in col_str or 'commissioni' in col_str:
            return ('SATISPAY', 0.7)
    
    return best_match


def identifica_fonte_da_nome_file(filename: str) -> str:
    """
    Fallback: identifica fonte dal nome del file.
    """
    filename_lower = filename.lower()
    
    if 'fortech' in filename_lower:
        return 'FORTECH'
    elif 'as400' in filename_lower or 'contanti' in filename_lower:
        return 'AS400'
    elif 'numia' in filename_lower or 'bancarie' in filename_lower:
        return 'NUMIA'
    elif 'petrolifere' in filename_lower or 'azzurro' in filename_lower:
        return 'IP_CARTE'
    elif 'buoni' in filename_lower or 'rosso' in filename_lower:
        return 'IP_BUONI'
    elif 'satispay' in filename_lower:
        return 'SATISPAY'
    
    return 'UNKNOWN'


def parse_excel_intelligente(file_path: Path) -> Dict:
    """
    Legge un file Excel, identifica automaticamente la fonte,
    e restituisce i dati strutturati.
    
    Returns:
        Dict con keys: fonte, confidence, records, errors
    """
    result = {
        'fonte': 'UNKNOWN',
        'confidence': 0.0,
        'records': [],
        'errors': [],
        'file_name': file_path.name
    }
    
    try:
        # Prova a leggere con header standard
        df = pd.read_excel(file_path)
        
        # Identifica fonte
        fonte, confidence = identifica_fonte(df)
        
        # Se confidence bassa, prova header riga 1
        if confidence < 0.5:
            df_alt = pd.read_excel(file_path, header=1)
            fonte_alt, confidence_alt = identifica_fonte(df_alt)
            if confidence_alt > confidence:
                df = df_alt
                fonte = fonte_alt
                confidence = confidence_alt
        
        # Se ancora bassa, usa nome file
        if confidence < 0.3:
            fonte = identifica_fonte_da_nome_file(file_path.name)
            confidence = 0.5 if fonte != 'UNKNOWN' else 0.0
        
        result['fonte'] = fonte
        result['confidence'] = confidence
        result['records'] = df.to_dict('records')
        result['row_count'] = len(df)
        result['columns'] = list(df.columns)
        
    except Exception as e:
        result['errors'].append(str(e))
    
    return result


def estrai_codice_pv(valore) -> Optional[str]:
    """Estrae il codice PV numerico da stringhe come '43809 - OPT1'"""
    if pd.isna(valore):
        return None
    match = re.match(r'(\d+)', str(valore))
    return match.group(1) if match else None


def normalizza_importo(valore) -> float:
    """Converte vari formati di importo in float"""
    if pd.isna(valore):
        return 0.0
    if isinstance(valore, (int, float)):
        return float(valore)
    
    # Rimuovi simboli valuta e spazi
    valore_str = str(valore).replace('€', '').replace(' ', '').strip()
    
    # Gestisci formato italiano (1.234,56) vs inglese (1,234.56)
    if ',' in valore_str and '.' in valore_str:
        if valore_str.rindex(',') > valore_str.rindex('.'):
            # Formato italiano: 1.234,56
            valore_str = valore_str.replace('.', '').replace(',', '.')
        else:
            # Formato inglese: 1,234.56
            valore_str = valore_str.replace(',', '')
    elif ',' in valore_str:
        # Solo virgola: assume italiano
        valore_str = valore_str.replace(',', '.')
    
    try:
        return float(valore_str)
    except ValueError:
        return 0.0


def normalizza_data(valore) -> Optional[str]:
    """Converte vari formati data in YYYY-MM-DD"""
    if pd.isna(valore):
        return None
    
    if isinstance(valore, pd.Timestamp):
        return valore.strftime('%Y-%m-%d')
    
    if isinstance(valore, datetime):
        return valore.strftime('%Y-%m-%d')
    
    valore_str = str(valore)
    
    # Prova vari formati
    formati = [
        '%Y-%m-%d',
        '%d/%m/%Y',
        '%d-%m-%Y',
        '%Y/%m/%d',
        '%d.%m.%Y'
    ]
    
    for fmt in formati:
        try:
            dt = datetime.strptime(valore_str[:10], fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    return valore_str[:10] if len(valore_str) >= 10 else None


# ============================================================================
# PARSER SPECIFICI PER FONTE
# ============================================================================

def parse_fortech(df: pd.DataFrame) -> List[Dict]:
    """Estrae dati strutturati da file Fortech"""
    records = []
    
    for _, row in df.iterrows():
        codice_pv = estrai_codice_pv(row.get('CodicePV'))
        if not codice_pv:
            continue
            
        records.append({
            'codice_pv': codice_pv,
            'data_contabile': normalizza_data(row.get('DataContabile')),
            'corrispettivo_totale': normalizza_importo(row.get('Corrispettivo Totale')),
            'fatture_postpagate': normalizza_importo(row.get('Fatture Postpagate Totale')),
            'fatture_prepagate': normalizza_importo(row.get('Fatture Prepagate Totale')),
            'buoni_totale': normalizza_importo(row.get('Buoni Totale')),
            'contanti_teorico': normalizza_importo(row.get('Incasso Contanti', 0))
        })
    
    return records


def parse_as400(df: pd.DataFrame) -> List[Dict]:
    """Estrae dati strutturati da file AS400"""
    records = []
    
    for _, row in df.iterrows():
        importo = normalizza_importo(row.get('Importo'))
        if importo == 0:
            continue
            
        records.append({
            'data_registrazione': normalizza_data(row.get('Registrazione//Data')),
            'data_documento': normalizza_data(row.get('Documento//Data')),
            'importo': importo,
            'segno': str(row.get('Segno', '')),
            'descrizione': str(row.get('Descrizione', ''))[:200]
        })
    
    return records


def parse_numia(df: pd.DataFrame) -> List[Dict]:
    """Estrae dati strutturati da file Numia"""
    records = []
    
    for _, row in df.iterrows():
        importo = normalizza_importo(row.get('Importo'))
        if importo == 0:
            continue
            
        records.append({
            'data_transazione': normalizza_data(row.get('Data e ora')),
            'importo': importo,
            'circuito': str(row.get('Circuito', '')),
            'stato': str(row.get('Stato operazione', ''))
        })
    
    return records


def parse_ip_portal(df: pd.DataFrame, tipo: str) -> List[Dict]:
    """Estrae dati strutturati da file iP Portal (Carte o Buoni)"""
    records = []
    
    for _, row in df.iterrows():
        importo = normalizza_importo(row.get('Importo'))
        if importo == 0:
            continue
        
        # Determina codice PV
        if tipo == 'IP_CARTE':
            codice_pv = estrai_codice_pv(row.get('PV'))
            data_op = row.get('Data\noperazione') or row.get('Data operazione')
        else:  # IP_BUONI
            codice_pv = estrai_codice_pv(row.get('Esercente'))
            data_op = row.get('Data operazione')
            
        records.append({
            'tipo': tipo,
            'codice_pv': codice_pv,
            'data_operazione': normalizza_data(data_op),
            'importo': importo,
            'prodotto': str(row.get('Prodotto', ''))[:100]
        })
    
    return records


# ============================================================================
# FUNZIONE PRINCIPALE
# ============================================================================

def processa_file_automatico(file_path: Path) -> Dict:
    """
    Processa un file Excel automaticamente:
    1. Identifica la fonte
    2. Applica il parser appropriato
    3. Restituisce dati normalizzati
    """
    info = parse_excel_intelligente(file_path)
    
    if info['fonte'] == 'UNKNOWN':
        info['errors'].append('Impossibile identificare la fonte del file')
        return info
    
    # Applica parser specifico
    try:
        df = pd.read_excel(file_path)
        
        if info['fonte'] == 'FORTECH':
            info['parsed_data'] = parse_fortech(df)
        elif info['fonte'] == 'AS400':
            info['parsed_data'] = parse_as400(df)
        elif info['fonte'] == 'NUMIA':
            info['parsed_data'] = parse_numia(df)
        elif info['fonte'] in ('IP_CARTE', 'IP_BUONI'):
            info['parsed_data'] = parse_ip_portal(df, info['fonte'])
            
        info['parsed_count'] = len(info.get('parsed_data', []))
        
    except Exception as e:
        info['errors'].append(f'Errore parsing: {str(e)}')
    
    return info
