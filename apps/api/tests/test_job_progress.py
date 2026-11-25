import json

import pytest
from fastapi import HTTPException

from removebg.api import append_job_log, get_transcript_corrections, list_jobs, public_job, remove_job_files, restore_jobs, save_transcript_corrections


def test_job_progress_log_coalesces_frame_updates(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("removebg.api.time.time", lambda: now[0])
    job = {
        "logs": [{"time": "00:00:00", "progress": 0, "message": "Mulai", "_at": now[0]}],
    }

    assert not append_job_log(job, "10 frame · 24 fps · 0.3/30 detik", 0.01)
    now[0] = 106.0
    assert append_job_log(job, "20 frame · 24 fps · 0.6/30 detik", 0.02)
    assert len(job["logs"]) == 2
    assert "_at" not in public_job({
        **job, "id": "job", "kind": "video", "state": "running", "progress": 0.02,
        "message": "Berjalan", "result": None, "error": None, "created_at": 100.0,
        "started_at": 100.0, "finished_at": None, "progress_updated_at": 106.0,
    })["logs"][-1]


def test_unchanged_queue_message_does_not_spam_activity_log(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("removebg.api.time.time", lambda: now[0])
    job = {"logs": [{"time": "00:00:00", "progress": 1, "message": "Menunggu pekerjaan lain selesai…", "_at": now[0]}]}

    now[0] += 30

    assert not append_job_log(job, "Menunggu pekerjaan lain selesai…", 0.01)
    assert len(job["logs"]) == 1


def test_job_list_keeps_all_active_jobs_without_returning_large_results(monkeypatch):
    monkeypatch.setattr("removebg.api.time.time", lambda: 10)
    sample = {
        "running": {"id": "running", "kind": "transcription", "state": "running", "progress": 0.48, "message": "Menganalisis audio", "created_at": 1, "started_at": 2, "finished_at": None},
        "queued": {"id": "queued", "kind": "download", "state": "queued", "progress": 0.01, "message": "Menunggu pekerjaan lain selesai", "created_at": 3, "started_at": None, "finished_at": None},
        "done": {"id": "done", "kind": "photo", "state": "completed", "progress": 1, "message": "Selesai", "created_at": 0, "started_at": 0, "finished_at": 1, "result": {"text": "large result is omitted"}},
    }
    monkeypatch.setattr("removebg.api.jobs", sample)

    result = list_jobs()["jobs"]

    assert [item["id"] for item in result] == ["queued", "running", "done"]
    assert all("result" not in item and "logs" not in item for item in result)


def test_restore_marks_unfinished_jobs_interrupted_and_keeps_finished_files(monkeypatch, tmp_path):
    monkeypatch.setattr("removebg.api.time.time", lambda: 4)
    output_root = tmp_path / "outputs"
    result_file = output_root / "done" / "result.txt"
    result_file.parent.mkdir(parents=True)
    result_file.write_text("saved", encoding="utf-8")
    store = tmp_path / "jobs.json"
    store.write_text(json.dumps([
        {
            "id": "running", "kind": "transcription", "state": "running", "progress": 0.48,
            "message": "Menganalisis", "created_at": 1, "started_at": 2, "finished_at": None,
            "progress_updated_at": 2, "result": None, "error": None, "logs": [], "files": {},
        },
        {
            "id": "done", "kind": "transcription", "state": "completed", "progress": 1,
            "message": "Selesai", "created_at": 1, "started_at": 2, "finished_at": 3,
            "progress_updated_at": 3, "result": {"files": {"txt": {"url": "kept"}}}, "error": None,
            "logs": [], "files": {"txt": {"path": str(result_file), "filename": "result.txt", "inline": False}},
        },
    ]), encoding="utf-8")
    monkeypatch.setattr("removebg.api.OUTPUTS", output_root)
    monkeypatch.setattr("removebg.api.JOB_STORE", store)
    restored = {}
    monkeypatch.setattr("removebg.api.jobs", restored)

    restore_jobs()

    assert restored["running"]["state"] == "failed"
    assert "dimulai ulang" in restored["running"]["message"]
    assert restored["done"]["files"]["txt"]["path"] == result_file.resolve()
    assert result_file.exists()


def test_remove_job_files_never_deletes_outside_outputs(monkeypatch, tmp_path):
    output_root = tmp_path / "outputs"
    outside = tmp_path / "keep.txt"
    outside.write_text("keep", encoding="utf-8")
    monkeypatch.setattr("removebg.api.OUTPUTS", output_root)

    remove_job_files({"files": {"result": {"path": outside}}})

    assert outside.read_text(encoding="utf-8") == "keep"


def test_transcript_corrections_are_saved_and_restored_with_the_job(monkeypatch, tmp_path):
    monkeypatch.setattr("removebg.api.time.time", lambda: 4)
    job = {
        "id": "transcript", "kind": "transcription", "state": "completed", "progress": 1,
        "message": "Selesai", "result": {"sentences": 2, "files": {}}, "error": None,
        "created_at": 1, "started_at": 1, "finished_at": 2, "progress_updated_at": 2,
        "logs": [], "files": {}, "corrections": None,
    }
    monkeypatch.setattr("removebg.api.jobs", {"transcript": job})
    monkeypatch.setattr("removebg.api.JOB_STORE", tmp_path / "jobs.json")

    with pytest.raises(HTTPException) as error:
        save_transcript_corrections("transcript", {"texts": ["satu"]})
    assert error.value.status_code == 400

    assert save_transcript_corrections("transcript", {"texts": ["satu", "اثنان"]}) == {"ok": True}
    assert get_transcript_corrections("transcript") == {"texts": ["satu", "اثنان"]}
    assert json.loads((tmp_path / "jobs.json").read_text(encoding="utf-8"))[0]["corrections"] == ["satu", "اثنان"]
    restore_jobs()
    assert get_transcript_corrections("transcript") == {"texts": ["satu", "اثنان"]}
