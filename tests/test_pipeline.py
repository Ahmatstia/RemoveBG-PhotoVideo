import threading
from fractions import Fraction
from types import SimpleNamespace

import av
import numpy as np
import pytest
from PIL import Image

from removebg.application import service
from removebg.domain import Cancelled, validate_points
from removebg.infrastructure.media import VideoWriter, checkerboard, inspect_video
from removebg.infrastructure.models import prune_session


class Matte:
    def process(self, rgb):
        alpha = np.zeros(rgb.shape[:2], dtype=np.uint8)
        alpha[:, rgb.shape[1] // 2:] = 255
        alpha[:, rgb.shape[1] // 2] = 128
        return rgb, alpha


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "OUTPUTS", tmp_path / "outputs")
    (tmp_path / "outputs").mkdir()
    path = tmp_path / "source.mkv"
    writer = VideoWriter(path, 64, 48, Fraction(25), "mask")
    for index, timestamp in enumerate([0, .04, .12, .16]):
        writer.write(np.full((48, 64), 60 + index, dtype=np.uint8), timestamp)
    writer.close()
    return path


def test_vfr_alpha_export(source):
    before = source.read_bytes()
    result, preview, report = service.run_video(
        source, "Manusia", "Detail", [], "transparent", False,
        threading.Event(), lambda *_: None, lambda *_: Matte(),
    )
    with av.open(result) as container:
        frames = list(container.decode(video=0))
    assert len(frames) == 4
    assert [round(float(f.pts * f.time_base), 2) for f in frames] == [0, .04, .12, .16]
    alpha = frames[0].to_ndarray(format="rgba")[..., 3]
    assert alpha[:, :32].max() == 0
    assert alpha[:, 33:].min() == 255
    assert abs(int(alpha[0, 32]) - 128) <= 2
    assert report["width"] == 64 and report["frames"] == 4
    assert source.read_bytes() == before
    with av.open(preview) as container:
        assert len(list(container.decode(video=0))) == 4


def test_mask_is_lossless(source):
    result, _, _ = service.run_video(source, "Manusia", "Detail", [], "mask", False,
                                   threading.Event(), lambda *_: None, lambda *_: Matte())
    with av.open(result) as container:
        alpha = next(container.decode(video=0)).to_ndarray(format="gray")
    expected = Matte().process(np.zeros((48, 64, 3), dtype=np.uint8))[1]
    np.testing.assert_array_equal(alpha, expected)


def test_cancel_cleans_partial_outputs(source):
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(Cancelled):
        service.run_video(source, "Manusia", "Detail", [], "mask", False,
                          cancel, lambda *_: None, lambda *_: Matte())
    assert list(service.OUTPUTS.iterdir()) == []
    assert source.exists()


def test_failure_cleans_partial_outputs(source):
    class Broken:
        def process(self, _):
            raise RuntimeError("model failure")
    with pytest.raises(RuntimeError, match="model failure"):
        service.run_video(source, "Manusia", "Detail", [], "mask", False,
                          threading.Event(), lambda *_: None, lambda *_: Broken())
    assert list(service.OUTPUTS.iterdir()) == []


def test_photo_rgba(source, tmp_path):
    photo = tmp_path / "photo.png"
    Image.new("RGB", (64, 48), "red").save(photo)
    result = service.run_photo(photo, "Manusia", "Detail", [], lambda *_: Matte())
    image = Image.open(result)
    assert image.mode == "RGBA" and image.size == (64, 48)
    assert image.getpixel((0, 0)) == (255, 0, 0, 0)


def test_pruning_keeps_conditioning_and_forward_window():
    initial = {0: "prompt"}
    session = SimpleNamespace(output_dict_per_obj={0: {"cond_frame_outputs": initial,
                              "non_cond_frame_outputs": dict.fromkeys(range(100))}},
                              frames_tracked_per_obj={0: dict.fromkeys(range(100))},
                              processed_frames=dict.fromkeys(range(100)))
    prune_session(session, 99, 16)
    assert session.output_dict_per_obj[0]["cond_frame_outputs"] == initial
    assert list(session.output_dict_per_obj[0]["non_cond_frame_outputs"]) == list(range(84, 100))
    assert list(session.processed_frames) == [99]
    assert len(session.frames_tracked_per_obj[0]) == 16


def test_selection_requires_foreground_and_valid_coordinates():
    for points in ([], [(1, 1, 0)], [(64, 0, 1)], [(-1, 0, 1)]):
        with pytest.raises(ValueError):
            validate_points(points, 64, 48)
    validate_points([(10, 10, 1), (0, 0, 0)], 64, 48)


def test_checker_does_not_change_opaque_pixels():
    rgb = np.full((16, 16, 3), 73, dtype=np.uint8)
    np.testing.assert_array_equal(checkerboard(rgb, np.full((16, 16), 255, dtype=np.uint8)), rgb)


def test_audio_mux_and_preview_limit(tmp_path, monkeypatch):
    import subprocess

    import imageio_ffmpeg
    monkeypatch.setattr(service, "OUTPUTS", tmp_path / "outputs")
    service.OUTPUTS.mkdir()
    source = tmp_path / "with audio.mp4"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-f", "lavfi", "-i",
                    "color=c=red:s=64x48:r=10:d=6", "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                    "-c:v", "libx264", "-c:a", "aac", "-shortest", str(source)], check=True)
    result, preview, report = service.run_video(source, "Manusia", "Detail", [], "transparent", True,
                                               threading.Event(), lambda *_: None, lambda *_: Matte())
    assert report["frames"] == 50
    with av.open(result) as container:
        assert len(container.streams.audio) == 1
        assert abs(container.duration / av.time_base - 5) < .15
        assert abs(float(container.streams.audio[0].start_time * container.streams.audio[0].time_base)) < .05
    with av.open(preview) as container:
        assert len(container.streams.audio) == 1 and len(container.streams.video) == 1
        assert abs(container.duration / av.time_base - 5) < .3
    mask, _, _ = service.run_video(source, "Manusia", "Detail", [], "mask", True,
                                   threading.Event(), lambda *_: None, lambda *_: Matte())
    with av.open(mask) as container:
        assert len(container.streams.audio) == 1


def test_rotated_video(tmp_path):
    import subprocess

    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    plain, rotated = tmp_path / "plain.mp4", tmp_path / "rotated.mp4"
    subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=64x48:r=5:d=1",
                    "-c:v", "libx264", str(plain)], check=True)
    subprocess.run([ffmpeg, "-v", "error", "-display_rotation", "90", "-i", str(plain), "-c", "copy", str(rotated)], check=True)
    info, rgb = inspect_video(rotated)
    assert (info.width, info.height) == (48, 64)
    assert rgb.shape == (64, 48, 3)


def test_custom_output_names(source, tmp_path):
    result, _, _ = service.run_video(source, "Manusia", "Detail", [], "transparent", False, threading.Event(),
                                     lambda *_: None, lambda *_: Matte(), output_name="Video Promo: Final?.mov")
    assert result.endswith("Video Promo Final.mov")
    mask, _, _ = service.run_video(source, "Manusia", "Detail", [], "mask", False, threading.Event(),
                                   lambda *_: None, lambda *_: Matte(), output_name="silent")
    assert mask.endswith("silent-hasil.mkv")
    default, _, _ = service.run_video(source, "Manusia", "Detail", [], "mask", False, threading.Event(),
                                      lambda *_: None, lambda *_: Matte(), output_name="  ../..  ")
    assert default.endswith("mask.mkv")
    photo = tmp_path / "photo.png"
    Image.new("RGB", (64, 48), "red").save(photo)
    named = service.run_photo(photo, "Manusia", "Detail", [], lambda *_: Matte(), output_name="foto-produk")
    assert named.endswith("foto-produk.png") and Image.open(named).mode == "RGBA"
    assert service.safe_name("con", "x") == "con-hasil"
    assert service.safe_name("", "x") == "x"


def test_mp4_green_and_black_export(source):
    result_green, _, report_green = service.run_video(
        source, "Manusia", "Detail", [], "mp4_green", False,
        threading.Event(), lambda *_: None, lambda *_: Matte(), output_name="green-test",
    )
    assert result_green.endswith("green-test.mp4")
    assert report_green["frames"] == 4
    with av.open(result_green) as container:
        assert len(container.streams.video) == 1
        frame = next(container.decode(video=0)).to_ndarray(format="rgb24")
        # In Matte(), left half has alpha 0 -> background color (green: 0, 255, 0)
        assert frame[:, :30, 1].mean() > 240
        assert frame[:, :30, 0].mean() < 15
        assert frame[:, :30, 2].mean() < 15

    result_black, _, _ = service.run_video(
        source, "Manusia", "Detail", [], "mp4_black", False,
        threading.Event(), lambda *_: None, lambda *_: Matte(), output_name="black-test",
    )
    assert result_black.endswith("black-test.mp4")
    with av.open(result_black) as container:
        assert len(container.streams.video) == 1
        frame = next(container.decode(video=0)).to_ndarray(format="rgb24")
        # In Matte(), left half has alpha 0 -> background color (black: 0, 0, 0)
        assert frame[:, :30].mean() < 15


