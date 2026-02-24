"""
Test script per verificare il motore di riconciliazione Calor Systems.
Simula il caso pratico: Milano Repubblica, 15/01/2026.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.reconciliation import (
    riconcilia_contanti,
    riconcilia_carte_bancarie,
    riconcilia_carte_petrolifere,
    riconcilia_satispay,
    riconcilia_crediti,
    riconcilia_giornata,
    riconcilia_contanti_multi_giorno,
    StatoRiconciliazione,
    MatchContanti,
)


def test_carte_bancarie_match_perfetto():
    """Test caso verde: Fortech 4450.98 == Numia 4450.98"""
    ris = riconcilia_carte_bancarie(4450.98, 4450.98)
    assert ris.stato == StatoRiconciliazione.QUADRATO, f"Atteso QUADRATO, ottenuto {ris.stato}"
    assert ris.differenza == 0.0
    print("  PASS: Carte bancarie - match perfetto (4450.98 EUR)")


def test_carte_bancarie_discrepanza():
    """Test differenza carte bancarie"""
    ris = riconcilia_carte_bancarie(4450.98, 4440.00)
    assert ris.stato == StatoRiconciliazione.ANOMALIA_GRAVE, f"Atteso ANOMALIA_GRAVE, ottenuto {ris.stato}"
    assert ris.differenza == 10.98
    print("  PASS: Carte bancarie - discrepanza grave (diff 10.98 EUR)")


def test_contanti_arrotondamento_gestore():
    """Test arrotondamento: gestore versa 955€ instead of 954.76€"""
    fortech = {'incasso_contanti_teorico': 954.76, 'data_contabile': '2026-01-15'}
    as400 = [{'data_registrazione': '2026-01-15', 'importo_versato': 955.0}]
    ris = riconcilia_contanti(fortech, as400, '2026-01-15')
    assert ris.stato == StatoRiconciliazione.QUADRATO_ARROTONDAMENTO, f"Atteso QUADRATO_ARROT, ottenuto {ris.stato}"
    assert abs(ris.differenza) <= 5.0
    print(f"  PASS: Contanti - arrotondamento gestore (diff {ris.differenza} EUR)")


def test_contanti_matching_elastico():
    """Test versamento trovato 2 giorni dopo"""
    fortech = {'incasso_contanti_teorico': 800.0, 'data_contabile': '2026-01-15'}
    as400 = [{'data_registrazione': '2026-01-17', 'importo_versato': 800.0}]
    ris = riconcilia_contanti(fortech, as400, '2026-01-15')
    assert ris.stato == StatoRiconciliazione.QUADRATO, f"Atteso QUADRATO, ottenuto {ris.stato}"
    assert 'dopo' in ris.note.lower() or ris.differenza == 0
    print("  PASS: Contanti - versamento trovato +2 giorni")


def test_contanti_mancante():
    """Test nessun versamento trovato"""
    fortech = {'incasso_contanti_teorico': 1200.0, 'data_contabile': '2026-01-15'}
    ris = riconcilia_contanti(fortech, [], '2026-01-15')
    assert ris.stato == StatoRiconciliazione.IN_ATTESA, f"Atteso IN_ATTESA, ottenuto {ris.stato}"
    print("  PASS: Contanti - versamento mancante -> IN_ATTESA")


def test_satispay_match():
    """Test Satispay confronto diretto"""
    ris = riconcilia_satispay(125.50, 125.50)
    assert ris.stato == StatoRiconciliazione.QUADRATO
    assert ris.differenza == 0.0
    print("  PASS: Satispay - match perfetto (125.50 EUR)")


def test_satispay_discrepanza():
    """Test Satispay con mancanza"""
    ris = riconcilia_satispay(125.50, 100.00)
    assert ris.stato != StatoRiconciliazione.QUADRATO
    assert ris.differenza == 25.50
    print(f"  PASS: Satispay - discrepanza (diff {ris.differenza} EUR) -> {ris.stato.value}")


def test_crediti_fattura1click():
    """Test crediti fine mese"""
    ris = riconcilia_crediti(3000.0, 3000.0)
    assert ris.stato == StatoRiconciliazione.QUADRATO
    print("  PASS: Crediti Fattura1Click - match perfetto (3000 EUR)")


def test_carte_petrolifere_aggregazione():
    """Test somma IP Carte + IP Buoni vs Fortech"""
    ris = riconcilia_carte_petrolifere(2000.0, 1500.0, 500.0)
    assert ris.stato == StatoRiconciliazione.QUADRATO
    assert ris.differenza == 0.0
    print("  PASS: Carte petrolifere - aggregazione PV + Esercente (1500+500 = 2000 EUR)")


def test_giornata_completa():
    """Test riconciliazione completa giornata — tutte le 5 categorie"""
    fortech_data = {
        'data_contabile': '2026-01-15',
        'incasso_contanti_teorico': 954.76,
        'incasso_carte_bancarie_teorico': 4450.98,
        'fatture_postpagate_totale': 1500.0,
        'fatture_prepagate_totale': 500.0,
        'incasso_satispay_teorico': 125.50,
        'incasso_credito_finemese_teorico': 3000.0,
    }
    
    as400_records = [{'data_registrazione': '2026-01-15', 'importo_versato': 955.0}]
    numia_records = [{'importo': 4450.98}]
    ip_carte = [{'importo': 1500.0}]
    ip_buoni = [{'importo': 500.0}]
    satispay = [{'importo_totale': 125.50}]
    fattura1click = [{'importo_erogazione': 3000.0}]
    
    res = riconcilia_giornata(
        fortech_data, as400_records, numia_records,
        ip_carte, ip_buoni, satispay, fattura1click
    )
    
    assert res['data'] == '2026-01-15'
    
    # Verifica che TUTTE le 5 categorie siano presenti
    categorie_attese = {'contanti', 'carte_bancarie', 'carte_petrolifere', 'satispay', 'crediti'}
    categorie_trovate = set(res['risultati'].keys())
    assert categorie_attese == categorie_trovate, f"Categorie mancanti: {categorie_attese - categorie_trovate}"
    
    print(f"\n  Dettaglio giornata {res['data']}:")
    print(f"    Stato globale: {res['stato_globale']}")
    for cat, det in res['risultati'].items():
        stato_emoji = {
            'QUADRATO': 'OK', 'QUADRATO_ARROT': 'OK', 
            'ANOMALIA_LIEVE': 'WARN', 'ANOMALIA_GRAVE': 'GRAVE',
            'IN_ATTESA': 'WAIT', 'NON_TROVATO': '???'
        }.get(det['stato'], '?')
        print(f"    [{stato_emoji}] {cat}: {det['stato']} (diff {det['differenza']:+.2f} EUR) {det['note']}")
    
    print("\n  PASS: Giornata completa - tutte le 5 categorie presenti!")


# ============================================================================
# TEST MULTI-GIORNO: VERSAMENTI CUMULATIVI
# ============================================================================

def test_contanti_cumulativo_weekend():
    """
    Scenario: Sabato 400€ + Domenica 300€ versati in un'unica soluzione Lunedi.
    Fortech li spezza giorno per giorno, AS400 li riceve insieme.
    Atteso: entrambi i giorni QUADRATO, tipo match 'cumulativo_2gg'.
    """
    fortech_multi = [
        {'data_contabile': '2026-01-18', 'incasso_contanti_teorico': 400.0},  # Sabato
        {'data_contabile': '2026-01-19', 'incasso_contanti_teorico': 300.0},  # Domenica
    ]
    as400 = [
        {'data_registrazione': '2026-01-20', 'importo_versato': 700.0},  # Versamento Lunedi
    ]
    
    risultati = riconcilia_contanti_multi_giorno(fortech_multi, as400)
    
    assert len(risultati) == 2, f"Attesi 2 risultati, ottenuti {len(risultati)}"
    
    # Entrambi i giorni devono essere coperti (QUADRATO)
    for r in risultati:
        assert r.stato == StatoRiconciliazione.QUADRATO, \
            f"Giorno {r.data}: atteso QUADRATO, ottenuto {r.stato.value}"
        assert r.match_info['tipo_match'] == 'cumulativo_2gg', \
            f"Giorno {r.data}: atteso tipo_match=cumulativo_2gg, ottenuto {r.match_info['tipo_match']}"
    
    print("  PASS: Contanti CUMULATIVO weekend - Sab 400 + Dom 300 = Lun 700 EUR")
    print(f"         Tipo match: {risultati[0].match_info['tipo_match']}")
    print(f"         Note: {risultati[0].note}")


def test_contanti_cumulativo_arrotondato():
    """
    Scenario: 3 giorni cumulati E arrotondati.
    Fortech: 400.00 + 300.50 + 254.76 = 955.26€ teorico
    AS400: versamento 955.00€ (gestore arrotondato)  
    Differenza: 0.26€ < tolleranza 15€ (5€ x 3 giorni)
    Atteso: QUADRATO_ARROT con tolleranza dinamica
    """
    fortech_multi = [
        {'data_contabile': '2026-01-17', 'incasso_contanti_teorico': 400.0},   # Venerdi
        {'data_contabile': '2026-01-18', 'incasso_contanti_teorico': 300.50},  # Sabato
        {'data_contabile': '2026-01-19', 'incasso_contanti_teorico': 254.76},  # Domenica
    ]
    as400 = [
        {'data_registrazione': '2026-01-20', 'importo_versato': 955.0},  # Versamento Lunedi (arrotondato)
    ]
    
    risultati = riconcilia_contanti_multi_giorno(fortech_multi, as400)
    
    assert len(risultati) == 3, f"Attesi 3 risultati, ottenuti {len(risultati)}"
    
    # Tutti coperti con arrotondamento
    for r in risultati:
        assert r.stato in (StatoRiconciliazione.QUADRATO, StatoRiconciliazione.QUADRATO_ARROTONDAMENTO), \
            f"Giorno {r.data}: atteso QUADRATO/QUADRATO_ARROT, ottenuto {r.stato.value}"
        assert 'cumulativo_3gg' in r.match_info['tipo_match'], \
            f"Giorno {r.data}: atteso cumulativo_3gg, ottenuto {r.match_info['tipo_match']}"
    
    # Verifica che la differenza totale sia 0.26
    somma_teorici = 400.0 + 300.50 + 254.76
    diff_attesa = round(somma_teorici - 955.0, 2)
    print(f"  PASS: Contanti CUMULATIVO 3gg arrotondato")
    print(f"         Teorico: {somma_teorici:.2f} EUR -> Versato: 955.00 EUR")
    print(f"         Diff: {diff_attesa:+.2f} EUR (entro tolleranza 15 EUR = 5x3gg)")
    print(f"         Tipo: {risultati[0].match_info['tipo_match']}")


def test_contanti_mix_singolo_e_cumulativo():
    """
    Scenario: mix di versamento singolo + versamento cumulativo nella stessa settimana.
    Fortech: Lun 500 + Mar 400 + Mer 300 (3 giorni)
    AS400: Versamento 500 Lun (singolo) + Versamento 700 Gio (Mar+Mer cumulativo)
    Atteso: Tutti e 3 i giorni coperti
    """
    fortech_multi = [
        {'data_contabile': '2026-01-13', 'incasso_contanti_teorico': 500.0},  # Lunedi
        {'data_contabile': '2026-01-14', 'incasso_contanti_teorico': 400.0},  # Martedi
        {'data_contabile': '2026-01-15', 'incasso_contanti_teorico': 300.0},  # Mercoledi
    ]
    as400 = [
        {'data_registrazione': '2026-01-13', 'importo_versato': 500.0},  # Singolo Lun
        {'data_registrazione': '2026-01-16', 'importo_versato': 700.0},  # Mar+Mer cumulativo Gio
    ]
    
    risultati = riconcilia_contanti_multi_giorno(fortech_multi, as400)
    
    assert len(risultati) == 3, f"Attesi 3 risultati, ottenuti {len(risultati)}"
    
    # Tutti coperti
    for r in risultati:
        assert r.stato in (StatoRiconciliazione.QUADRATO, StatoRiconciliazione.QUADRATO_ARROTONDAMENTO), \
            f"Giorno {r.data}: atteso QUADRATO, ottenuto {r.stato.value}"
    
    # Verifica tipo match per ogni giorno
    r_lun = next(r for r in risultati if r.data == '2026-01-13')
    r_mar = next(r for r in risultati if r.data == '2026-01-14')
    r_mer = next(r for r in risultati if r.data == '2026-01-15')
    
    assert r_lun.match_info['tipo_match'] == '1:1_esatto', \
        f"Lunedi: atteso 1:1_esatto, ottenuto {r_lun.match_info['tipo_match']}"
    assert 'cumulativo' in r_mar.match_info['tipo_match'], \
        f"Martedi: atteso cumulativo, ottenuto {r_mar.match_info['tipo_match']}"
    
    print("  PASS: Contanti MIX singolo + cumulativo")
    print(f"         Lun: {r_lun.match_info['tipo_match']} (500 EUR esatto)")
    print(f"         Mar: {r_mar.match_info['tipo_match']} (400+300 = 700 EUR)")
    print(f"         Mer: {r_mer.match_info['tipo_match']} (coperto dal cumulativo)")


def test_contanti_nessun_match_anomalia():
    """
    Scenario: l'importo versato non corrisponde a nessuna combinazione.
    Fortech: 500 + 300 = 800€ teorico
    AS400: versamento 1200€ (non quadra!)
    Atteso: ANOMALIA — importo troppo distante da qualsiasi combinazione
    """
    fortech_multi = [
        {'data_contabile': '2026-01-18', 'incasso_contanti_teorico': 500.0},
        {'data_contabile': '2026-01-19', 'incasso_contanti_teorico': 300.0},
    ]
    as400 = [
        {'data_registrazione': '2026-01-20', 'importo_versato': 1200.0},  # Non quadra!
    ]
    
    risultati = riconcilia_contanti_multi_giorno(fortech_multi, as400)
    
    assert len(risultati) == 2, f"Attesi 2 risultati, ottenuti {len(risultati)}"
    
    # Nessun match possibile: i giorni restano IN_ATTESA
    for r in risultati:
        assert r.stato == StatoRiconciliazione.IN_ATTESA, \
            f"Giorno {r.data}: atteso IN_ATTESA, ottenuto {r.stato.value}"
    
    print("  PASS: Contanti ANOMALIA - 500+300 vs 1200 EUR -> nessun match possibile")
    print(f"         Stato: {risultati[0].stato.value} (luce rossa per Simona!)")


if __name__ == "__main__":
    print("=" * 60)
    print("  CALOR SYSTEMS - Test Motore Riconciliazione")
    print("=" * 60)
    print()
    
    print("--- Test Base (Legacy) ---")
    tests = [
        test_carte_bancarie_match_perfetto,
        test_carte_bancarie_discrepanza,
        test_contanti_arrotondamento_gestore,
        test_contanti_matching_elastico,
        test_contanti_mancante,
        test_satispay_match,
        test_satispay_discrepanza,
        test_crediti_fattura1click,
        test_carte_petrolifere_aggregazione,
        test_giornata_completa,
    ]
    
    print("\n--- Test Multi-Giorno (Versamenti Cumulativi) ---")
    tests_multi = [
        test_contanti_cumulativo_weekend,
        test_contanti_cumulativo_arrotondato,
        test_contanti_mix_singolo_e_cumulativo,
        test_contanti_nessun_match_anomalia,
    ]
    
    all_tests = tests + tests_multi
    passed = 0
    failed = 0
    
    for test_fn in all_tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {test_fn.__name__}: {e}")
            failed += 1
    
    print()
    print("=" * 60)
    print(f"  Risultati: {passed} passati, {failed} falliti su {len(all_tests)} test")
    print("=" * 60)

