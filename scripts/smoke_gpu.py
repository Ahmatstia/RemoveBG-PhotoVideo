"""Real inference check and bounded-memory tracking check; not a quality benchmark."""
import json
import threading
import time
from fractions import Fraction
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from removebg.application.service import run_video
from removebg.infrastructure.media import VideoWriter, checkerboard
from removebg.infrastructure.models import HumanMatting, ObjectSegmentation, release_gpu


def main():
    directory = Path("data/samples")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "astronaut.png"
    if not path.exists():
        raise SystemExit("Download astronaut.png from scikit-image v0.25.2 into data/samples first; see README.")
    photo = Image.open(path).convert("RGB")
    source = np.asarray(photo)
    metrics = {}
    for name, create in [("RVM", lambda: HumanMatting("Detail")),
                         ("SAM2", lambda: ObjectSegmentation([(260, 110, 1), (180, 350, 1), (30, 30, 0)]))]:
        model = create()
        torch.cuda.reset_peak_memory_stats()
        start = time.monotonic()
        for index in range(24):
            foreground, alpha = model.process(source)
        torch.cuda.synchronize()
        assert foreground.shape == source.shape and alpha.shape == source.shape[:2]
        assert alpha.max() > 200 and alpha.min() < 30, "Model produced a degenerate mask"
        if name == "SAM2":
            assert len(model.session.processed_frames) == 1
            assert len(model.session.output_dict_per_obj[0]["non_cond_frame_outputs"]) <= model.history
        metrics[name] = {"frames": 24, "seconds": round(time.monotonic()-start, 2),
                         "peak_allocated_mib": round(torch.cuda.max_memory_allocated()/1024**2)}
        Image.fromarray(checkerboard(foreground, alpha)).save(directory / f"{name}-preview.png")
        del model
        release_gpu()
        print(name, metrics[name], flush=True)
    clip = directory / "synthetic-1080p.mp4"
    writer = VideoWriter(clip, 1920, 1080, Fraction(30), "preview")
    canvas = Image.new("RGB", (1920, 1080), (80, 90, 100))
    canvas.paste(photo.resize((1080, 1080)), (420, 0))
    for index in range(30):
        writer.write(np.asarray(canvas), Fraction(index, 30))
    writer.close()
    output, preview, report = run_video(clip, "Manusia", "Detail", [], "transparent", False,
                                      threading.Event(), lambda *_: None)
    metrics["1080p_pipeline"] = report
    metrics["1080p_pipeline"]["output"] = output
    metrics["1080p_pipeline"]["preview"] = preview
    (directory / "smoke-report.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2), flush=True)


if __name__ == "__main__":
    main()
