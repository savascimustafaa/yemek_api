import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify
from datetime import datetime
import urllib3
import pdfplumber
import io
import os
import re
from urllib.parse import urljoin, quote
from PIL import Image

# Güvenlik uyarılarını kapatıyoruz
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def get_current_date():
    return datetime.now().strftime('%d.%m.%Y')

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
        actual_meals = meals[2:] if len(meals) > 2 else []
        if not actual_meals:
            actual_meals = ["Hafta sonu veya tatil nedeniyle menü bulunamadı."] if datetime.now().weekday() >= 5 else ["Menü henüz girilmemiş."]
        return {"sourceName": "ABB Gençlik Sofrası", "date": get_current_date(), "meals": actual_meals}
    except:
        return {"sourceName": "ABB Gençlik Sofrası", "meals": ["Hata oluştu."]}

# --- 2. ÇANKAYA GENÇLİK SOFRASI ---
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
        return {"sourceName": "Çankaya Gençlik Sofrası", "meals": ["Bağlantı hatası."]}

def get_kyk_ankara_menu():
    try:
        # 1. ADIM: F12 panelinden "Request URL" kısmında bulduğun tam adresi buraya yapıştır.
        # (Örnek: "https://api.siteninadi.com/liste?cityId=6&mealType=1" gibi bir şey olmalı)
        api_url = "https://kykyemekliste.com/api/menu/liste?cityId=6&mealType=1" 
        #burası değişti 
        # Site bot olduğumuzu sanıp engellemesin diye tarayıcı kimliğine bürünüyoruz
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # 2. ADIM: İsteği atıp, veriyi doğrudan JSON (Sözlük/Liste) formatında alıyoruz.
        response = requests.get(api_url, headers=headers, verify=False, timeout=10)
        data = response.json() 

        # 3. ADIM: Tarih formatlarımızı belirliyoruz
        api_tarihi = datetime.now().strftime("%Y-%m-%d")    # JSON içinde aramak için (Örn: 2026-04-15)
        ekran_tarihi = datetime.now().strftime("%d.%m.%Y")  # Ekranda göstermek için (Örn: 15.04.2026)
        
        gunluk_menu = None
        
        # 4. ADIM: Tüm JSON listesini dönüp bugünün menüsünü buluyoruz
        for gun in data:
            if gun.get("date") == api_tarihi:
                gunluk_menu = gun
                break
                
        # Eğer bugüne ait menü sisteme girilmemişse:
        if not gunluk_menu:
            return {
                "sourceName": "KYK Ankara Akşam Yemeği", 
                "date": ekran_tarihi, 
                "meals": ["Bugün için menü bulunamadı."]
            }

        # 5. ADIM: Yemekleri ve kaloriyi tek bir listeye topluyoruz
        # DİKKAT: "second", "third", "calorie" gibi key isimlerini F12 panelindeki 
        # (►) okuna tıklayarak açtığın yerden teyit et ve gerekirse burada düzelt.
        meals = []
        
        if "first" in gunluk_menu: 
            meals.append(gunluk_menu["first"])
            
        if "second" in gunluk_menu: 
            meals.append(gunluk_menu["second"])
            
        if "third" in gunluk_menu: 
            meals.append(gunluk_menu["third"])
            
        if "fourth" in gunluk_menu: 
            meals.append(gunluk_menu["fourth"])
        
        if "calorie" in gunluk_menu: 
            meals.append(f"Toplam Kalori: {gunluk_menu['calorie']}")

        # 6. ADIM: Sonucu ekran_tarihi ile birlikte uygulamaya (Flutter'a) gönderiyoruz
        return {
            "sourceName": "KYK Ankara Akşam Yemeği", 
            "date": ekran_tarihi, 
            "meals": meals
        }

    except Exception as e:
        # Kodun nerede patladığını terminalden görebilmek için:
        print(f"KYK Menü Çekme Hatası: {e}")
        
        # Hata anında bile arayüze güncel tarihi yollayalım ki ekran boş kalmasın
        hata_tarihi = datetime.now().strftime("%d.%m.%Y")
        return {
            "sourceName": "KYK Ankara Akşam Yemeği", 
            "date": hata_tarihi, 
            "meals": ["Hata oluştu veya veri çekilemedi."]
        }

# --- 4. ANKARA ÜNİVERSİTESİ ---
def get_ankara_uni():
    # Bu link her gün girdiğinde o günün menü resmini üretir
    # OCR ile uğraşmak yerine direkt bu linki Flutter'a yollayabiliriz
    url = "https://sksbasvuru.ankara.edu.tr/kayit/moduller/yemeklistesi/yemek.php"
    
    return {
        "sourceName": "Ankara Üniversitesi",
        "date": datetime.now().strftime("%d.%m.%Y"),
        "isImage": True, # Flutter'a bunun bir resim olduğunu haber veriyoruz
        "imageUrl": url
    }
    
    
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def get_current_date():
    return datetime.now().strftime("%d.%m.%Y")
def get_haci_bayram_pdf():
    try:
        pdf_url = "https://hacibayram.edu.tr/api/files/1/Hac%C4%B1bayram%20AHBV/sks(tr-TR)/YEMEK%20N%C4%B0SAN/cikti%20nisan.pdf"
        response = requests.get(pdf_url, headers=HEADERS, verify=False, timeout=20)
        
        if response.status_code != 200:
             return {"sourceName": "AHBVÜ", "meals": ["PDF'e ulaşılamadı."]}

        today_day = str(datetime.now().day) 
        
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            for page in pdf.pages:
                words = page.extract_words()
                
                hedef_x_merkez = None
                hedef_y_baslangic = None
                
                for word in words:
                    if word['text'] == today_day or word['text'] == f"0{today_day}":
                        hedef_x_merkez = (word['x0'] + word['x1']) / 2
                        hedef_y_baslangic = word['bottom']
                        break
                
                if hedef_x_merkez is None:
                    continue 
                
                sutun_kelimeleri = []
                for word in words:
                    word_merkez = (word['x0'] + word['x1']) / 2
                    
                    # GÜNCELLEME 1: Tolerans 70'ten 85'e çıkarıldı! 
                    # "Meyve" gibi sütun kenarına yaslı kelimeler artık kaçmayacak.
                    if word['top'] >= hedef_y_baslangic - 5 and abs(word_merkez - hedef_x_merkez) < 110:
                        sutun_kelimeleri.append(word)
                
                sutun_kelimeleri.sort(key=lambda w: w['top'])
                
                satirlar = []
                mevcut_satir = []
                son_y = -1
                
                for word in sutun_kelimeleri:
                    if son_y == -1 or abs(word['top'] - son_y) < 5:
                        mevcut_satir.append(word['text'])
                    else:
                        satirlar.append(" ".join(mevcut_satir))
                        mevcut_satir = [word['text']]
                    son_y = word['top']
                    
                if mevcut_satir:
                    satirlar.append(" ".join(mevcut_satir))

                meals = []
                baslik_gecildi = False
                aylar = ["OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN", "TEMMUZ", "AĞUSTOS", "EYLÜL", "EKİM", "KASIM", "ARALIK"]
                
                next_week = int(today_day) + 7
                if next_week > 31: next_week -= 30 
                next_week_str = str(next_week)

                for line in satirlar:
                    if not line.strip(): continue
                    upper_line = line.upper()
                    
                    if re.search(rf'(^|\b)0?{next_week_str}(\b|$)', line):
                        break
                        
                    if baslik_gecildi and any(ay in upper_line for ay in aylar):
                        break

                    if re.search(rf'(^|\b)0?{today_day}(\b|$)', line):
                        baslik_gecildi = True
                        continue
                        
                    baslik_gecildi = True 

                    # ==========================================
                    # GÜNCELLEME 2: KUSURSUZ VİTRİN TEMİZLİĞİ
                    # ==========================================
                    
                    # 1. Boşluklu harfleri otomatik birleştir (T u r ş u -> Turşu, K c a l -> Kcal)
                    cleaned = re.sub(r'(?<!\S)(\w(?: \w)+)(?!\S)', lambda m: m.group(1).replace(' ', ''), line)
                    
                    # 2. Normal parantezleri ve içindekileri sil
                    cleaned = re.sub(r'\(.*?\)', '', cleaned)
                    
                    # 3. Kcal, gr, kalori geçen kelimeleri tamamen uçur
                    cleaned = re.sub(r'(?i)\b\w*(kcal|gr|kalori)\w*\b', '', cleaned)
                    
                    # 4. Rakamları sil
                    cleaned = re.sub(r'\b\d+\b', '', cleaned)
                    
                    # 5. Kapanmamış parantez ve çöpleri sil
                    cleaned = re.sub(r'[)(*?\-+/]', ' ', cleaned)
                    
                    # 6. Fazla boşlukları tek boşluğa indir
                    cleaned = " ".join(cleaned.split())
                    
                    # 7. Tekrar Eden Kelime Yokedici (Çorbası Çorbası -> Çorbası)
                    words_in_line = cleaned.split()
                    deduped = []
                    for w in words_in_line:
                        if not deduped or deduped[-1].lower() != w.lower():
                            deduped.append(w)
                    cleaned = " ".join(deduped)

                    # Anlamlıysa listeye ekle
                    if len(cleaned) > 2 and "tatil" not in cleaned.lower():
                        meals.append(cleaned)

                if meals:
                    return {
                        "sourceName": "AHBVÜ Yemek Menüsü", 
                        "date": get_current_date(), 
                        "meals": meals
                    }

        return {"sourceName": "AHBVÜ Yemek Menüsü", "date": get_current_date(), "meals": ["Bugün için menü bulunamadı veya hafta sonu."]}
        
    except Exception as e:
        print(f"AHBVÜ Menü Hatası: {e}")
        return {"sourceName": "AHBVÜ", "meals": ["Menü verileri okunurken hata oluştu."]}



# --- API UÇ NOKTASI ---
@app.route('/api/menus')
def get_menus():
    results = [
        get_abb_menu(),
        get_cankaya_menu(),
        get_kyk_ankara_menu(),
        get_haci_bayram_pdf(),
        get_ankara_uni(),
    ]
    return jsonify(results)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    # Threading eklemek çoklu isteklerde uygulamanın kilitlenmesini engeller
    app.run(debug=True, host='0.0.0.0', port=port, threaded=True)
