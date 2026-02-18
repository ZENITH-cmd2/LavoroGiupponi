import sqlite3

conn = sqlite3.connect('calor_systems.db')
cur = conn.cursor()

print('='*60)
print('VERIFICA TABELLA NUMIA (Carte Bancarie):')
print('='*60)

cur.execute("SELECT COUNT(*) FROM verifica_numia")
count = cur.fetchone()[0]
print(f'  Righe totali in verifica_numia: {count}')

if count > 0:
    cur.execute("SELECT * FROM verifica_numia LIMIT 3")
    rows = cur.fetchall()
    print('  Sample dati:')
    for row in rows:
        print(f'    {row}')
else:
    print('  ⚠️  NESSUN DATO CARTE BANCARIE IMPORTATO!')
    print('  ℹ️  Per importare: caricare file Numia tramite dashboard')

print()
print('='*60)
print('VERIFICA DATI FORTECH (Teorico Carte):')
print('='*60)

cur.execute("""
    SELECT 
        data_contabile,
        corrispettivo_totale,
        (COALESCE(fatture_postpagate_totale, 0) + COALESCE(fatture_prepagate_totale, 0)) as carte_petro,
        COALESCE(buoni_totale, 0) as buoni,
        COALESCE(incasso_carte_bancarie_teorico, 0) as carte_bancarie_teorico
    FROM import_fortech_master 
    LIMIT 5
""")
print('  Colonne: data_contabile, corrispett_totale, carte_petro, buoni, carte_bancarie_teorico')
for row in cur.fetchall():
    print(f'    {row}')

print()
print('='*60)
print('PROBLEMA IDENTIFICATO:')
print('='*60)
print('  Le carte bancarie mostrano 0 perché:')
print('  1. La tabella verifica_numia è vuota (nessun file Numia importato)')
print('  2. Quindi numia_totale = 0 sempre')
print('  3. diff_numia = teorico - 0 = sempre rosso/mancante')

conn.close()
