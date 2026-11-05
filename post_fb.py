import sqlite3
import requests
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = str(BASE_DIR / "database.sqlite")

# Ambil kredensial dari Environment Variable (GitHub Secrets)
PAGE_ID = os.environ.get("FB_PAGE_ID")
ACCESS_TOKEN = os.environ.get("FB_ACCESS_TOKEN")

def post_to_facebook():
    if not PAGE_ID or not ACCESS_TOKEN:
        print("Error: FB_PAGE_ID atau FB_ACCESS_TOKEN belum diset.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Ambil 1 artikel yang belum diposting (status_fb = 0)
    c.execute("SELECT id, judul, konten, link FROM artikel WHERE status_fb = 0 LIMIT 1")
    artikel = c.fetchone()

    if not artikel:
        print("Tidak ada artikel baru untuk diposting.")
        conn.close()
        return

    art_id, judul, konten, link = artikel
    
    # Buat pesan Facebook
    pesan = f"{judul}\n\nBaca selengkapnya: {link}"
    
    # Tembak ke Facebook Graph API
    url = f"https://graph.facebook.com/{PAGE_ID}/feed"
    payload = {'message': pesan, 'access_token': ACCESS_TOKEN}
    
    print(f"Mencoba posting: {judul[:30]}...")
    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        print("✅ Berhasil posting ke Facebook!")
        # Tandai artikel sudah diposting
        c.execute("UPDATE artikel SET status_fb = 1 WHERE id = ?", (art_id,))
        conn.commit()
    else:
        print(f"❌ Gagal posting: {response.text}")

    conn.close()

if __name__ == "__main__":
    post_to_facebook()
