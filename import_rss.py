import sqlite3
import feedparser
import requests
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = str(BASE_DIR / "database.sqlite")
RSS_FILE = str(BASE_DIR / "rss_list.txt")

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Tambahkan kolom 'status_fb' untuk menandai apakah sudah diposting ke FB
    c.execute("""
        CREATE TABLE IF NOT EXISTS artikel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE, judul TEXT, konten TEXT, 
            tanggal_publish TEXT, status_fb INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def proses_feed(url):
    url = url.strip()
    if not url or url.startswith("#"): return
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        feed = feedparser.parse(resp.content)
        conn = sqlite3.connect(DB_PATH, timeout=15)
        c = conn.cursor()
        
        # Filter 1 jam terakhir
        batas_waktu = datetime.now() - timedelta(hours=1)

        for entry in feed.entries[:10]: # Ambil 10 terbaru per feed
            link = entry.get('link', '')
            judul = entry.get('title', '')
            if not link: continue
            
            # Cek waktu
            pub = entry.get('published_parsed')
            if pub:
                waktu = datetime(*pub[:6])
                if waktu < batas_waktu: continue # Lewati jika lebih dari 1 jam

            c.execute("INSERT OR IGNORE INTO artikel (link, judul, konten, tanggal_publish) VALUES (?, ?, ?, ?)",
                      (link, judul, entry.get('summary', ''), datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception:
        pass

if __name__ == "__main__":
    init_db()
    with open(RSS_FILE, "r") as f:
        urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    
    print(f"Mulai scraping {len(urls)} RSS...")
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(proses_feed, u): u for u in urls}
        for f in as_completed(futures): f.result()
    print("Scraping selesai.")
