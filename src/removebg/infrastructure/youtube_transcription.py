import subprocess
import threading
import time
from pathlib import Path

import imageio_ffmpeg
from yt_dlp import YoutubeDL

from removebg.domain import Cancelled
from removebg.infrastructure.youtube_common import youtube_url


def download_audio(url, folder: Path, progress, cancel: threading.Event):
    folder.mkdir(parents=True, exist_ok=True)

    def report_download(state):
        if cancel.is_set():
            raise Cancelled("Proses dibatalkan.")
        if state.get("status") == "downloading":
            total = state.get("total_bytes") or state.get("total_bytes_estimate") or 0
            fraction = state.get("downloaded_bytes", 0) / total if total else 0
            progress(0.05 + min(fraction, 1) * 0.25, "Mengambil audio dari YouTube…")

    options = {
        "format": "bestaudio/best",
        "outtmpl": str(folder / "source.%(ext)s"),
        "noplaylist": True,
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
            source = Path(downloader.prepare_filename(info))
    except Cancelled:
        raise
    except Exception as error:
        raise ValueError(f"Gagal mengambil audio YouTube: {error}") from error

    if cancel.is_set():
        raise Cancelled("Proses dibatalkan.")
    if not source.exists():
        matches = list(folder.glob("source.*"))
        if not matches:
            raise ValueError("Audio dari YouTube tidak ditemukan setelah diunduh.")
        source = matches[0]

    wav = folder / "audio.wav"
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
               "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)]
    log_path = folder / "ffmpeg.log"
    with log_path.open("w+", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            while process.poll() is None:
                if cancel.is_set():
                    raise Cancelled("Proses dibatalkan.")
                time.sleep(0.1)
            if process.returncode:
                log.seek(0)
                raise ValueError("Persiapan audio gagal: " + log.read()[-1200:])
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()
    source.unlink(missing_ok=True)
    log_path.unlink(missing_ok=True)
    return wav, {"title": info.get("title") or "Video YouTube", "id": info.get("id"), "url": info.get("webpage_url") or youtube_url(url)}
