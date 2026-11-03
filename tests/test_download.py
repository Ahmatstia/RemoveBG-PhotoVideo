import threading
import subprocess
import json
from pathlib import Path

import av
import imageio_ffmpeg
import pytest

from removebg.application import youtube_download
from removebg.infrastructure import youtube_video
from removebg.infrastructure import browser_capture


@pytest.mark.parametrize("url", [
    "https://fcaimg.com/v/XKpZWWoH1",
    "https://media.twimg.date/UZtntO1w1.mp4",
    "https://108.181.6.9/video/",
])
def test_generic_download_accepts_public_video_urls(url):
    assert youtube_video.platform_url(url, "Link umum") == url


def test_generic_download_unwraps_cpo_proxy_page_to_source_url():
    proxy_url = (
        "https://108.181.6.9/video-68JiF1TSNZF/booty-beauty-of-the-week-07-26/"
        "?__cpo=aHR0cHM6Ly93d3cuZXBvcm5lci5jb20"
    )
    assert youtube_video.platform_url(proxy_url, "Link umum") == (
        "https://www.eporner.com/video-68JiF1TSNZF/booty-beauty-of-the-week-07-26/"
    )


@pytest.mark.parametrize("url", [
    "file:///video.mp4",
    "http://127.0.0.1:7860/api/health",
    "http://192.168.1.1/video.mp4",
    "https://localhost/video.mp4",
    "https://user:pass@example.com/video.mp4",
])
def test_generic_download_rejects_local_or_invalid_urls(url):
    with pytest.raises(ValueError):
        youtube_video.platform_url(url, "Link umum")


@pytest.mark.parametrize("url", [
    "https://example.com/video-page",
    "http://8.8.8.8/video.mp4",
])
def test_browser_capture_accepts_public_http_urls(url, monkeypatch):
    monkeypatch.setattr(browser_capture.socket, "getaddrinfo", lambda *_args: [(None, None, None, None, ("93.184.216.34", 0))])
    assert browser_capture.is_public_http_url(url)


@pytest.mark.parametrize("url", [
    "file:///C:/secret.txt",
    "http://127.0.0.1:7860/api/health",
    "http://192.168.1.1/video.mp4",
    "https://localhost/video",
    "https://user:pass@example.com/video",
])
def test_browser_capture_rejects_non_public_urls(url):
    assert not browser_capture.is_public_http_url(url)


def test_browser_capture_rejects_hosts_resolving_to_private_addresses(monkeypatch):
    monkeypatch.setattr(browser_capture.socket, "getaddrinfo", lambda *_args: [(None, None, None, None, ("10.0.0.4", 0))])
    assert not browser_capture.is_public_http_url("https://example.com/video")


def test_browser_capture_reports_dns_failures_as_connection_issues(monkeypatch):
    def fail_dns(*_args):
        raise browser_capture.socket.gaierror("name resolution failed")

    monkeypatch.setattr(browser_capture.socket, "getaddrinfo", fail_dns)
    assert "DNS" in browser_capture.public_http_url_error("https://example.com/video")


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
            return self.payload if self.payload is not None else json.loads(self.text)

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


def test_instagram_public_graphql_downloads_carousel_without_login(tmp_path, monkeypatch):
    output_dir = tmp_path / "outputs"
    monkeypatch.setattr(youtube_download, "OUTPUTS", output_dir)
    monkeypatch.setattr(youtube_download, "prepare_dirs", lambda: output_dir.mkdir(parents=True, exist_ok=True))
    image_urls = [f"https://scontent.cdninstagram.com/photo-{index}.jpg?stp=dst-jpg_e35_p1080x1080" for index in (1, 2)]

    class Response:
        headers = {"Content-Type": "image/jpeg"}

        def __init__(self, payload=None, text=""):
            self.payload = payload
            self.text = text

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

        def iter_content(self, chunk_size):
            assert chunk_size == 256 * 1024
            yield b"photo"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    class Cookies:
        def get(self, key):
            return "csrf-token" if key == "csrftoken" else None

    class FakeSession:
        def __init__(self):
            self.headers = {}
            self.cookies = Cookies()
            self.get_calls = []

        def get(self, url, **kwargs):
            self.get_calls.append(url)
            if url == "https://www.instagram.com/":
                return Response(text='["LSD",[],{"token":"lsd-token"}')
            if "get_ruling_for_content" in url:
                return Response(payload={"status": "ok"})
            return Response()

        def post(self, url, **kwargs):
            assert url == "https://www.instagram.com/api/graphql"
            assert kwargs["data"]["doc_id"] == youtube_download._INSTAGRAM_POLARIS_POST_QUERY
            assert json.loads(kwargs["data"]["variables"]) == {"media_id": "4021496157832799036"}
            return Response(payload={"data": {"xig_polaris_media": {"if_not_gated_logged_out": {
                "code": "DfPOXLhOOM8",
                "carousel_media": [
                    {"image_versions2": {"candidates": [
                        {"url": image_url.replace("1080x1080", "320x320")},
                        {"url": image_url},
                    ]}}
                    for image_url in image_urls
                ],
            }}}})

        def close(self):
            return None

    session = FakeSession()
    monkeypatch.setattr(youtube_download.requests, "Session", lambda: session)
    result = youtube_download.run_instagram_photo_download(
        "https://www.instagram.com/p/DfPOXLhOOM8/", "ig-carousel",
        lambda *_: None, threading.Event(),
    )

    assert [image["filename"] for image in result["images"]] == ["ig-carousel-01.jpg", "ig-carousel-02.jpg"]
    assert [Path(image["path"]).read_bytes() for image in result["images"]] == [b"photo", b"photo"]
    assert session.get_calls[-2:] == image_urls


def test_instagram_non_json_response_falls_back_to_public_preview(tmp_path, monkeypatch):
    output_dir = tmp_path / "outputs"
    monkeypatch.setattr(youtube_download, "OUTPUTS", output_dir)
    monkeypatch.setattr(youtube_download, "prepare_dirs", lambda: output_dir.mkdir(parents=True, exist_ok=True))
    thumbnail = "https://scontent.cdninstagram.com/preview.jpg"

    class Response:
        headers = {"Content-Type": "image/jpeg"}

        def __init__(self, payload=None, text=""):
            self.payload = payload
            self.text = text

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload if self.payload is not None else json.loads(self.text)

        def iter_content(self, chunk_size):
            assert chunk_size == 256 * 1024
            yield b"preview"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    class Cookies:
        def get(self, key):
            return "csrf-token" if key == "csrftoken" else None

    class FakeSession:
        def __init__(self):
            self.headers = {}
            self.cookies = Cookies()
            self.query_attempts = 0

        def get(self, url, **_):
            if url == "https://www.instagram.com/":
                return Response(text='["LSD",[],{"token":"lsd-token"}')
            if "get_ruling_for_content" in url:
                return Response(payload={"status": "ok"})
            if "oembed" in url:
                return Response(payload={"type": "rich", "thumbnail_url": thumbnail})
            return Response()

        def post(self, *_args, **_kwargs):
            self.query_attempts += 1
            return Response(text="<html>Instagram page</html>")

        def close(self):
            return None

    session = FakeSession()
    monkeypatch.setattr(youtube_download.requests, "Session", lambda: session)
    result = youtube_download.run_instagram_photo_download(
        "https://www.instagram.com/p/DfPOXLhOOM8/", "ig-preview",
        lambda *_: None, threading.Event(),
    )

    assert session.query_attempts == 2
    assert len(result["images"]) == 1
    assert result["notice"].startswith("Instagram hanya memberikan pratinjau")
    assert Path(result["images"][0]["path"]).read_bytes() == b"preview"


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
