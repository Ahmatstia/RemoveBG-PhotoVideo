import csv
import json
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

shop_id = 617908491
item_id = 12077537305
canonical_url = f"https://shopee.co.id/product/{shop_id}/{item_id}"
SHOPEE_CDN_IMAGE = "https://down-id.img.susercontent.com/file/"

with open('data/shopee_cookies.json') as f:
    cookie_str = json.load(f)['cookie_string']

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--disable-blink-features=AutomationControlled'])
    context = browser.new_context(
        viewport={'width': 1280, 'height': 850},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    )
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

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

    intercepted = []
    seen_ids = set()

    def on_res(response):
        if 'get_ratings' in response.url and response.status == 200:
            try:
                data = response.json()
                rats = data.get('data', {}).get('ratings') or []
                for r in rats:
                    cid = r.get('cmmtid')
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        variant = ""
                        p_items = r.get("product_items") or []
                        if p_items and isinstance(p_items, list):
                            variant = p_items[0].get("model_name") or ""

                        img_hashes = r.get("images") or []
                        img_urls = [f"{SHOPEE_CDN_IMAGE}{h}" for h in img_hashes]
                        vid_urls = [v.get("url") for v in (r.get("videos") or []) if isinstance(v, dict) and v.get("url")]

                        seller_reply = ""
                        reply_obj = r.get("Item_rating_reply")
                        if reply_obj and isinstance(reply_obj, dict):
                            seller_reply = reply_obj.get("comment") or ""

                        ctime = r.get("ctime")
                        date_str = ""
                        if ctime:
                            try:
                                ts = ctime / 1000 if ctime > 30000000000 else ctime
                                date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                            except Exception:
                                date_str = str(ctime)

                        item = {
                            "review_id": cid,
                            "username": r.get("author_username", "Anonim"),
                            "rating_bintang": r.get("rating_star", 0),
                            "tanggal": date_str,
                            "varian": variant,
                            "ulasan": (r.get("comment") or "").strip(),
                            "jumlah_foto": len(img_urls),
                            "link_foto": " | ".join(img_urls),
                            "jumlah_video": len(vid_urls),
                            "link_video": " | ".join(vid_urls),
                            "respon_penjual": seller_reply.strip(),
                            "like_count": r.get("like_count", 0),
                        }
                        intercepted.append(item)
                print(f"[PAGE INTERCEPT] Got ratings! Total now: {len(intercepted)}", flush=True)
            except Exception as e:
                pass

    page.on('response', on_res)

    print("Membuka produk KUCADI...", flush=True)
    page.goto(canonical_url, wait_until='commit')
    page.wait_for_timeout(3000)

    print("Menggulir halaman...", flush=True)
    for y in range(800, 5200, 600):
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(800)

    # Click next page via JS click for 9 more pages (target ~50-60 reviews)
    for page_i in range(2, 11):
        page.evaluate("""() => {
            const btn = document.querySelector('.shopee-page-controller button.shopee-icon-button--right');
            if (btn && !btn.disabled) {
                btn.click();
            }
        }""")
        page.wait_for_timeout(2500)
        if len(intercepted) >= 50:
            break

    print(f"\n[✓] BERHASIL! Total Ulasan Terkumpul: {len(intercepted)} ulasan.")
    
    # Save files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = f"data/outputs/ulasan_kucadi_{timestamp}.csv"
    out_json = f"data/outputs/ulasan_kucadi_{timestamp}.json"
    
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "review_id", "username", "rating_bintang", "tanggal", "varian",
        "ulasan", "jumlah_foto", "link_foto", "jumlah_video", "link_video",
        "respon_penjual", "like_count"
    ]
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(intercepted)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(intercepted, f, ensure_ascii=False, indent=2)

    print(f"[✓] File CSV: {Path(out_csv).resolve()}")
    print(f"[✓] File JSON: {Path(out_json).resolve()}")

    browser.close()
