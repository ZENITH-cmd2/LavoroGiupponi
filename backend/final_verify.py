import os, sys
sys.path.insert(0, '.')
from core.database import Database
from core.importer import DataImporter
from core.analyzer import Analyzer

db = Database(os.path.dirname(os.path.abspath('.')))
conn = db.get_connection()
for t in ['import_fortech_master', 'verifica_contanti_as400', 'verifica_numia', 'verifica_ip_portal', 'verifica_satispay', 'verifica_credito_clienti', 'report_riconciliazioni']:
    conn.execute(f'DELETE FROM {t}')
conn.commit()

files = [
    '../Dati_excel/A_FILE GENERALE DA FORTECH_MILANO REPUBBLICA.xlsx',
    '../Dati_excel/1_CONTROLLO CONTANTI DA AS400_GIALLO.xlsx',
    '../Dati_excel/2_CONTROLLO CARTE BANCARIE DA NUMIA_VERDE.xlsx',
    '../Dati_excel/3_CONTROLLO CARTE PETROLIFERE DA IPORTAL_AZZURRO.xlsx',
    '../Dati_excel/4_CONTROLLO BUONI IP DA IPORTAL_ROSSO.xlsx',
    '../Dati_excel/5_CONTROLLO SATISPAY DA PORTALE SATISPAY_GRIGIO.xlsx'
]
importer = DataImporter(db)
importer.import_files(files)

cur = conn.cursor()
for t in ['import_fortech_master', 'verifica_contanti_as400', 'verifica_numia', 'verifica_ip_portal', 'verifica_satispay']:
    cur.execute(f'SELECT COUNT(*) FROM {t}')
    print(f'{t}: {cur.fetchone()[0]}')

cur.execute('SELECT impianto_id, COUNT(*) FROM verifica_ip_portal GROUP BY impianto_id')
print(f'IP Portal by Impianto: {cur.fetchall()}')

cur.execute('SELECT id FROM impianti WHERE codice_pv_fortech="43809"')
print(f'43809 ID: {cur.fetchone()[0]}')

analyzer = Analyzer(db)
analyzer.run_analysis()

cur.execute('SELECT COUNT(*) FROM report_riconciliazioni WHERE valore_fortech > 0')
print(f'Non-zero results: {cur.fetchone()[0]}')

conn.close()
