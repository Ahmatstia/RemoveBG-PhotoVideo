import base64
import ipaddress
import threading
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

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
    parsed = urlparse(str(value or "").strip())
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if platform == "Link umum":
        if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
            raise ValueError("Masukkan URL video publik dengan alamat http:// atau https:// yang valid.")
        try:
            parsed.port
        except ValueError as error:
            raise ValueError("Port URL tidak valid.") from error
        if host == "localhost" or host.endswith((".localhost", ".local")):
            raise ValueError("Link umum hanya menerima alamat website publik.")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Link umum hanya menerima alamat IP publik.")
        proxy_origin = next((item for key, item in parse_qsl(parsed.query, keep_blank_values=True) if key == "__cpo"), None)
        if address is not None and proxy_origin:
            try:
                padding = "=" * (-len(proxy_origin) % 4)
                origin = urlparse(base64.urlsafe_b64decode(proxy_origin + padding).decode("utf-8"))
                origin_host = (origin.hostname or "").lower().removeprefix("www.")
                try:
                    origin_address = ipaddress.ip_address(origin_host)
                except ValueError:
                    origin_address = None
                if (
                    origin.scheme not in {"http", "https"}
                    or not origin.hostname
                    or origin.username
                    or origin.password
                    or origin.path not in {"", "/"}
                    or origin.query
                    or origin.fragment
                    or origin_host == "localhost"
                    or origin_host.endswith((".localhost", ".local"))
                    or (origin_address is not None and not origin_address.is_global)
                ):
                    return parsed.geturl()
                origin.port
            except (ValueError, UnicodeDecodeError):
                return parsed.geturl()
            source_query = [(key, item) for key, item in parse_qsl(parsed.query, keep_blank_values=True) if key != "__cpo"]
            return urlunparse((origin.scheme, origin.netloc, parsed.path, parsed.params, urlencode(source_query), parsed.fragment))
        return parsed.geturl()

    hosts = PLATFORMS.get(platform)
    if not hosts or parsed.scheme not in {"http", "https"} or not any(host == domain or host.endswith("." + domain) for domain in hosts):
        supported = ", ".join((*PLATFORMS, "Link umum"))
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
        message = str(error).lower()
        if platform != "YouTube" or "sign in" not in message or "bot" not in message:
            raise ValueError(f"Gagal mengunduh video {platform}: {error}") from error

        progress(0, "YouTube menolak jalur standar; mencoba mode tanpa login (resolusi bisa terbatas)…")
        retry_options = {**options, "extractor_args": {"youtube": {"player_client": ["android"]}}}
        try:
            with YoutubeDL(retry_options) as downloader:
                info = downloader.extract_info(platform_url(url, platform), download=True)
        except Cancelled:
            raise
        except Exception as retry_error:
            raise ValueError(f"Gagal mengunduh video {platform}: {retry_error}") from retry_error
    files = [path for path in folder.glob("video.*") if path.is_file() and path.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov", ".m4v"}]
    if not files:
        raise ValueError("File video tidak ditemukan setelah proses unduh.")
    return files[0], info.get("title") or f"Video {platform}"
