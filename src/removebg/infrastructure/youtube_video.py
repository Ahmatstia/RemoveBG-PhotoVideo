import threading
from pathlib import Path

import imageio_ffmpeg
from yt_dlp import YoutubeDL

from removebg.domain import Cancelled
FORMATS = {
    "Terbaik": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
    "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
}


PLATFORMS = {
    "YouTube": ("youtube.com", "youtu.be"),
    "Instagram": ("instagram.com",),
    "TikTok": ("tiktok.com",),
    "Twitter/X": ("twitter.com", "x.com"),
}


def platform_url(value, platform):
    from urllib.parse import urlparse

    hosts = PLATFORMS.get(platform)
    parsed = urlparse(str(value or "").strip())
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if not hosts or parsed.scheme not in {"http", "https"} or not any(host == domain or host.endswith("." + domain) for domain in hosts):
        supported = ", ".join(PLATFORMS)
        raise ValueError(f"Masukkan URL {platform} yang valid. Platform yang didukung: {supported}.")
    return parsed.geturl()


def download_video(url, platform, quality, folder: Path, progress, cancel: threading.Event):
    folder.mkdir(parents=True, exist_ok=True)

    def report_download(state):
        if cancel.is_set():
            raise Cancelled("Proses dibatalkan.")
        if state.get("status") == "downloading":
            total = state.get("total_bytes") or state.get("total_bytes_estimate") or 0
            fraction = state.get("downloaded_bytes", 0) / total if total else 0
            progress(min(0.95, fraction), f"Mengunduh video {platform}…")

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    options = {
        "format": FORMATS.get(quality, FORMATS["Terbaik"]),
        "outtmpl": str(folder / "video.%(ext)s"),
        "merge_output_format": "mp4",
        "ffmpeg_location": ffmpeg_exe,
        "noplaylist": True,
        "windowsfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "js_runtimes": {"node": {}},
        "socket_timeout": 30,
        "retries": 3,
        "progress_hooks": [report_download],
    }
    try:
        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(platform_url(url, platform), download=True)
    except Cancelled:
        raise
    except Exception as error:
        raise ValueError(f"Gagal mengunduh video {platform}: {error}") from error
    files = [path for path in folder.glob("video.*") if path.is_file() and path.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov", ".m4v"}]
    if not files:
        raise ValueError("File video tidak ditemukan setelah proses unduh.")
    return files[0], info.get("title") or f"Video {platform}"
