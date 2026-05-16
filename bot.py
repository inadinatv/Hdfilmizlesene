import requests
from bs4 import BeautifulSoup
import re
import json
import base64
import codecs
import time
from datetime import datetime
import urllib.parse

BASE_URL = "https://www.fullhdfilmizlesene.life"

# Github Actions limitlerine takılmamak için test amaçlı 3 kategori ekledim. İstediğin kadar artırabilirsin.
KATEGORILER = {
    "En Çok İzlenen Filmler": "/en-cok-izlenen-filmler-izle-hd/",
    "Aksiyon Filmleri": "/filmizle/aksiyon-filmleri-hdf-izle/",
    "Bilim Kurgu Filmleri": "/filmizle/bilim-kurgu-filmleri-izle-2/"
}

# --- YARDIMCI FONKSİYONLAR ---
def string_decode(s):
    """Kotlin'deki atob(rtt()) mantığının Python karşılığı (Rot13 + Base64)"""
    try:
        rot13_str = codecs.encode(s, 'rot_13')
        return base64.b64decode(rot13_str).decode('utf-8')
    except:
        return ""

# --- ÖZEL ÇIKARICILAR (EXTRACTORS) ---
def trstx2m3u8(url):
    """trstx.org sunucularından m3u8 çıkarır"""
    oturum = requests.Session()
    oturum.headers.update({"User-Agent": "Mozilla/5.0", "Referer": BASE_URL})
    try:
        istek = oturum.get(url, timeout=10)
        file_match = re.search(r'file\":\"([^\"]+)\"', istek.text)
        if not file_match: return None
        
        post_link = "https://trstx.org/" + file_match.group(1).replace("\\", "")
        post_istek = oturum.post(post_link, timeout=10).json()
        
        if len(post_istek) > 1 and "file" in post_istek[1]:
            m3u8_url = "https://trstx.org/playlist/" + post_istek[1]["file"][1:] + ".txt"
            sonuc = oturum.post(m3u8_url, timeout=10)
            return sonuc.text.strip()
    except Exception as e:
        print(f"Trstx Hatası: {e}")
    return None

def turboimgz2m3u8(url):
    """turbo.imgz.me sunucularından m3u8 çıkarır"""
    try:
        url = url.split("||")[-1] # Özel formatı temizle
        istek = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": BASE_URL}, timeout=10)
        file_match = re.search(r'file:\s*"(.*?)",', istek.text)
        if file_match:
            return file_match.group(1)
    except:
        pass
    return None

def m3u8_coz(iframe_url):
    """Gelen iframe linkine göre doğru extractor'ı seçer."""
    if "trstx.org" in iframe_url:
        return trstx2m3u8(iframe_url)
    elif "turbo.imgz.me" in iframe_url:
        return turboimgz2m3u8(iframe_url)
    else:
        # Diğer sunucular için şimdilik kaynak linki döndür (veya buraya rapidvid vb. eklenebilir)
        return iframe_url

# --- ANA SİTE (IFRAME) BULUCU ---
def get_stream_links(url):
    oturum = requests.Session()
    oturum.headers.update({"User-Agent": "Mozilla/5.0"})
    
    try:
        istek = oturum.get(url, follow_redirects=True, timeout=10)
        soup = BeautifulSoup(istek.text, 'html.parser')
        
        script = soup.find(lambda tag: tag.name == 'script' and 'scx = ' in tag.text)
        if not script: return None

        scx_data = json.loads(re.findall(r'scx = (.*?);', script.text)[0])
        
        # Öncelikli olarak TR ve Hızlı sunucuları kontrol et
        for key in ["tr", "fast", "proton"]:
            if key in scx_data and "sx" in scx_data[key] and "t" in scx_data[key]["sx"]:
                t = scx_data[key]["sx"]["t"]
                
                # Linkleri çöz
                if isinstance(t, list) and len(t) > 0:
                    decoded = string_decode(t[0])
                    if decoded: return m3u8_coz(decoded)
                elif isinstance(t, dict):
                    for k, v in t.items():
                        decoded = string_decode(v)
                        if decoded: return m3u8_coz(decoded)
        return None
    except Exception as e:
        print(f"Iframe çekilirken hata: {e}")
        return None

# --- ANA BOT MANTIĞI ---
def bot_calistir():
    zaman = datetime.now().strftime("%d-%m-%Y %H:%M")
    print(f"[{zaman}] M3U Botu çalışmaya başladı (Ham .m3u8 Modu)...")
    
    m3u_icerik = "#EXTM3U\n"
    
    for kategori_adi, kategori_yolu in KATEGORILER.items():
        print(f"\n>> Kategori işleniyor: {kategori_adi}")
        kat_url = BASE_URL + kategori_yolu
        
        try:
            req = requests.get(kat_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(req.content, 'html.parser')
            
            # Her kategoriden ilk 5 filmi çek
            for li in soup.select("li.film")[:5]:
                baslik = li.select_one("span.film-title").text.strip()
                film_url = li.select_one("a").get("href")
                afis_url = li.select_one("img").get("data-src") or ""
                
                if not film_url.startswith("http"):
                    film_url = BASE_URL + film_url
                
                print(f"  Film çözülüyor: {baslik}")
                stream_link = get_stream_links(film_url)
                
                if stream_link and (".m3u8" in stream_link or ".mp4" in stream_link):
                    print("    [+] m3u8 bulundu!")
                    m3u_icerik += f'#EXTINF:-1 group-title="{kategori_adi}" tvg-logo="{afis_url}",{baslik}\n'
                    m3u_icerik += f'{stream_link}\n'
                else:
                    print("    [-] m3u8 bulunamadı, atlanıyor.")
                
                time.sleep(1.5) # Siteyi yormamak ve engellenmemek için bekleme
                
        except Exception as e:
            print(f"Kategori hatası ({kategori_adi}): {e}")

    with open("filmler.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_icerik)
        
    print("\n✅ M3U dosyası başarıyla oluşturuldu!")

if __name__ == "__main__":
    bot_calistir()
