import atexit
import json
import logging
import os
import shutil
import threading
import uuid
import webbrowser
from pathlib import Path

import torch
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from removebg.application.service import run_photo, run_video
from removebg.application.transcription import run_youtube_transcription
from removebg.application.youtube_download import run_instagram_photo_download, run_tiktok_photo_download, run_tiktok_video_download, run_video_download
from removebg.config import OUTPUTS, ROOT, clear_outputs, prepare_dirs
from removebg.domain import Cancelled
from removebg.infrastructure.media import inspect_video, read_photo
from removebg.infrastructure.browser_capture import run_browser_capture

logger = logging.getLogger(__name__)
WEB_OUT = ROOT / "web" / "out"
UPLOAD_DIR = OUTPUTS / "uploads"
MAX_UPLOAD_BYTES = 20 * 1024**3
UPLOAD_TYPES = {
    "video": {".mp4", ".mov", ".mkv", ".avi", ".webm"},
    "photo": {".png", ".jpg", ".jpeg", ".webp"},
}
jobs = {}
uploads = {}
media_captures = {}
state_lock = threading.Lock()
work_lock = threading.Lock()
app = FastAPI(title="RemoveBG Local API", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["Content-Type"],
)


def public_job(job):
    return {key: job[key] for key in ("id", "kind", "state", "progress", "message", "result", "error")}


def save_upload(upload_id, kind, path):
    try:
        if kind == "video":
            info, image = inspect_video(path)
            details = {
                "width": info.width,
                "height": info.height,
                "duration": info.duration,
                "fps": float(info.rate),
                "has_audio": info.has_audio,
            }
        else:
            image = read_photo(path)
            details = {"width": image.shape[1], "height": image.shape[0]}
        from PIL import Image

        preview = Image.fromarray(image)
        preview.thumbnail((900, 900), Image.Resampling.LANCZOS)
        preview_path = UPLOAD_DIR / f"{upload_id}.webp"
        preview.save(preview_path, "WEBP", quality=84, method=4)
        uploads[upload_id] = {"kind": kind, "path": path, "preview": preview_path, "details": details}
        return details
    except BaseException:
        path.unlink(missing_ok=True)
        raise


@app.get("/api/health")
def health():
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    return {"ok": True, "gpu": gpu}


@app.get("/api/languages")
def languages():
    from transformers.models.whisper.tokenization_whisper import LANGUAGES

    return {"languages": ["Auto", *sorted(LANGUAGES.values())]}


@app.post("/api/uploads")
async def create_upload(file: UploadFile = File(...), kind: str = Form(...)):
    if kind not in UPLOAD_TYPES:
        raise HTTPException(400, "Jenis file tidak didukung.")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in UPLOAD_TYPES[kind]:
        raise HTTPException(400, "Format file tidak didukung.")
    prepare_dirs()
    upload_id = uuid.uuid4().hex
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / f"{upload_id}{suffix}"
    total = 0
    try:
        with path.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Ukuran file maksimal 20 GB.")
                target.write(chunk)
        details = save_upload(upload_id, kind, path)
        return {"id": upload_id, "kind": kind, "details": details, "preview_url": f"/api/uploads/{upload_id}/preview"}
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    except Exception as error:
        path.unlink(missing_ok=True)
        raise HTTPException(400, str(error)) from error
    finally:
        await file.close()


@app.get("/api/uploads/{upload_id}/preview")
def upload_preview(upload_id: str):
    item = uploads.get(upload_id)
    if not item or not item["preview"].is_file():
        raise HTTPException(404, "Pratinjau sudah tidak tersedia.")
    return FileResponse(item["preview"], media_type="image/webp")


@app.delete("/api/uploads/{upload_id}")
def delete_upload(upload_id: str):
    item = uploads.pop(upload_id, None)
    if item:
        item["path"].unlink(missing_ok=True)
        item["preview"].unlink(missing_ok=True)
    return {"ok": True}


def register_file(job, key, path, filename, inline=False):
    job["files"][key] = {"path": Path(path), "filename": filename, "inline": inline}
    return {"url": f"/api/jobs/{job['id']}/files/{key}", "filename": filename}


def run_job(job, payload):
    cancel = job["cancel"]

    def progress(value, message):
        with state_lock:
            job["progress"] = max(0, min(float(value), 1))
            job["message"] = str(message)

    try:
        while not work_lock.acquire(timeout=0.25):
            if cancel.is_set():
                raise Cancelled("Proses dibatalkan.")
            progress(0.01, "Menunggu pekerjaan lain selesai…")
        try:
            if cancel.is_set():
                raise Cancelled("Proses dibatalkan.")
            kind = payload["kind"]
            if kind in UPLOAD_TYPES:
                item = uploads.get(str(payload.get("upload_id", "")))
                if not item or item["kind"] != kind:
                    raise ValueError("File sumber tidak ditemukan. Unggah kembali file.")
                source = item["path"]
            if kind == "video":
                progress(0.02, "Memuat model dan memproses video…")
                result, preview, report = run_video(
                    str(source), payload.get("mode", "Manusia"), payload.get("quality", "Detail"),
                    payload.get("points", []), payload.get("export", "transparent"), False,
                    cancel, progress, output_name=payload.get("name"),
                )
                files = {
                    "result": register_file(job, "result", result, Path(result).name, inline=True),
                    "preview": register_file(job, "preview", preview, Path(preview).name, inline=True),
                }
                metadata = {"report": report}
            elif kind == "photo":
                progress(0.02, "Memuat model dan menghapus latar foto…")
                result = run_photo(
                    str(source), payload.get("mode", "Manusia"), "Detail",
                    payload.get("points", []), output_name=payload.get("name"),
                )
                if cancel.is_set():
                    Path(result).unlink(missing_ok=True)
                    Path(result).parent.rmdir()
                    raise Cancelled("Proses dibatalkan.")
                files = {"result": register_file(job, "result", result, Path(result).name, inline=True)}
                metadata = {}
            elif kind == "transcription":
                result = run_youtube_transcription(
                    payload.get("url", ""), payload.get("language", "Auto"), payload.get("name", ""),
                    progress, cancel,
                )
                files = {
                    key: register_file(job, key, result[key], Path(result[key]).name)
                    for key in ("txt", "srt", "vtt", "json")
                }
                metadata = {key: result[key] for key in ("text", "title", "words", "sentences")}
            elif kind == "download":
                url = str(payload.get("url", ""))
                platform = payload.get("platform", "YouTube")
                if platform == "TikTok" and "/photo/" in url.lower():
                    result = run_tiktok_photo_download(url, payload.get("name", ""), progress, cancel)
                    files = {
                        f"image_{index}": register_file(job, f"image_{index}", image["path"], image["filename"], inline=True)
                        for index, image in enumerate(result["images"], 1)
                    }
                    metadata = {"title": result["title"], "images": len(result["images"])}
                elif platform == "TikTok":
                    result = run_tiktok_video_download(
                        url, payload.get("name", ""), progress, cancel,
                    )
                    files = {"result": register_file(job, "result", result["path"], Path(result["path"]).name, inline=True)}
                    metadata = {"title": result["title"], "size": result["size"]}
                elif platform == "Instagram" and "/p/" in url.lower():
                    photo_error = None
                    try:
                        result = run_instagram_photo_download(url, payload.get("name", ""), progress, cancel)
                    except Cancelled:
                        raise
                    except Exception as error:
                        photo_error = error
                        result = None
                    if result:
                        files = {
                            f"image_{index}": register_file(job, f"image_{index}", image["path"], image["filename"], inline=True)
                            for index, image in enumerate(result["images"], 1)
                        }
                        metadata = {
                            "title": result["title"], "images": len(result["images"]),
                            "notice": result.get("notice"),
                        }
                    else:
                        try:
                            result = run_video_download(
                                url, platform, payload.get("quality", "Terbaik"), payload.get("name", ""), progress, cancel,
                            )
                        except Exception as video_error:
                            if photo_error:
                                photo_message = str(photo_error).lower()
                                if "no video" in str(video_error).lower() and any(
                                    text in photo_message for text in ("login", "tanpa login", "akses publik")
                                ):
                                    raise ValueError(
                                        "Instagram tidak membuka foto posting ini melalui akses publik tanpa login. "
                                        "Jalur video tidak berlaku karena posting tersebut tidak berisi video."
                                    ) from video_error
                                raise ValueError(f"Gagal mengambil media Instagram. Foto: {photo_error} Video: {video_error}") from video_error
                            raise
                        files = {"result": register_file(job, "result", result["path"], Path(result["path"]).name, inline=True)}
                        metadata = {"title": result["title"], "size": result["size"]}
                else:
                    result = run_video_download(
                        url, platform, payload.get("quality", "Terbaik"), payload.get("name", ""), progress, cancel,
                    )
                    files = {"result": register_file(job, "result", result["path"], Path(result["path"]).name, inline=True)}
                    metadata = {"title": result["title"], "size": result["size"]}
            else:
                raise ValueError("Jenis pekerjaan tidak dikenal.")
            with state_lock:
                job["result"] = {**metadata, "files": files}
                job["state"] = "completed"
                job["progress"] = 1
                job["message"] = "Selesai."
        finally:
            work_lock.release()
    except Cancelled as error:
        with state_lock:
            job["state"] = "cancelled"
            job["message"] = str(error) or "Proses dibatalkan."
    except Exception as error:
        logger.exception("Local processing job failed")
        with state_lock:
            job["state"] = "failed"
            job["error"] = str(error)
            job["message"] = "Proses gagal."
    finally:
        upload_id = payload.get("upload_id")
        if upload_id:
            item = uploads.pop(str(upload_id), None)
            if item:
                item["path"].unlink(missing_ok=True)
                item["preview"].unlink(missing_ok=True)


@app.post("/api/jobs")
def create_job(payload: str = Form(...)):
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise HTTPException(400, "Data pekerjaan tidak valid.") from error
    kind = data.get("kind")
    if kind not in {"video", "photo", "transcription", "download"}:
        raise HTTPException(400, "Jenis pekerjaan tidak dikenal.")
    if kind in UPLOAD_TYPES and not data.get("upload_id"):
        raise HTTPException(400, "Pilih file terlebih dahulu.")
    if kind in {"transcription", "download"} and not str(data.get("url", "")).strip():
        raise HTTPException(400, "Masukkan tautan video terlebih dahulu.")
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "kind": kind,
        "state": "queued",
        "progress": 0,
        "message": "Menyiapkan pekerjaan…",
        "result": None,
        "error": None,
        "cancel": threading.Event(),
        "files": {},
    }
    with state_lock:
        jobs[job_id] = job
    threading.Thread(target=run_job, args=(job, data), daemon=True).start()
    return public_job(job)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Pekerjaan tidak ditemukan.")
    return public_job(job)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Pekerjaan tidak ditemukan.")
    job["cancel"].set()
    return {"ok": True}


def run_media_capture(capture_id, url):
    capture = media_captures[capture_id]
    try:
        run_browser_capture(url, capture, capture["cancel"])
    except Exception as error:
        logger.info("Generic media capture failed: %s", error)
        capture.update(state="failed", message=str(error))


@app.post("/api/media-captures")
def create_media_capture(url: str = Form(...)):
    from removebg.infrastructure.youtube_video import platform_url

    try:
        clean_url = platform_url(url, "Link umum")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    capture_id = uuid.uuid4().hex
    capture = {
        "id": capture_id,
        "state": "queued",
        "message": "Menyiapkan browser sementara…",
        "candidates": [],
        "cancel": threading.Event(),
    }
    media_captures[capture_id] = capture
    threading.Thread(target=run_media_capture, args=(capture_id, clean_url), daemon=True).start()
    return {key: value for key, value in capture.items() if key not in {"cancel"}}


@app.get("/api/media-captures/{capture_id}")
def get_media_capture(capture_id: str):
    capture = media_captures.get(capture_id)
    if not capture:
        raise HTTPException(status_code=404, detail="Sesi deteksi tidak ditemukan.")
    return {key: value for key, value in capture.items() if key not in {"cancel"}}


@app.delete("/api/media-captures/{capture_id}")
def stop_media_capture(capture_id: str):
    capture = media_captures.get(capture_id)
    if capture:
        capture["cancel"].set()
        capture.update(state="cancelled", message="Sesi browser ditutup.")
    return {"ok": True}


@app.get("/api/jobs/{job_id}/files/{file_key}")
def job_file(job_id: str, file_key: str, download: bool = False):
    job = jobs.get(job_id)
    item = job["files"].get(file_key) if job else None
    if not item or not item["path"].is_file():
        raise HTTPException(404, "File hasil tidak ditemukan.")
    return FileResponse(
        item["path"],
        filename=None if item["inline"] and not download else item["filename"],
        content_disposition_type="attachment" if download or not item["inline"] else "inline",
    )


if WEB_OUT.is_dir():
    app.mount("/", StaticFiles(directory=WEB_OUT, html=True), name="web")


def main():
    clear_outputs()
    prepare_dirs()
    atexit.register(clear_outputs)
    log_path = ROOT / "data" / "app.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, filename=log_path, encoding="utf-8")
    if os.environ.get("MYTOOLS_OPEN_BROWSER") != "0":
        threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:7860")).start()
    uvicorn.run(app, host="127.0.0.1", port=7860, log_level="warning")


if __name__ == "__main__":
    main()
