import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import av
import imageio_ffmpeg
import requests

from removebg.application.service import safe_name
from removebg.config import OUTPUTS, prepare_dirs
from removebg.domain import Cancelled
from removebg.infrastructure.youtube_video import download_video, platform_url

_INSTAGRAM_POLARIS_POST_QUERY = "27130156389949648"
_INSTAGRAM_LSD_PATTERN = r'\["LSD",\[\],\{"token":"([^"]+)"'


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
            shutil.rmtree(job, ignore_errors=True)
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


def run_instagram_photo_download(url, output_name, progress, cancel: threading.Event):
    """Download public Instagram post photos using its logged-out media query."""
    import json
    import re

    import requests

    clean_url = platform_url(url, "Instagram")
    match = re.search(r"/p/([A-Za-z0-9_-]+)", urlparse(clean_url).path)
    if not match:
        return None
    shortcode = match.group(1)
    media_id = 0
    for char in shortcode:
        try:
            media_id = media_id * 64 + "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_".index(char)
        except ValueError as error:
            raise ValueError("Tautan posting Instagram tidak valid.") from error

    prepare_dirs()
    job = OUTPUTS / uuid.uuid4().hex[:12]
    job.mkdir()
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.instagram.com",
        "Referer": "https://www.instagram.com/",
        "X-IG-App-ID": "936619743392459",
        "X-ASBD-ID": "198387",
        "X-IG-WWW-Claim": "0",
    })
    try:
        if cancel.is_set():
            raise Cancelled("Proses dibatalkan.")
        query_name = "PolarisLoggedOutDesktopWWWPostRootContentQuery"
        media = None
        extraction_error = None
        for attempt in range(2):
            if cancel.is_set():
                raise Cancelled("Proses dibatalkan.")
            progress(0.02 + attempt * 0.02, "Mengambil data posting foto Instagram publik…")
            try:
                home = session.get("https://www.instagram.com/", timeout=(10, 20))
                home.raise_for_status()
                token_match = re.search(_INSTAGRAM_LSD_PATTERN, home.text)
                csrf = session.cookies.get("csrftoken")
                if not token_match or not csrf:
                    raise ValueError("Instagram tidak memberikan token akses publik untuk posting ini.")
                lsd = token_match.group(1)
                ruling = session.get(
                    "https://i.instagram.com/api/v1/web/get_ruling_for_content/",
                    params={"content_type": "MEDIA", "target_id": str(media_id)},
                    timeout=(10, 20),
                )
                ruling.raise_for_status()
                ruling_data = ruling.json()
                if (ruling_data or {}).get("status") != "ok":
                    raise ValueError("Instagram tidak membuka posting ini untuk akses tanpa login.")
                query = session.post(
                    "https://www.instagram.com/api/graphql",
                    headers={
                        "X-FB-Friendly-Name": query_name,
                        "X-CSRFToken": csrf,
                        "X-FB-LSD": lsd,
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": f"https://www.instagram.com/p/{shortcode}/",
                    },
                    data={
                        "lsd": lsd,
                        "fb_api_caller_class": "RelayModern",
                        "fb_api_req_friendly_name": query_name,
                        "server_timestamps": "true",
                        "variables": json.dumps({"media_id": str(media_id)}, separators=(",", ":")),
                        "doc_id": _INSTAGRAM_POLARIS_POST_QUERY,
                    },
                    timeout=(10, 25),
                )
                query.raise_for_status()
                data = query.json()
                media = (((data.get("data") or {}).get("xig_polaris_media") or {}).get("if_not_gated_logged_out") or {})
                if media:
                    break
                raise ValueError("Instagram tidak mengembalikan data media publik untuk posting ini.")
            except (ValueError, requests.exceptions.JSONDecodeError) as error:
                extraction_error = error
                if attempt == 0:
                    continue
        photos = []
        if media:
            for child in media.get("carousel_media") or [media]:
                if child.get("video_versions"):
                    continue
                candidates = (child.get("image_versions2") or {}).get("candidates") or []
                candidates = [candidate for candidate in candidates if candidate.get("url")]
                if candidates:
                    def resolution(candidate):
                        width = candidate.get("width") or 0
                        height = candidate.get("height") or 0
                        if not width or not height:
                            stp = parse_qs(urlparse(candidate["url"]).query).get("stp", [""])[0]
                            dimensions = re.search(r"_p(\d+)x(\d+)", stp)
                            if dimensions:
                                width, height = map(int, dimensions.groups())
                        return width * height

                    photos.append(max(candidates, key=resolution)["url"])
        preview_only = False
        if not photos and media:
            shutil.rmtree(job, ignore_errors=True)
            return None
        if not photos:
            try:
                preview = session.get(
                    "https://www.instagram.com/api/v1/oembed/",
                    params={"url": clean_url},
                    timeout=(10, 20),
                )
                preview.raise_for_status()
                preview_data = preview.json()
                thumbnail = preview_data.get("thumbnail_url")
                if preview_data.get("type") != "rich" or not thumbnail:
                    raise ValueError("Instagram tidak menyediakan pratinjau foto publik.")
                photos = [thumbnail]
                preview_only = True
            except (requests.RequestException, ValueError) as fallback_error:
                raise ValueError(
                    "Instagram tidak mengirim data foto setelah dicoba ulang; "
                    f"pratinjau publik juga gagal ({fallback_error})."
                ) from extraction_error

        stem = safe_name(output_name, f"foto-instagram-{shortcode}")
        results = []
        for index, image_url in enumerate(photos, 1):
            if cancel.is_set():
                raise Cancelled("Proses dibatalkan.")
            parsed = urlparse(image_url)
            host = (parsed.hostname or "").lower()
            if parsed.scheme != "https" or not (host.endswith("fbcdn.net") or host.endswith("cdninstagram.com")):
                raise ValueError("Instagram mengembalikan tautan foto yang tidak valid.")
            progress(0.1 + 0.85 * (index - 1) / len(photos), f"Mengunduh foto Instagram {index}/{len(photos)}…")
            with session.get(image_url, stream=True, timeout=(10, 45)) as response:
                response.raise_for_status()
                media_type = response.headers.get("Content-Type", "").lower().split(";", 1)[0]
                extensions = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
                extension = extensions.get(media_type)
                if not extension:
                    raise ValueError("Instagram tidak mengembalikan file foto yang didukung.")
                final = job / f"{stem}-{index:02d}{extension}"
                with final.open("wb") as target:
                    for chunk in response.iter_content(chunk_size=256 * 1024):
                        if cancel.is_set():
                            raise Cancelled("Proses dibatalkan.")
                        if chunk:
                            target.write(chunk)
            results.append({"path": str(final), "filename": final.name, "size": final.stat().st_size})

        progress(1, f"{len(results)} foto Instagram siap.")
        result = {"title": stem, "images": results}
        if preview_only:
            result["notice"] = "Instagram hanya memberikan pratinjau foto; kualitas dan jumlah foto carousel mungkin terbatas."
        return result
    except BaseException:
        shutil.rmtree(job, ignore_errors=True)
        raise
    finally:
        session.close()


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
