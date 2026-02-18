import sqlite3

conn = sqlite3.connect('calor_systems.db')
cur = conn.cursor()

print('='*60)
print('TABELLE CREATE:')
print('='*60)
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cur.fetchall()
for row in tables:
    cur.execute(f'SELECT COUNT(*) FROM {row[0]}')
    count = cur.fetchone()[0]
    print(f'  {row[0]}: {count} record')

print()
print('='*60)
print('VISTE CREATE:')
print('='*60)
cur.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")
for row in cur.fetchall():
    print(f'  {row[0]}')

print()
print('='*60)
print('IMPIANTI REGISTRATI:')
print('='*60)
cur.execute('SELECT id, nome_impianto, codice_pv_fortech FROM impianti')
for row in cur.fetchall():
    print(f'  ID {row[0]}: {row[1]} (PV: {row[2]})')

print()
print('='*60)
print('ESEMPIO DATI FORTECH:')
print('='*60)
cur.execute('SELECT data_contabile, corrispettivo_totale, fatture_postpagate_totale, buoni_totale FROM import_fortech_master LIMIT 5')
for row in cur.fetchall():
    print(f'  {row[0]}: Totale={row[1]}, Postpagate={row[2]}, Buoni={row[3]}')

print()
print('='*60)
print('DETTAGLIO IP PORTAL:')
print('='*60)
cur.execute('SELECT tipo_transazione, COUNT(*) FROM verifica_ip_portal GROUP BY tipo_transazione')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]} record')

conn.close()
