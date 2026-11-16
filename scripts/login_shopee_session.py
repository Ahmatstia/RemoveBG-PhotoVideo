"""
Shopee Session Initializer & Login Helper
========================================
Skrip ini membuka jendela Google Chrome dengan profil data/shopee_profile.
Anda cukup login ke akun Shopee sekali saja (bisa scan QR via aplikasi Shopee di HP).
Setelah berhasil login, sesi dan seluruh cookie akan diekstrak dan disimpan otomatis ke:
1. data/shopee_cookies.json (digunakan otomatis oleh mode API Cepat dan Playwright)
2. data/shopee_profile (digunakan otomatis oleh Playwright persistent browser)
"""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

PROFILE_DIR = Path("data/shopee_profile").resolve()
COOKIES_FILE = Path("data/shopee_cookies.json").resolve()


def main():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("       SHOPEE SESSION INITIALIZER (LOGIN RESMI SEKALI SAJA)       ")
    print("=" * 65)
    print(f"[*] Lokasi profil browser: {PROFILE_DIR}")
    print("[*] Membuka Google Chrome...")
    print("[*] CARA LOGIN CEPAT:")
    print("    1. Pada jendela Chrome yang terbuka, Anda bisa scan QR dengan aplikasi Shopee di HP")
    print("       atau masukkan nomor HP / email Shopee Anda.")
    print("    2. Setelah berhasil masuk ke Shopee (muncul nama akun Anda):")
    print("    3. Tekan ENTER di terminal ini.\n")

    with sync_playwright() as p:
        chrome_exe = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        use_chrome = chrome_exe.is_file()

        launch_kwargs = {
            "user_data_dir": str(PROFILE_DIR),
            "headless": False,
            "viewport": {"width": 1280, "height": 850},
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if use_chrome:
            launch_kwargs["channel"] = "chrome"

        context = p.chromium.launch_persistent_context(**launch_kwargs)
        page = context.new_page()

        print("[*] Mengarahkan ke halaman login Shopee...")
        try:
            page.goto("https://shopee.co.id/buyer/login", wait_until="commit")
        except Exception:
            pass

        try:
            input("\n--> Tekan ENTER di sini setelah Anda selesai login di jendela Chrome... ")
        except (KeyboardInterrupt, EOFError):
            pass

        # Ekstrak semua cookies
        cookies = context.cookies()
        context.close()

    cookie_parts = [f"{c['name']}={c['value']}" for c in cookies]
    cookie_str = "; ".join(cookie_parts)

    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "cookies": cookies,
            "cookie_string": cookie_str,
            "total": len(cookies),
        }, f, indent=2)

    has_login_token = any(c['name'] in ('SPC_EC', 'SPC_U', 'SPC_SI') for c in cookies)

    print("\n" + "=" * 65)
    print(f"[✓] Berhasil menyimpan {len(cookies)} cookies ke {COOKIES_FILE}!")
    if has_login_token:
        print("[✓] Status Sesi: TERVERIFIKASI LOGIN (SPC_EC / User ID ditemukan).")
    else:
        print("[!] Perhatian: Token login belum terdeteksi. Pastikan Anda telah menyelesaikan login di jendela browser.")
    print("[✓] Sekarang Anda bisa melakukan scraping Shopee dengan lancar di UI atau Terminal!")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
