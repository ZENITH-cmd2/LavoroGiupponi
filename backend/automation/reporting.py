"""
CALOR SYSTEMS - Modulo Reporting
Generazione report anomalie e analisi per management by exception
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import json


@dataclass
class ReportAnomalie:
    """Report giornaliero anomalie"""
    data_generazione: datetime
    periodo_da: str
    periodo_a: str
    totale_giornate: int
    giornate_quadrate: int
    giornate_anomalia: int
    tasso_anomalie: float
    anomalie: List[Dict]
    riepilogo_per_categoria: Dict
    riepilogo_per_impianto: Dict


def genera_report_anomalie(
    riconciliazioni: List[Dict],
    periodo_da: str = None,
    periodo_a: str = None
) -> ReportAnomalie:
    """
    Genera report anomalie per il periodo specificato.
    
    Args:
        riconciliazioni: Lista risultati riconciliazione
        periodo_da: Data inizio (YYYY-MM-DD)
        periodo_a: Data fine (YYYY-MM-DD)
    
    Returns:
        ReportAnomalie con statistiche e dettagli
    """
    # Filtra per periodo se specificato
    if periodo_da:
        riconciliazioni = [r for r in riconciliazioni if r.get('data', '') >= periodo_da]
    if periodo_a:
        riconciliazioni = [r for r in riconciliazioni if r.get('data', '') <= periodo_a]
    
    totale = len(riconciliazioni)
    quadrate = sum(1 for r in riconciliazioni if r.get('stato_globale') == 'QUADRATO')
    anomalie = totale - quadrate
    
    # Estrai solo anomalie
    lista_anomalie = []
    riepilogo_categoria = {}
    riepilogo_impianto = {}
    
    for ric in riconciliazioni:
        if ric.get('stato_globale') in ('ANOMALIA_LIEVE', 'ANOMALIA_GRAVE', 'ANOMALIA'):
            anomalia_entry = {
                'data': ric.get('data'),
                'impianto_id': ric.get('impianto_id'),
                'impianto_nome': ric.get('impianto_nome', ''),
                'stato': ric.get('stato_globale'),
                'dettagli': []
            }
            
            for cat, risultato in ric.get('risultati', {}).items():
                if risultato.get('stato') in ('ANOMALIA_LIEVE', 'ANOMALIA_GRAVE', 'MANCANTE'):
                    anomalia_entry['dettagli'].append({
                        'categoria': cat,
                        'teorico': risultato.get('teorico'),
                        'reale': risultato.get('reale'),
                        'differenza': risultato.get('differenza'),
                        'note': risultato.get('note', '')
                    })
                    
                    # Riepilogo per categoria
                    if cat not in riepilogo_categoria:
                        riepilogo_categoria[cat] = {'count': 0, 'totale_diff': 0}
                    riepilogo_categoria[cat]['count'] += 1
                    riepilogo_categoria[cat]['totale_diff'] += abs(risultato.get('differenza', 0))
            
            if anomalia_entry['dettagli']:
                lista_anomalie.append(anomalia_entry)
                
                # Riepilogo per impianto
                imp_id = ric.get('impianto_id')
                if imp_id not in riepilogo_impianto:
                    riepilogo_impianto[imp_id] = {
                        'nome': ric.get('impianto_nome', ''),
                        'anomalie': 0,
                        'totale_diff': 0
                    }
                riepilogo_impianto[imp_id]['anomalie'] += 1
                riepilogo_impianto[imp_id]['totale_diff'] += sum(
                    abs(d.get('differenza', 0)) for d in anomalia_entry['dettagli']
                )
    
    return ReportAnomalie(
        data_generazione=datetime.now(),
        periodo_da=periodo_da or (riconciliazioni[0].get('data') if riconciliazioni else ''),
        periodo_a=periodo_a or (riconciliazioni[-1].get('data') if riconciliazioni else ''),
        totale_giornate=totale,
        giornate_quadrate=quadrate,
        giornate_anomalia=anomalie,
        tasso_anomalie=round(anomalie / totale * 100, 1) if totale > 0 else 0,
        anomalie=lista_anomalie,
        riepilogo_per_categoria=riepilogo_categoria,
        riepilogo_per_impianto=riepilogo_impianto
    )


def genera_html_report(report: ReportAnomalie) -> str:
    """
    Genera report HTML per visualizzazione/stampa.
    """
    # Colori per categoria
    colori = {
        'contanti': '#FFC107',
        'carte_bancarie': '#4CAF50',
        'carte_petrolifere': '#2196F3',
        'buoni': '#F44336',
        'satispay': '#9E9E9E'
    }
    
    html = f"""
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Report Anomalie - Calor Systems</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f7fa; padding: 20px; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .header {{ background: #1e2a38; color: white; padding: 30px; border-radius: 12px 12px 0 0; }}
        .header h1 {{ font-size: 24px; margin-bottom: 10px; }}
        .header .meta {{ opacity: 0.8; font-size: 14px; }}
        .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; padding: 20px; background: white; }}
        .stat {{ text-align: center; padding: 15px; border-radius: 8px; background: #f5f7fa; }}
        .stat-value {{ font-size: 32px; font-weight: 700; color: #1e2a38; }}
        .stat-label {{ font-size: 12px; color: #607d8b; text-transform: uppercase; }}
        .stat.alert .stat-value {{ color: #f44336; }}
        .section {{ background: white; padding: 20px; margin-top: 20px; border-radius: 8px; }}
        .section h2 {{ font-size: 18px; color: #1e2a38; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #e0e6ed; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e0e6ed; }}
        th {{ background: #f5f7fa; font-weight: 600; font-size: 12px; text-transform: uppercase; color: #607d8b; }}
        .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
        .badge-grave {{ background: #ffebee; color: #c62828; }}
        .badge-lieve {{ background: #fff3e0; color: #ef6c00; }}
        .diff {{ font-family: monospace; }}
        .diff.positive {{ color: #c62828; }}
        .diff.negative {{ color: #2e7d32; }}
        .cat-badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; margin-right: 4px; }}
        .footer {{ text-align: center; padding: 20px; color: #9e9e9e; font-size: 12px; }}
        @media print {{
            body {{ background: white; padding: 0; }}
            .header {{ border-radius: 0; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Report Anomalie Riconciliazione</h1>
            <div class="meta">
                Periodo: {report.periodo_da} → {report.periodo_a} | 
                Generato: {report.data_generazione.strftime('%d/%m/%Y %H:%M')}
            </div>
        </div>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{report.totale_giornate}</div>
                <div class="stat-label">Giornate Analizzate</div>
            </div>
            <div class="stat">
                <div class="stat-value">{report.giornate_quadrate}</div>
                <div class="stat-label">Quadrate ✓</div>
            </div>
            <div class="stat alert">
                <div class="stat-value">{report.giornate_anomalia}</div>
                <div class="stat-label">Con Anomalie</div>
            </div>
            <div class="stat">
                <div class="stat-value">{report.tasso_anomalie}%</div>
                <div class="stat-label">Tasso Anomalie</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📋 Riepilogo per Categoria</h2>
            <table>
                <thead>
                    <tr>
                        <th>Categoria</th>
                        <th>Anomalie</th>
                        <th>Totale Differenze</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    for cat, info in sorted(report.riepilogo_per_categoria.items(), key=lambda x: x[1]['count'], reverse=True):
        colore = colori.get(cat, '#9e9e9e')
        html += f"""
                    <tr>
                        <td><span class="cat-badge" style="background: {colore}20; color: {colore};">{cat.upper()}</span></td>
                        <td>{info['count']}</td>
                        <td class="diff positive">€ {info['totale_diff']:.2f}</td>
                    </tr>
"""
    
    html += """
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>🏢 Riepilogo per Impianto</h2>
            <table>
                <thead>
                    <tr>
                        <th>Impianto</th>
                        <th>Anomalie</th>
                        <th>Totale Differenze</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    for imp_id, info in sorted(report.riepilogo_per_impianto.items(), key=lambda x: x[1]['anomalie'], reverse=True):
        html += f"""
                    <tr>
                        <td>{info['nome']}</td>
                        <td>{info['anomalie']}</td>
                        <td class="diff positive">€ {info['totale_diff']:.2f}</td>
                    </tr>
"""
    
    html += """
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>🔍 Dettaglio Anomalie</h2>
            <table>
                <thead>
                    <tr>
                        <th>Data</th>
                        <th>Impianto</th>
                        <th>Categoria</th>
                        <th>Teorico</th>
                        <th>Reale</th>
                        <th>Differenza</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    for anomalia in report.anomalie[:50]:  # Limita a 50
        for det in anomalia['dettagli']:
            colore = colori.get(det['categoria'], '#9e9e9e')
            diff = det.get('differenza', 0)
            diff_class = 'positive' if diff > 0 else 'negative'
            html += f"""
                    <tr>
                        <td>{anomalia['data']}</td>
                        <td>{anomalia['impianto_nome']}</td>
                        <td><span class="cat-badge" style="background: {colore}20; color: {colore};">{det['categoria'].upper()}</span></td>
                        <td class="diff">€ {det.get('teorico', 0):.2f}</td>
                        <td class="diff">€ {det.get('reale', 0):.2f}</td>
                        <td class="diff {diff_class}">€ {diff:+.2f}</td>
                    </tr>
"""
    
    html += f"""
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            Calor Smart Recon - Sistema Automatico di Riconciliazione
        </div>
    </div>
</body>
</html>
"""
    
    return html


def genera_json_report(report: ReportAnomalie) -> str:
    """Genera report in formato JSON per API"""
    return json.dumps({
        'data_generazione': report.data_generazione.isoformat(),
        'periodo': {'da': report.periodo_da, 'a': report.periodo_a},
        'statistiche': {
            'totale_giornate': report.totale_giornate,
            'giornate_quadrate': report.giornate_quadrate,
            'giornate_anomalia': report.giornate_anomalia,
            'tasso_anomalie': report.tasso_anomalie
        },
        'riepilogo_categoria': report.riepilogo_per_categoria,
        'riepilogo_impianto': report.riepilogo_per_impianto,
        'anomalie': report.anomalie
    }, indent=2, default=str)


# ============================================================================
# REPORT TREND E PATTERN
# ============================================================================

def analizza_trend_settimanale(riconciliazioni: List[Dict]) -> Dict:
    """
    Analizza trend settimanale delle anomalie.
    """
    giorni_settimana = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
    trend = {g: {'totale': 0, 'anomalie': 0} for g in giorni_settimana}
    
    for ric in riconciliazioni:
        data_str = ric.get('data')
        if not data_str:
            continue
            
        try:
            data = datetime.strptime(data_str[:10], '%Y-%m-%d')
            giorno = giorni_settimana[data.weekday()]
            trend[giorno]['totale'] += 1
            if ric.get('stato_globale') != 'QUADRATO':
                trend[giorno]['anomalie'] += 1
        except ValueError:
            continue
    
    # Calcola percentuali
    for giorno, info in trend.items():
        if info['totale'] > 0:
            info['tasso'] = round(info['anomalie'] / info['totale'] * 100, 1)
        else:
            info['tasso'] = 0
    
    return trend


def identifica_impianti_critici(
    riconciliazioni: List[Dict],
    soglia_tasso: float = 30.0
) -> List[Dict]:
    """
    Identifica impianti con tasso anomalie sopra soglia.
    """
    per_impianto = {}
    
    for ric in riconciliazioni:
        imp_id = ric.get('impianto_id')
        if imp_id not in per_impianto:
            per_impianto[imp_id] = {
                'nome': ric.get('impianto_nome', ''),
                'totale': 0,
                'anomalie': 0,
                'diff_totale': 0
            }
        
        per_impianto[imp_id]['totale'] += 1
        if ric.get('stato_globale') != 'QUADRATO':
            per_impianto[imp_id]['anomalie'] += 1
            per_impianto[imp_id]['diff_totale'] += sum(
                abs(r.get('differenza', 0)) for r in ric.get('risultati', {}).values()
            )
    
    # Filtra per soglia
    critici = []
    for imp_id, info in per_impianto.items():
        if info['totale'] > 0:
            tasso = info['anomalie'] / info['totale'] * 100
            if tasso >= soglia_tasso:
                critici.append({
                    'impianto_id': imp_id,
                    'impianto_nome': info['nome'],
                    'tasso_anomalie': round(tasso, 1),
                    'totale_diff': round(info['diff_totale'], 2),
                    'giornate_controllate': info['totale']
                })
    
    return sorted(critici, key=lambda x: x['tasso_anomalie'], reverse=True)
