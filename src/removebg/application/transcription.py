import json
import os
import shutil
import threading
import uuid
from functools import lru_cache
from pathlib import Path

import torch
import imageio_ffmpeg
from transformers import pipeline

from removebg.application.service import safe_name
from removebg.config import MODELS, OUTPUTS, prepare_dirs
from removebg.domain import Cancelled
from removebg.infrastructure.models import release_cached_models, release_gpu
from removebg.infrastructure.youtube_transcription import download_audio

MODEL_ID = "openai/whisper-large-v3"


@lru_cache(maxsize=1)
def transcriber():
    ffmpeg_dir = str(Path(imageio_ffmpeg.get_ffmpeg_exe()).parent)
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    use_gpu = torch.cuda.is_available()
    return pipeline(
        "automatic-speech-recognition",
        model=MODEL_ID,
        torch_dtype=torch.float16 if use_gpu else torch.float32,
        model_kwargs={"cache_dir": str(MODELS / "huggingface")},
        device=0 if use_gpu else -1,
        chunk_length_s=30,
        stride_length_s=(5, 5),
    )


def unload_transcriber():
    transcriber.cache_clear()
    release_gpu()


def timestamp(seconds, separator=","):
    millis = max(0, round(float(seconds) * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def sentence_groups(words):
    groups, current = [], []
    for word in words:
        if current and (word["start"] - current[-1]["end"] >= 1.2 or len(current) >= 20):
            groups.append(current)
            current = []
        current.append(word)
        if word["text"].rstrip().endswith((".", "?", "!", "؟", "۔", "…")):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return [{"start": group[0]["start"], "end": group[-1]["end"],
             "text": "".join(word["text"] for word in group).strip(), "words": group}
            for group in groups]


def write_transcript(folder: Path, stem: str, title: str, source_url: str, language: str, words):
    sentences = sentence_groups(words)
    plain = "\n".join(item["text"] for item in sentences)
    srt = "\n\n".join(f"{index}\n{timestamp(item['start'])} --> {timestamp(item['end'])}\n{item['text']}"
                       for index, item in enumerate(sentences, 1))
    vtt = "WEBVTT\n\n" + "\n\n".join(f"{timestamp(item['start'], '.')} --> {timestamp(item['end'], '.')}\n{item['text']}"
                                         for item in sentences)
    paths = {"txt": folder / f"{stem}.txt", "srt": folder / f"{stem}.srt",
             "vtt": folder / f"{stem}.vtt", "json": folder / f"{stem}.json"}
    paths["txt"].write_text(plain + "\n", encoding="utf-8")
    paths["srt"].write_text(srt + "\n", encoding="utf-8")
    paths["vtt"].write_text(vtt + "\n", encoding="utf-8")
    timed_sentences = [{**item, "start_time": timestamp(item["start"], "."),
                        "end_time": timestamp(item["end"], "."),
                        "words": [{**word, "start_time": timestamp(word["start"], "."),
                                   "end_time": timestamp(word["end"], ".")} for word in item["words"]]}
                       for item in sentences]
    paths["json"].write_text(json.dumps({"title": title, "url": source_url, "language": language,
                                         "model": MODEL_ID, "sentences": timed_sentences},
                                        ensure_ascii=False, indent=2), encoding="utf-8")
    return paths, plain, sentences


def run_youtube_transcription(url, language, output_name, progress, cancel: threading.Event):
    prepare_dirs()
    job = OUTPUTS / uuid.uuid4().hex[:12]
    job.mkdir()
    work = job / "work"
    try:
        if shutil.disk_usage(job).free < 1024**3:
            raise ValueError("Sediakan minimal 1 GB ruang disk kosong untuk mengolah transkrip.")
        wav, metadata = download_audio(url, work, progress, cancel)
        progress(0.36, "Audio siap. Memuat model Whisper multilingual (unduhan pertama beberapa GB)…")
        if cancel.is_set():
            raise Cancelled("Proses dibatalkan.")
        release_cached_models()
        model = transcriber()
        progress(0.48, "Menganalisis ucapan dan menyelaraskan waktu setiap kata…")
        options = {"task": "transcribe"}
        if str(language or "Auto").strip().lower() not in {"", "auto", "otomatis"}:
            options["language"] = str(language).strip()
        def interrupt_if_cancelled(_module, _inputs):
            if cancel.is_set():
                raise Cancelled("Proses dibatalkan.")

        hook = model.model.register_forward_pre_hook(interrupt_if_cancelled)
        try:
            result = model(str(wav), return_timestamps="word", generate_kwargs=options)
        finally:
            hook.remove()
        if cancel.is_set():
            raise Cancelled("Proses dibatalkan.")
        words = []
        for chunk in result.get("chunks", []):
            span = chunk.get("timestamp") or (None, None)
            if span[0] is None or span[1] is None:
                continue
            word = str(chunk.get("text") or "")
            if word.strip():
                words.append({"text": word, "start": round(float(span[0]), 3), "end": round(float(span[1]), 3)})
        if not words:
            raise ValueError("Model tidak menemukan ucapan yang dapat ditranskripsikan.")
        stem = safe_name(output_name, safe_name(metadata["title"], "transkrip-youtube"))
        paths, plain, sentences = write_transcript(job, stem, metadata["title"], metadata["url"],
                                                   str(language or "Auto"), words)
        shutil.rmtree(work, ignore_errors=True)
        progress(1, "Transkrip selesai.")
        return {**{kind: str(path) for kind, path in paths.items()}, "text": plain,
                "words": len(words), "sentences": len(sentences), "title": metadata["title"]}
    except BaseException:
        shutil.rmtree(job, ignore_errors=True)
        raise
    finally:
        release_gpu()
