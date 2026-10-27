import subprocess
import threading
import time
from fractions import Fraction
from pathlib import Path

import av
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageOps

from removebg.domain import Cancelled, VideoInfo


def frame_rgb(frame):
    rgb = frame.to_ndarray(format="rgb24")
    rotation = getattr(frame, "rotation", 0)
    if rotation:
        if rotation % 90:
            raise ValueError("Rotasi video harus kelipatan 90 derajat.")
        rgb = np.rot90(rgb, int(rotation / 90))
    return np.ascontiguousarray(rgb)


def inspect_video(path):
    with av.open(str(path)) as container:
        if not container.streams.video:
            raise ValueError("File tidak mempunyai stream video.")
        stream = container.streams.video[0]
        if stream.codec_context.color_trc in (16, 18):
            raise ValueError("Video HDR belum didukung. Ekspor sumber ke SDR Rec.709 terlebih dahulu.")
        first = next(container.decode(stream), None)
        if first is None:
            raise ValueError("Video kosong atau tidak dapat dibaca.")
        rgb = frame_rgb(first)
        height, width = rgb.shape[:2]
        if min(width, height) > 1080 or max(width, height) > 1920:
            raise ValueError("Versi ini mendukung hingga 1920×1080 atau 1080×1920, tanpa mengecilkan ekspor.")
        duration = float(stream.duration * stream.time_base) if stream.duration else (container.duration or 0) / av.time_base
        if duration <= 0 or duration > 901:
            raise ValueError("Durasi harus terbaca dan maksimal 15 menit.")
        rate = stream.average_rate or Fraction(30)
        return VideoInfo(width, height, duration, rate, stream.frames, bool(container.streams.audio)), rgb


def read_photo(path):
    with Image.open(path) as image:
        if image.width * image.height > 40_000_000:
            raise ValueError("Foto maksimal 40 megapiksel.")
        rgb = np.array(ImageOps.exif_transpose(image).convert("RGB"))
    return rgb


def checkerboard(foreground, alpha):
    h, w = alpha.shape
    y, x = np.ogrid[:h, :w]
    board = np.where((x // 24 + y // 24) % 2, 190, 225).astype(np.float32)
    weight = alpha[..., None].astype(np.float32) / 255
    return np.rint(foreground * weight + board[..., None] * (1 - weight)).astype(np.uint8)


class VideoWriter:
    def __init__(self, path, width, height, rate, kind):
        self.container = av.open(str(path), "w")
        self.kind = kind
        try:
            codec = {"transparent": "prores_ks", "mask": "ffv1", "preview": "libx264"}[kind]
            self.stream = self.container.add_stream(codec, rate=rate)
            self.stream.width = width
            self.stream.height = height
            self.stream.time_base = Fraction(1, 90000)
            self.stream.codec_context.time_base = Fraction(1, 90000)
            if kind != "mask":
                self.stream.codec_context.colorspace = 1
                self.stream.codec_context.color_primaries = 1
                self.stream.codec_context.color_trc = 1
                self.stream.codec_context.color_range = 1
            if kind == "transparent":
                self.stream.pix_fmt = "yuva444p10le"
                self.stream.options = {"profile": "4", "alpha_bits": "16"}
                self.stream.codec_context.flags |= av.codec.context.Flags.qscale
                self.stream.codec_context.global_quality = 4
            elif kind == "mask":
                self.stream.pix_fmt = "gray"
                self.stream.options = {"level": "3"}
            else:
                self.stream.pix_fmt = "yuv420p"
                self.stream.options = {"crf": "18", "preset": "veryfast"}
        except BaseException:
            self.container.close()
            raise

    def write(self, pixels, timestamp):
        fmt = "gray" if self.kind == "mask" else "rgba" if self.kind == "transparent" else "rgb24"
        frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(pixels), format=fmt)
        if self.kind != "mask":
            frame = frame.reformat(format=self.stream.pix_fmt, dst_colorspace="ITU709")
        frame.time_base = Fraction(1, 90000)
        frame.pts = round(timestamp * 90000)
        for packet in self.stream.encode(frame):
            self.container.mux(packet)

    def close(self):
        try:
            for packet in self.stream.encode():
                self.container.mux(packet)
        finally:
            self.container.close()

    def abort(self):
        self.container.close()


def attach_audio(video, source, target, origin, duration, cancel: threading.Event):
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-copyts",
               "-i", str(video), "-i", str(source), "-map", "0:v:0", "-map", "1:a:0?",
               "-c:v", "copy", "-c:a", "pcm_s16le", "-af", f"asetpts=PTS-{float(origin):.9f}/TB,atrim=start=0",
               "-t", f"{duration:.9f}", "-map_metadata", "-1", str(target)]
    log = Path(target).with_suffix(".ffmpeg.log")
    with log.open("w+") as stderr:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=stderr, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            while process.poll() is None:
                if cancel.is_set():
                    raise Cancelled("Proses dibatalkan.")
                time.sleep(0.1)
            if process.returncode:
                stderr.seek(0)
                raise RuntimeError("Ekspor audio gagal: " + stderr.read()[-2000:])
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()
    log.unlink(missing_ok=True)
