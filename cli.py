"""
MyTools Interactive Hybrid Terminal CLI
=======================================
Studio cepat lokal untuk Media, Web Scraping & Riset AI.
Dapat dijalankan langsung melalui double-click 'mytools.bat' atau 'python cli.py'.
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# Setup environment path
ROOT_DIR = Path(__file__).resolve().parent
os.chdir(ROOT_DIR)
sys.path.insert(0, str(ROOT_DIR / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT_DIR / "scripts"))

# ANSI Colors for terminal
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    GRAY = "\033[90m"

# Enable VT100 colors in Windows console
if sys.platform == "win32":
    os.system("color")


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    print(f"{Color.CYAN}{Color.BOLD}")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║                 MYTOOLS HYBRID TERMINAL                        ║")
    print("║         Studio Cepat: Media, Web Scraping & Riset AI           ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"{Color.RESET}")


def open_in_explorer(path: Path):
    if sys.platform == "win32":
        try:
            if path.is_file():
                subprocess.Popen(f'explorer /select,"{path.resolve()}"')
            else:
                subprocess.Popen(f'explorer "{path.resolve()}"')
        except Exception:
            pass


def open_file(path: Path):
    if sys.platform == "win32":
        try:
            os.startfile(str(path.resolve()))
        except Exception:
            pass


# -------------------------------------------------------------
# FITUR 1: SHOPEE REVIEW SCRAPER
# -------------------------------------------------------------
def menu_shopee():
    from scripts.shopee_playwright_scraper import scrape_with_playwright

    print(f"\n{Color.BOLD}{Color.YELLOW}=== [1] SHOPEE REVIEW SCRAPER (CSV & JSON) ==={Color.RESET}")
    url = input(f"{Color.BOLD}Masukkan URL Produk Shopee:{Color.RESET} ").strip()
    if not url:
        print(f"{Color.RED}[!] URL tidak boleh kosong.{Color.RESET}")
        return

    # Target ulasan
    lim_str = input(f"Target jumlah ulasan [50]: ").strip()
    limit = int(lim_str) if lim_str.isdigit() and int(lim_str) > 0 else 50

    # Filter rating bintang
    print("\nFilter Rating Bintang:")
    print(" [0] Semua Rating (Bintang 1 - 5)")
    print(" [5] ⭐⭐⭐⭐⭐ Hanya Bintang 5")
    print(" [4] ⭐⭐⭐⭐ Hanya Bintang 4")
    print(" [3] ⭐⭐⭐ Hanya Bintang 3")
    print(" [2] ⭐⭐ Hanya Bintang 2")
    print(" [1] ⭐ Hanya Bintang 1 (Ulasan Negatif)")
    star_str = input("Pilih filter [0]: ").strip()
    star = int(star_str) if star_str.isdigit() and 0 <= int(star_str) <= 5 else 0

    # Filter teks / media
    print("\nFilter Tambahan:")
    print(" [0] Semua ulasan (tanpa filter)")
    print(" [1] Hanya ulasan yang ada teks komentar")
    print(" [2] Hanya ulasan yang ada foto / video")
    filt_str = input("Pilih [0]: ").strip()
    with_comment = filt_str == "1"
    with_media = filt_str == "2"

    print(f"\n{Color.CYAN}[*] Menjalankan Playwright Scraper untuk: {url}{Color.RESET}")
    print(f"[*] Target: {limit} ulasan | Bintang: {star or 'Semua'} | Headless: True")

    try:
        reviews = scrape_with_playwright(
            url=url,
            max_reviews=limit,
            headless=True,
            star_filter=star,
            with_media=with_media,
            with_comment=with_comment,
        )

        if reviews:
            print(f"\n{Color.GREEN}{Color.BOLD}[✓] BERHASIL! Berhasil mengumpulkan {len(reviews)} ulasan.{Color.RESET}")
            # Pratinjau 3 ulasan teratas
            print(f"\n{Color.BOLD}Contoh Ulasan yang Tertangkap:{Color.RESET}")
            for i, r in enumerate(reviews[:3], 1):
                star_icon = "⭐" * r.get("rating_bintang", 5)
                print(f" {i}. [{r.get('username')}] {star_icon} ({r.get('varian') or 'Standar'}):")
                print(f"    \"{r.get('ulasan', '')[:90]}...\"")
                if r.get("jumlah_foto"):
                    print(f"    📸 Foto: {r.get('jumlah_foto')} gambar")

            ask = input(f"\n{Color.BOLD}Buka file CSV di Excel / Folder sekarang? (y/n) [y]: {Color.RESET}").strip().lower()
            if ask in ("", "y", "ya", "yes"):
                open_in_explorer(Path("data/outputs"))
        else:
            print(f"\n{Color.RED}[!] Tidak ada ulasan yang berhasil diambil.{Color.RESET}")
            print("[i] Pastikan sesi cookie Shopee Anda aktif via menu [6] Login Shopee.")

    except Exception as e:
        print(f"\n{Color.RED}[!] Terjadi kesalahan saat scraping: {e}{Color.RESET}")


# -------------------------------------------------------------
# FITUR 2: BATCH & SINGLE VIDEO DOWNLOADER
# -------------------------------------------------------------
def menu_video():
    from scripts.batch_video_downloader import download_batch_videos, download_single_video, DOWNLOADS_DIR

    print(f"\n{Color.BOLD}{Color.YELLOW}=== [2] VIDEO DOWNLOADER (TIKTOK, YOUTUBE, IG, FB, X) ==={Color.RESET}")
    print(" [1] 📹 Unduh 1 Video (Single Link)")
    print(" [2] 🚀 Unduh BANYAK Video Sekaligus (Multi-URL Paste)")
    print(" [3] 📄 Unduh dari File Teks (daftar_link.txt)")
    print(" [0] Kembali ke Menu Utama")

    choice = input(f"\n{Color.BOLD}Pilih opsi [1-3]: {Color.RESET}").strip()
    if choice == "0":
        return

    # Pilihan Kualitas / Format
    print(f"\nPilihan Format & Kualitas:")
    print(" [1] Video Resolusi Terbaik (MP4)")
    print(" [2] Hanya Musik / Audio (MP3)")
    print(" [3] Video 1080p Full HD")
    print(" [4] Video 720p HD")
    q_str = input("Pilih format [1]: ").strip()
    quality_map = {"1": "Terbaik", "2": "Audio", "3": "1080p", "4": "720p"}
    quality = quality_map.get(q_str, "Terbaik")

    urls = []
    if choice == "1":
        single_url = input(f"\n{Color.BOLD}Masukkan URL Video (TikTok / YouTube / IG / FB / X):{Color.RESET} ").strip()
        if single_url:
            urls = [single_url]
    elif choice == "2":
        print(f"\n{Color.CYAN}Tempelkan semua link video Anda di bawah ini.")
        print("Dapat paste puluhan link sekaligus. Tekan ENTER 2x (baris kosong) untuk mulai download:{Color.RESET}")
        lines = []
        while True:
            try:
                line = input()
                if not line.strip():
                    break
                # Handle jika ada multiple link dalam satu baris (dipisah spasi/koma)
                extracted = re.findall(r"https?://[^\s,]+", line)
                if extracted:
                    lines.extend(extracted)
                else:
                    lines.append(line.strip())
            except EOFError:
                break
        urls = lines
    elif choice == "3":
        txt_file = input(f"\n{Color.BOLD}Masukkan path file teks (misal: links.txt):{Color.RESET} ").strip()
        p = Path(txt_file)
        if p.is_file():
            content = p.read_text(encoding="utf-8", errors="ignore")
            urls = re.findall(r"https?://[^\s,]+", content)
            print(f"[✓] Berhasil menemukan {len(urls)} link dari file {p.name}.")
        else:
            print(f"{Color.RED}[!] File '{txt_file}' tidak ditemukan.{Color.RESET}")
            return

    if not urls:
        print(f"{Color.RED}[!] Tidak ada link yang dimasukkan.{Color.RESET}")
        return

    res = download_batch_videos(urls=urls, quality=quality, target_folder=DOWNLOADS_DIR)

    if res.get("success"):
        ask = input(f"\n{Color.BOLD}Buka folder video di Windows Explorer sekarang? (y/n) [y]: {Color.RESET}").strip().lower()
        if ask in ("", "y", "ya", "yes"):
            open_in_explorer(DOWNLOADS_DIR)


# -------------------------------------------------------------
# FITUR 3: HAPUS BACKGROUND FOTO
# -------------------------------------------------------------
def menu_removebg():
    from removebg.application.service import run_photo

    print(f"\n{Color.BOLD}{Color.YELLOW}=== [3] HAPUS BACKGROUND FOTO (AI INSPYRENET) ==={Color.RESET}")
    print(" [1] 🖼️  Proses 1 Foto")
    print(" [2] 📁 Proses BANYAK Foto Sekaligus (1 Folder Penuh)")
    print(" [0] Kembali ke Menu Utama")

    choice = input(f"\n{Color.BOLD}Pilih opsi [1-2]: {Color.RESET}").strip()
    if choice == "0":
        return

    out_dir = Path("data/outputs/removebg").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if choice == "1":
        img_path = input(f"{Color.BOLD}Masukkan path file foto (JPG/PNG/WebP):{Color.RESET} ").strip().strip('"')
        p = Path(img_path)
        if not p.is_file():
            print(f"{Color.RED}[!] File tidak ditemukan.{Color.RESET}")
            return
        print(f"[*] Memproses AI Background Remover untuk: {p.name}...")
        try:
            out_file = run_photo(path=str(p), mode="Orang / Umum", quality="Terbaik", points=[])
            final_p = out_dir / f"{p.stem}-transparent.png"
            shutil.move(out_file, str(final_p))
            print(f"{Color.GREEN}[✓] SUKSES! Tersimpan di: {final_p.resolve()}{Color.RESET}")
            open_file(final_p)
        except Exception as e:
            print(f"{Color.RED}[!] Gagal memproses: {e}{Color.RESET}")

    elif choice == "2":
        folder_path = input(f"{Color.BOLD}Masukkan path folder berisi foto:{Color.RESET} ").strip().strip('"')
        dir_p = Path(folder_path)
        if not dir_p.is_dir():
            print(f"{Color.RED}[!] Folder tidak ditemukan.{Color.RESET}")
            return

        image_files = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
            image_files.extend(dir_p.glob(ext))

        if not image_files:
            print(f"{Color.RED}[!] Tidak ada file gambar ditemukan di folder tersebut.{Color.RESET}")
            return

        print(f"\n{Color.CYAN}[*] Ditemukan {len(image_files)} foto. Memulai pemrosesan batch...{Color.RESET}")
        succ = 0
        for i, img in enumerate(image_files, 1):
            print(f"[{i}/{len(image_files)}] Memproses {img.name}...", end="", flush=True)
            try:
                out_file = run_photo(path=str(img), mode="Orang / Umum", quality="Terbaik", points=[])
                final_p = out_dir / f"{img.stem}-transparent.png"
                shutil.move(out_file, str(final_p))
                print(f" {Color.GREEN}[✓] Selesai{Color.RESET}")
                succ += 1
            except Exception as e:
                print(f" {Color.RED}[✗] Gagal: {e}{Color.RESET}")

        print(f"\n{Color.GREEN}{Color.BOLD}[✓] BATCH SELESAI: {succ}/{len(image_files)} foto berhasil dipotong background!{Color.RESET}")
        open_in_explorer(out_dir)


# -------------------------------------------------------------
# FITUR 4: TRANSKRIP AUDIO / VIDEO KE TEKS (WHISPER)
# -------------------------------------------------------------
def menu_transcribe():
    print(f"\n{Color.BOLD}{Color.YELLOW}=== [4] TRANSKRIP AUDIO / VIDEO (WHISPER AI) ==={Color.RESET}")
    file_path = input(f"{Color.BOLD}Masukkan path file video / audio (MP4/MP3/WAV/MKV):{Color.RESET} ").strip().strip('"')
    p = Path(file_path)
    if not p.is_file():
        print(f"{Color.RED}[!] File tidak ditemukan.{Color.RESET}")
        return

    from removebg.application.transcription import transcriber, load_audio_array
    import imageio_ffmpeg
    import av

    out_dir = Path("data/outputs/transkrip").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_txt = out_dir / f"{p.stem}-transkrip.txt"

    print(f"\n[*] Menyiapkan Whisper Speech-to-Text Model...")
    try:
        # Convert audio to wav mono 16khz
        temp_wav = out_dir / "temp_audio.wav"
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ffmpeg, "-y", "-i", str(p), "-ac", "1", "-ar", "16000", str(temp_wav)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        audio_data = load_audio_array(temp_wav)
        print("[*] Menganalisis ucapan & mentranskrip ke teks...")
        asr = transcriber()
        result = asr(audio_data["raw"], return_timestamps=True)
        temp_wav.unlink(missing_ok=True)

        text = result.get("text", "").strip()
        out_txt.write_text(text, encoding="utf-8")

        print(f"\n{Color.GREEN}{Color.BOLD}[✓] TRANSKRIP SELESAI!{Color.RESET}")
        print(f"Hasil teks tersimpan di: {out_txt.resolve()}")
        print(f"\n{Color.BOLD}Cuplikan Teks Transkrip:{Color.RESET}")
        print("-" * 50)
        print(text[:400] + ("..." if len(text) > 400 else ""))
        print("-" * 50)
        open_file(out_txt)
    except Exception as e:
        print(f"{Color.RED}[!] Gagal melakukan transkripsi: {e}{Color.RESET}")


# -------------------------------------------------------------
# FITUR 5: SISTEM PENDUKUNG KEPUTUSAN (SPK)
# -------------------------------------------------------------
def menu_spk():
    print(f"\n{Color.BOLD}{Color.YELLOW}=== [5] SISTEM PENDUKUNG KEPUTUSAN (SPK) ==={Color.RESET}")
    print("Modul SPK (TOPSIS, SAW, AHP) terintegrasi dengan database keputusan lokal.")
    print("Untuk visualisasi matriks kriteria dan perankingan grafik alternatif:")
    print("Sangat direkomendasikan membukanya di Web UI.")
    ask = input("\nBuka halaman SPK di Web UI sekarang? (y/n) [y]: ").strip().lower()
    if ask in ("", "y", "ya", "yes"):
        menu_open_web(path="/decision-support")


# -------------------------------------------------------------
# FITUR 6: LOGIN / CEK COOKIE SHOPEE
# -------------------------------------------------------------
def menu_shopee_session():
    print(f"\n{Color.BOLD}{Color.YELLOW}=== [6] PENGATURAN SESI LOGIN SHOPEE ==={Color.RESET}")
    from scripts.login_shopee_session import main as login_main, COOKIES_FILE

    if COOKIES_FILE.is_file():
        try:
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                total = d.get("total", 0)
                print(f"{Color.GREEN}[✓] File sesi Shopee terdeteksi: {total} cookies tersimpan di {COOKIES_FILE.name}{Color.RESET}")
        except Exception:
            pass

    print("\nPilihan:")
    print(" [1] 🚀 Buka Browser Chrome untuk Login (Bisa Scan QR via HP)")
    print(" [2] 📋 Tempel Cookie String Baru secara Manual")
    print(" [0] Kembali")

    c = input("\nPilih [1-2]: ").strip()
    if c == "1":
        login_main()
    elif c == "2":
        raw_cookie = input("\nTempelkan cookie lengkap Anda di sini:\n> ").strip()
        if raw_cookie:
            from removebg.application.shopee_scraping import save_cookie_string
            save_cookie_string(raw_cookie)
            print(f"{Color.GREEN}[✓] Cookie berhasil disimpan ke {COOKIES_FILE}!{Color.RESET}")


# -------------------------------------------------------------
# FITUR 7: BUKA WEB UI (LOCAL BROWSER)
# -------------------------------------------------------------
def menu_open_web(path: str = ""):
    print(f"\n{Color.CYAN}[*] Memeriksa status Web UI lokal di http://127.0.0.1:7860...{Color.RESET}")
    import urllib.request
    running = False
    try:
        with urllib.request.urlopen("http://127.0.0.1:7860/api/health", timeout=2) as resp:
            if resp.status == 200:
                running = True
    except Exception:
        running = False

    target_url = f"http://127.0.0.1:7860{path}"

    if running:
        print(f"{Color.GREEN}[✓] Web UI aktif! Membuka di browser: {target_url}{Color.RESET}")
        import webbrowser
        webbrowser.open(target_url)
    else:
        print(f"[*] Menjalankan server lokal MyTools di latar belakang...")
        subprocess.Popen(
            [sys.executable, "-m", "removebg.api"],
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
        )
        time.sleep(2.5)
        import webbrowser
        webbrowser.open(target_url)


# -------------------------------------------------------------
# MAIN LOOP
# -------------------------------------------------------------
def main_interactive():
    while True:
        clear_screen()
        print_banner()
        print(f" {Color.BOLD}Silakan pilih fitur yang ingin digunakan:{Color.RESET}\n")
        print(f"  {Color.GREEN}[1]{Color.RESET} 🛒 {Color.BOLD}Scraping Ulasan Shopee{Color.RESET} (CSV & JSON - Akurat)")
        print(f"  {Color.GREEN}[2]{Color.RESET} 🎬 {Color.BOLD}Video Downloader{Color.RESET} (TikTok, YouTube, IG, FB - Single & BANYAK)")
        print(f"  {Color.GREEN}[3]{Color.RESET} ✂️  {Color.BOLD}Hapus Background Foto{Color.RESET} (AI InSPyReNet - 1 Foto / Batch Folder)")
        print(f"  {Color.GREEN}[4]{Color.RESET} 🎙️  {Color.BOLD}Transkrip Audio / Video{Color.RESET} (Whisper AI ke Teks TXT)")
        print(f"  {Color.GREEN}[5]{Color.RESET} 📊 {Color.BOLD}Sistem Pendukung Keputusan{Color.RESET} (SPK TOPSIS / SAW / AHP)")
        print(f"  {Color.CYAN}[6]{Color.RESET} 🔑 {Color.BOLD}Kelola Sesi Login Shopee{Color.RESET} (QR Scan Helper)")
        print(f"  {Color.CYAN}[7]{Color.RESET} 🌐 {Color.BOLD}Buka Web UI di Browser{Color.RESET} (http://127.0.0.1:7860)")
        print(f"  {Color.RED}[0]{Color.RESET} 🚪 {Color.BOLD}Keluar{Color.RESET}")
        print("\n" + "─" * 65)

        pilihan = input(f"{Color.BOLD}Pilih nomor menu [0-7]: {Color.RESET}").strip()

        if pilihan == "1":
            menu_shopee()
        elif pilihan == "2":
            menu_video()
        elif pilihan == "3":
            menu_removebg()
        elif pilihan == "4":
            menu_transcribe()
        elif pilihan == "5":
            menu_spk()
        elif pilihan == "6":
            menu_shopee_session()
        elif pilihan == "7":
            menu_open_web()
        elif pilihan in ("0", "exit", "quit", "q"):
            print(f"\n{Color.CYAN}Terima kasih telah menggunakan MyTools! Sampai jumpa.{Color.RESET}\n")
            break
        else:
            print(f"\n{Color.RED}[!] Pilihan tidak valid. Tekan Enter untuk mengulang.{Color.RESET}")

        input(f"\n{Color.GRAY}Tekan ENTER untuk kembali ke Menu Utama...{Color.RESET}")


def main():
    parser = argparse.ArgumentParser(description="MyTools Hybrid Interactive CLI")
    parser.add_argument("command", nargs="?", choices=["shopee", "video", "removebg", "transcribe", "web"], help="Perintah langsung")
    parser.add_argument("--url", type=str, help="URL target")
    parser.add_argument("--batch", type=str, help="File teks berisi daftar link (untuk video)")
    parser.add_argument("--limit", type=int, default=50, help="Jumlah limit")
    parser.add_argument("--quality", type=str, default="Terbaik", help="Kualitas video (Terbaik, Audio, 1080p, 720p)")

    args = parser.parse_args()

    # Jika dipanggil tanpa argumen -> Masuk ke Menu Interaktif
    if not args.command:
        main_interactive()
        return

    # Direct CLI command handling
    if args.command == "video":
        from scripts.batch_video_downloader import download_batch_videos, DOWNLOADS_DIR
        urls = []
        if args.batch:
            p = Path(args.batch)
            if p.is_file():
                urls = re.findall(r"https?://[^\s,]+", p.read_text(encoding="utf-8"))
        elif args.url:
            urls = [args.url]
        if urls:
            download_batch_videos(urls, quality=args.quality, target_folder=DOWNLOADS_DIR)
        else:
            print("[!] Berikan --url atau --batch.")

    elif args.command == "shopee":
        from scripts.shopee_playwright_scraper import scrape_with_playwright
        if args.url:
            scrape_with_playwright(url=args.url, max_reviews=args.limit, headless=True)
        else:
            print("[!] Berikan --url.")

    elif args.command == "web":
        menu_open_web()


if __name__ == "__main__":
    main()
