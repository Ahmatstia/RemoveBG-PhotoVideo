"""
Shopee Review Scraper via Playwright (Browser Automation)
========================================================
Skrip ini menggunakan browser Playwright otomatis sehingga:
1. Memuat seluruh JavaScript, cookie, dan token anti-bot Shopee secara alami.
2. Menggunakan cookie sesi Shopee yang tersimpan di data/shopee_cookies.json atau lewat --cookie.
3. Menghapus overlay modal Shopee dan melakukan paginasi klik otomatis lewat JavaScript.
4. Menyimpan hasil lengkap ke CSV (UTF-8 BOM siap buka di Excel) dan JSON.
"""

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

SHOPEE_CDN_IMAGE = "https://down-id.img.susercontent.com/file/"
COOKIES_FILE = Path("data/shopee_cookies.json").resolve()


def parse_shopee_url(url: str):
    cleaned = str(url or "").strip()
    match = re.search(r"i\.(\d+)\.(\d+)", cleaned)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"/product/(\d+)/(\d+)", cleaned)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def get_saved_cookie_string() -> str:
    if COOKIES_FILE.is_file():
        try:
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return (data.get("cookie_string") or "").strip()
        except Exception:
            pass
    return ""


def scrape_with_playwright(
    url: str,
    max_reviews: int = 50,
    headless: bool = True,
    cookie: str = "",
    star_filter: int = 0,
    with_media: bool = False,
    with_comment: bool = False,
    output_csv: str = "",
):
    shop_id, item_id = parse_shopee_url(url)
    if not shop_id or not item_id:
        print("[!] URL produk Shopee tidak valid. Pastikan memuat ID Toko dan ID Produk.")
        return []

    canonical_url = f"https://shopee.co.id/product/{shop_id}/{item_id}"
    effective_cookie = cookie.strip() or get_saved_cookie_string()

    print("\n" + "=" * 60)
    print("      SHOPEE SCRAPER - AUTOMATED BROWSER (PLAYWRIGHT)       ")
    print("=" * 60)
    print(f"[*] URL Canonical: {canonical_url}")
    print(f"[*] Target Ulasan: {max_reviews}")
    print(f"[*] Filter Bintang: {star_filter or 'Semua'}")
    print(f"[*] Mode Headless: {headless}")
    print(f"[*] Cookie sesi terdeteksi: {'Ya' if effective_cookie else 'Tidak'}")
    print("[*] Membuka browser Chrome...")

    collected_reviews = []
    seen_ids = set()

    with sync_playwright() as p:
        chrome_exe = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        use_chrome = chrome_exe.is_file()

        launch_kwargs = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        }
        if use_chrome:
            launch_kwargs["channel"] = "chrome"

        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            viewport={"width": 1280, "height": 850},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )

        # Inject cookie jika ada
        if effective_cookie:
            cookie_list = []
            for part in effective_cookie.split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if k:
                        cookie_list.append({
                            "name": k,
                            "value": v,
                            "domain": ".shopee.co.id",
                            "path": "/",
                        })
            if cookie_list:
                try:
                    context.add_cookies(cookie_list)
                    print(f"[*] Berhasil menyematkan {len(cookie_list)} cookie sesi login.")
                except Exception as exc:
                    print(f"[!] Gagal menyematkan cookies: {exc}")

        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
        """)

        page = context.new_page()

        def parse_ratings_list(ratings):
            added = 0
            for r in ratings:
                star = r.get("rating_star", 0)
                if star_filter > 0 and star != star_filter:
                    continue

                comment = (r.get("comment") or "").strip()
                if with_comment and not comment:
                    continue

                image_hashes = r.get("images") or []
                image_urls = [f"{SHOPEE_CDN_IMAGE}{h}" for h in image_hashes]
                video_urls = [v.get("url") for v in (r.get("videos") or []) if isinstance(v, dict) and v.get("url")]

                if with_media and not (image_urls or video_urls):
                    continue

                cmmtid = r.get("cmmtid")
                if cmmtid and cmmtid not in seen_ids:
                    seen_ids.add(cmmtid)

                    variant = ""
                    product_items = r.get("product_items") or []
                    if product_items and isinstance(product_items, list):
                        variant = product_items[0].get("model_name") or ""

                    seller_reply = ""
                    reply_obj = r.get("Item_rating_reply")
                    if reply_obj and isinstance(reply_obj, dict):
                        seller_reply = reply_obj.get("comment") or ""

                    ctime = r.get("ctime")
                    date_str = ""
                    if ctime:
                        try:
                            date_str = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            date_str = str(ctime)

                    review_item = {
                        "review_id": cmmtid,
                        "username": r.get("author_username", "Anonim"),
                        "rating_bintang": star,
                        "tanggal": date_str,
                        "varian": variant,
                        "ulasan": comment,
                        "jumlah_foto": len(image_urls),
                        "link_foto": " | ".join(image_urls),
                        "jumlah_video": len(video_urls),
                        "link_video": " | ".join(video_urls),
                        "respon_penjual": seller_reply.strip(),
                        "like_count": r.get("like_count", 0),
                    }
                    collected_reviews.append(review_item)
                    added += 1
                    print(f"[+] Berhasil mengambil {len(collected_reviews)}/{max_reviews} ulasan...")
            return added

        def handle_response(response):
            if "get_ratings" in response.url and response.status == 200:
                try:
                    res_json = response.json()
                    ratings = res_json.get("data", {}).get("ratings") or []
                    parse_ratings_list(ratings)
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            print("[*] Membuka halaman produk Shopee...")
            try:
                page.goto(canonical_url, wait_until="commit", timeout=20000)
            except Exception:
                pass
            page.wait_for_timeout(3000)

            # Dismiss modal popup jika ada
            try:
                page.keyboard.press("Escape")
                page.evaluate("() => { const m = document.querySelector('#modal'); if (m) m.remove(); }")
            except Exception:
                pass

            print("[*] Menggulir ke bagian ulasan pembeli...")
            for _ in range(8):
                page.mouse.wheel(0, 700)
                page.wait_for_timeout(800)

            page.wait_for_timeout(2000)

            # Paginasi halaman selanjutnya lewat JavaScript click
            page_i = 1
            max_pages = min(50, (max_reviews // 5) + 3)

            while len(collected_reviews) < max_reviews and page_i <= max_pages:
                clicked = page.evaluate("""() => {
                    const btn = document.querySelector('.shopee-page-controller button.shopee-icon-button--right');
                    if (btn && !btn.disabled) {
                        btn.click();
                        return true;
                    }
                    return false;
                }""")

                if not clicked:
                    next_page_num = page_i + 1
                    clicked = page.evaluate(f"""() => {{
                        const btns = Array.from(document.querySelectorAll('.shopee-page-controller button'));
                        const target = btns.find(b => b.innerText.trim() === '{next_page_num}');
                        if (target) {{
                            target.click();
                            return true;
                        }}
                        return false;
                    }}""")

                if not clicked:
                    break

                page_i += 1
                page.wait_for_timeout(2500)

        except Exception as e:
            print(f"[!] Terjadi kesalahan navigasi: {e}")
        finally:
            browser.close()

    final_reviews = collected_reviews[:max_reviews]
    print(f"\n[✓] Selesai! Berhasil mengumpulkan {len(final_reviews)} ulasan.")

    if final_reviews:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_csv = output_csv or f"data/outputs/shopee_playwright_{shop_id}_{item_id}_{timestamp}.csv"
        final_json = final_csv.rsplit(".", 1)[0] + ".json"

        p_csv = Path(final_csv)
        p_csv.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "review_id", "username", "rating_bintang", "tanggal", "varian",
            "ulasan", "jumlah_foto", "link_foto", "jumlah_video", "link_video",
            "respon_penjual", "like_count"
        ]
        with open(p_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(final_reviews)

        with open(final_json, "w", encoding="utf-8") as f:
            json.dump(final_reviews, f, ensure_ascii=False, indent=2)

        print(f"[✓] File CSV tersimpan: {p_csv.resolve()}")
        print(f"[✓] File JSON tersimpan: {Path(final_json).resolve()}")

    return final_reviews


def main():
    parser = argparse.ArgumentParser(description="Scrape ulasan Shopee dengan Playwright Browser.")
    parser.add_argument("--url", type=str, required=True, help="URL produk Shopee")
    parser.add_argument("--limit", type=int, default=50, help="Jumlah ulasan target (default: 50)")
    parser.add_argument("--headless", action="store_true", help="Jalankan headless")
    parser.add_argument("--cookie", type=str, default="", help="Cookie sesi Shopee login (opsional)")
    parser.add_argument("--star", type=int, default=0, help="Filter rating bintang (0 = semua, 1-5)")
    parser.add_argument("--media", action="store_true", help="Hanya ulasan yang memiliki foto/video")
    parser.add_argument("--comment", action="store_true", help="Hanya ulasan yang memiliki teks ulasan")
    parser.add_argument("--output", type=str, default="", help="Nama path file output CSV")

    args = parser.parse_args()
    scrape_with_playwright(
        url=args.url,
        max_reviews=args.limit,
        headless=args.headless,
        cookie=args.cookie,
        star_filter=args.star,
        with_media=args.media,
        with_comment=args.comment,
        output_csv=args.output,
    )


if __name__ == "__main__":
    main()
