import threading
from pathlib import Path

import imageio_ffmpeg
from yt_dlp import YoutubeDL

from removebg.domain import Cancelled
from removebg.infrastructure.youtube_common import youtube_url


FORMATS = {
    "Terbaik": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
    "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
}


def download_video(url, quality, folder: Path, progress, cancel: threading.Event):
    folder.mkdir(parents=True, exist_ok=True)

    def report_download(state):
        if cancel.is_set():
            raise Cancelled("Proses dibatalkan.")
        if state.get("status") == "downloading":
            total = state.get("total_bytes") or state.get("total_bytes_estimate") or 0
            fraction = state.get("downloaded_bytes", 0) / total if total else 0
            progress(min(0.95, fraction), "Mengunduh video YouTube…")

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
            info = downloader.extract_info(youtube_url(url), download=True)
    except Cancelled:
        raise
    except Exception as error:
        raise ValueError(f"Gagal mengunduh video YouTube: {error}") from error
    files = [path for path in folder.glob("video.*") if path.is_file() and path.suffix.lower() in {".mp4", ".mkv", ".webm"}]
    if not files:
        raise ValueError("File video tidak ditemukan setelah proses unduh.")
    return files[0], info.get("title") or "Video YouTube"
