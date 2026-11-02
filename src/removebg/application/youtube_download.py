import shutil
import threading
import uuid
from pathlib import Path

from removebg.application.service import safe_name
from removebg.config import OUTPUTS, prepare_dirs
from removebg.domain import Cancelled
from removebg.infrastructure.youtube_video import download_video


def run_youtube_download(url, quality, output_name, progress, cancel: threading.Event):
    prepare_dirs()
    job = OUTPUTS / uuid.uuid4().hex[:12]
    job.mkdir()
    work = job / "work"
    try:
        progress(0.02, "Memeriksa video YouTube…")
        path, title = download_video(url, quality, work, progress, cancel)
        if cancel.is_set():
            raise Cancelled("Proses dibatalkan.")
        final = job / f"{safe_name(output_name, safe_name(title, 'video-youtube'))}{path.suffix.lower()}"
        path.replace(final)
        shutil.rmtree(work, ignore_errors=True)
        progress(1, "Unduhan selesai.")
        return {"path": str(final), "title": title, "size": final.stat().st_size}
    except BaseException:
        shutil.rmtree(job, ignore_errors=True)
        raise
