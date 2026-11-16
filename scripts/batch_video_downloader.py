"""
Batch & Single Video Downloader Helper
======================================
Mendukung unduh video tunggal atau banyak sekaligus (batch multi-URL):
- TikTok (TikWM tanpa watermark, auto fallback)
- YouTube (Video HD / Audio MP3)
- Instagram Reels / Post
- Twitter / X / Facebook / Link umum
"""

import os
import re
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from removebg.application.youtube_download import run_tiktok_video_download, run_video_download
from removebg.config import OUTPUTS, prepare_dirs


DOWNLOADS_DIR = Path("data/outputs/downloads").resolve()


def detect_platform(url: str) -> str:
    cleaned = str(url or "").strip().lower()
    parsed = urlparse(cleaned)
    host = (parsed.hostname or "").removeprefix("www.")

    if any(d in host for d in ("tiktok.com", "douyin.com", "vt.tiktok.com", "vm.tiktok.com")):
        return "TikTok"
    if any(d in host for d in ("youtube.com", "youtu.be")):
        return "YouTube"
    if "instagram.com" in host:
        return "Instagram"
    if any(d in host for d in ("twitter.com", "x.com")):
        return "Twitter/X"
    return "Link umum"


def download_single_video(
    url: str,
    quality: str = "Terbaik",
    target_folder: Path = DOWNLOADS_DIR,
    progress_callback = None,
    cancel_event: threading.Event = None,
) -> dict:
    if cancel_event is None:
        cancel_event = threading.Event()
    if progress_callback is None:
        progress_callback = lambda fraction, msg: None

    target_folder.mkdir(parents=True, exist_ok=True)
    platform = detect_platform(url)

    result = None
    # Khusus TikTok, prioritaskan TikWM (tanpa watermark & tanpa login)
    if platform == "TikTok":
        try:
            result = run_tiktok_video_download(url, output_name="", progress=progress_callback, cancel=cancel_event)
        except Exception as e:
            # Fallback ke general yt-dlp jika TikWM gagal
            progress_callback(0.1, f"TikWM dialihkan ke engine sekunder: {e}")
            result = run_video_download(url, platform="TikTok", quality=quality, output_name="", progress=progress_callback, cancel=cancel_event)
    else:
        result = run_video_download(url, platform=platform, quality=quality, output_name="", progress=progress_callback, cancel=cancel_event)

    # Pindahkan hasil akhir ke target_folder
    src_path = Path(result["path"])
    final_path = target_folder / src_path.name
    if final_path != src_path:
        shutil.move(str(src_path), str(final_path))
        # Bersihkan folder UUID sementara
        shutil.rmtree(src_path.parent, ignore_errors=True)

    result["path"] = str(final_path)
    result["filename"] = final_path.name
    result["platform"] = platform
    return result


def download_batch_videos(
    urls: list[str],
    quality: str = "Terbaik",
    target_folder: Path = DOWNLOADS_DIR,
) -> dict:
    clean_urls = [u.strip() for u in urls if u and u.strip().startswith(("http://", "https://"))]
    if not clean_urls:
        return {"success": [], "failed": [], "total": 0}

    target_folder.mkdir(parents=True, exist_ok=True)
    total = len(clean_urls)
    success = []
    failed = []

    print(f"\n[*] Memulai proses Batch Download ({total} video)...")
    print(f"[*] Folder penyimpanan: {target_folder}\n")

    for index, url in enumerate(clean_urls, 1):
        platform = detect_platform(url)
        print(f"[{index}/{total}] [{platform}] {url}")

        last_msg = ""
        def on_progress(fraction, message):
            nonlocal last_msg
            if message != last_msg:
                last_msg = message
                pct = int(fraction * 100)
                sys.stdout.write(f"\r      ⏳ {pct}% - {message[:55]}...")
                sys.stdout.flush()

        try:
            res = download_single_video(
                url=url,
                quality=quality,
                target_folder=target_folder,
                progress_callback=on_progress,
            )
            file_mb = round(Path(res["path"]).stat().st_size / (1024 * 1024), 2)
            sys.stdout.write("\r" + " " * 75 + "\r")
            print(f"      [✓] SUKSES: {res['filename']} ({file_mb} MB)")
            success.append(res)
        except Exception as exc:
            sys.stdout.write("\r" + " " * 75 + "\r")
            print(f"      [✗] GAGAL: {exc}")
            failed.append({"url": url, "error": str(exc)})

        # Jeda sejenak antar link agar ramah server
        time.sleep(1.0)

    print("\n" + "=" * 65)
    print(f"[✓] RINGKASAN BATCH: {len(success)}/{total} Berhasil Diunduh!")
    if failed:
        print(f"[!] {len(failed)} link gagal diproses.")
    print(f"📂 Folder Hasil: {target_folder.resolve()}")
    print("=" * 65)

    return {"success": success, "failed": failed, "total": total, "folder": str(target_folder)}
