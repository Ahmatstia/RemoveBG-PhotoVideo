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


EMPTY_PLAYER = '<div class="player empty">Preview akan muncul di sini setelah proses selesai.</div>'


def video_player(path):
    # Native <video controls> provides play, seek, volume and mute; gr.Video has no volume control.
    if not path:
        return EMPTY_PLAYER
    url = "/gradio_api/file=" + quote(Path(path).as_posix(), safe="/:")
    return (f'<div class="player"><video src="{url}" controls playsinline preload="metadata" '
            f'controlslist="nodownload"></video><p>🔊 Gunakan ikon speaker pada pemutar untuk mute atau mengatur volume.</p></div>')


EMPTY_DOWNLOAD = '<div class="download-placeholder" style="padding:16px;text-align:center;color:#8c7a7c;font-size:13px;border:1.5px dashed #3a2327;border-radius:14px;background:#100a0b;margin-top:12px;">Tombol unduh akan muncul di sini setelah proses selesai.</div>'


def download_card(file_path):
    if not file_path or not Path(file_path).exists():
        return EMPTY_DOWNLOAD
    path = Path(file_path)
    size_mb = path.stat().st_size / (1024 * 1024)
    filename = path.name
    ext = path.suffix.lower()
    url = "/gradio_api/file=" + quote(path.as_posix(), safe="/:")
    if ext == ".mov":
        badge = "✨ Video Transparan (MOV ProRes 4444)"
        desc = "Background 100% transparan / bolong (hanya objek/manusia). Siap langsung ditumpuk ke timeline CapCut PC, Premiere Pro, After Effects, atau DaVinci Resolve tanpa kunci warna."
    elif ext == ".mp4":
        badge = "🟩 Video Layar Hijau / Hitam (MP4)"
        desc = "Format MP4 standar dengan warna latar solid. Gunakan efek Chroma Key (Kunci Kroma) di aplikasi HP untuk menghilangkan warna latarnya."
    elif ext == ".mkv":
        badge = "⬛ Mask Lossless (MKV FFV1)"
        desc = "Video siluet matte hitam-putih untuk masking komposit profesional."
    else:
        badge = "🖼 Foto PNG Transparan"
        desc = "Foto PNG transparan tanpa latar belakang."

    return (
        f'<div class="download-box">'
        f'<div class="download-meta">'
        f'<span class="download-badge">{badge}</span>'
        f'<span class="download-filesize">💾 {size_mb:.1f} MB</span>'
        f'</div>'
        f'<div class="download-filename">📁 <b>{filename}</b></div>'
        f'<p class="download-desc">{desc}</p>'
        f'<a href="{url}" download="{filename}" class="btn-download-hero">'
        f"⬇ UNDUH {filename} ({size_mb:.1f} MB)"
        f"</a>"
        f'<p class="download-path-tip">📍 File juga tersimpan offline di laptopmu: <code>{path.parent}</code></p>'
        f"</div>"
    )


def default_name(path):
    return f"{Path(path).stem}-tanpa-latar" if path else ""


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
        done = f"{report['frames']} frame · {report['wall_seconds']:.1f} detik proses · {report['pipeline_fps']:.1f} fps"
        status = (f"✅ **Selesai** · `{Path(result).name}` · durasi {clock(report['processed_seconds'])} · {done}. "
                  "Klik tombol merah besar di bawah untuk mengunduh.")
        size_mb = Path(result).stat().st_size / (1024 * 1024)
        btn_update = gr.update(value=str(result), label=f"⬇ Unduh {Path(result).name} ({size_mb:.1f} MB)", visible=True)
        return download_card(result), btn_update, video_player(preview), status
    except Cancelled:
        return EMPTY_DOWNLOAD, gr.update(visible=False), EMPTY_PLAYER, "Dibatalkan. File sumber tidak diubah."
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


def process_photo(path, mode, quality, points, name):
    if not path:
        raise gr.Error("Pilih foto terlebih dahulu.")
    try:
        result = run_photo(path, mode, quality, points, output_name=name)
        size_mb = Path(result).stat().st_size / (1024 * 1024)
        btn_update = gr.update(value=str(result), label=f"⬇ Unduh {Path(result).name} ({size_mb:.1f} MB)", visible=True)
        return result, download_card(result), btn_update
    except Exception as error:
        logger.exception("Photo processing failed")
        raise gr.Error(str(error)) from error


SUBJECTS = [("🧍 Manusia · otomatis", "Manusia"), ("📦 Objek lain · klik manual", "Objek umum")]
POINTS = [("🟢 Pertahankan", "Pertahankan"), ("🔴 Buang", "Buang")]
QUALITIES = [("✨ Detail · lebih halus", "Detail"), ("⚡ Cepat", "Cepat")]
EXPORTS = [
    ("✨ Transparan Asli (.mov ProRes 4444) · Latar kosong / hanya objek, untuk CapCut PC / Premiere / DaVinci", "transparent"),
    ("🟩 Layar Hijau (.mp4 Chroma Key) · Background hijau solid, siap pakai di HP / CapCut mobile", "mp4_green"),
    ("⬛ Layar Hitam (.mp4 H.264) · Background hitam solid, kompatibel semua pemutar", "mp4_black"),
    ("⬛⬜ Mask Hitam-Putih (.mkv) · Luma Matte FFV1", "mask"),
]


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
                        step(3, "Pilih format hasil & nama file", "Pilih Transparan untuk hanya objek/manusia saja, atau Layar Hijau jika butuh green screen.")
                        export = gr.Radio(EXPORTS, value="transparent", label="Pilihan Format Hasil Video", elem_classes="choice")
                        gr.HTML(
                            '<div class="hint" style="margin-top:6px;margin-bottom:12px;">'
                            '💡 <b>Panduan Hasil:</b><br>'
                            '• <b>✨ Transparan Asli (.mov ProRes)</b>: Latar belakang 100% bolong / transparan (hanya manusia atau objek). Langsung tempel ke video apa pun tanpa perlu chroma key.<br>'
                            '• <b>🟩 Layar Hijau (.mp4)</b>: Memakai background hijau solid jika aplikasi video di HP Anda (CapCut mobile/InShot) mewajibkan format MP4 dan fitur Chroma Key.'
                            '</div>'
                        )
                        video_name = gr.Textbox(label="Nama file hasil", placeholder="contoh: video-promo-final", max_lines=1,
                                                info="Tanpa ekstensi. Format (.mov atau .mp4) ditambahkan otomatis.")
                        start = gr.Button("🚀 Proses video", variant="primary", size="lg")
                        cancel = gr.Button("Batalkan", variant="stop", size="sm")
                        status = gr.Markdown("Siap. Pilih video, tentukan format & nama file, lalu klik **Proses video**.", elem_classes="status")
                    with gr.Group(elem_classes="card"):
                        gr.HTML('<div class="step-title">Hasil</div><p class="step-sub" style="margin-left:0">Preview hanya <b>5 detik pertama</b> (pola kotak = transparan). Unduh file lengkap melalui tombol di bawah.</p>')
                        preview = gr.HTML(EMPTY_PLAYER)
                        result_card = gr.HTML(EMPTY_DOWNLOAD)
                        result_btn = gr.DownloadButton("⬇ Unduh Alternatif File Video", variant="secondary", size="lg", visible=False)
            mode.change(toggle_subject, mode, [quality, object_box], queue=False)
            source.change(default_name, source, video_name, queue=False)
            source.change(load_source, source, [frame, original, points, details], concurrency_id="gpu")
            frame.select(select_point, [original, points, action], [frame, points], queue=False)
            clear.click(clear_points, original, [frame, points], queue=False)
            start.click(
                process_video,
                [source, mode, quality, points, export, video_name],
                [result_card, result_btn, preview, status],
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
                    step(3, "Nama file & proses", "Tentukan nama file hasil, lalu klik Hapus latar foto.")
                    photo_name = gr.Textbox(label="Nama file hasil", placeholder="contoh: foto-produk", max_lines=1,
                                            info="Tanpa ekstensi. .png ditambahkan otomatis. Karakter terlarang dibuang.")
                    photo_start = gr.Button("🚀 Hapus latar foto", variant="primary", size="lg")
                    photo_result = gr.Image(label="Hasil PNG transparan", type="filepath", interactive=False)
                    photo_card = gr.HTML(EMPTY_DOWNLOAD)
                    photo_download = gr.DownloadButton("⬇ Unduh PNG", variant="primary", size="lg", visible=False)
            photo_mode.change(lambda subject: gr.update(visible=subject == "Objek umum"), photo_mode, photo_object_box, queue=False)
            photo.change(default_name, photo, photo_name, queue=False)
            photo.change(lambda path: load_source(path, True), photo, [photo_frame, photo_original, photo_points, photo_info], concurrency_id="gpu")
            photo_frame.select(select_point, [photo_original, photo_points, photo_action], [photo_frame, photo_points], queue=False)
            photo_clear.click(clear_points, photo_original, [photo_frame, photo_points], queue=False)
            photo_start.click(
                process_photo,
                [photo, photo_mode, gr.State("Detail"), photo_points, photo_name],
                [photo_result, photo_card, photo_download],
                concurrency_id="gpu",
                concurrency_limit=1,
            )
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
