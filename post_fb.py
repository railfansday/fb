import sqlite3
import requests
import os
from pathlib import Path

# ==========================================================================
# KONFIGURASI
# ==========================================================================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = str(BASE_DIR / "database.sqlite")

# ⚠️ Ambil kredensial dari Environment Variable (GitHub Secrets)
PAGE_ID = os.environ.get("FB_PAGE_ID")
ACCESS_TOKEN = os.environ.get("FB_ACCESS_TOKEN")

def post_to_facebook():
    print("=" * 50)
    print("MULAI POSTING KE FACEBOOK")
    print("=" * 50)

    if not PAGE_ID or not ACCESS_TOKEN:
        print("❌ ERROR: FB_PAGE_ID atau FB_ACCESS_TOKEN belum diset di GitHub Secrets.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Ambil 1 artikel yang belum diposting (status_fb = 0)
    # Ubah LIMIT 1 menjadi LIMIT 3 jika ingin posting 3 artikel sekaligus per run
    c.execute("SELECT id, judul, konten, gambar, link FROM artikel WHERE status_fb = 0 LIMIT 1")
    artikel = c.fetchone()

    if not artikel:
        print("✅ Tidak ada artikel baru di database yang perlu diposting.")
        conn.close()
        return

    art_id, judul, konten, gambar, link = artikel
    
    # Siapkan pesan Facebook
    pesan = f"📰 {judul}\n\nBaca berita selengkapnya di sini: {link}\n\n#Berita #Otomotif #Football"
    
    # Tembak ke Facebook Graph API (Kirim Link agar FB otomatis ambil gambar)
    url = f"https://graph.facebook.com/{PAGE_ID}/feed"
    payload = {
        'message': pesan,
        'link': link, 
        'access_token': ACCESS_TOKEN
    }
    
    print(f"[*] Mencoba posting: {judul[:50]}...")
    try:
        response = requests.post(url, data=payload, timeout=15)
        
        if response.status_code == 200:
            print("✅ Berhasil diposting ke Facebook!")
            # Tandai artikel sudah diposting
            c.execute("UPDATE artikel SET status_fb = 1 WHERE id = ?", (art_id,))
            conn.commit()
        else:
            print(f"❌ Gagal posting. Status: {response.status_code}")
            print(f"   Pesan Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Terjadi error jaringan: {e}")

    conn.close()

if __name__ == "__main__":
    post_to_facebook()
