import json
import shutil
import time
import uuid

import av
import numpy as np
from PIL import Image

from removebg.config import OUTPUTS, prepare_dirs
from removebg.domain import Cancelled, validate_points
from removebg.infrastructure.media import (
    VideoWriter,
    attach_audio,
    checkerboard,
    frame_rgb,
    inspect_video,
    read_photo,
)
from removebg.infrastructure.models import create_model, release_gpu


def run_video(path, mode, quality, points, export, preview_only, cancel, progress, model_factory=create_model):
    info, _ = inspect_video(path)
    if mode == "Objek umum":
        validate_points(points, info.width, info.height)
    prepare_dirs()
    job = OUTPUTS / uuid.uuid4().hex[:12]
    job.mkdir()
    model = writer = preview_writer = None
    started = time.monotonic()
    frames = 0
    final = job / ("hasil.mov" if export == "transparent" else "mask.mkv")
    silent = job / ("silent.mov" if export == "transparent" else "silent.mkv")
    preview = job / "preview.mp4"
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
        preview_writer = VideoWriter(preview, *preview_size, info.rate, "preview")
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
                pixels = np.dstack((foreground, alpha)) if export == "transparent" else alpha
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
        if export == "transparent" and info.has_audio:
            attach_audio(silent, path, final, origin, end, cancel)
            silent.unlink()
        else:
            silent.rename(final)
        seconds = time.monotonic() - started
        report = {"mode": mode, "quality": quality, "frames": frames, "width": info.width,
                  "height": info.height, "processed_seconds": end, "wall_seconds": round(seconds, 2),
                  "pipeline_fps": round(frames / seconds, 2), "export": export,
                  "preview_only": preview_only, "audio": info.has_audio and export == "transparent"}
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


def run_photo(path, mode, quality, points, model_factory=create_model):
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
        output = OUTPUTS / (uuid.uuid4().hex[:12] + ".png")
        Image.fromarray(np.dstack((foreground, alpha))).save(output)
        return str(output)
    finally:
        del model
        release_gpu()
