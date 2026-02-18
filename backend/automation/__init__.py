"""
CALOR SYSTEMS - Automation Package
"""

from .data_ingestion import (
    identifica_fonte,
    parse_excel_intelligente,
    processa_file_automatico
)

from .reconciliation import (
    StatoRiconciliazione,
    RisultatoRiconciliazione,
    riconcilia_contanti,
    riconcilia_carte_bancarie,
    riconcilia_carte_petrolifere,
    riconcilia_giornata,
    analizza_anomalie_ricorrenti
)

from .security_alerts import (
    TipoAlert,
    AlertSicurezza,
    controlla_apertura_cassa,
    calcola_contante_tra_aperture,
    monitora_sicurezza_db,
    genera_email_alert
)

from .reporting import (
    genera_report_anomalie,
    genera_html_report,
    genera_json_report,
    analizza_trend_settimanale,
    identifica_impianti_critici
)

__all__ = [
    # Data Ingestion
    'identifica_fonte',
    'parse_excel_intelligente',
    'processa_file_automatico',
    
    # Reconciliation
    'StatoRiconciliazione',
    'RisultatoRiconciliazione',
    'riconcilia_contanti',
    'riconcilia_carte_bancarie',
    'riconcilia_carte_petrolifere',
    'riconcilia_giornata',
    'analizza_anomalie_ricorrenti',
    
    # Security
    'TipoAlert',
    'AlertSicurezza',
    'controlla_apertura_cassa',
    'calcola_contante_tra_aperture',
    'monitora_sicurezza_db',
    'genera_email_alert',
    
    # Reporting
    'genera_report_anomalie',
    'genera_html_report',
    'genera_json_report',
    'analizza_trend_settimanale',
    'identifica_impianti_critici'
]
