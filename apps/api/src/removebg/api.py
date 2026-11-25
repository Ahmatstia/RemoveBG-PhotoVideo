import json
import logging
import os
import shutil
import threading
import time
import uuid
import webbrowser
from pathlib import Path

import torch
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from removebg.application.service import run_photo, run_video, safe_name
from removebg.application.shopee_scraping import run_shopee_scrape
from removebg.application.transcription import run_file_transcription, run_youtube_transcription
from removebg.application.youtube_download import run_instagram_photo_download, run_tiktok_photo_download, run_tiktok_video_download, run_video_download
from removebg.config import OUTPUTS, ROOT, prepare_dirs
from removebg.domain import Cancelled
from removebg.infrastructure.media import inspect_video, read_photo
from removebg.infrastructure.browser_capture import run_browser_capture
from removebg.modules.decision_support.presentation.router import router as decision_support_router

logger = logging.getLogger(__name__)
WEB_OUT = ROOT / "apps" / "web" / "out"
UPLOAD_DIR = OUTPUTS / "uploads"
MAX_UPLOAD_BYTES = 20 * 1024**3
MAX_VIDEO_BATCH = 10
UPLOAD_TYPES = {
    "video": {".mp4", ".mov", ".mkv", ".avi", ".webm"},
    "photo": {".png", ".jpg", ".jpeg", ".webp"},
    "transcription": {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"},
}
jobs = {}
uploads = {}
media_captures = {}
state_lock = threading.Lock()
work_lock = threading.Lock()
JOB_STORE = OUTPUTS.parent / "jobs.json"
JOB_RETENTION_SECONDS = 7 * 24 * 60 * 60
app = FastAPI(title="RemoveBG Local API", docs_url=None, redoc_url=None)
app.include_router(decision_support_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["Content-Type"],
)


def public_job(job):
    result = {key: job[key] for key in (
        "id", "kind", "state", "progress", "message", "result", "error", "logs",
        "created_at", "started_at", "finished_at", "progress_updated_at",
    )}
    result["logs"] = [{key: value for key, value in log.items() if key != "_at"} for log in job["logs"]]
    return result


def save_jobs_locked():
    JOB_STORE.parent.mkdir(parents=True, exist_ok=True)
    snapshot = []
    for job in jobs.values():
        snapshot.append({
            key: job[key] for key in (
                "id", "kind", "state", "progress", "message", "result", "error",
                "created_at", "started_at", "finished_at", "progress_updated_at", "logs",
            )
        } | {"files": {
            key: {**item, "path": str(item["path"])} for key, item in job["files"].items()
        }, "corrections": job.get("corrections")})
    temporary = JOB_STORE.with_suffix(".tmp")
    try:
        temporary.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        temporary.replace(JOB_STORE)
    except OSError:
        logger.exception("Unable to persist job history")
        temporary.unlink(missing_ok=True)


def remove_job_files(job):
    root = OUTPUTS.resolve()
    parents = set()
    for item in job.get("files", {}).values():
        path = Path(item["path"]).resolve()
        if path == root or root not in path.parents:
            continue
        path.unlink(missing_ok=True)
        parents.update(path.parents)
    for folder in sorted(parents, key=lambda path: len(path.parts), reverse=True):
        if folder == root or root not in folder.parents:
            continue
        try:
            folder.rmdir()
        except OSError:
            pass


def restore_jobs():
    if not JOB_STORE.is_file():
        return
    now = time.time()
    root = OUTPUTS.resolve()
    restored = {}
    try:
        stored = json.loads(JOB_STORE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Unable to read persisted job history")
        return
    for job in stored:
        age_anchor = job.get("finished_at") or job.get("created_at", now)
        if now - age_anchor > JOB_RETENTION_SECONDS:
            remove_job_files(job)
            continue
        files = {}
        for key, item in job.get("files", {}).items():
            path = Path(item["path"]).resolve()
            if root in path.parents and path.is_file():
                files[key] = {**item, "path": path}
        if job.get("state") in {"queued", "running"}:
            job.update(
                state="failed", message="Backend dimulai ulang; pekerjaan ini tidak dapat dilanjutkan otomatis.",
                error="Proses terhenti saat backend dimulai ulang.", finished_at=now,
            )
            job.setdefault("logs", []).append({
                "time": time.strftime("%H:%M:%S"), "progress": round(job.get("progress", 0) * 100),
                "message": job["message"], "_at": now,
            })
        job["files"] = files
        if isinstance(job.get("result"), dict):
            job["result"]["files"] = {
                key: value for key, value in job["result"].get("files", {}).items() if key in files
            }
        job["cancel"] = threading.Event()
        job.setdefault("corrections", None)
        restored[job["id"]] = job
    with state_lock:
        jobs.clear()
        jobs.update(restored)
        save_jobs_locked()


def append_job_log(job, message, progress):
    now = time.time()
    logs = job["logs"]
    last = logs[-1] if logs else None
    changed_stage = last is None or message != last["message"]
    noisy_frame_update = message[:1].isdigit() and " frame · " in message
    milestone = last is not None and abs(progress - last["progress"] / 100) >= 0.05
    elapsed = last is not None and now - last["_at"] >= 5
    if last is None or (changed_stage and not noisy_frame_update) or milestone or (elapsed and noisy_frame_update):
        logs.append({
            "time": time.strftime("%H:%M:%S"),
            "progress": round(progress * 100),
            "message": message,
            "_at": now,
        })
        del logs[:-100]
        return True
    return False


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
        if kind == "transcription":
            details = {"size": total}
            uploads[upload_id] = {"kind": kind, "path": path, "preview": None, "filename": file.filename, "details": details}
        else:
            details = save_upload(upload_id, kind, path)
        return {"id": upload_id, "kind": kind, "filename": file.filename, "details": details,
                "preview_url": f"/api/uploads/{upload_id}/preview" if kind != "transcription" else None}
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
        if item.get("preview"):
            item["preview"].unlink(missing_ok=True)
    return {"ok": True}


def register_file(job, key, path, filename, inline=False):
    job["files"][key] = {"path": Path(path), "filename": filename, "inline": inline}
    return {"url": f"/api/jobs/{job['id']}/files/{key}", "filename": filename}


def run_job(job, payload):
    cancel = job["cancel"]

    def progress(value, message):
        with state_lock:
            val = max(job["progress"], min(float(value), 1))
            msg = str(message)
            job.update(progress=val, message=msg, progress_updated_at=time.time())
            if append_job_log(job, msg, val):
                save_jobs_locked()

    try:
        while not work_lock.acquire(timeout=0.25):
            if cancel.is_set():
                raise Cancelled("Proses dibatalkan.")
            progress(0.01, "Menunggu pekerjaan lain selesai…")
        try:
            if cancel.is_set():
                raise Cancelled("Proses dibatalkan.")
            with state_lock:
                job.update(state="running", started_at=time.time())
                append_job_log(job, "Worker mulai menjalankan pekerjaan.", job["progress"])
                save_jobs_locked()
            kind = payload["kind"]
            video_items = []
            if kind == "video" and payload.get("upload_ids"):
                for upload_id in payload["upload_ids"]:
                    item = uploads.get(str(upload_id))
                    if not item or item["kind"] != "video":
                        raise ValueError("Salah satu file video batch sudah tidak tersedia. Pilih ulang file tersebut.")
                    video_items.append((str(upload_id), item))
            if kind in UPLOAD_TYPES and payload.get("upload_id"):
                item = uploads.get(str(payload.get("upload_id", "")))
                if not item or item["kind"] != kind:
                    raise ValueError("File sumber tidak ditemukan. Unggah kembali file.")
                source = item["path"]
            if kind == "video":
                if video_items:
                    files, batch_results = {}, []
                    count = len(video_items)
                    output_names = payload.get("output_names", [])
                    used_names = set()
                    for index, (upload_id, item) in enumerate(video_items, 1):
                        filename = item.get("filename") or Path(item["path"]).name
                        requested_name = output_names[index - 1] if isinstance(output_names, list) and index <= len(output_names) else ""
                        output_name = safe_name(str(requested_name).strip(), f"{Path(filename).stem}-hasil")
                        base_name, suffix = output_name, 2
                        while output_name.casefold() in used_names:
                            output_name = f"{base_name}-{suffix}"
                            suffix += 1
                        used_names.add(output_name.casefold())
                        def item_progress(value, message):
                            progress(((index - 1) + min(max(float(value), 0), 1)) / count,
                                     f"[{index}/{count}] {filename}: {message}")
                        if cancel.is_set():
                            raise Cancelled("Batch video dibatalkan.")
                        try:
                            result, preview, report = run_video(
                                str(item["path"]), payload.get("mode", "Manusia"), payload.get("quality", "Detail"),
                                payload.get("points", []), payload.get("export", "transparent"), False,
                                cancel, item_progress, output_name=output_name,
                            )
                            result_key, preview_key = f"result_{index}", f"preview_{index}"
                            files[result_key] = register_file(job, result_key, result, Path(result).name, inline=True)
                            files[preview_key] = register_file(job, preview_key, preview, Path(preview).name, inline=True)
                            batch_results.append({"filename": filename, "status": "completed", "result_key": result_key, "preview_key": preview_key, "report": report})
                            with state_lock:
                                job["result"] = {"items": batch_results.copy(), "files": files.copy()}
                                save_jobs_locked()
                        except Cancelled:
                            raise
                        except Exception as error:
                            batch_results.append({"filename": filename, "status": "failed", "error": str(error)})
                            item_progress(1, f"Gagal: {error}")
                        finally:
                            delete_upload(upload_id)
                    metadata = {"items": batch_results}
                else:
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
                    cancel=cancel, progress=progress,
                )
                if cancel.is_set():
                    Path(result).unlink(missing_ok=True)
                    Path(result).parent.rmdir()
                    raise Cancelled("Proses dibatalkan.")
                files = {"result": register_file(job, "result", result, Path(result).name, inline=True)}
                metadata = {}
            elif kind == "transcription":
                if payload.get("upload_id"):
                    result = run_file_transcription(
                        source, item.get("filename") or Path(source).name,
                        payload.get("language", "Auto"), payload.get("name", ""), progress, cancel,
                    )
                else:
                    result = run_youtube_transcription(
                        payload.get("url", ""), payload.get("language", "Auto"), payload.get("name", ""),
                        progress, cancel,
                    )
                files = {
                    key: register_file(job, key, result[key], Path(result[key]).name)
                    for key in ("txt", "srt", "vtt", "json")
                }
                metadata = {key: result[key] for key in ("text", "title", "words", "sentences")}
                metadata["source_type"] = "file" if payload.get("upload_id") else "youtube"
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
            elif kind == "scraping":
                url = str(payload.get("url", ""))
                result = run_shopee_scrape(
                    url=url,
                    max_reviews=int(payload.get("limit", 50)),
                    star_filter=int(payload.get("star", 0)),
                    with_media_only=bool(payload.get("media_only", False)),
                    with_comment_only=bool(payload.get("comment_only", False)),
                    cookies=str(payload.get("cookie", "")),
                    use_browser=bool(payload.get("use_browser", False)),
                    output_name=payload.get("name", ""),
                    progress=progress,
                    cancel=cancel,
                )
                files = {
                    "csv": register_file(job, "csv", result["path_csv"], Path(result["path_csv"]).name),
                    "json": register_file(job, "json", result["path_json"], Path(result["path_json"]).name),
                }
                metadata = {
                    "title": result["title"],
                    "total": result["total_reviews"],
                    "preview_rows": result.get("preview_rows", []),
                }
            else:
                raise ValueError("Jenis pekerjaan tidak dikenal.")
            with state_lock:
                job["result"] = {**metadata, "files": files}
                job["state"] = "completed"
                job["progress"] = 1
                job["message"] = "Selesai."
                job["finished_at"] = time.time()
                append_job_log(job, "Pekerjaan selesai.", 1)
                save_jobs_locked()
        finally:
            work_lock.release()
    except Cancelled as error:
        with state_lock:
            job["state"] = "cancelled"
            job["message"] = str(error) or "Proses dibatalkan."
            job["finished_at"] = time.time()
            append_job_log(job, job["message"], job.get("progress", 0))
            save_jobs_locked()
    except Exception as error:
        logger.exception("Local processing job failed")
        with state_lock:
            job["state"] = "failed"
            job["error"] = str(error)
            job["message"] = "Proses gagal."
            job["finished_at"] = time.time()
            append_job_log(job, f"Gagal: {error}", job.get("progress", 0))
            save_jobs_locked()
    finally:
        raw_upload_ids = payload.get("upload_ids", [])
        upload_ids = raw_upload_ids if isinstance(raw_upload_ids, list) else []
        if payload.get("upload_id"):
            upload_ids.append(payload["upload_id"])
        for upload_id in dict.fromkeys(map(str, upload_ids)):
            item = uploads.pop(upload_id, None)
            if item:
                item["path"].unlink(missing_ok=True)
                if item.get("preview"):
                    item["preview"].unlink(missing_ok=True)


@app.post("/api/jobs")
def create_job(payload: str = Form(...)):
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise HTTPException(400, "Data pekerjaan tidak valid.") from error
    kind = data.get("kind")
    if kind not in {"video", "photo", "transcription", "download", "scraping"}:
        raise HTTPException(400, "Jenis pekerjaan tidak dikenal.")
    if "upload_ids" in data and kind != "video":
        raise HTTPException(400, "Batch unggahan hanya tersedia untuk pemrosesan video.")
    if kind == "video" and "upload_ids" in data:
        upload_ids = data["upload_ids"]
        if not isinstance(upload_ids, list) or not 1 <= len(upload_ids) <= MAX_VIDEO_BATCH or len(set(map(str, upload_ids))) != len(upload_ids):
            raise HTTPException(400, f"Pilih 1–{MAX_VIDEO_BATCH} video untuk satu batch.")
        if any(not uploads.get(str(upload_id)) or uploads[str(upload_id)]["kind"] != "video" for upload_id in upload_ids):
            raise HTTPException(404, "Salah satu file video batch sudah tidak tersedia. Unggah ulang file tersebut.")
        output_names = data.get("output_names")
        if output_names is not None and (not isinstance(output_names, list) or len(output_names) != len(upload_ids) or any(not isinstance(name, str) for name in output_names)):
            raise HTTPException(400, "Nama hasil harus tersedia untuk setiap video batch.")
    elif kind in {"video", "photo"} and not data.get("upload_id"):
        raise HTTPException(400, "Pilih file terlebih dahulu.")
    if kind == "transcription" and data.get("upload_id"):
        source_upload = uploads.get(str(data["upload_id"]))
        if not source_upload or source_upload["kind"] != "transcription":
            raise HTTPException(404, "File audio/video tidak tersedia. Unggah kembali file tersebut.")
    if kind in {"download", "scraping"} and not str(data.get("url", "")).strip():
        raise HTTPException(400, "Masukkan tautan terlebih dahulu.")
    if kind == "transcription" and not data.get("upload_id") and not str(data.get("url", "")).strip():
        raise HTTPException(400, "Masukkan tautan YouTube atau pilih file audio/video.")
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
        "corrections": None,
        "created_at": time.time(),
        "started_at": None,
        "finished_at": None,
        "progress_updated_at": time.time(),
        "logs": [
            {
                "time": time.strftime("%H:%M:%S"),
                "progress": 0,
                "message": "Menyiapkan pekerjaan…",
                "_at": time.time(),
            }
        ],
    }
    with state_lock:
        jobs[job_id] = job
        save_jobs_locked()
    threading.Thread(target=run_job, args=(job, data), daemon=True).start()
    return public_job(job)


@app.get("/api/jobs")
def list_jobs():
    with state_lock:
        now = time.time()
        expired = [
            item for item in jobs.values()
            if item["state"] not in {"queued", "running"}
            and now - (item.get("finished_at") or item["created_at"]) > JOB_RETENTION_SECONDS
        ]
        if expired:
            for item in expired:
                remove_job_files(item)
                jobs.pop(item["id"], None)
            save_jobs_locked()
        ordered = sorted(jobs.values(), key=lambda item: item["created_at"])
        active = [item for item in ordered if item["state"] in {"queued", "running"}]
        finished = [item for item in ordered if item["state"] not in {"queued", "running"}][-12:]
        visible = sorted([*active, *finished], key=lambda item: item["created_at"], reverse=True)
        return {
            "jobs": [
                {
                    "id": item["id"], "kind": item["kind"], "state": item["state"],
                    "progress": item["progress"], "message": item["message"],
                    "created_at": item["created_at"], "started_at": item["started_at"],
                    "finished_at": item["finished_at"],
                }
                for item in visible
            ]
        }


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Pekerjaan tidak ditemukan.")
    return public_job(job)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    with state_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Pekerjaan tidak ditemukan.")
        if job["state"] in {"queued", "running"}:
            job["cancel"].set()
    return {"ok": True}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    with state_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Pekerjaan tidak ditemukan.")
        if job["state"] in {"queued", "running"}:
            raise HTTPException(409, "Pekerjaan yang sedang berjalan tidak dapat dihapus.")
        remove_job_files(job)
        del jobs[job_id]
        save_jobs_locked()
    return {"ok": True}


@app.get("/api/jobs/{job_id}/transcript-corrections")
def get_transcript_corrections(job_id: str):
    with state_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Pekerjaan tidak ditemukan.")
        if job["kind"] != "transcription" or job["state"] != "completed":
            raise HTTPException(409, "Koreksi tersedia setelah transkrip selesai.")
        return {"texts": job.get("corrections")}


@app.put("/api/jobs/{job_id}/transcript-corrections")
def save_transcript_corrections(job_id: str, payload: dict):
    with state_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Pekerjaan tidak ditemukan.")
        if job["kind"] != "transcription" or job["state"] != "completed":
            raise HTTPException(409, "Koreksi hanya dapat disimpan untuk transkrip yang selesai.")
        texts = payload.get("texts")
        expected = (job.get("result") or {}).get("sentences")
        if not isinstance(texts, list) or len(texts) != expected or not all(isinstance(text, str) for text in texts):
            raise HTTPException(400, "Daftar koreksi tidak sesuai dengan jumlah kalimat transkrip.")
        if any(len(text) > 20_000 for text in texts) or sum(map(len, texts)) > 2_000_000:
            raise HTTPException(413, "Ukuran koreksi transkrip terlalu besar.")
        job["corrections"] = texts
        save_jobs_locked()
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
    prepare_dirs()
    restore_jobs()
    log_path = ROOT / "data" / "app.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, filename=log_path, encoding="utf-8")
    if os.environ.get("MYTOOLS_OPEN_BROWSER") != "0":
        threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:7860")).start()
    uvicorn.run(app, host="127.0.0.1", port=7860, log_level="warning")


if __name__ == "__main__":
    main()
