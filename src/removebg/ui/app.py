import logging
import os
import threading
from pathlib import Path
from urllib.parse import quote

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import gradio as gr
import torch
from PIL import Image, ImageDraw

from removebg.application.service import run_photo, run_video
from removebg.config import OUTPUTS, ROOT, prepare_dirs
from removebg.domain import Cancelled
from removebg.infrastructure.media import inspect_video, read_photo
from removebg.ui.theme import CSS, FORCE_DARK, make_theme

logger = logging.getLogger(__name__)
running = {}


def load_source(path, is_photo=False):
    if not path:
        return None, None, [], "Pilih file untuk memulai."
    try:
        if is_photo:
            rgb = read_photo(path)
            details = f"{rgb.shape[1]} × {rgb.shape[0]} · Foto"
        else:
            info, rgb = inspect_video(path)
            details = f"{info.width} × {info.height} · {info.duration:.1f} detik · {float(info.rate):.2f} fps · Audio {'ada' if info.has_audio else 'tidak ada'}"
        image = Image.fromarray(rgb)
        return image, image, [], f"✅ **{details}**"
    except Exception as error:
        raise gr.Error(str(error)) from error


def select_point(original, points, action, event: gr.SelectData):
    if original is None:
        raise gr.Error("Pilih file terlebih dahulu.")
    points = list(points or []) + [(event.index[0], event.index[1], 1 if action == "Pertahankan" else 0)]
    annotated = original.copy()
    draw = ImageDraw.Draw(annotated)
    radius = max(4, min(original.size) // 90)
    for x, y, label in points:
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill="#22c55e" if label else "#ff2d46", outline="white", width=2)
    return annotated, points


def clear_points(original):
    return original, []


def clock(seconds):
    seconds = round(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


EMPTY_PLAYER = '<div class="player empty">Preview hasil akan muncul di sini</div>'


def video_player(path):
    if not path:
        return EMPTY_PLAYER
    url = "/gradio_api/file=" + quote(Path(path).as_posix(), safe="/:")
    return f'<div class="player"><video src="{url}" controls playsinline preload="metadata" controlslist="nodownload"></video></div>'


EMPTY_DOWNLOAD = '<div style="padding:14px;text-align:center;color:#6d5b5e;font-size:13px;border:1.5px dashed #2a181b;border-radius:14px;background:#11090b;margin-top:10px;">File hasil unduhan akan muncul di sini.</div>'


def download_card(file_path):
    if not file_path or not Path(file_path).exists():
        return EMPTY_DOWNLOAD
    path = Path(file_path)
    size_mb = path.stat().st_size / (1024 * 1024)
    filename = path.name
    ext = path.suffix.lower()
    url = "/gradio_api/file=" + quote(path.as_posix(), safe="/:")
    badge = "Transparan" if ext == ".mov" else "Layar Hijau" if "hijau" in filename.lower() or ext == ".mp4" else "Mask" if ext == ".mkv" else "PNG"
    return (
        f'<div class="download-box">'
        f'<div class="download-row">'
        f'  <div class="download-info">'
        f'    <div class="download-filename">📁 {filename}</div>'
        f'    <div class="download-sub"><span class="download-pill">{badge}</span> · {size_mb:.1f} MB</div>'
        f'  </div>'
        f'  <a href="{url}" download="{filename}" class="btn-download-clean">'
        f'    ⬇ Unduh File'
        f'  </a>'
        f'</div>'
        f'</div>'
    )


def default_name(path):
    return f"{Path(path).stem}-hasil" if path else ""


def process_video(path, mode, quality, points, export, name, request: gr.Request, progress=gr.Progress()):  # noqa: B008 - Gradio injects progress via this default.
    if not path:
        raise gr.Error("Pilih video terlebih dahulu.")
    cancel = threading.Event()
    running[request.session_hash] = cancel
    try:
        result, preview, report = run_video(
            path, mode, quality, points, export, False, cancel,
            lambda fraction, description: progress(fraction, desc=description),
            output_name=name,
        )
        done = f"{report['frames']} frame ({report['pipeline_fps']:.1f} fps) · {clock(report['processed_seconds'])}"
        status = f"✅ **Selesai** · {done}"
        return download_card(result), video_player(preview), status
    except Cancelled:
        return EMPTY_DOWNLOAD, EMPTY_PLAYER, "Proses dibatalkan."
    except torch.cuda.OutOfMemoryError as error:
        raise gr.Error("VRAM tidak cukup. Gunakan mode Cepat.") from error
    except Exception as error:
        logger.exception("Video processing failed")
        raise gr.Error(str(error)) from error
    finally:
        running.pop(request.session_hash, None)


def stop(request: gr.Request):
    event = running.get(request.session_hash)
    if event:
        event.set()
        return "Membatalkan proses..."
    return "Tidak ada proses aktif."


def process_photo(path, mode, quality, points, name):
    if not path:
        raise gr.Error("Pilih foto terlebih dahulu.")
    try:
        result = run_photo(path, mode, quality, points, output_name=name)
        return result, download_card(result)
    except Exception as error:
        logger.exception("Photo processing failed")
        raise gr.Error(str(error)) from error


SUBJECTS = [("🧍 Manusia (Otomatis)", "Manusia"), ("📦 Objek (Pilih Titik)", "Objek umum")]
POINTS = [("🟢 Simpan", "Pertahankan"), ("🔴 Hapus", "Buang")]
QUALITIES = [("✨ Detail", "Detail"), ("⚡ Cepat", "Cepat")]
EXPORTS = [
    ("✨ Transparan (.mov)", "transparent"),
    ("🟩 Layar Hijau (.mp4)", "mp4_green"),
    ("⬛ Layar Hitam (.mp4)", "mp4_black"),
    ("⬛⬜ Mask (.mkv)", "mask"),
]


def step(number, title, subtitle):
    return gr.HTML(f'<div class="step-title"><span class="step-no">{number}</span>{title}</div><p class="step-sub">{subtitle}</p>')


def toggle_subject(subject):
    return gr.update(visible=subject == "Manusia"), gr.update(visible=subject == "Objek umum")


def hero(gpu):
    return f"""<div class="hero">
  <div class="hero-top"><div class="logo">✂</div><h1>RemoveBG <span>Local</span></h1></div>
  <p>Hapus latar belakang video dan foto secara instan, rapi, dan 100% offline.</p>
  <div class="chips">
    <span class="chip">⚡ {gpu}</span>
    <span class="chip ok">🔊 Audio Utuh</span>
    <span class="chip ok">🔒 100% Offline</span>
  </div>
</div>"""


def build_app():
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CUDA belum tersedia — jalankan setup.ps1"
    with gr.Blocks(title="RemoveBG Local", theme=make_theme(), css=CSS, js=FORCE_DARK) as app:
        gr.HTML(hero(gpu))
        with gr.Tab("🎬 Video"):
            original = gr.State()
            points = gr.State([])
            with gr.Row(equal_height=False):
                with gr.Column(scale=5):
                    with gr.Group(elem_classes="card"):
                        step(1, "Unggah Video", "Format: MP4, MOV, MKV, AVI, WEBM")
                        source = gr.File(label="Video", show_label=False, file_types=[".mp4", ".mov", ".mkv", ".avi", ".webm"], type="filepath", elem_classes="upload-zone")
                        details = gr.Markdown("Belum ada video dipilih.", elem_classes="meta")
                    with gr.Group(elem_classes="card"):
                        step(2, "Pilih Subjek", "Otomatis atau tunjuk titik objek")
                        mode = gr.Radio(SUBJECTS, value="Manusia", show_label=False, elem_classes="choice")
                        quality = gr.Radio(QUALITIES, value="Detail", label="Kualitas", elem_classes="choice")
                        with gr.Column(visible=False) as object_box:
                            gr.HTML('<div class="hint">Klik objek pada frame. <b>🟢 Simpan</b> untuk objek, <b>🔴 Hapus</b> untuk latar.</div>')
                            frame = gr.Image(type="pil", show_label=False, interactive=False)
                            action = gr.Radio(POINTS, value="Pertahankan", label="Jenis Titik", elem_classes="choice")
                            clear = gr.Button("Hapus Semua Titik", size="sm")
                with gr.Column(scale=5):
                    with gr.Group(elem_classes="card"):
                        step(3, "Format & Proses", "Tentukan format dan nama file")
                        export = gr.Radio(EXPORTS, value="transparent", label="Format Output", elem_classes="choice")
                        video_name = gr.Textbox(label="Nama File", placeholder="video-hasil", max_lines=1)
                        start = gr.Button("🚀 Mulai Proses", variant="primary", size="lg")
                        cancel = gr.Button("Batal", variant="stop", size="sm")
                        status = gr.Markdown("Siap memproses.", elem_classes="status")
                    with gr.Group(elem_classes="card"):
                        gr.HTML('<div class="step-title">Hasil</div><p class="step-sub" style="margin-left:0">Preview 5 detik pertama. Unduh file lengkap di bawah.</p>')
                        preview = gr.HTML(EMPTY_PLAYER)
                        result_card = gr.HTML(EMPTY_DOWNLOAD)
            mode.change(toggle_subject, mode, [quality, object_box], queue=False)
            source.change(default_name, source, video_name, queue=False)
            source.change(load_source, source, [frame, original, points, details], concurrency_id="gpu")
            frame.select(select_point, [original, points, action], [frame, points], queue=False)
            clear.click(clear_points, original, [frame, points], queue=False)
            start.click(
                process_video,
                [source, mode, quality, points, export, video_name],
                [result_card, preview, status],
                concurrency_id="gpu",
                concurrency_limit=1,
            )
            cancel.click(stop, outputs=status, queue=False)
        with gr.Tab("🖼 Foto"):
            photo_original = gr.State()
            photo_points = gr.State([])
            with gr.Row(equal_height=False):
                with gr.Column(scale=5):
                    with gr.Group(elem_classes="card"):
                        step(1, "Unggah Foto", "Format: PNG, JPG, WEBP")
                        photo = gr.File(label="Foto", show_label=False, file_types=[".png", ".jpg", ".jpeg", ".webp"], type="filepath", elem_classes="upload-zone")
                        photo_info = gr.Markdown("Belum ada foto dipilih.", elem_classes="meta")
                    with gr.Group(elem_classes="card"):
                        step(2, "Pilih Subjek", "Otomatis atau tunjuk titik objek")
                        photo_mode = gr.Radio(SUBJECTS, value="Manusia", show_label=False, elem_classes="choice")
                        with gr.Column(visible=False) as photo_object_box:
                            gr.HTML('<div class="hint">Klik objek pada foto. <b>🟢 Simpan</b> untuk objek, <b>🔴 Hapus</b> untuk latar.</div>')
                            photo_frame = gr.Image(type="pil", interactive=False, show_label=False)
                            photo_action = gr.Radio(POINTS, value="Pertahankan", label="Jenis Titik", elem_classes="choice")
                            photo_clear = gr.Button("Hapus Semua Titik", size="sm")
                with gr.Column(scale=5), gr.Group(elem_classes="card"):
                    step(3, "Proses", "Tentukan nama file hasil")
                    photo_name = gr.Textbox(label="Nama File", placeholder="foto-hasil", max_lines=1)
                    photo_start = gr.Button("🚀 Hapus Latar", variant="primary", size="lg")
                    photo_result = gr.Image(label="Hasil Transparan", type="filepath", interactive=False)
                    photo_card = gr.HTML(EMPTY_DOWNLOAD)
            photo_mode.change(lambda subject: gr.update(visible=subject == "Objek umum"), photo_mode, photo_object_box, queue=False)
            photo.change(default_name, photo, photo_name, queue=False)
            photo.change(lambda path: load_source(path, True), photo, [photo_frame, photo_original, photo_points, photo_info], concurrency_id="gpu")
            photo_frame.select(select_point, [photo_original, photo_points, photo_action], [photo_frame, photo_points], queue=False)
            photo_clear.click(clear_points, photo_original, [photo_frame, photo_points], queue=False)
            photo_start.click(
                process_photo,
                [photo, photo_mode, gr.State("Detail"), photo_points, photo_name],
                [photo_result, photo_card],
                concurrency_id="gpu",
                concurrency_limit=1,
            )
        gr.HTML('<div class="footer-note">RemoveBG Local · 100% Offline &amp; Privat · Hasil tersimpan di <code>data/outputs</code></div>')
    return app


def main():
    prepare_dirs()
    logging.basicConfig(level=logging.INFO, filename=ROOT / "data" / "app.log", encoding="utf-8")
    build_app().queue(max_size=4, default_concurrency_limit=1).launch(
        server_name="127.0.0.1", inbrowser=True, share=False,
        allowed_paths=[str(OUTPUTS)], max_file_size="20gb",
    )


if __name__ == "__main__":
    main()
