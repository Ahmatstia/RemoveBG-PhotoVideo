import json
import re
import shutil
import time
import uuid
from pathlib import Path

import av
import numpy as np
from PIL import Image

from removebg.config import OUTPUTS, prepare_dirs
from removebg.domain import Cancelled, validate_points
from removebg.infrastructure.media import (
    VideoWriter,
    attach_audio,
    checkerboard,
    composite_color,
    frame_rgb,
    inspect_video,
    read_photo,
)
from removebg.infrastructure.models import create_model, release_gpu

RESERVED_NAMES = {"silent", "preview", "preview-silent", "report"}
WINDOWS_DEVICES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def safe_name(name, default):
    """Turn user text into a safe Windows file stem (no extension, no path, no reserved names)."""
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(name or "")).strip().strip(".")
    if Path(text).suffix.lower() in {".mov", ".mkv", ".mp4", ".png"}:
        text = Path(text).stem
    text = text.strip().strip(".")[:100].strip()
    if not text:
        return default
    if text.lower() in RESERVED_NAMES or text.lower() in WINDOWS_DEVICES:
        text += "-hasil"
    return text


def run_video(path, mode, quality, points, export, preview_only, cancel, progress, model_factory=create_model, output_name=None):
    info, _ = inspect_video(path)
    if mode == "Objek umum":
        validate_points(points, info.width, info.height)
    prepare_dirs()
    job = OUTPUTS / uuid.uuid4().hex[:12]
    job.mkdir()
    model = writer = preview_writer = None
    started = time.monotonic()
    frames = 0
    extension = "mov" if export == "transparent" else "mkv" if export == "mask" else "mp4"
    default_base = "hasil" if export == "transparent" else "mask" if export == "mask" else "video-tanpa-latar"
    final = job / f"{safe_name(output_name, default_base)}.{extension}"
    silent = job / f"silent.{extension}"
    preview = job / "preview.mp4"
    silent_preview = job / "preview-silent.mp4"
    try:
        if shutil.disk_usage(job).free < 2 * 1024**3:
            raise ValueError("Sediakan minimal 2 GB ruang disk kosong sebelum memproses.")
        progress(0, "Memuat model (unduhan diperlukan pada penggunaan pertama)…")
        model = model_factory(mode, quality, points)
        if cancel.is_set():
            raise Cancelled()
        writer = VideoWriter(silent, info.width, info.height, info.rate, export)
        preview_size = (max(2, round(info.width * min(1, 640 / info.width)) // 2 * 2),
                        max(2, round(info.height * min(1, 640 / info.width)) // 2 * 2))
        preview_writer = VideoWriter(silent_preview, *preview_size, info.rate, "preview")
        origin = last = None
        end = 0.0
        with av.open(str(path)) as container:
            for frame in container.decode(video=0):
                if cancel.is_set():
                    raise Cancelled()
                if frame.pts is None:
                    raise ValueError("Video tidak mempunyai timestamp lengkap. Konversikan sumber terlebih dahulu.")
                absolute = frame.pts * frame.time_base
                if origin is None:
                    origin = absolute
                timestamp = absolute - origin
                if last is not None and timestamp <= last:
                    raise ValueError("Timestamp video tidak berurutan; ekspor dibatalkan agar audio tidak bergeser.")
                if preview_only and timestamp >= 5:
                    break
                if timestamp > 901:
                    raise ValueError("Video melebihi 15 menit.")
                rgb = frame_rgb(frame)
                if rgb.shape[:2] != (info.height, info.width):
                    raise ValueError("Resolusi berubah di tengah video; pisahkan video per klip.")
                foreground, alpha = model.process(rgb)
                if export == "transparent":
                    pixels = np.dstack((foreground, alpha))
                elif export == "mask":
                    pixels = alpha
                elif export == "mp4_green":
                    pixels = composite_color(foreground, alpha, (0, 255, 0))
                elif export == "mp4_black":
                    pixels = composite_color(foreground, alpha, (0, 0, 0))
                else:
                    pixels = np.dstack((foreground, alpha))
                writer.write(pixels, timestamp)
                if timestamp < 5:
                    display = Image.fromarray(checkerboard(foreground, alpha)).resize(preview_size, Image.Resampling.LANCZOS)
                    preview_writer.write(np.array(display), timestamp)
                frames += 1
                end = float(timestamp + (frame.duration * frame.time_base if frame.duration else 1 / info.rate))
                last = timestamp
                if frames % 10 == 0:
                    elapsed = time.monotonic() - started
                    limit = min(info.duration, 5) if preview_only else info.duration
                    progress(min(float(timestamp) / limit, 0.99), f"{frames} frame · {frames / elapsed:.1f} fps · {float(timestamp):.1f}/{limit:.1f} detik")
                    if shutil.disk_usage(job).free < 512 * 1024**2:
                        raise ValueError("Disk hampir penuh. Proses dihentikan; file sumber tetap aman.")
        if not frames:
            raise ValueError("Tidak ada frame yang berhasil diproses.")
        writer.close()
        writer = None
        preview_writer.close()
        preview_writer = None
        if cancel.is_set():
            raise Cancelled()
        progress(0.99, "Menyelesaikan ekspor dan audio…")
        if info.has_audio:
            audio_codec = "aac" if extension == "mp4" else "pcm_s16le"
            attach_audio(silent, path, final, origin, end, cancel, audio_codec)
            silent.unlink()
            attach_audio(silent_preview, path, preview, origin, min(end, 5.0), cancel, "aac")
            silent_preview.unlink()
        else:
            silent.rename(final)
            silent_preview.rename(preview)
        seconds = time.monotonic() - started
        report = {"mode": mode, "quality": quality, "frames": frames, "width": info.width,
                  "height": info.height, "processed_seconds": end, "wall_seconds": round(seconds, 2),
                  "pipeline_fps": round(frames / seconds, 2), "export": export,
                  "preview_only": preview_only, "audio": info.has_audio}
        (job / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        progress(1, "Selesai")
        return str(final), str(preview), report
    except BaseException:
        if writer is not None:
            writer.abort()
        if preview_writer is not None:
            preview_writer.abort()
        # Only remove this job's generated partial files, never an input or another job.
        shutil.rmtree(job)
        raise
    finally:
        del model
        release_gpu()


def run_photo(path, mode, quality, points, model_factory=create_model, output_name=None):
    rgb = read_photo(path)
    if min(rgb.shape[:2]) > 2160 or max(rgb.shape[:2]) > 3840:
        raise ValueError("Foto maksimal 3840×2160 / 2160×3840 untuk penggunaan VRAM yang terkendali.")
    if mode == "Objek umum":
        validate_points(points, rgb.shape[1], rgb.shape[0])
    model = None
    try:
        model = model_factory(mode, quality, points)
        foreground, alpha = model.process(rgb)
        prepare_dirs()
        folder = OUTPUTS / uuid.uuid4().hex[:12]
        folder.mkdir()
        output = folder / (safe_name(output_name, "foto") + ".png")
        Image.fromarray(np.dstack((foreground, alpha))).save(output)
        return str(output)
    finally:
        del model
        release_gpu()
