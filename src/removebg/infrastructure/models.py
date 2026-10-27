import gc
import os
import urllib.request
from functools import lru_cache

import numpy as np
import torch
from PIL import Image, ImageFilter
from transformers import Sam2VideoModel, Sam2VideoProcessor

from removebg.config import MODELS, SAM_ID, prepare_dirs
from removebg.domain import validate_points


def require_gpu():
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA tidak tersedia. Jalankan setup.ps1 dan periksa driver NVIDIA.")


def release_gpu():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def rvm_path():
    prepare_dirs()
    path = MODELS / "rvm_mobilenetv3_fp32.torchscript"
    if not path.exists():
        url = "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/" + path.name
        partial = path.with_suffix(".download")
        try:
            with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as target:
                while chunk := response.read(1024 * 1024):
                    target.write(chunk)
            os.replace(partial, path)
        finally:
            partial.unlink(missing_ok=True)
    return path


@lru_cache(maxsize=1)
def human_network():
    require_gpu()
    return torch.jit.load(str(rvm_path()), map_location="cuda").eval().half()


class HumanMatting:
    def __init__(self, quality="Detail"):
        self.model = human_network()
        self.states = [None] * 4
        self.quality = quality

    @torch.inference_mode()
    def process(self, rgb):
        source = torch.from_numpy(np.array(rgb, copy=True, order="C")).to("cuda", torch.float16)
        source = source.permute(2, 0, 1).unsqueeze(0).div_(255)
        # RVM refines at source resolution; this ratio only controls its coarse stage.
        ratio = min(1.0, (432 if self.quality == "Detail" else 270) / min(rgb.shape[:2]))
        foreground, alpha, *self.states = self.model(source, *self.states, ratio)
        foreground = foreground[0].permute(1, 2, 0).clamp(0, 1).mul(255).round().byte().cpu().numpy()
        alpha = alpha[0, 0].clamp(0, 1).mul(255).round().byte().cpu().numpy()
        return foreground, alpha


def prune_session(session, frame_index, history):
    """Keep the initial prompt and the exact forward-tracking memory window."""
    cutoff = frame_index - history + 1
    for outputs in session.output_dict_per_obj.values():
        tracked = outputs["non_cond_frame_outputs"]
        for index in list(tracked):
            if index < cutoff:
                del tracked[index]
    for tracked in session.frames_tracked_per_obj.values():
        for index in list(tracked):
            if index < cutoff:
                del tracked[index]
    if session.processed_frames:
        for index in list(session.processed_frames):
            if index != frame_index:
                del session.processed_frames[index]


@lru_cache(maxsize=1)
def object_network():
    require_gpu()
    prepare_dirs()
    model = Sam2VideoModel.from_pretrained(SAM_ID, cache_dir=MODELS / "huggingface").to("cuda").eval()
    processor = Sam2VideoProcessor.from_pretrained(SAM_ID, cache_dir=MODELS / "huggingface")
    return model, processor


class ObjectSegmentation:
    def __init__(self, points):
        self.model, self.processor = object_network()
        self.session = self.processor.init_video_session(
            inference_device="cuda", inference_state_device="cuda", dtype=torch.float32,
        )
        self.points = points
        self.index = 0
        self.history = max(self.model.config.num_maskmem, self.model.config.max_object_pointers_in_encoder)

    @torch.inference_mode()
    def process(self, rgb):
        inputs = self.processor(images=np.array(rgb, copy=True, order="C"), return_tensors="pt").to("cuda")
        if self.index == 0:
            validate_points(self.points, rgb.shape[1], rgb.shape[0])
            self.processor.add_inputs_to_inference_session(
                inference_session=self.session, frame_idx=0, obj_ids=1,
                input_points=[[[[x, y] for x, y, _ in self.points]]],
                input_labels=[[[label for _, _, label in self.points]]],
                original_size=inputs.original_sizes[0],
            )
        with torch.autocast("cuda", dtype=torch.bfloat16):
            result = self.model(inference_session=self.session, frame=inputs.pixel_values[0], frame_idx=self.index)
        logits = self.processor.post_process_masks(
            [result.pred_masks.float()], original_sizes=inputs.original_sizes, binarize=False,
        )[0][0, 0]
        # shortcut: feather only the contour; true hair/glass transparency needs a dedicated matting model.
        mask = (logits > 0).byte().mul(255).cpu().numpy()
        alpha = np.array(Image.fromarray(mask).filter(ImageFilter.GaussianBlur(0.6)))
        prune_session(self.session, self.index, self.history)
        self.index += 1
        return rgb, alpha


def create_model(mode, quality, points):
    return HumanMatting(quality) if mode == "Manusia" else ObjectSegmentation(points)
