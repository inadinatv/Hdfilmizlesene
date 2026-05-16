import cloudscraper
from bs4 import BeautifulSoup
import re
import json
import base64
import codecs
import time
from datetime import datetime

BASE_URL = "https://www.fullhdfilmizlesene.life"

KATEGORILER = {
    "En Çok İzlenen Filmler": "/en-cok-izlenen-filmler-izle-hd/",
    "Aksiyon Filmleri": "/filmizle/aksiyon-filmleri-hdf-izle/",
    "Bilim Kurgu Filmleri": "/filmizle/bilim-kurgu-filmleri-izle-2/"
}

# Standart 'requests' yerine Cloudflare aşabilen 'cloudscraper' kullanıyoruz
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

def string_decode(s):
    try:
        rot13_str = codecs.encode(s, 'rot_13')
        return base64.b64decode(rot13_str).decode('utf-8')
    except:
        return None

def trstx2m3u8(url):
    try:
        req = scraper.get(url, headers={"Referer": BASE_URL}, timeout=15)
        file_match = re.search(r'file\":\"([^\"]+)\"', req.text)
        if not file_match: return None
        
        post_link = "https://trstx.org/" + file_match.group(1).replace("\\", "")
        post_req = scraper.post(post_link, headers={"Referer": url}, timeout=15).json()
        
        if len(post_req) > 1 and "file" in post_req[1]:
            m3u8_url = "https://trstx.org/playlist/" + post_req[1]["file"][1:] + ".txt"
            sonuc = scraper.post(m3u8_url, headers={"Referer": url}, timeout=15)
            return sonuc.text.strip()
    except Exception as e:
        print(f"      [!] Trstx Çözme Hatası: {e}")
    return None

def turboimgz2m3u8(url):
    try:
        url = url.split("||")[-1]
        req = scraper.get(url, headers={"Referer": BASE_URL}, timeout=15)
        file_match = re.search(r'file:\s*"(.*?)",', req.text)
        if file_match:
            return file_match.group(1)
    except Exception as e:
        print(f"      [!] TurboImgz Çözme Hatası: {e}")
    return None

def m3u8_coz(iframe_url):
    """Gelen iframe linkini desteklenen sunuculara göre ayıklar"""
    print(f"    [?] Sunucu test ediliyor: {iframe_url.split('/')[2]}")
    if "trstx" in iframe_url:
        return trstx2m3u8(iframe_url)
    elif "turbo.imgz" in iframe_url:
        return turboimgz2m3u8(iframe_url)
    return None # Desteklenmeyen bir sunucuysa None döner, bot diğer sunucuya geçer

def get_stream_links(url):
    try:
        istek = scraper.get(url, timeout=15)
        
        # BeautifulSoup yerine doğrudan güçlü Regex ile 'scx' datasını arıyoruz
        scx_match = re.search(r'scx\s*=\s*(\{.*?\});', istek.text)
        if not scx_match:
            print("    [!] Sitede scx verisi bulunamadı (Cloudflare engellemiş olabilir).")
            return None

        scx_data = json.loads(scx_match.group(1))
        
        # Tüm olası sunucu tiplerini sırayla dene. Biri patlarsa diğerinden m3u8 yakalayacağız.
        for key in ["tr", "fast", "proton", "en", "atom"]:
            if key in scx_data and "sx" in scx_data[key] and "t" in scx_data[key]["sx"]:
                t = scx_data[key]["sx"]["t"]
                
                links_to_test = []
                if isinstance(t, list):
                    links_to_test = t
                elif isinstance(t, dict):
                    links_to_test = list(t.values())
                    
                for encoded_link in links_to_test:
                    decoded = string_decode(encoded_link)
                    if decoded:
                        sonuc_link = m3u8_coz(decoded)
                        # Eğer geçerli bir m3u8, mp4 veya txt playlist dönerse işlemi tamamla!
                        if sonuc_link and (".m3u8" in sonuc_link or ".mp4" in sonuc_link or ".txt" in sonuc_link):
                            return sonuc_link
        return None
    except Exception as e:
        print(f"    [!] Film sayfası taranırken hata: {e}")
        return None

def bot_calistir():
    zaman = datetime.now().strftime("%d-%m-%Y %H:%M")
    print(f"[{zaman}] Güçlendirilmiş M3U Botu çalışmaya başladı...")
    
    m3u_icerik = "#EXTM3U\n"
    film_bulundu = False
    
    for kategori_adi, kategori_yolu in KATEGORILER.items():
        print(f"\n>> Kategori işleniyor: {kategori_adi}")
        kat_url = BASE_URL + kategori_yolu
        
        try:
            req = scraper.get(kat_url, timeout=15)
            soup = BeautifulSoup(req.content, 'html.parser')
            
            # Şimdilik her kategoriden 10 film alıyor (Test bitince kaldırabilirsin)
            for li in soup.select("li.film")[:10]:
                baslik = li.select_one("span.film-title").text.strip()
                film_url = li.select_one("a").get("href")
                afis_url = li.select_one("img").get("data-src") or ""
                
                if not film_url.startswith("http"):
                    film_url = BASE_URL + film_url
                
                print(f"  🎬 Film: {baslik}")
                stream_link = get_stream_links(film_url)
                
                if stream_link:
                    print("    ✅ BAŞARILI! m3u8 linki eklendi.")
                    m3u_icerik += f'#EXTINF:-1 group-title="{kategori_adi}" tvg-logo="{afis_url}",{baslik}\n'
                    m3u_icerik += f'{stream_link}\n'
                    film_bulundu = True
                else:
                    print("    ❌ Başarısız: Bu film için uygun m3u8 bulunamadı.")
                
                time.sleep(2) # Sitenin banlamaması için her film arası 2 saniye bekle
                
        except Exception as e:
            print(f"Kategori hatası ({kategori_adi}): {e}")

    if film_bulundu:
        with open("filmler.m3u", "w", encoding="utf-8") as f:
            f.write(m3u_icerik)
        print("\n🎉 M3U dosyası başarıyla dolu bir şekilde oluşturuldu!")
    else:
        print("\n⚠️ HİÇBİR FİLM ÇEKİLEMEDİ! Logları kontrol et.")

if __name__ == "__main__":
    bot_calistir()
