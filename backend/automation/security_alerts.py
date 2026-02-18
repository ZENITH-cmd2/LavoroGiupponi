"""
CALOR SYSTEMS - Modulo Alert Sicurezza
Monitoraggio aperture casse per impianti Self-Service (Taleggio)
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import sqlite3


class TipoAlert(Enum):
    """Tipi di alert di sicurezza"""
    APERTURA_NON_AUTORIZZATA = "APERTURA_NON_AUTORIZZATA"
    DISCREPANZA_CONTANTE = "DISCREPANZA_CONTANTE"
    MANCATO_VERSAMENTO = "MANCATO_VERSAMENTO"
    APERTURA_MULTIPLA = "APERTURA_MULTIPLA"


@dataclass
class AlertSicurezza:
    """Alert di sicurezza generato"""
    impianto_id: int
    impianto_nome: str
    tipo: TipoAlert
    timestamp: datetime
    messaggio: str
    severita: str  # CRITICA, ALTA, MEDIA
    dettagli: Dict = None
    
    def to_dict(self) -> Dict:
        return {
            'impianto_id': self.impianto_id,
            'impianto_nome': self.impianto_nome,
            'tipo': self.tipo.value,
            'timestamp': self.timestamp.isoformat(),
            'messaggio': self.messaggio,
            'severita': self.severita,
            'dettagli': self.dettagli or {}
        }


# Mapping giorni settimana italiano -> numero
GIORNI_IT = {
    'lunedi': 0, 'lunedì': 0,
    'martedi': 1, 'martedì': 1,
    'mercoledi': 2, 'mercoledì': 2,
    'giovedi': 3, 'giovedì': 3,
    'venerdi': 4, 'venerdì': 4,
    'sabato': 5,
    'domenica': 6
}


def ottieni_numero_giorno(giorno_str: str) -> int:
    """Converte nome giorno in numero (0=lunedì, 6=domenica)"""
    return GIORNI_IT.get(giorno_str.lower().strip(), -1)


def controlla_apertura_cassa(
    timestamp_apertura: datetime,
    giorno_autorizzato: str,
    impianto_id: int,
    impianto_nome: str
) -> Optional[AlertSicurezza]:
    """
    Verifica se un'apertura cassa è avvenuta nel giorno autorizzato.
    
    Args:
        timestamp_apertura: Quando è stata aperta la cassa
        giorno_autorizzato: Giorno previsto (es. "giovedì")
        impianto_id: ID impianto
        impianto_nome: Nome impianto per messaggio
    
    Returns:
        AlertSicurezza se apertura non autorizzata, None altrimenti
    """
    giorno_autorizzato_num = ottieni_numero_giorno(giorno_autorizzato)
    giorno_apertura_num = timestamp_apertura.weekday()
    
    if giorno_autorizzato_num == -1:
        # Giorno non configurato, non possiamo validare
        return None
    
    if giorno_apertura_num != giorno_autorizzato_num:
        # ALERT! Apertura in giorno non autorizzato
        giorni_it_inv = {v: k for k, v in GIORNI_IT.items() if 'ì' not in k}
        giorno_apertura_nome = giorni_it_inv.get(giorno_apertura_num, 'sconosciuto')
        
        return AlertSicurezza(
            impianto_id=impianto_id,
            impianto_nome=impianto_nome,
            tipo=TipoAlert.APERTURA_NON_AUTORIZZATA,
            timestamp=timestamp_apertura,
            messaggio=f"⚠️ APERTURA CASSA NON AUTORIZZATA: {impianto_nome} aperta il {giorno_apertura_nome.upper()} (autorizzato: {giorno_autorizzato})",
            severita='CRITICA',
            dettagli={
                'giorno_apertura': giorno_apertura_nome,
                'giorno_previsto': giorno_autorizzato,
                'ora_apertura': timestamp_apertura.strftime('%H:%M')
            }
        )
    
    return None


def calcola_contante_tra_aperture(
    apertura_precedente: datetime,
    apertura_corrente: datetime,
    incassi_fortech: List[Dict]
) -> Dict:
    """
    Calcola quanto contante è entrato tra due aperture consecutive.
    
    Args:
        apertura_precedente: Timestamp apertura precedente
        apertura_corrente: Timestamp apertura corrente
        incassi_fortech: Lista incassi giornalieri da Fortech
    
    Returns:
        Dict con totale_atteso, giorni_coperti, dettaglio_giornaliero
    """
    totale_atteso = 0
    giorni = []
    
    for incasso in incassi_fortech:
        data_incasso_str = incasso.get('data_contabile')
        if not data_incasso_str:
            continue
            
        try:
            if isinstance(data_incasso_str, str):
                data_incasso = datetime.strptime(data_incasso_str[:10], '%Y-%m-%d')
            else:
                data_incasso = data_incasso_str
        except ValueError:
            continue
        
        # Includi se tra le due aperture
        if apertura_precedente.date() <= data_incasso.date() < apertura_corrente.date():
            contanti = incasso.get('contanti_teorico', 0) or 0
            totale_atteso += contanti
            giorni.append({
                'data': data_incasso.strftime('%Y-%m-%d'),
                'contanti': contanti
            })
    
    return {
        'totale_atteso': round(totale_atteso, 2),
        'giorni_coperti': len(giorni),
        'periodo': {
            'da': apertura_precedente.strftime('%Y-%m-%d'),
            'a': apertura_corrente.strftime('%Y-%m-%d')
        },
        'dettaglio': giorni
    }


def verifica_versamento(
    contante_atteso: float,
    versato_effettivo: float,
    impianto_id: int,
    impianto_nome: str,
    tolleranza: float = 10.0
) -> Optional[AlertSicurezza]:
    """
    Verifica se il versamento corrisponde al contante atteso.
    
    Args:
        contante_atteso: Totale contante calcolato da Fortech
        versato_effettivo: Importo effettivamente versato
        tolleranza: Differenza massima accettabile
    
    Returns:
        AlertSicurezza se discrepanza significativa
    """
    differenza = contante_atteso - versato_effettivo
    
    if abs(differenza) <= tolleranza:
        return None
    
    if differenza > 0:
        # Meno versato del previsto
        severita = 'CRITICA' if differenza > 100 else 'ALTA'
        messaggio = f"⚠️ DISCREPANZA CONTANTE: {impianto_nome} - Versato €{versato_effettivo:.2f}, atteso €{contante_atteso:.2f} (mancano €{differenza:.2f})"
    else:
        # Versato più del previsto (meno grave ma strano)
        severita = 'MEDIA'
        messaggio = f"ℹ️ ECCEDENZA CONTANTE: {impianto_nome} - Versato €{versato_effettivo:.2f}, atteso €{contante_atteso:.2f} (extra €{abs(differenza):.2f})"
    
    return AlertSicurezza(
        impianto_id=impianto_id,
        impianto_nome=impianto_nome,
        tipo=TipoAlert.DISCREPANZA_CONTANTE,
        timestamp=datetime.now(),
        messaggio=messaggio,
        severita=severita,
        dettagli={
            'atteso': contante_atteso,
            'versato': versato_effettivo,
            'differenza': differenza
        }
    )


def controlla_aperture_multiple(
    eventi_apertura: List[Dict],
    finestra_ore: int = 24,
    soglia_aperture: int = 2
) -> List[AlertSicurezza]:
    """
    Rileva aperture multiple sospette in una finestra temporale.
    
    Args:
        eventi_apertura: Lista eventi con timestamp
        finestra_ore: Finestra temporale in ore
        soglia_aperture: Numero aperture per alert
    
    Returns:
        Lista di AlertSicurezza per pattern sospetti
    """
    alerts = []
    
    # Ordina per timestamp
    eventi_ordinati = sorted(eventi_apertura, key=lambda x: x.get('timestamp', ''))
    
    for i, evento in enumerate(eventi_ordinati):
        ts_str = evento.get('timestamp')
        if not ts_str:
            continue
            
        try:
            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        except ValueError:
            continue
        
        # Conta aperture nella finestra
        aperture_in_finestra = 1
        fine_finestra = ts + timedelta(hours=finestra_ore)
        
        for j in range(i + 1, len(eventi_ordinati)):
            ts_j_str = eventi_ordinati[j].get('timestamp')
            if ts_j_str:
                try:
                    ts_j = datetime.fromisoformat(ts_j_str.replace('Z', '+00:00'))
                    if ts_j <= fine_finestra:
                        aperture_in_finestra += 1
                except ValueError:
                    pass
        
        if aperture_in_finestra > soglia_aperture:
            alerts.append(AlertSicurezza(
                impianto_id=evento.get('impianto_id', 0),
                impianto_nome=evento.get('impianto_nome', 'Sconosciuto'),
                tipo=TipoAlert.APERTURA_MULTIPLA,
                timestamp=ts,
                messaggio=f"⚠️ APERTURE MULTIPLE: {aperture_in_finestra} aperture in {finestra_ore}h",
                severita='ALTA',
                dettagli={'aperture_count': aperture_in_finestra, 'finestra_ore': finestra_ore}
            ))
            break  # Evita duplicati
    
    return alerts


# ============================================================================
# MONITORAGGIO DATABASE
# ============================================================================

def monitora_sicurezza_db(db_path: str) -> List[AlertSicurezza]:
    """
    Esegue controllo sicurezza su tutti gli impianti self-service.
    
    Args:
        db_path: Path al database SQLite
    
    Returns:
        Lista di tutti gli alert attivi
    """
    alerts = []
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Trova impianti self-service
    cur.execute("""
        SELECT id, nome_impianto, giorno_ritiro_cassa
        FROM impianti
        WHERE tipo_gestione = 'SELF_SERVICE' AND attivo = 1
    """)
    impianti_self = [dict(row) for row in cur.fetchall()]
    
    for impianto in impianti_self:
        imp_id = impianto['id']
        imp_nome = impianto['nome_impianto']
        giorno_ritiro = impianto.get('giorno_ritiro_cassa', 'giovedi')
        
        # Controlla ultime aperture
        cur.execute("""
            SELECT timestamp_apertura, giorno_settimana, apertura_autorizzata
            FROM eventi_sicurezza_casse
            WHERE impianto_id = ?
            ORDER BY timestamp_apertura DESC
            LIMIT 10
        """, (imp_id,))
        
        eventi = [dict(row) for row in cur.fetchall()]
        
        for evento in eventi:
            ts_str = evento.get('timestamp_apertura')
            if not ts_str:
                continue
                
            try:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            except ValueError:
                continue
            
            # Controlla autorizzazione
            alert = controlla_apertura_cassa(ts, giorno_ritiro, imp_id, imp_nome)
            if alert:
                alerts.append(alert)
    
    conn.close()
    return alerts


# ============================================================================
# INVIO NOTIFICHE
# ============================================================================

def genera_email_alert(alert: AlertSicurezza) -> Dict:
    """
    Genera contenuto email per un alert.
    
    Returns:
        Dict con subject, body_html, body_text
    """
    emoji_severita = {
        'CRITICA': '🔴',
        'ALTA': '🟠',
        'MEDIA': '🟡'
    }
    
    emoji = emoji_severita.get(alert.severita, '⚪')
    
    subject = f"{emoji} {alert.tipo.value} - {alert.impianto_nome}"
    
    body_text = f"""
ALERT SICUREZZA CALOR SYSTEMS
{'=' * 40}

Impianto: {alert.impianto_nome}
Tipo: {alert.tipo.value}
Severità: {alert.severita}
Timestamp: {alert.timestamp.strftime('%d/%m/%Y %H:%M')}

{alert.messaggio}

Dettagli: {alert.dettagli}

---
Questo messaggio è stato generato automaticamente dal sistema Calor Smart Recon.
"""

    body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; padding: 20px;">
    <div style="background: {'#f44336' if alert.severita == 'CRITICA' else '#ff9800' if alert.severita == 'ALTA' else '#ffc107'}; 
                color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
        <h2 style="margin: 0;">{emoji} {alert.tipo.value}</h2>
        <p style="margin: 5px 0 0 0;">Impianto: <strong>{alert.impianto_nome}</strong></p>
    </div>
    
    <p style="font-size: 16px; color: #333;">{alert.messaggio}</p>
    
    <table style="background: #f5f5f5; padding: 10px; border-radius: 4px; width: 100%;">
        <tr><td><strong>Timestamp:</strong></td><td>{alert.timestamp.strftime('%d/%m/%Y %H:%M')}</td></tr>
        <tr><td><strong>Severità:</strong></td><td>{alert.severita}</td></tr>
    </table>
    
    <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">
    <p style="color: #999; font-size: 12px;">Calor Smart Recon - Sistema Automatico</p>
</body>
</html>
"""

    return {
        'subject': subject,
        'body_html': body_html,
        'body_text': body_text,
        'priority': 'high' if alert.severita == 'CRITICA' else 'normal'
    }
