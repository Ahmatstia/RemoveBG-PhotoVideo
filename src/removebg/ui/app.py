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
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


EMPTY_PLAYER = '<div class="player empty">Preview akan muncul di sini setelah proses selesai.</div>'


def video_player(path):
    # Native <video controls> provides play, seek, volume and mute; gr.Video has no volume control.
    if not path:
        return EMPTY_PLAYER
    url = "/gradio_api/file=" + quote(Path(path).as_posix(), safe="/:")
    return (f'<div class="player"><video src="{url}" controls playsinline preload="metadata" '
            f'controlslist="nodownload"></video><p>🔊 Gunakan ikon speaker pada pemutar untuk mute atau mengatur volume.</p></div>')


def process_video(path, mode, quality, points, export, preview_only, request: gr.Request, progress=gr.Progress()):  # noqa: B008 - Gradio injects progress via this default.
    if not path:
        raise gr.Error("Pilih video terlebih dahulu.")
    cancel = threading.Event()
    running[request.session_hash] = cancel
    try:
        result, preview, report = run_video(
            path, mode, quality, points, export, preview_only, cancel,
            lambda fraction, description: progress(fraction, desc=description),
        )
        done = f"{report['frames']} frame · {report['wall_seconds']:.1f} detik proses · {report['pipeline_fps']:.1f} fps"
        if preview_only:
            status = (f"⏱ **Uji 5 detik selesai** ({done}). Ini hanya cuplikan awal, bukan hasil akhir. "
                      "Klik **🚀 Proses video lengkap** untuk memproses seluruh video.")
        else:
            status = (f"✅ **Video lengkap selesai** · durasi {clock(report['processed_seconds'])} · {done}. "
                      "File di **Unduh hasil** berisi seluruh durasi; preview di atas hanya 5 detik pertama.")
        return result, video_player(preview), status
    except Cancelled:
        return None, EMPTY_PLAYER, "Dibatalkan. File sumber tidak diubah."
    except torch.cuda.OutOfMemoryError as error:
        raise gr.Error("VRAM tidak cukup. Tutup aplikasi GPU lain atau gunakan mode Cepat.") from error
    except Exception as error:
        logger.exception("Video processing failed")
        raise gr.Error(str(error)) from error
    finally:
        running.pop(request.session_hash, None)


def stop(request: gr.Request):
    event = running.get(request.session_hash)
    if event:
        event.set()
        return "Pembatalan diminta; menunggu operasi model/frame aktif selesai."
    return "Tidak ada proses aktif pada sesi ini."


def process_photo(path, mode, quality, points):
    if not path:
        raise gr.Error("Pilih foto terlebih dahulu.")
    try:
        result = run_photo(path, mode, quality, points)
        return result, result
    except Exception as error:
        logger.exception("Photo processing failed")
        raise gr.Error(str(error)) from error


SUBJECTS = [("🧍 Manusia · otomatis", "Manusia"), ("📦 Objek lain · klik manual", "Objek umum")]
POINTS = [("🟢 Pertahankan", "Pertahankan"), ("🔴 Buang", "Buang")]
QUALITIES = [("✨ Detail · lebih halus", "Detail"), ("⚡ Cepat", "Cepat")]
EXPORTS = [("🎬 Video transparan · MOV ProRes 4444 + audio", "transparent"),
           ("⬛⬜ Mask hitam-putih · MKV lossless + audio", "mask")]


def step(number, title, subtitle):
    return gr.HTML(f'<div class="step-title"><span class="step-no">{number}</span>{title}</div><p class="step-sub">{subtitle}</p>')


def toggle_subject(subject):
    return gr.update(visible=subject == "Manusia"), gr.update(visible=subject == "Objek umum")


def hero(gpu):
    return f"""<div class="hero">
  <div class="hero-top"><div class="logo">✂</div><h1>RemoveBG <span>Local</span></h1></div>
  <p>Hapus latar belakang video &amp; foto dalam tiga langkah. Berani, rapi, dan 100% berjalan di laptopmu.</p>
  <div class="chips"><span class="chip">⚡ {gpu}</span><span class="chip">🎞 Hingga 1080p · 15 menit</span>
  <span class="chip ok">🔊 Audio tetap terjaga</span><span class="chip ok">🔒 Tanpa cloud</span></div>
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
                        step(1, "Pilih video", "Seret file ke kotak di bawah. MP4, MOV, MKV, AVI, atau WEBM.")
                        source = gr.File(label="Video", show_label=False, file_types=[".mp4", ".mov", ".mkv", ".avi", ".webm"], type="filepath", elem_classes="upload-zone")
                        details = gr.Markdown("Belum ada video dipilih.", elem_classes="meta")
                    with gr.Group(elem_classes="card"):
                        step(2, "Apa yang dipertahankan?", "Pilih manusia untuk hasil otomatis, atau objek lain jika kamu ingin menunjuknya.")
                        mode = gr.Radio(SUBJECTS, value="Manusia", show_label=False, elem_classes="choice")
                        quality = gr.Radio(QUALITIES, value="Detail", label="Kualitas", info="Detail lebih bagus untuk subjek full-body. Ukuran video hasil tetap sama.", elem_classes="choice")
                        with gr.Column(visible=False) as object_box:
                            gr.HTML('<div class="hint">Klik bagian objek pada gambar di bawah. <b>🟢 Pertahankan</b> untuk objek, <b>🔴 Buang</b> untuk latar yang ikut terpilih. Gunakan satu klip tanpa pergantian adegan.</div>')
                            frame = gr.Image(type="pil", show_label=False, interactive=False)
                            action = gr.Radio(POINTS, value="Pertahankan", label="Jenis titik", elem_classes="choice")
                            clear = gr.Button("Hapus semua titik", size="sm")
                with gr.Column(scale=5):
                    with gr.Group(elem_classes="card"):
                        step(3, "Pilih hasil & mulai", "Coba 5 detik dulu untuk memeriksa tepian, lalu proses seluruh video.")
                        export = gr.Radio(EXPORTS, value="transparent", show_label=False, elem_classes="choice")
                        with gr.Row():
                            trial = gr.Button("⏱ Uji 5 detik", size="lg")
                            start = gr.Button("🚀 Proses video lengkap", variant="primary", size="lg")
                        cancel = gr.Button("Batalkan", variant="stop", size="sm")
                        status = gr.Markdown("Siap. Mulai dengan **Uji 5 detik**.", elem_classes="status")
                    with gr.Group(elem_classes="card"):
                        gr.HTML('<div class="step-title">Hasil</div><p class="step-sub" style="margin-left:0">Preview hanya <b>5 detik pertama</b> (pola kotak = transparan). Hasil akhir seluruh durasi ada di tombol unduh di bawahnya.</p>')
                        preview = gr.HTML(EMPTY_PLAYER)
                        result = gr.File(label="⬇ Unduh hasil", interactive=False)
            mode.change(toggle_subject, mode, [quality, object_box], queue=False)
            source.change(load_source, source, [frame, original, points, details], concurrency_id="gpu")
            frame.select(select_point, [original, points, action], [frame, points], queue=False)
            clear.click(clear_points, original, [frame, points], queue=False)
            inputs = [source, mode, quality, points, export]
            start.click(process_video, inputs + [gr.State(False)], [result, preview, status], concurrency_id="gpu", concurrency_limit=1)
            trial.click(process_video, inputs + [gr.State(True)], [result, preview, status], concurrency_id="gpu", concurrency_limit=1)
            cancel.click(stop, outputs=status, queue=False)
        with gr.Tab("🖼 Foto"):
            photo_original = gr.State()
            photo_points = gr.State([])
            with gr.Row(equal_height=False):
                with gr.Column(scale=5):
                    with gr.Group(elem_classes="card"):
                        step(1, "Pilih foto", "PNG, JPG, atau WEBP hingga 3840×2160.")
                        photo = gr.File(label="Foto", show_label=False, file_types=[".png", ".jpg", ".jpeg", ".webp"], type="filepath", elem_classes="upload-zone")
                        photo_info = gr.Markdown("Belum ada foto dipilih.", elem_classes="meta")
                    with gr.Group(elem_classes="card"):
                        step(2, "Apa yang dipertahankan?", "Manusia otomatis. Objek lain: klik langsung pada foto.")
                        photo_mode = gr.Radio(SUBJECTS, value="Manusia", show_label=False, elem_classes="choice")
                        with gr.Column(visible=False) as photo_object_box:
                            gr.HTML('<div class="hint">Klik objek pada foto. <b>🟢 Pertahankan</b> untuk objek, <b>🔴 Buang</b> untuk bagian latar yang ikut terpilih.</div>')
                            photo_frame = gr.Image(type="pil", interactive=False, show_label=False)
                            photo_action = gr.Radio(POINTS, value="Pertahankan", label="Jenis titik", elem_classes="choice")
                            photo_clear = gr.Button("Hapus semua titik", size="sm")
                with gr.Column(scale=5), gr.Group(elem_classes="card"):
                    step(3, "Hapus latar", "Hasilnya PNG transparan.")
                    photo_start = gr.Button("🚀 Hapus latar foto", variant="primary", size="lg")
                    photo_result = gr.Image(label="Hasil PNG transparan", type="filepath", interactive=False)
                    photo_download = gr.File(label="⬇ Unduh PNG", interactive=False)
            photo_mode.change(lambda subject: gr.update(visible=subject == "Objek umum"), photo_mode, photo_object_box, queue=False)
            photo.change(lambda path: load_source(path, True), photo, [photo_frame, photo_original, photo_points, photo_info], concurrency_id="gpu")
            photo_frame.select(select_point, [photo_original, photo_points, photo_action], [photo_frame, photo_points], queue=False)
            photo_clear.click(clear_points, photo_original, [photo_frame, photo_points], queue=False)
            photo_start.click(process_photo, [photo, photo_mode, gr.State("Detail"), photo_points], [photo_result, photo_download], concurrency_id="gpu", concurrency_limit=1)
        gr.HTML('<div class="footer-note">Berjalan lokal di 127.0.0.1 · Model diunduh saat pertama dipakai · Input video SDR, hasil AI 8-bit · Rambut halus, kaca, dan motion blur dapat memerlukan koreksi · Hasil tersimpan di <code>data/outputs</code></div>')
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
