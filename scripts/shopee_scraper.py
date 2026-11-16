"""
Shopee Product Review Scraper
=============================
Alat untuk mengekstrak ulasan/review produk dari Shopee secara akurat dan lengkap.

Fitur:
- Ekstraksi detail: username, rating bintang, tanggal, varian produk, teks ulasan, link foto/video, respon penjual.
- Mengubah hash foto Shopee menjadi link gambar asli CDN (https://down-id.img.susercontent.com/file/...).
- Dukungan pagination untuk mengambil puluhan hingga ribuan ulasan.
- Pilihan filter: Semua rating, khusus bintang tertentu (1-5), atau hanya yang ada komentar/media.
- Ekspor ke CSV (UTF-8 BOM siap buka di Excel tanpa teks rusak) dan JSON.
- Mendukung input Cookie untuk melewati proteksi bot Shopee (Error 403).
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

SHOPEE_CDN_IMAGE = "https://down-id.img.susercontent.com/file/"
COOKIES_FILE = Path("data/shopee_cookies.json").resolve()


def get_saved_cookie_string() -> str:
    if COOKIES_FILE.is_file():
        try:
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return (data.get("cookie_string") or "").strip()
        except Exception:
            pass
    return ""


def parse_shopee_url(url: str):
    """
    Ekstrak shop_id dan item_id dari berbagai format URL Shopee:
    - https://shopee.co.id/product/12345/67890
    - https://shopee.co.id/Nama-Produk-i.12345.67890
    - https://shopee.co.id/universal-link/product/12345/67890
    """
    cleaned = url.strip()
    
    # Format i.<shopid>.<itemid>
    match = re.search(r"i\.(\d+)\.(\d+)", cleaned)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # Format /product/<shopid>/<itemid>
    match = re.search(r"/product/(\d+)/(\d+)", cleaned)
    if match:
        return int(match.group(1)), int(match.group(2))

    # Jika link pendek (shope.ee / s.shopee.co.id), resolve redirect
    if "shope.ee" in cleaned or "s.shopee.co.id" in cleaned:
        try:
            print("Resolving short URL Shopee...")
            resp = requests.head(cleaned, allow_redirects=True, timeout=10)
            return parse_shopee_url(resp.url)
        except Exception as e:
            print(f"Gagal resolve redirect short link: {e}")

    return None, None


class ShopeeReviewScraper:
    def __init__(self, cookies: str = ""):
        self.session = requests.Session()
        self.cookies_str = cookies.strip() or get_saved_cookie_string()
        
        # Headers standar browser agar tidak dicurigai sebagai bot kasar
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://shopee.co.id/",
            "Accept": "application/json",
            "x-api-source": "rweb",
            "x-shopee-language": "id",
        }
        if self.cookies_str:
            self.headers["Cookie"] = self.cookies_str

    def scrape(
        self,
        shop_id: int,
        item_id: int,
        max_reviews: int = 100,
        star_filter: int = 0,     # 0: Semua, 1-5: Bintang 1-5
        with_media_only: bool = False,
        with_comment_only: bool = False,
        delay_per_page: float = 1.0,
    ):
        """
        Scrape ulasan produk Shopee melalui API endpoint get_ratings.
        """
        # Tentukan filter: 0 = Semua, 1 = Ada Komentar, 2 = Ada Media/Foto
        filter_type = 0
        if with_media_only:
            filter_type = 2
        elif with_comment_only:
            filter_type = 1

        all_reviews = []
        offset = 0
        limit = 50  # Shopee mengizinkan hingga ~50 ulasan per batch request
        
        print(f"\n[*] Memulai scraping ulasan untuk ShopID: {shop_id}, ItemID: {item_id}")
        print(f"[*] Target ulasan: {max_reviews} | Filter Bintang: {star_filter or 'Semua'}")

        while len(all_reviews) < max_reviews:
            current_limit = min(limit, max_reviews - len(all_reviews))
            
            # Endpoint v2 Shopee Ratings
            api_url = (
                f"https://shopee.co.id/api/v2/item/get_ratings?"
                f"itemid={item_id}&shopid={shop_id}"
                f"&offset={offset}&limit={current_limit}"
                f"&type={star_filter}&filter={filter_type}&flag=1"
            )

            try:
                response = self.session.get(api_url, headers=self.headers, timeout=15)
                
                if response.status_code == 403:
                    print("\n[!] Error 403 Forbidden: Shopee memblokir request.")
                    print("[!] Shopee memerlukan Cookie aktif dari browser.")
                    print("[!] Solusi: Buka shopee.co.id di browser, salin Cookie dari Inspect Element (Network tab),")
                    print("    lalu jalankan script dengan parameter --cookie \"<cookie_kamu>\"\n")
                    break
                
                if response.status_code != 200:
                    print(f"[!] Request gagal dengan HTTP status {response.status_code}: {response.text[:150]}")
                    break

                res_json = response.json()
                data = res_json.get("data")
                if not data:
                    print(f"[!] Respon API tidak memiliki atribut data: {res_json}")
                    break

                ratings = data.get("ratings") or []
                if not ratings:
                    print("[*] Tidak ada lagi ulasan tambahan yang ditemukan.")
                    break

                for r in ratings:
                    # Ambil varian produk jika ada
                    variant = ""
                    product_items = r.get("product_items") or []
                    if product_items and isinstance(product_items, list):
                        variant = product_items[0].get("model_name") or ""

                    # Ambil lampiran foto
                    image_hashes = r.get("images") or []
                    image_urls = [f"{SHOPEE_CDN_IMAGE}{h}" for h in image_hashes]

                    # Ambil video jika ada
                    video_urls = []
                    videos = r.get("videos") or []
                    for v in videos:
                        if isinstance(v, dict) and v.get("url"):
                            video_urls.append(v.get("url"))

                    # Respon penjual
                    seller_reply = ""
                    reply_obj = r.get("Item_rating_reply")
                    if reply_obj and isinstance(reply_obj, dict):
                        seller_reply = reply_obj.get("comment") or ""

                    # Format tanggal
                    ctime = r.get("ctime")
                    date_str = ""
                    if ctime:
                        try:
                            date_str = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            date_str = str(ctime)

                    review_item = {
                        "review_id": r.get("cmmtid"),
                        "username": r.get("author_username", "Anonim"),
                        "rating_bintang": r.get("rating_star", 0),
                        "tanggal": date_str,
                        "varian": variant,
                        "ulasan": (r.get("comment") or "").strip(),
                        "jumlah_foto": len(image_urls),
                        "link_foto": " | ".join(image_urls),
                        "jumlah_video": len(video_urls),
                        "link_video": " | ".join(video_urls),
                        "respon_penjual": seller_reply.strip(),
                        "like_count": r.get("like_count", 0),
                    }
                    all_reviews.append(review_item)

                    if len(all_reviews) >= max_reviews:
                        break

                print(f"[*] Berhasil mengambil {len(all_reviews)}/{max_reviews} ulasan...")
                offset += len(ratings)

                # Delay sopan agar tidak dianggap spam/DDoS
                time.sleep(delay_per_page)

            except Exception as exc:
                print(f"[!] Terjadi kesalahan saat request: {exc}")
                break

        print(f"\n[+] Total ulasan yang berhasil diekstrak: {len(all_reviews)}")
        return all_reviews


def save_to_csv(reviews: list, filename: str):
    """Simpan ke file CSV dengan encoding utf-8-sig (kompatibel Excel tanpa teks rusak)."""
    if not reviews:
        print("[!] Tidak ada data untuk disimpan ke CSV.")
        return

    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "review_id",
        "username",
        "rating_bintang",
        "tanggal",
        "varian",
        "ulasan",
        "jumlah_foto",
        "link_foto",
        "jumlah_video",
        "link_video",
        "respon_penjual",
        "like_count",
    ]

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(reviews)

    print(f"[✓] File CSV berhasil disimpan di: {path.resolve()}")


def save_to_json(reviews: list, filename: str):
    """Simpan ke file JSON terstruktur."""
    if not reviews:
        return

    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)

    print(f"[✓] File JSON berhasil disimpan di: {path.resolve()}")


def interactive_mode():
    """Mode interaktif jika pengguna menjalankan script tanpa argumen CLI."""
    print("=" * 60)
    print("     SHOPEE PRODUCT REVIEW SCRAPER (AKURAT & LENGKAP)      ")
    print("=" * 60)
    print("Tips: Masukkan URL produk Shopee dari browser Anda.")
    print("Contoh URL: https://shopee.co.id/product/42702581/23081198424\n")

    url = input("Masukkan URL Produk Shopee: ").strip()
    while not url:
        url = input("URL tidak boleh kosong. Masukkan URL: ").strip()

    shop_id, item_id = parse_shopee_url(url)
    if not shop_id or not item_id:
        print("[!] Format URL tidak dikenali. Pastikan URL memiliki shopid dan itemid.")
        return

    limit_input = input("Jumlah ulasan yang ingin diambil [default: 50]: ").strip()
    limit = int(limit_input) if limit_input.isdigit() else 50

    print("\nFilter Bintang:")
    print("0: Semua Bintang")
    print("1: Bintang 1 Saja")
    print("2: Bintang 2 Saja")
    print("3: Bintang 3 Saja")
    print("4: Bintang 4 Saja")
    print("5: Bintang 5 Saja")
    star_input = input("Pilih filter bintang [0-5, default: 0]: ").strip()
    star = int(star_input) if star_input in {"0", "1", "2", "3", "4", "5"} else 0

    print("\n[PENTING] Shopee sering kali memblokir akses tanpa Cookie (Error 403).")
    print("Jika Anda memiliki cookie dari browser (Chrome/Edge), tempel di sini.")
    print("Jika tidak ada, tekan ENTER untuk mencoba tanpa cookie.")
    cookie = input("Cookie Shopee (opsional): ").strip()

    scraper = ShopeeReviewScraper(cookies=cookie)
    reviews = scraper.scrape(shop_id=shop_id, item_id=item_id, max_reviews=limit, star_filter=star)

    if reviews:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_csv = f"data/outputs/shopee_reviews_{shop_id}_{item_id}_{timestamp}.csv"
        output_json = f"data/outputs/shopee_reviews_{shop_id}_{item_id}_{timestamp}.json"
        
        save_to_csv(reviews, output_csv)
        save_to_json(reviews, output_json)
        print("\n[✓] Selesai! Anda dapat membuka file CSV di Excel atau Google Sheets.")
    else:
        print("\n[!] Gagal mengambil ulasan. Ikuti petunjuk memasukkan Cookie di atas.")


def main():
    parser = argparse.ArgumentParser(description="Scrape ulasan produk Shopee secara akurat.")
    parser.add_argument("--url", type=str, help="URL produk Shopee")
    parser.add_argument("--shopid", type=int, help="Shop ID Shopee (jika tanpa --url)")
    parser.add_argument("--itemid", type=int, help="Item ID Shopee (jika tanpa --url)")
    parser.add_argument("--limit", type=int, default=50, help="Jumlah maksimal ulasan yang diambil (default: 50)")
    parser.add_argument("--star", type=int, default=0, choices=[0, 1, 2, 3, 4, 5], help="Filter rating bintang (0 = semua, 1-5 = bintang)")
    parser.add_argument("--media", action="store_true", help="Hanya ulasan yang memiliki foto/video")
    parser.add_argument("--comment", action="store_true", help="Hanya ulasan yang memiliki teks komentar")
    parser.add_argument("--cookie", type=str, default="", help="Cookie sesi Shopee untuk bypass blokir 403")
    parser.add_argument("--cookie-file", type=str, default="", help="File teks berisi cookie Shopee")
    parser.add_argument("--output", type=str, default="", help="Nama file output CSV (misal: hasil.csv)")

    args = parser.parse_args()

    # Jika tidak ada argumen sama sekali, masuk ke interactive mode
    if len(sys.argv) == 1:
        interactive_mode()
        return

    # Ambil cookie dari file jika diberikan
    cookie_str = args.cookie
    if args.cookie_file and os.path.exists(args.cookie_file):
        cookie_str = Path(args.cookie_file).read_text(encoding="utf-8").strip()

    shop_id = args.shopid
    item_id = args.itemid

    if args.url:
        parsed_shop, parsed_item = parse_shopee_url(args.url)
        if not parsed_shop or not parsed_item:
            print("[!] URL Shopee tidak valid.")
            sys.exit(1)
        shop_id = parsed_shop
        item_id = parsed_item

    if not shop_id or not item_id:
        print("[!] Berikan --url atau kombinasi --shopid dan --itemid.")
        sys.exit(1)

    scraper = ShopeeReviewScraper(cookies=cookie_str)
    reviews = scraper.scrape(
        shop_id=shop_id,
        item_id=item_id,
        max_reviews=args.limit,
        star_filter=args.star,
        with_media_only=args.media,
        with_comment_only=args.comment,
    )

    if reviews:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_csv = args.output or f"data/outputs/shopee_reviews_{shop_id}_{item_id}_{timestamp}.csv"
        output_json = output_csv.rsplit(".", 1)[0] + ".json"

        save_to_csv(reviews, output_csv)
        save_to_json(reviews, output_json)
    else:
        print("[!] Tidak ada data ulasan yang berhasil diambil.")


if __name__ == "__main__":
    main()

