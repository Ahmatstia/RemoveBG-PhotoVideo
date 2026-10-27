import logging
import os
import threading

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import gradio as gr
import torch
from PIL import Image, ImageDraw

from removebg.application.service import run_photo, run_video
from removebg.config import OUTPUTS, ROOT, prepare_dirs
from removebg.domain import Cancelled
from removebg.infrastructure.media import inspect_video, read_photo

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
        return image, image, [], details
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
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill="#15b981" if label else "#ed514d", outline="white", width=2)
    return annotated, points


def clear_points(original):
    return original, []


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
        status = f"Selesai · {report['frames']} frame · {report['wall_seconds']:.1f} detik proses · {report['pipeline_fps']:.1f} fps"
        return result, preview, status
    except Cancelled:
        return None, None, "Dibatalkan. File sumber tidak diubah."
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


def build_app():
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CUDA belum tersedia — jalankan setup.ps1"
    theme = gr.themes.Soft(primary_hue="emerald", neutral_hue="slate")
    with gr.Blocks(title="RemoveBG Local", theme=theme, css=".gradio-container {max-width: 1180px !important}") as app:
        gr.Markdown("# RemoveBG Local\nHapus latar, pertahankan subjek. Video & foto diproses di laptopmu.")
        gr.Markdown(f"**GPU:** {gpu} · **Video:** hingga 1080p / 15 menit · **Ekspor:** resolusi sumber")
        with gr.Tab("Video"):
            original = gr.State()
            points = gr.State([])
            with gr.Row():
                with gr.Column():
                    source = gr.File(label="1. Pilih video", file_types=[".mp4", ".mov", ".mkv", ".avi", ".webm"], type="filepath")
                    details = gr.Markdown("Pilih file untuk memulai.")
                    mode = gr.Radio(["Manusia", "Objek umum"], value="Manusia", label="2. Subjek")
                    gr.Markdown("**Manusia:** otomatis mengambil orang yang terdeteksi. **Objek umum:** klik bagian objek pada frame pertama; tambahkan titik Buang untuk mengecualikan latar. Gunakan satu klip kontinu tanpa pergantian adegan.")
                    frame = gr.Image(type="pil", label="Frame pertama — klik untuk memilih objek", interactive=False)
                    with gr.Row():
                        action = gr.Radio(["Pertahankan", "Buang"], value="Pertahankan", label="Jenis titik")
                        clear = gr.Button("Hapus titik")
                with gr.Column():
                    quality = gr.Radio(["Detail", "Cepat"], value="Detail", label="Kualitas manusia", info="Detail membantu subjek full-body; resolusi ekspor tetap sama. Objek umum memakai SAM 2 Small pada kedua pilihan.")
                    export = gr.Dropdown([("MOV transparan · ProRes 4444 + audio", "transparent"), ("Mask lossless · MKV FFV1 tanpa audio", "mask")], value="transparent", label="3. Format ekspor")
                    gr.Markdown("MOV transparan berukuran besar. Jika editor tidak mendukungnya, gunakan mask putih/hitam bersama video sumber. Preview menggunakan pola kotak; pola tersebut tidak masuk ke hasil transparan.")
                    with gr.Row():
                        trial = gr.Button("Uji 5 detik pertama")
                        start = gr.Button("Proses video lengkap", variant="primary")
                        cancel = gr.Button("Batalkan", variant="stop")
                    status = gr.Markdown("Siap. Uji klip pendek terlebih dahulu untuk memeriksa tepian.")
                    preview = gr.Video(label="Preview 5 detik · tanpa audio", interactive=False)
                    result = gr.File(label="Unduh hasil", interactive=False)
            source.change(load_source, source, [frame, original, points, details], concurrency_id="gpu")
            frame.select(select_point, [original, points, action], [frame, points], queue=False)
            clear.click(clear_points, original, [frame, points], queue=False)
            inputs = [source, mode, quality, points, export]
            start.click(process_video, inputs + [gr.State(False)], [result, preview, status], concurrency_id="gpu", concurrency_limit=1)
            trial.click(process_video, inputs + [gr.State(True)], [result, preview, status], concurrency_id="gpu", concurrency_limit=1)
            cancel.click(stop, outputs=status, queue=False)
        with gr.Tab("Foto"):
            photo_original = gr.State()
            photo_points = gr.State([])
            with gr.Row():
                with gr.Column():
                    photo = gr.File(label="Pilih foto", file_types=[".png", ".jpg", ".jpeg", ".webp"], type="filepath")
                    photo_info = gr.Markdown("Foto hingga 3840×2160 atau 2160×3840; hasil PNG transparan.")
                    photo_mode = gr.Radio(["Manusia", "Objek umum"], value="Manusia", label="Subjek foto")
                    photo_frame = gr.Image(type="pil", interactive=False, label="Klik subjek untuk mode Objek umum")
                    photo_action = gr.Radio(["Pertahankan", "Buang"], value="Pertahankan", label="Jenis titik")
                    photo_clear = gr.Button("Hapus titik foto")
                    photo_start = gr.Button("Hapus latar foto", variant="primary")
                with gr.Column():
                    photo_result = gr.Image(label="Hasil PNG transparan", type="filepath", interactive=False)
                    photo_download = gr.File(label="Unduh PNG", interactive=False)
            photo.change(lambda path: load_source(path, True), photo, [photo_frame, photo_original, photo_points, photo_info], concurrency_id="gpu")
            photo_frame.select(select_point, [photo_original, photo_points, photo_action], [photo_frame, photo_points], queue=False)
            photo_clear.click(clear_points, photo_original, [photo_frame, photo_points], queue=False)
            photo_start.click(process_photo, [photo, photo_mode, gr.State("Detail"), photo_points], [photo_result, photo_download], concurrency_id="gpu", concurrency_limit=1)
        gr.Markdown("Berjalan lokal di 127.0.0.1. Model diunduh pada penggunaan pertama. Input video: SDR; hasil AI 8-bit. SAM 2 menghasilkan segmentasi, sehingga rambut halus, kaca, dan motion blur dapat memerlukan koreksi. Hasil tersimpan di `data/outputs`.")
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
