import csv
import json
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

shop_id = 617908491
item_id = 12077537305
canonical_url = f"https://shopee.co.id/product/{shop_id}/{item_id}"
max_reviews = 50
output_csv = "data/outputs/kucadi_kursi_kantor_reviews.csv"
output_json = "data/outputs/kucadi_kursi_kantor_reviews.json"
SHOPEE_CDN_IMAGE = "https://down-id.img.susercontent.com/file/"

with open("data/shopee_cookies.json") as f:
    cookie_str = json.load(f)["cookie_string"]

print("=" * 65)
print("   SCRAPING ULASAN SHOPEE - KUCADI KURSI KANTOR (50 ULASAN)   ")
print("=" * 65)
print(f"[*] URL: {canonical_url}")
print(f"[*] Target Ulasan: {max_reviews}")
print("[*] Meluncurkan browser otomatis...")

collected_reviews = []
seen_ids = set()

with sync_playwright() as p:
    browser = p.chromium.launch(
        channel="chrome",
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 850},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.navigator.chrome = { runtime: {} };
    """)

    cookie_list = []
    for part in cookie_str.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            k = k.strip()
            v = v.strip()
            if k:
                cookie_list.append({"name": k, "value": v, "domain": ".shopee.co.id", "path": "/"})
    context.add_cookies(cookie_list)

    page = context.new_page()

    def handle_response(response):
        if "get_ratings" in response.url and response.status == 200:
            try:
                res_json = response.json()
                ratings = res_json.get("data", {}).get("ratings") or []
                for r in ratings:
                    cmmtid = r.get("cmmtid")
                    if cmmtid and cmmtid not in seen_ids:
                        seen_ids.add(cmmtid)

                        variant = ""
                        product_items = r.get("product_items") or []
                        if product_items and isinstance(product_items, list):
                            variant = product_items[0].get("model_name") or ""

                        image_hashes = r.get("images") or []
                        image_urls = [f"{SHOPEE_CDN_IMAGE}{h}" for h in image_hashes]
                        video_urls = [v.get("url") for v in (r.get("videos") or []) if isinstance(v, dict) and v.get("url")]

                        seller_reply = ""
                        reply_obj = r.get("Item_rating_reply")
                        if reply_obj and isinstance(reply_obj, dict):
                            seller_reply = reply_obj.get("comment") or ""

                        ctime = r.get("ctime")
                        date_str = ""
                        if ctime:
                            try:
                                # handle both seconds and ms
                                ts = ctime / 1000 if ctime > 30000000000 else ctime
                                date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                            except Exception:
                                date_str = str(ctime)

                        review_item = {
                            "review_id": cmmtid,
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
                        collected_reviews.append(review_item)
                        print(f"[+] Ulasan ke-{len(collected_reviews)}: ⭐{review_item['rating_bintang']} | {review_item['username']} ({review_item['varian'] or 'Standar'}): \"{review_item['ulasan'][:50]}...\"", flush=True)
            except Exception as exc:
                print("Error parsing response:", exc, flush=True)

    page.on("response", handle_response)

    print("[*] Membuka halaman produk Shopee...", flush=True)
    page.goto(canonical_url, wait_until="commit")
    page.wait_for_timeout(3000)

    # Dismiss modal jika ada
    try:
        page.keyboard.press("Escape")
        page.evaluate("() => { const m = document.querySelector('#modal'); if (m) m.remove(); }")
    except Exception:
        pass

    print("[*] Menggulir ke container ulasan pembeli...", flush=True)
    for y in range(800, 5200, 600):
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(800)

    # Tunggu komponen pagination ulasan termuat di DOM
    try:
        page.wait_for_selector(".shopee-page-controller, .product-ratings-comments, .shopee-product-rating", timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(2000)

    # Klik halaman selanjutnya secara berkala
    page_i = 1
    max_pages = (max_reviews // 5) + 5
    consecutive_fails = 0

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
            consecutive_fails += 1
            if consecutive_fails >= 3:
                print("[*] Tidak ada tombol halaman berikutnya lagi.", flush=True)
                break
            page.wait_for_timeout(2000)
            continue

        consecutive_fails = 0
        page_i += 1
        page.wait_for_timeout(2500)

    browser.close()

final_reviews = collected_reviews[:max_reviews]
print("\n" + "=" * 65)
print(f"[✓] SUKSES! Berhasil mengumpulkan {len(final_reviews)} ulasan produk KUCADI!")
print("=" * 65)

if final_reviews:
    p_csv = Path(output_csv)
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

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(final_reviews, f, ensure_ascii=False, indent=2)

    print(f"[✓] File CSV tersimpan: {p_csv.resolve()}")
    print(f"[✓] File JSON tersimpan: {Path(output_json).resolve()}")
