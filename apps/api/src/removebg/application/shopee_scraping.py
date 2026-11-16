import csv
import json
import logging
import os
import re
import shutil
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests

from removebg.application.service import safe_name
from removebg.config import OUTPUTS, prepare_dirs
from removebg.domain import Cancelled

logger = logging.getLogger(__name__)
SHOPEE_CDN_IMAGE = "https://down-id.img.susercontent.com/file/"
PROFILE_DIR = Path("data/shopee_profile").resolve()
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


def save_cookie_string(cookie_str: str):
    if not cookie_str or not cookie_str.strip():
        return
    try:
        COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        cookies_list = []
        for part in cookie_str.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                k = k.strip()
                v = v.strip()
                if k:
                    cookies_list.append({"name": k, "value": v, "domain": ".shopee.co.id", "path": "/"})
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump({"cookies": cookies_list, "cookie_string": cookie_str.strip(), "total": len(cookies_list)}, f, indent=2)
    except Exception as e:
        logger.warning(f"Gagal menyimpan cookies: {e}")


def parse_shopee_url(url: str):
    cleaned = str(url or "").strip()
    match = re.search(r"i\.(\d+)\.(\d+)", cleaned)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"/product/(\d+)/(\d+)", cleaned)
    if match:
        return int(match.group(1)), int(match.group(2))
    if "shope.ee" in cleaned or "s.shopee.co.id" in cleaned:
        try:
            resp = requests.head(cleaned, allow_redirects=True, timeout=10)
            return parse_shopee_url(resp.url)
        except Exception:
            pass
    return None, None


def run_shopee_scraping_api(
    shop_id: int,
    item_id: int,
    max_reviews: int,
    star_filter: int,
    with_media_only: bool,
    with_comment_only: bool,
    cookies: str,
    progress,
    cancel: threading.Event,
):
    filter_type = 0
    if with_media_only:
        filter_type = 2
    elif with_comment_only:
        filter_type = 1

    session = requests.Session()
    canonical_url = f"https://shopee.co.id/product/{shop_id}/{item_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": canonical_url,
        "Accept": "application/json",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        "x-api-source": "rweb",
        "x-shopee-language": "id",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }
    if cookies and cookies.strip():
        headers["Cookie"] = cookies.strip()
        csrf_match = re.search(r"csrftoken=([a-zA-Z0-9_-]+)", cookies)
        if csrf_match:
            headers["x-csrftoken"] = csrf_match.group(1)

    all_reviews = []
    offset = 0
    limit = 50

    while len(all_reviews) < max_reviews:
        if cancel.is_set():
            raise Cancelled("Proses dibatalkan.")

        current_limit = min(limit, max_reviews - len(all_reviews))
        api_url = (
            f"https://shopee.co.id/api/v2/item/get_ratings?"
            f"itemid={item_id}&shopid={shop_id}"
            f"&offset={offset}&limit={current_limit}"
            f"&type={star_filter}&filter={filter_type}&flag=1"
        )

        progress(
            min(0.9, len(all_reviews) / max_reviews) if max_reviews else 0.1,
            f"Mengambil ulasan Shopee ({len(all_reviews)}/{max_reviews})…",
        )

        try:
            response = session.get(api_url, headers=headers, timeout=15)
        except Exception as exc:
            raise ValueError(f"Koneksi ke Shopee gagal: {exc}") from exc

        if response.status_code == 403 or (response.status_code == 200 and "error" in response.text and "90309999" in response.text):
            raise ValueError(
                "Shopee membatasi ulasan untuk sesi ini (Error 90309999). "
                "Gunakan mode Browser Otomatis (Playwright) atau perbarui Cookie Shopee login Anda."
            )

        if response.status_code != 200:
            raise ValueError(f"Shopee merespons dengan status HTTP {response.status_code}.")

        try:
            res_json = response.json()
        except Exception:
            raise ValueError("Respon Shopee bukan format JSON yang valid.")

        data = res_json.get("data") or {}
        ratings = data.get("ratings") or []
        if not ratings:
            break

        for r in ratings:
            variant = ""
            product_items = r.get("product_items") or []
            if product_items and isinstance(product_items, list):
                variant = product_items[0].get("model_name") or ""

            image_hashes = r.get("images") or []
            image_urls = [f"{SHOPEE_CDN_IMAGE}{h}" for h in image_hashes]

            video_urls = []
            for v in r.get("videos") or []:
                if isinstance(v, dict) and v.get("url"):
                    video_urls.append(v.get("url"))

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

        offset += len(ratings)
        time.sleep(0.4)

    return all_reviews


def run_shopee_scraping_playwright(
    shop_id: int,
    item_id: int,
    max_reviews: int,
    star_filter: int,
    with_media_only: bool,
    with_comment_only: bool,
    cookies: str,
    progress,
    cancel: threading.Event,
):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ValueError("Playwright belum terpasang.")

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    canonical_url = f"https://shopee.co.id/product/{shop_id}/{item_id}"

    progress(0.05, "Membuka browser Playwright terisolasi…")
    collected_reviews = []
    seen_ids = set()

    with sync_playwright() as p:
        chrome_exe = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        use_chrome_channel = chrome_exe.is_file()

        launch_kwargs = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        }
        if use_chrome_channel:
            launch_kwargs["channel"] = "chrome"

        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            viewport={"width": 1280, "height": 850},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )

        # Inject cookie jika ada
        if cookies and cookies.strip():
            cookie_list = []
            for part in cookies.split(";"):
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
                except Exception as exc:
                    logger.warning(f"Gagal menambahkan cookie ke Playwright: {exc}")

        # Mask webdriver
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
        """)

        page = context.new_page()

        def parse_ratings_list(ratings):
            added = 0
            for r in ratings:
                # Apply filter jika dispesifikasikan
                star = r.get("rating_star", 0)
                if star_filter > 0 and star != star_filter:
                    continue
                
                comment = (r.get("comment") or "").strip()
                if with_comment_only and not comment:
                    continue

                image_hashes = r.get("images") or []
                image_urls = [f"{SHOPEE_CDN_IMAGE}{h}" for h in image_hashes]
                video_urls = [v.get("url") for v in (r.get("videos") or []) if isinstance(v, dict) and v.get("url")]

                if with_media_only and not (image_urls or video_urls):
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

                    collected_reviews.append({
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
                    })
                    added += 1
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
            progress(0.15, "Membuka halaman produk Shopee…")
            try:
                page.goto(canonical_url, wait_until="commit", timeout=20000)
            except Exception:
                pass
            page.wait_for_timeout(3000)

            # Dismiss modal popup / overlay jika ada
            try:
                page.keyboard.press("Escape")
                page.evaluate("() => { const m = document.querySelector('#modal'); if (m) m.remove(); }")
            except Exception:
                pass

            # Scroll ke ulasan
            progress(0.25, "Menggulir ke bagian ulasan pembeli…")
            for y in range(800, 5200, 600):
                if cancel.is_set():
                    raise Cancelled("Proses dibatalkan.")
                page.mouse.wheel(0, 600)
                page.wait_for_timeout(700)

            # Berikan waktu agar ulasan halaman pertama selesai dimuat
            page.wait_for_timeout(2000)

            # Paginasi klik tombol Next via JS agar terhindar dari overlay pointer events
            max_pages = min(50, (max_reviews // 5) + 3)
            page_i = 1

            while len(collected_reviews) < max_reviews and page_i <= max_pages:
                if cancel.is_set():
                    raise Cancelled("Proses dibatalkan.")

                progress(
                    min(0.95, 0.3 + (len(collected_reviews) / max_reviews) * 0.65),
                    f"Mengambil ulasan Shopee ({len(collected_reviews)}/{max_reviews})…",
                )

                clicked = page.evaluate("""() => {
                    const btn = document.querySelector('.shopee-page-controller button.shopee-icon-button--right');
                    if (btn && !btn.disabled) {
                        btn.click();
                        return true;
                    }
                    return false;
                }""")

                if not clicked:
                    # Coba klik berdasarkan nomor halaman jika tombol panah tidak ada
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
                    # Tidak ada halaman berikutnya lagi
                    break

                page_i += 1
                page.wait_for_timeout(2500)

        finally:
            browser.close()

    return collected_reviews[:max_reviews]


def run_shopee_scrape(
    url: str,
    max_reviews: int = 50,
    star_filter: int = 0,
    with_media_only: bool = False,
    with_comment_only: bool = False,
    cookies: str = "",
    use_browser: bool = False,
    output_name: str = "",
    progress = None,
    cancel: threading.Event = None,
):
    if progress is None:
        progress = lambda fraction, description: None
    if cancel is None:
        cancel = threading.Event()

    shop_id, item_id = parse_shopee_url(url)
    if not shop_id or not item_id:
        raise ValueError("URL Shopee tidak valid. Pastikan link produk memuat Shop ID dan Item ID.")

    effective_cookie = (cookies or "").strip()
    if not effective_cookie:
        effective_cookie = get_saved_cookie_string()
    else:
        save_cookie_string(effective_cookie)

    prepare_dirs()
    job_dir = OUTPUTS / uuid.uuid4().hex[:12]
    job_dir.mkdir(parents=True, exist_ok=True)

    progress(0.02, "Memeriksa tautan produk Shopee…")
    reviews = []

    if not use_browser:
        try:
            reviews = run_shopee_scraping_api(
                shop_id=shop_id,
                item_id=item_id,
                max_reviews=max_reviews,
                star_filter=star_filter,
                with_media_only=with_media_only,
                with_comment_only=with_comment_only,
                cookies=effective_cookie,
                progress=progress,
                cancel=cancel,
            )
        except Exception as exc:
            logger.info(f"API mode tidak berhasil ({exc}), beralih otomatis ke Playwright browser.")
            reviews = []

    # Jika mode Playwright dipilih atau jika API mode memerlukan browser context
    if not reviews:
        reviews = run_shopee_scraping_playwright(
            shop_id=shop_id,
            item_id=item_id,
            max_reviews=max_reviews,
            star_filter=star_filter,
            with_media_only=with_media_only,
            with_comment_only=with_comment_only,
            cookies=effective_cookie,
            progress=progress,
            cancel=cancel,
        )

    if not reviews:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise ValueError(
            "Gagal mengambil ulasan produk Shopee. Pastikan Cookie login Shopee masih aktif dan valid."
        )

    title = safe_name(output_name, f"ulasan-shopee-{shop_id}-{item_id}")
    csv_path = job_dir / f"{title}.csv"
    json_path = job_dir / f"{title}.json"

    fieldnames = [
        "review_id", "username", "rating_bintang", "tanggal", "varian",
        "ulasan", "jumlah_foto", "link_foto", "jumlah_video", "link_video",
        "respon_penjual", "like_count",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(reviews)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)

    progress(1.0, f"Selesai. Berhasil mengekstrak {len(reviews)} ulasan.")

    return {
        "title": title,
        "total_reviews": len(reviews),
        "path_csv": str(csv_path),
        "path_json": str(json_path),
        "preview_rows": reviews[:10],
    }
