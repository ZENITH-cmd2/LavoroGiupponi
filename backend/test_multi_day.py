"""Quick inline test for multi-day matching"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.reconciliation import (
    riconcilia_contanti_multi_giorno,
    riconcilia_contanti,
    riconcilia_carte_bancarie,
    StatoRiconciliazione,
)

errors = 0

# ---- Legacy tests ----
print("=== LEGACY TESTS ===")

r = riconcilia_carte_bancarie(4450.98, 4450.98)
ok = r.stato == StatoRiconciliazione.QUADRATO
print(f"  {'PASS' if ok else 'FAIL'}: Carte bancarie match")
if not ok: errors += 1

f = {'incasso_contanti_teorico': 954.76, 'data_contabile': '2026-01-15'}
a = [{'data_registrazione': '2026-01-15', 'importo_versato': 955.0}]
r = riconcilia_contanti(f, a, '2026-01-15')
ok = r.stato == StatoRiconciliazione.QUADRATO_ARROTONDAMENTO
print(f"  {'PASS' if ok else 'FAIL'}: Contanti arrotondamento (stato={r.stato.value})")
if not ok: errors += 1

f = {'incasso_contanti_teorico': 800.0, 'data_contabile': '2026-01-15'}
a = [{'data_registrazione': '2026-01-17', 'importo_versato': 800.0}]
r = riconcilia_contanti(f, a, '2026-01-15')
ok = r.stato == StatoRiconciliazione.QUADRATO
print(f"  {'PASS' if ok else 'FAIL'}: Contanti elastico +2gg (stato={r.stato.value})")
if not ok: errors += 1

# ---- Multi-day tests ----
print("\n=== MULTI-DAY TESTS ===")

# Test 1: Cumulative weekend
ft = [
    {'data_contabile': '2026-01-18', 'incasso_contanti_teorico': 400.0},
    {'data_contabile': '2026-01-19', 'incasso_contanti_teorico': 300.0},
]
a400 = [{'data_registrazione': '2026-01-20', 'importo_versato': 700.0}]
res = riconcilia_contanti_multi_giorno(ft, a400)
ok = len(res) == 2 and all(r.stato == StatoRiconciliazione.QUADRATO for r in res)
tm = res[0].match_info['tipo_match'] if res else 'N/A'
print(f"  {'PASS' if ok else 'FAIL'}: Weekend cumulativo Sab400+Dom300=Lun700 (tipo={tm})")
if not ok:
    errors += 1
    for r in res:
        print(f"    DEBUG: {r.data} stato={r.stato.value} match={r.match_info}")

# Test 2: Cumulative + rounding (3 days)
ft = [
    {'data_contabile': '2026-01-17', 'incasso_contanti_teorico': 400.0},
    {'data_contabile': '2026-01-18', 'incasso_contanti_teorico': 300.50},
    {'data_contabile': '2026-01-19', 'incasso_contanti_teorico': 254.76},
]
a400 = [{'data_registrazione': '2026-01-20', 'importo_versato': 955.0}]
res = riconcilia_contanti_multi_giorno(ft, a400)
ok = len(res) == 3 and all(
    r.stato in (StatoRiconciliazione.QUADRATO, StatoRiconciliazione.QUADRATO_ARROTONDAMENTO) 
    for r in res
)
tm = res[0].match_info['tipo_match'] if res else 'N/A'
diff = round(400.0 + 300.50 + 254.76 - 955.0, 2)
print(f"  {'PASS' if ok else 'FAIL'}: Cumulativo 3gg arrotondato (diff={diff}, tipo={tm})")
if not ok:
    errors += 1
    for r in res:
        print(f"    DEBUG: {r.data} stato={r.stato.value} match={r.match_info}")

# Test 3: Mix single + cumulative
ft = [
    {'data_contabile': '2026-01-13', 'incasso_contanti_teorico': 500.0},
    {'data_contabile': '2026-01-14', 'incasso_contanti_teorico': 400.0},
    {'data_contabile': '2026-01-15', 'incasso_contanti_teorico': 300.0},
]
a400 = [
    {'data_registrazione': '2026-01-13', 'importo_versato': 500.0},
    {'data_registrazione': '2026-01-16', 'importo_versato': 700.0},
]
res = riconcilia_contanti_multi_giorno(ft, a400)
ok = len(res) == 3 and all(
    r.stato in (StatoRiconciliazione.QUADRATO, StatoRiconciliazione.QUADRATO_ARROTONDAMENTO) 
    for r in res
)
types = [r.match_info['tipo_match'] for r in res]
print(f"  {'PASS' if ok else 'FAIL'}: Mix singolo+cumulativo (tipi={types})")
if not ok:
    errors += 1
    for r in res:
        print(f"    DEBUG: {r.data} stato={r.stato.value} match={r.match_info}")

# Test 4: No match (anomaly)
ft = [
    {'data_contabile': '2026-01-18', 'incasso_contanti_teorico': 500.0},
    {'data_contabile': '2026-01-19', 'incasso_contanti_teorico': 300.0},
]
a400 = [{'data_registrazione': '2026-01-20', 'importo_versato': 1200.0}]
res = riconcilia_contanti_multi_giorno(ft, a400)
ok = len(res) == 2 and all(r.stato == StatoRiconciliazione.IN_ATTESA for r in res)
print(f"  {'PASS' if ok else 'FAIL'}: Nessun match possibile -> IN_ATTESA")
if not ok:
    errors += 1
    for r in res:
        print(f"    DEBUG: {r.data} stato={r.stato.value} match={r.match_info}")

print(f"\n=== RESULT: {'ALL PASSED' if errors == 0 else f'{errors} FAILED'} ===")
