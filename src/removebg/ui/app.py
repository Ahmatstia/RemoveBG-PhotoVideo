import atexit
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
from transformers.models.whisper.tokenization_whisper import LANGUAGES

from removebg.application.service import run_photo, run_video
from removebg.application.transcription import run_youtube_transcription
from removebg.application.youtube_download import run_youtube_download
from removebg.config import OUTPUTS, ROOT, clear_outputs, prepare_dirs
from removebg.domain import Cancelled
from removebg.infrastructure.media import inspect_video, read_photo
from removebg.ui.theme import CSS, FORCE_DARK, make_theme

logger = logging.getLogger(__name__)
running = {}
TRANSCRIPT_LANGUAGES = [(name.title(), name) for name in sorted(LANGUAGES.values())]
TRANSCRIPT_LANGUAGES.insert(0, ("Auto", "Auto"))


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


EMPTY_DOWNLOAD = '<div class="download-empty">File hasil unduhan akan muncul di sini.</div>'


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


def process_transcription(url, language, name, request: gr.Request, progress=gr.Progress()):  # noqa: B008 - Gradio injects progress via this default.
    if not str(url or "").strip():
        raise gr.Error("Tempel tautan video YouTube terlebih dahulu.")
    cancel = threading.Event()
    running[request.session_hash] = cancel
    try:
        result = run_youtube_transcription(
            url, language, name,
            lambda fraction, description: progress(fraction, desc=description), cancel,
        )
        status = f"✅ **Selesai** · {result['title']} · {result['sentences']} kalimat · {result['words']} kata"
        return result["text"], result["txt"], result["srt"], result["vtt"], result["json"], status
    except Cancelled:
        return "", None, None, None, None, "Proses transkrip dibatalkan."
    except torch.cuda.OutOfMemoryError as error:
        raise gr.Error("VRAM tidak cukup untuk model Whisper. Tutup aplikasi GPU lain, lalu coba lagi.") from error
    except Exception as error:
        logger.exception("YouTube transcription failed")
        raise gr.Error(str(error)) from error
    finally:
        running.pop(request.session_hash, None)


def process_youtube_download(url, quality, name, request: gr.Request, progress=gr.Progress()):  # noqa: B008 - Gradio injects progress via this default.
    if not str(url or "").strip():
        raise gr.Error("Tempel tautan video YouTube terlebih dahulu.")
    cancel = threading.Event()
    running[request.session_hash] = cancel
    try:
        result = run_youtube_download(
            url, quality, name,
            lambda fraction, description: progress(fraction, desc=description), cancel,
        )
        return result["path"], f"✅ **Selesai** · {result['title']} · {result['size'] / (1024 * 1024):.1f} MB"
    except Cancelled:
        return None, "Unduhan dibatalkan."
    except Exception as error:
        logger.exception("YouTube video download failed")
        raise gr.Error(str(error)) from error
    finally:
        running.pop(request.session_hash, None)


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
  <div class="hero-top">
    <div class="hero-brand">
      <div class="logo">✂</div>
      <div class="hero-titles">
        <h1>RemoveBG <span>Local</span></h1>
        <p>Hapus latar video dan foto, buat transkrip multilingual, dan simpan video YouTube langsung dari PC-mu.</p>
      </div>
    </div>
    <div class="theme-switch-container">
      <button id="theme-toggle-btn" type="button" class="theme-btn" onclick="window.toggleTheme()">
        <span class="theme-icon">🍦</span> <span class="theme-text">Mode Krem & Putih</span>
      </button>
    </div>
  </div>
  <div class="chips">
    <span class="chip">⚡ {gpu}</span>
    <span class="chip ok">🔊 Audio Utuh</span>
    <span class="chip ok">🔒 Pemrosesan lokal</span>
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
        with gr.Tab("📝 Transkrip YouTube"):
            with gr.Row(equal_height=False):
                with gr.Column(scale=4):
                    with gr.Group(elem_classes="card"):
                        step(1, "Tautan YouTube", "Fitur ini menghasilkan transkrip; file video tidak disimpan.")
                        transcript_url = gr.Textbox(label="URL video", placeholder="https://www.youtube.com/watch?v=…", max_lines=1)
                        transcript_language = gr.Dropdown(TRANSCRIPT_LANGUAGES, label="Bahasa", value="Auto", filterable=True, allow_custom_value=False)
                        transcript_name = gr.Textbox(label="Nama file", placeholder="otomatis dari judul video", max_lines=1)
                        transcript_start = gr.Button("🚀 Buat Transkrip", variant="primary", size="lg")
                        transcript_cancel = gr.Button("Batal", variant="stop", size="sm")
                        transcript_status = gr.Markdown("Siap membuat transkrip.", elem_classes="status")
                    with gr.Group(elem_classes="card"):
                        step(2, "Unduh hasil transkrip", "SRT/VTT berisi waktu per kalimat. JSON berisi waktu tiap kata.")
                        transcript_txt = gr.File(label="Teks (.txt)", interactive=False)
                        transcript_srt = gr.File(label="Subtitle (.srt)", interactive=False)
                        transcript_vtt = gr.File(label="Subtitle Web (.vtt)", interactive=False)
                        transcript_json = gr.File(label="Kata + timestamp (.json)", interactive=False)
                with gr.Column(scale=6):
                    with gr.Group(elem_classes="card"):
                        gr.HTML('<div class="step-title">Pratinjau Transkrip</div><p class="step-sub" style="margin-left:0">Cari nama bahasa di dropdown atau pilih Auto. Jika bahasa sudah diketahui, pilihan manual menghindari deteksi bahasa dan memakai decoding lebih teliti.</p>')
                        transcript_preview = gr.Textbox(label="Hasil", lines=26, max_lines=40, interactive=False, placeholder="Hasil transkrip akan muncul di sini.")
            transcript_start.click(
                process_transcription,
                [transcript_url, transcript_language, transcript_name],
                [transcript_preview, transcript_txt, transcript_srt, transcript_vtt, transcript_json, transcript_status],
                concurrency_id="gpu",
                concurrency_limit=1,
            )
            transcript_cancel.click(stop, outputs=transcript_status, queue=False)
        with gr.Tab("⬇️ Unduh YouTube"):
            with gr.Row(equal_height=False):
                with gr.Column(scale=5):
                    with gr.Group(elem_classes="card"):
                        step(1, "Tautan YouTube", "Fitur ini mengunduh file video dan tidak membuat transkrip.")
                        download_url = gr.Textbox(label="URL video", placeholder="https://www.youtube.com/watch?v=…", max_lines=1)
                        download_quality = gr.Radio(["Terbaik", "1080p", "720p"], value="Terbaik", label="Kualitas video", elem_classes="choice")
                        download_name = gr.Textbox(label="Nama file (opsional)", placeholder="otomatis dari judul video", max_lines=1)
                        download_start = gr.Button("🚀 Unduh Video", variant="primary", size="lg")
                        download_cancel = gr.Button("Batal", variant="stop", size="sm")
                        download_status = gr.Markdown("Siap mengunduh video.", elem_classes="status")
                with gr.Column(scale=5):
                    with gr.Group(elem_classes="card"):
                        gr.HTML('<div class="step-title">File Video</div><p class="step-sub" style="margin-left:0">File tersimpan di folder output project dan dapat diunduh dari sini.</p>')
                        download_result = gr.File(label="Hasil Video", interactive=False)
            download_start.click(
                process_youtube_download,
                [download_url, download_quality, download_name],
                [download_result, download_status],
                concurrency_id="youtube-download",
                concurrency_limit=1,
            )
            download_cancel.click(stop, outputs=download_status, queue=False)
        gr.HTML('<div class="footer-note">Hasil disimpan sementara selama aplikasi berjalan. Klik Unduh untuk menyimpan salinan.</div>')
    return app


def main():
    clear_outputs()
    prepare_dirs()
    atexit.register(clear_outputs)
    logging.basicConfig(level=logging.INFO, filename=ROOT / "data" / "app.log", encoding="utf-8")
    build_app().queue(max_size=4, default_concurrency_limit=1).launch(
        server_name="127.0.0.1", inbrowser=True, share=False,
        allowed_paths=[str(OUTPUTS)], max_file_size="20gb",
    )


if __name__ == "__main__":
    main()
