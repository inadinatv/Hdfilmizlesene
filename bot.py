import requests
from bs4 import BeautifulSoup
import re
import json
import base64
import codecs
import time
from datetime import datetime

BASE_URL = "https://www.fullhdfilmizlesene.life"

# GitHub Actions'da çok uzun sürüp takılmaması için kategori sayısını veya çekilecek film sayısını limitli tutmak iyidir.
KATEGORILER = {
    "En Çok İzlenen Filmler": "/en-cok-izlenen-filmler-izle-hd/",
    "Aksiyon Filmleri": "/filmizle/aksiyon-filmleri-hdf-izle/",
    "Bilim Kurgu Filmleri": "/filmizle/bilim-kurgu-filmleri-izle-2/"
}

# --- ŞİFRE ÇÖZÜCÜLER (Kotlin'deki atob(rtt(s)) işleminin Python karşılığı) ---
def string_decode(s):
    try:
        rot13_str = codecs.encode(s, 'rot_13')
        return base64.b64decode(rot13_str).decode('utf-8')
    except:
        return ""

# --- VİDEO LİNKİ ÇIKARICI (bakalim.py'den uyarlandı) ---
def get_stream_link(url):
    oturum = requests.Session()
    oturum.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    
    try:
        istek = oturum.get(url, follow_redirects=True, timeout=10)
        soup = BeautifulSoup(istek.text, 'html.parser')
        
        script = soup.find(lambda tag: tag.name == 'script' and 'scx = ' in tag.text)
        if not script: return None

        scx_data = json.loads(re.findall(r'scx = (.*?);', script.text)[0])
        
        # Sadece hızlı ve Türkçe (tr, fast, proton) sunucularını alalım
        for key in ["tr", "fast", "proton"]:
            if key in scx_data and "sx" in scx_data[key] and "t" in scx_data[key]["sx"]:
                t = scx_data[key]["sx"]["t"]
                if isinstance(t, list) and len(t) > 0:
                    decoded = string_decode(t[0])
                    if decoded: return decoded
                elif isinstance(t, dict):
                    for k, v in t.items():
                        decoded = string_decode(v)
                        if decoded: return decoded
        return None
    except Exception as e:
        print(f"Video linki çekilirken hata: {e}")
        return None

# --- ANA BOT MANTIĞI ---
def bot_calistir():
    zaman = datetime.now().strftime("%d-%m-%Y %H:%M")
    print(f"[{zaman}] M3U Botu çalışmaya başladı...")
    
    m3u_icerik = "#EXTM3U\n"
    
    for kategori_adi, kategori_yolu in KATEGORILER.items():
        print(f"Kategori işleniyor: {kategori_adi}")
        kat_url = BASE_URL + kategori_yolu
        
        try:
            req = requests.get(kat_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(req.content, 'html.parser')
            
            # Her kategoriden ilk 5 filmi alalım (Test için sayıyı düşük tuttum)
            for li in soup.select("li.film")[:5]:
                baslik = li.select_one("span.film-title").text.strip()
                film_url = li.select_one("a").get("href")
                afis_url = li.select_one("img").get("data-src") or ""
                
                if not film_url.startswith("http"):
                    film_url = BASE_URL + film_url
                
                print(f"  Film çözülüyor: {baslik}")
                stream_link = get_stream_link(film_url)
                
                if stream_link:
                    m3u_icerik += f'#EXTINF:-1 group-title="{kategori_adi}" tvg-logo="{afis_url}",{baslik}\n'
                    m3u_icerik += f'{stream_link}\n'
                
                time.sleep(1) # Sunucuyu yormamak için
                
        except Exception as e:
            print(f"Kategori hatası ({kategori_adi}): {e}")

    with open("filmler.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_icerik)
        
    print("M3U dosyası başarıyla oluşturuldu!")

if __name__ == "__main__":
    bot_calistir()
