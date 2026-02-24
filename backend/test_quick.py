"""Test semplice ASCII-only per Windows PowerShell"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.reconciliation import (
    riconcilia_carte_bancarie,
    riconcilia_satispay,
    riconcilia_crediti,
    riconcilia_contanti,
    riconcilia_carte_petrolifere,
    riconcilia_giornata,
    StatoRiconciliazione
)

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  PASS: {name} {detail}")
        passed += 1
    else:
        print(f"  FAIL: {name} {detail}")
        failed += 1

print("=== TEST RICONCILIAZIONE ===\n")

# Test 1: Carte bancarie match perfetto
r = riconcilia_carte_bancarie(4450.98, 4450.98)
check("Carte bancarie match", r.stato == StatoRiconciliazione.QUADRATO, f"stato={r.stato.value}")

# Test 2: Carte bancarie discrepanza
r = riconcilia_carte_bancarie(4450.98, 4440.00)
check("Carte bancarie diff", r.stato == StatoRiconciliazione.ANOMALIA_GRAVE, f"diff={r.differenza}")

# Test 3: Satispay match
r = riconcilia_satispay(125.50, 125.50)
check("Satispay match", r.stato == StatoRiconciliazione.QUADRATO, f"diff={r.differenza}")

# Test 4: Satispay discrepanza
r = riconcilia_satispay(125.50, 100.00)
check("Satispay diff", r.stato != StatoRiconciliazione.QUADRATO, f"diff={r.differenza}")

# Test 5: Crediti match
r = riconcilia_crediti(3000.0, 3000.0)
check("Crediti match", r.stato == StatoRiconciliazione.QUADRATO, f"diff={r.differenza}")

# Test 6: Contanti arrotondamento
f = {'incasso_contanti_teorico': 954.76, 'data_contabile': '2026-01-15'}
a = [{'data_registrazione': '2026-01-15', 'importo_versato': 955.0}]
r = riconcilia_contanti(f, a, '2026-01-15')
check("Contanti arrotond.", r.stato == StatoRiconciliazione.QUADRATO_ARROTONDAMENTO, f"diff={r.differenza}")

# Test 7: Contanti elastico +2gg
f = {'incasso_contanti_teorico': 800.0, 'data_contabile': '2026-01-15'}
a = [{'data_registrazione': '2026-01-17', 'importo_versato': 800.0}]
r = riconcilia_contanti(f, a, '2026-01-15')
check("Contanti +2gg", r.stato == StatoRiconciliazione.QUADRATO, f"diff={r.differenza}")

# Test 8: Contanti mancante
f = {'incasso_contanti_teorico': 1200.0, 'data_contabile': '2026-01-15'}
r = riconcilia_contanti(f, [], '2026-01-15')
check("Contanti mancante", r.stato == StatoRiconciliazione.IN_ATTESA, f"stato={r.stato.value}")

# Test 9: Carte petrolifere aggregazione
r = riconcilia_carte_petrolifere(2000.0, 1500.0, 500.0)
check("Petrol. aggregaz.", r.stato == StatoRiconciliazione.QUADRATO, f"diff={r.differenza}")

# Test 10: Giornata completa - 5 categorie
fortech = {
    'data_contabile': '2026-01-15',
    'incasso_contanti_teorico': 954.76,
    'incasso_carte_bancarie_teorico': 4450.98,
    'fatture_postpagate_totale': 1500.0,
    'fatture_prepagate_totale': 500.0,
    'incasso_satispay_teorico': 125.50,
    'incasso_credito_finemese_teorico': 3000.0,
}
res = riconcilia_giornata(
    fortech,
    [{'data_registrazione': '2026-01-15', 'importo_versato': 955.0}],
    [{'importo': 4450.98}],
    [{'importo': 1500.0}],
    [{'importo': 500.0}],
    [{'importo_totale': 125.50}],
    [{'importo_erogazione': 3000.0}]
)

categorie = sorted(res['risultati'].keys())
check("Giornata 5 cat.", categorie == ['carte_bancarie', 'carte_petrolifere', 'contanti', 'crediti', 'satispay'],
      f"categorie={categorie}")

print(f"\n  Dettaglio giornata {res['data']}:")
for k, v in res['risultati'].items():
    print(f"    {k}: {v['stato']} (diff={v['differenza']})")

print(f"\n=== RISULTATI: {passed}/{passed+failed} passati ===")
