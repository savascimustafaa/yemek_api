import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify
from datetime import datetime
import urllib3
import pdfplumber
import io
import re

# Güvenlik uyarılarını kapatıyoruz
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# --- 1. ABB GENÇLİK SOFRASI ---
def get_abb_menu():
    try:
        url = 'https://forms.ankara.bel.tr/genclik-sofrasi-menu'
        response = requests.get(url, headers=HEADERS, verify=False, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        meals = []
        for item in soup.find_all(['li', 'strong', 'b', 'h5']):
            text = item.text.strip()
            if 3 < len(text) < 40 and "Gençlik" not in text and "Sofrası" not in text:
                if text not in meals: meals.append(text)
        return {
            "sourceName": "ABB Gençlik Sofrası",
            "date": datetime.now().strftime('%d.%m.%Y'),
            "meals": meals[2:] if meals else ["Menü bulunamadı."]
        }
    except:
        return {"sourceName": "ABB", "meals": ["Bağlantı hatası."]}

# --- 2. KYK AKŞAM MENÜSÜ ---
def get_kyk_ankara_menu():
    try:
        url = 'https://kykmenulistesi.com.tr/'
        response = requests.get(url, headers=HEADERS, verify=False, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        meals = []
        lines = soup.get_text(separator='|', strip=True).split('|')
        
        aksam_basladi_mi = False
        for line in lines:
            line_temiz = line.strip()
            if "Akşam Menüsü" in line_temiz:
                aksam_basladi_mi = True
                continue
            if aksam_basladi_mi:
                if "öğe" in line_temiz.lower() or "puan" in line_temiz.lower():
                    break
                if "günün yemeği" not in line_temiz.lower() and "kalori" not in line_temiz.lower():
                    if len(line_temiz) > 3 and not line_temiz.isdigit():
                        meals.append(line_temiz)
                        
        return {
            "sourceName": "KYK Akşam Menüsü",
            "date": datetime.now().strftime('%d.%m.%Y'),
            "meals": meals if meals else ["Akşam menüsü bulunamadı."]
        }
    except:
        return {"sourceName": "KYK Akşam", "date": "Hata", "meals": ["Bağlantı hatası."]}

# --- 3. ÇANKAYA GENÇLİK SOFRASI (RESİM LİNKİ) ---
def get_cankaya_menu():
    try:
        url = 'https://www.cankaya.bel.tr/sayfalar/menulerimiz'
        response = requests.get(url, headers=HEADERS, verify=False, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        link = None
        for a in soup.find_all('a'):
            if "Gençlik Sofrası" in a.get_text():
                href = a.get('href', '')
                link = "https://www.cankaya.bel.tr" + href if href.startswith('/') else href
                break
        return {"sourceName": "Çankaya Gençlik Sofrası", "date": "Haftalık Görsel", "meals": [link] if link else ["Link bulunamadı."]}
    except:
        return {"sourceName": "Çankaya", "meals": ["Bağlantı hatası."]}

# --- 4. HACI BAYRAM (PDF ANALİZİ) ---
def get_haci_bayram_pdf():
    try:
        pdf_url = "https://hacibayram.edu.tr/api/files/1/Hac%C4%B1bayram%20AHBV/sks(tr-TR)/YEMEK%20N%C4%B0SAN/cikti%20nisan.pdf"
        response = requests.get(pdf_url, headers=HEADERS, verify=False, timeout=20)
        
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            table = pdf.pages[0].extract_table()
            bugun = str(datetime.now().day) # Bugünün gününü (Örn: 8) arar
            meals = []

            if table:
                for row in table:
                    for cell in row:
                        if cell and bugun in cell:
                            
                            text = cell.replace('\n', ' ')
                            # Kcal bazlı ayır
                            lines = re.findall(r'[^)]+Kcal\)', text)
                            meals = [' '.join(line.split()) for line in lines]

                            break
                    if meals: 
                        break
        
        return {
            "sourceName": "AHBVÜ Yemek Menüsü",
            "date": datetime.now().strftime('%d.%m.%Y'),
            "meals": meals if meals else ["PDF'te menü bulunamadı."]
        }
    except Exception as e:
        return {"sourceName": "AHBVÜ", "date": "Hata", "meals": [f"Hata: {str(e)[:15]}"]}

# --- API ---
@app.route('/api/menus')
def get_menus():
    return jsonify([
        get_haci_bayram_pdf(),
        get_abb_menu(),
        get_cankaya_menu(),
        get_kyk_ankara_menu()
    ])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)