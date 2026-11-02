import threading
import subprocess
from pathlib import Path

import av
import imageio_ffmpeg
import pytest

from removebg.application import youtube_download
from removebg.infrastructure import youtube_video


def test_youtube_bot_check_retries_with_android_client(tmp_path, monkeypatch):
    calls = []

    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options
            calls.append(options)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def extract_info(self, url, download):
            assert url == "https://youtu.be/video-id"
            assert download is True
            if len(calls) == 1:
                raise Exception("Sign in to confirm you’re not a bot")
            (tmp_path / "video.mp4").write_bytes(b"video")
            return {"title": "Test video"}

    monkeypatch.setattr(youtube_video, "YoutubeDL", FakeYoutubeDL)
    progress = []
    result = youtube_video.download_video(
        "https://youtu.be/video-id", "YouTube", "Terbaik", tmp_path,
        lambda value, message: progress.append((value, message)), threading.Event(),
    )

    assert len(calls) == 2
    assert "extractor_args" not in calls[0]
    assert calls[1]["extractor_args"] == {"youtube": {"player_client": ["android"]}}
    assert result == (tmp_path / "video.mp4", "Test video")
    assert "mode tanpa login" in progress[-1][1]


def test_tiktok_download_uses_public_provider_and_streams_video(tmp_path, monkeypatch):
    output_dir = tmp_path / "outputs"
    monkeypatch.setattr(youtube_download, "OUTPUTS", output_dir)
    monkeypatch.setattr(youtube_download, "prepare_dirs", lambda: output_dir.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(youtube_download, "_transcode_tiktok_to_h264", lambda source, target, *_: source.replace(target))
    calls = []

    class Response:
        def __init__(self, payload=None, headers=None, chunks=()):
            self.payload = payload
            self.headers = headers or {}
            self.chunks = chunks

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

        def iter_content(self, chunk_size):
            assert chunk_size == 256 * 1024
            yield from self.chunks

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if url == "https://www.tikwm.com/api/":
            return Response({
                "code": 0,
                "data": {
                    "id": "1234567890123456789",
                    "title": "Demo clip",
                    "hdplay": "https://v16m.tiktokcdn-us.com/video.mp4?token=demo",
                },
            })
        return Response(
            headers={"Content-Type": "video/mp4", "Content-Length": "10"},
            chunks=[b"video", b"bytes"],
        )

    monkeypatch.setattr(youtube_download.requests, "get", fake_get)
    updates = []
    result = youtube_download.run_tiktok_video_download(
        "https://www.tiktok.com/@creator/video/1234567890123456789",
        "my-video", lambda value, message: updates.append((value, message)), threading.Event(),
    )

    assert len(calls) == 2
    assert calls[0][0] == "https://www.tikwm.com/api/"
    assert calls[0][1]["params"]["url"].endswith("1234567890123456789")
    assert calls[1][0].startswith("https://v16m.tiktokcdn-us.com/")
    assert result["title"] == "my-video"
    assert result["size"] == 10
    assert Path(result["path"]).read_bytes() == b"videobytes"
    assert updates[-1] == (1, "Unduhan TikTok selesai.")


def test_tiktok_hd_hevc_is_converted_to_h264_at_same_resolution(tmp_path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    source = tmp_path / "hevc.mp4"
    target = tmp_path / "h264.mp4"
    subprocess.run([
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=red:s=64x48:r=5:d=0.5",
        "-c:v", "libx265", "-x265-params", "log-level=error", "-pix_fmt", "yuv420p", str(source),
    ], check=True)

    dimensions = youtube_download._transcode_tiktok_to_h264(
        source, target, threading.Event(), lambda *_: None,
    )

    with av.open(str(target)) as container:
        stream = next(stream for stream in container.streams if stream.type == "video")
        assert stream.codec_context.name == "h264"
        assert (stream.codec_context.width, stream.codec_context.height) == dimensions == (64, 48)


@pytest.mark.parametrize("url", [
    "http://v16m.tiktokcdn-us.com/video.mp4",
    "https://evil.example/video.mp4",
    "https://tiktok.com/video.mp4",
])
def test_tiktok_media_url_must_use_https_cdn(url):
    assert not youtube_download._is_tiktok_cdn_url(url)


def test_tiktok_media_url_accepts_tiktok_cdn_subdomain():
    assert youtube_download._is_tiktok_cdn_url("https://v16m.tiktokcdn-us.com/video.mp4")
