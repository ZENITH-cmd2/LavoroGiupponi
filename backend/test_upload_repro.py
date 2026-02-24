import requests
import os

url = 'http://localhost:5000/api/upload'
excel_dir = '../Dati_excel'
files = [
    'A_FILE GENERALE DA FORTECH_MILANO REPUBBLICA.xlsx',
    '1_CONTROLLO CONTANTI DA AS400_GIALLO.xlsx',
    '2_CONTROLLO CARTE BANCARIE DA NUMIA_VERDE.xlsx',
    '3_CONTROLLO CARTE PETROLIFERE DA IPORTAL_AZZURRO.xlsx',
    '4_CONTROLLO BUONI IP DA IPORTAL_ROSSO.xlsx',
    '5_CONTROLLO SATISPAY DA PORTALE SATISPAY_GRIGIO.xlsx'
]

file_handles = []
multipart_data = []

try:
    for filename in files:
        path = os.path.join(excel_dir, filename)
        f = open(path, 'rb')
        file_handles.append(f)
        multipart_data.append(('files[]', (filename, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')))

    print(f"Uploading {len(files)} files to {url}...")
    response = requests.post(url, files=multipart_data)
    print(f"Status Code: {response.status_code}")
    print("Response JSON:")
    try:
        print(response.json())
    except:
        print(response.text)
except requests.exceptions.ConnectionError:
    print("CONNECTION FAILED - Server might have crashed!")
except Exception as e:
    print(f"Error: {e}")
finally:
    for f in file_handles:
        f.close()
