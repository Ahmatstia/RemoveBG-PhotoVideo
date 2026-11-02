import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path

import av
import imageio_ffmpeg
import requests

from removebg.application.service import safe_name
from removebg.config import OUTPUTS, prepare_dirs
from removebg.domain import Cancelled
from removebg.infrastructure.youtube_video import download_video, platform_url


def run_tiktok_video_download(url, output_name, progress, cancel: threading.Event):
    """Use TikWM to resolve public TikTok video URLs without browser cookies."""
    prepare_dirs()
    job = OUTPUTS / uuid.uuid4().hex[:12]
    job.mkdir()
    source = job / "source.mp4"
    final = job / f"{safe_name(output_name, 'video-tiktok')}.mp4"
    try:
        if cancel.is_set():
            raise Cancelled("Proses dibatalkan.")
        clean_url = platform_url(url, "TikTok")
        progress(0.03, "Mengambil tautan video publik dari TikWM…")
        response = requests.get(
            "https://www.tikwm.com/api/",
            params={"url": clean_url, "hd": "1"},
            headers={"User-Agent": "MyTools Local Video Downloader"},
            timeout=(10, 25),
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") or {}
        video_id = _tiktok_video_id(clean_url)
        if payload.get("code") != 0 or (video_id and str(data.get("id", "")) != video_id):
            raise ValueError("TikWM tidak dapat menyediakan video ini. Pastikan posting dapat dilihat publik.")
        media_url = data.get("hdplay") or data.get("play") or data.get("wmplay")
        if not _is_tiktok_cdn_url(media_url):
            raise ValueError("TikWM tidak mengembalikan tautan video TikTok yang valid.")

        title = safe_name(output_name, safe_name(data.get("title"), "video-tiktok"))
        source = job / f"{title}-source.mp4"
        final = job / f"{title}.mp4"
        progress(0.08, "Mengunduh video ke penyimpanan sementara…")
        with requests.get(
            media_url,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.tiktok.com/"},
            stream=True,
            timeout=(15, 45),
        ) as media:
            media.raise_for_status()
            content_type = media.headers.get("Content-Type", "").lower()
            if "video/" not in content_type and "octet-stream" not in content_type:
                raise ValueError("Server TikTok tidak mengembalikan file video.")
            total = int(media.headers.get("Content-Length") or 0)
            received = 0
            with source.open("wb") as target:
                for chunk in media.iter_content(chunk_size=256 * 1024):
                    if cancel.is_set():
                        raise Cancelled("Proses dibatalkan.")
                    if not chunk:
                        continue
                    target.write(chunk)
                    received += len(chunk)
                    fraction = received / total if total else 0
                    progress(min(0.97, 0.08 + fraction * 0.89), "Mengunduh video TikTok…")
        if not received:
            raise ValueError("File video yang diterima kosong.")
        _transcode_tiktok_to_h264(source, final, cancel, progress)
        source.unlink(missing_ok=True)
        progress(1, "Unduhan TikTok selesai.")
        return {"path": str(final), "title": title, "size": final.stat().st_size}
    except Cancelled:
        shutil.rmtree(job, ignore_errors=True)
        raise
    except (requests.RequestException, ValueError) as error:
        shutil.rmtree(job, ignore_errors=True)
        if isinstance(error, ValueError):
            raise
        raise ValueError(f"Gagal mengunduh video TikTok lewat TikWM: {error}") from error
    except BaseException:
        shutil.rmtree(job, ignore_errors=True)
        raise


def _transcode_tiktok_to_h264(source: Path, target: Path, cancel: threading.Event, progress):
    with av.open(str(source)) as container:
        video_stream = next((stream for stream in container.streams if stream.type == "video"), None)
        if video_stream is None:
            raise ValueError("File TikTok tidak memiliki stream video.")
        codec = video_stream.codec_context.name
        dimensions = (video_stream.codec_context.width, video_stream.codec_context.height)
    if codec in {"h264", "avc1"}:
        source.replace(target)
        return dimensions

    progress(0.97, "Mengubah codec ke H.264 dan mempertahankan resolusi HD…")
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source), "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(target),
    ]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    while process.poll() is None:
        if cancel.wait(0.25):
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise Cancelled("Proses dibatalkan.")
    _, stderr = process.communicate()
    if process.returncode:
        detail = stderr.decode("utf-8", errors="replace")[-500:].strip()
        raise ValueError("Gagal mengubah video TikTok ke format H.264." + (f" {detail}" if detail else ""))
    with av.open(str(target)) as container:
        output_stream = next((stream for stream in container.streams if stream.type == "video"), None)
        if output_stream is None or output_stream.codec_context.name != "h264":
            raise ValueError("Hasil konversi bukan video H.264 yang kompatibel.")
        output_dimensions = (output_stream.codec_context.width, output_stream.codec_context.height)
    if output_dimensions != dimensions:
        raise ValueError("Resolusi video berubah saat konversi H.264.")
    return output_dimensions


def _tiktok_video_id(url):
    import re

    match = re.search(r"/(?:video|photo)/(\d+)", url)
    return match.group(1) if match else ""


def _is_tiktok_cdn_url(value):
    from urllib.parse import urlparse

    parsed = urlparse(str(value or ""))
    host = (parsed.hostname or "").lower()
    allowed = ("tiktokcdn.com", "tiktokcdn-us.com", "tiktokcdn-eu.com")
    return parsed.scheme == "https" and any(host == domain or host.endswith("." + domain) for domain in allowed)


def run_tiktok_photo_download(url, output_name, progress, cancel: threading.Event):
    """Download a TikTok photo post as individual image files."""
    prepare_dirs()
    job = OUTPUTS / uuid.uuid4().hex[:12]
    job.mkdir()
    work = job / "photos"
    work.mkdir()
    log_path = job / "gallery-dl.log"
    command = [
        sys.executable, "-m", "gallery_dl", "--config-ignore",
        "--directory", str(work), "--filename", "{num:>03}.{extension}",
        "--filter", "extension in ('jpg', 'jpeg', 'png', 'webp')", platform_url(url, "TikTok"),
    ]
    try:
        progress(0.02, "Mengambil foto dari posting TikTok…")
        with log_path.open("w", encoding="utf-8", errors="replace") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            while process.poll() is None:
                if cancel.wait(0.25):
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    raise Cancelled("Proses dibatalkan.")
                progress(0.35, "Mengunduh foto slideshow TikTok…")
        if process.returncode:
            details = log_path.read_text(encoding="utf-8", errors="replace")[-1200:].strip()
            raise ValueError("Gagal mengambil foto TikTok." + (f" {details}" if details else ""))
        images = sorted(
            (path for path in work.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}),
            key=lambda path: (0, int(path.stem)) if path.stem.isdigit() else (1, path.name.lower()),
        )
        if not images:
            raise ValueError("Posting TikTok tidak menghasilkan foto yang bisa diunduh.")
        safe_stem = safe_name(output_name, "foto-tiktok")
        results = []
        for index, path in enumerate(images, 1):
            final = job / f"{safe_stem}-{index:02d}{path.suffix.lower()}"
            path.replace(final)
            results.append({"path": str(final), "filename": final.name, "size": final.stat().st_size})
        shutil.rmtree(work, ignore_errors=True)
        log_path.unlink(missing_ok=True)
        progress(1, f"{len(results)} foto siap.")
        return {"title": safe_stem, "images": results}
    except BaseException:
        shutil.rmtree(job, ignore_errors=True)
        raise


def run_video_download(url, platform, quality, output_name, progress, cancel: threading.Event):
    prepare_dirs()
    job = OUTPUTS / uuid.uuid4().hex[:12]
    job.mkdir()
    work = job / "work"
    try:
        progress(0.02, f"Memeriksa video {platform}…")
        path, title = download_video(url, platform, quality, work, progress, cancel)
        if cancel.is_set():
            raise Cancelled("Proses dibatalkan.")
        final = job / f"{safe_name(output_name, safe_name(title, 'video'))}{path.suffix.lower()}"
        path.replace(final)
        shutil.rmtree(work, ignore_errors=True)
        progress(1, "Unduhan selesai.")
        return {"path": str(final), "title": title, "size": final.stat().st_size}
    except BaseException:
        shutil.rmtree(job, ignore_errors=True)
        raise
