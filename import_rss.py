import sqlite3
import feedparser
import requests
from bs4 import BeautifulSoup
import os
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

# ==========================================================================
# KONFIGURASI
# ==========================================================================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = str(BASE_DIR / "database.sqlite")
RSS_FILE = str(BASE_DIR / "rss_list.txt")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

ADSTERRA_CODE = """
<div style="text-align:center; margin:20px 0;">
    <script type="text/javascript">
        atOptions = {'key' : 'f9e40eb3b3cd05f1038aac7b36b33ad2','format' : 'iframe','height' : 90,'width' : 728,'params' : {}};
    </script>
    <script type="text/javascript" src="https://upholdbrilliancerecast.com/f9e40eb3b3cd05f1038aac7b36b33ad2/invoke.js"></script>
</div>
"""

# ==========================================================================
# FUNGSI DATABASE
# ==========================================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS artikel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE, judul TEXT, konten TEXT, gambar TEXT,
            tanggal_publish TEXT, status_fb INTEGER DEFAULT 0
        )
    """)
    # Cek kolom baru jika database sudah ada
    c.execute("PRAGMA table_info(artikel)")
    cols = [col[1] for col in c.fetchall()]
    if 'gambar' not in cols: c.execute("ALTER TABLE artikel ADD COLUMN gambar TEXT")
    if 'status_fb' not in cols: c.execute("ALTER TABLE artikel ADD COLUMN status_fb INTEGER DEFAULT 0")
    conn.commit()
    conn.close()

# ==========================================================================
# FUNGSI SCRAPING KONTEN LENGKAP
# ==========================================================================
def ambil_konten_lengkap(url):
    try:
        # Timeout 5 detik agar tidak macet
        response = requests.get(url, headers=HEADERS, timeout=5)
        if response.status_code != 200: return None, None
        
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. AMBIL GAMBAR UTAMA (OG:IMAGE)
        gambar = None
        og_image = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'og:image'})
        if og_image and og_image.get('content'):
            gambar = og_image['content']

        # 2. AMBIL SEMUA PARAGRAF TEKS
        paragraphs = soup.find_all('p')
        teks_lengkap = []
        for p in paragraphs:
            text = p.get_text().strip()
            # Buang teks sampah
            if len(text) > 40 and not any(x in text.lower() for x in ['cookie', 'privacy policy', 'subscribe', 'all rights reserved', 'terms of use']):
                teks_lengkap.append(f"<p>{text}</p>")

        return "\n".join(teks_lengkap) if teks_lengkap else None, gambar
    except Exception:
        return None, None

# ==========================================================================
# FUNGSI PROSES FEED
# ==========================================================================
def proses_feed(feed_url):
    feed_url = feed_url.strip()
    if not feed_url or feed_url.startswith("#"): return 0, 0

    baru = 0
    duplikat = 0

    try:
        # Ambil RSS dengan timeout
        resp = requests.get(feed_url, headers=HEADERS, timeout=8)
        if resp.status_code != 200: return 0, 0
        
        feed = feedparser.parse(resp.content)
        conn = sqlite3.connect(DB_PATH, timeout=15)
        c = conn.cursor()

        # Ambil 5 artikel terbaru per feed (ubah angka ini jika ingin lebih banyak)
        for entry in feed.entries[:5]:
            link = entry.get('link', '')
            judul = entry.get('title', 'Tanpa Judul')
            if not link: continue

            # Cek apakah link sudah ada di database (Duplikat)
            c.execute("SELECT id FROM artikel WHERE link = ?", (link,))
            if c.fetchone():
                duplikat += 1
                continue

            # Buka link untuk ambil teks & gambar
            html_teks, gambar = ambil_konten_lengkap(link)
            
            # Jika gagal ambil teks, gunakan ringkasan RSS
            if not html_teks:
                html_teks = f"<p>{entry.get('summary', 'Konten tidak tersedia.')}</p>"

            # Susun konten dengan iklan
            img_tag = f'<div style="text-align:center; margin-bottom:20px;"><img src="{gambar}" alt="{judul}" style="max-width:100%; height:auto;"></div>' if gambar else ""
            konten_lengkap = f"{img_tag}\n{ADSTERRA_CODE}\n{html_teks}\n{ADSTERRA_CODE}"

            # Simpan ke Database
            try:
                c.execute(
                    "INSERT INTO artikel (link, judul, konten, gambar, tanggal_publish, status_fb) VALUES (?, ?, ?, ?, ?, 0)",
                    (link, judul, konten_lengkap, gambar, datetime.now().isoformat())
                )
                conn.commit()
                baru += 1
            except Exception:
                pass
                
        conn.close()
    except Exception:
        pass
        
    return baru, duplikat

# ==========================================================================
# MAIN
# ==========================================================================
if __name__ == "__main__":
    print("=" * 50)
    print("MULAI SCRAPING KONTEN LENGKAP")
    print("=" * 50)
    
    if not os.path.exists(RSS_FILE):
        print(f"[ERROR] File {RSS_FILE} tidak ditemukan!")
        exit(1)
        
    init_db()
    
    with open(RSS_FILE, "r", encoding="utf-8") as f:
        rss_urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        
    print(f"[*] Memproses {len(rss_urls)} sumber RSS...")
    
    total_baru, total_duplikat = 0, 0
    
    # Gunakan 10 worker (paralel) agar cepat
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(proses_feed, url): url for url in rss_urls}
        for future in as_completed(futures):
            b, d = future.result()
            total_baru += b
            total_duplikat += d

    print("\n" + "="*45)
    print(f"[SELESAI]")
    print(f" - Artikel Baru disimpan : {total_baru}")
    print(f" - Dilewati (Duplikat)   : {total_duplikat}")
    print("="*45)
