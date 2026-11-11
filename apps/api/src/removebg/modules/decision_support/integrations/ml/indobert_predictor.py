import json
from functools import lru_cache
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from removebg.config import ROOT
from removebg.modules.decision_support.domain.taxonomy import ASPECTS, LABELS

MODEL_PATH = ROOT / "ml" / "artifacts" / "decision-support-absa"


class IndoBertAspectPredictor:
    def model_version(self):
        version_path = MODEL_PATH / "MODEL_VERSION.txt"
        return version_path.read_text(encoding="utf-8").strip() if version_path.is_file() else "decision-support-absa-local"

    def health(self):
        weights_exist = any((MODEL_PATH / name).is_file() for name in ("model.safetensors", "pytorch_model.bin"))
        ready = (MODEL_PATH / "config.json").is_file() and (MODEL_PATH / "evaluation.json").is_file() and weights_exist
        evaluation = None
        if ready:
            try:
                evaluation = json.loads((MODEL_PATH / "evaluation.json").read_text(encoding="utf-8")).get("best_eval")
            except (OSError, json.JSONDecodeError):
                ready = False
        return {"ready": ready, "base_model": "indobenchmark/indobert-base-p1",
                "evaluation": evaluation, "labels": list(LABELS)}

    @lru_cache(maxsize=1)
    def _load(self):
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH, local_files_only=True)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model.to(device).eval()
        return tokenizer, model, device, self.model_version()

    def analyze(self, reviews):
        tokenizer, model, device, version = self._load()
        predictions = []
        for review in reviews:
            aspect_names = list(ASPECTS)
            inputs = tokenizer([review["text"]] * len(aspect_names), [ASPECTS[key] for key in aspect_names],
                               return_tensors="pt", truncation=True, padding=True, max_length=192).to(device)
            with torch.inference_mode():
                probabilities = torch.softmax(model(**inputs).logits.float(), dim=-1).cpu()
            for aspect_key, probs in zip(aspect_names, probabilities.tolist()):
                label_index = max(range(len(probs)), key=probs.__getitem__)
                sentiment = LABELS[label_index]
                if sentiment != "not_mentioned" and probs[label_index] >= 0.55:
                    predictions.append((review["id"], aspect_key, sentiment, probs[label_index]))
        return predictions, version


predictor = IndoBertAspectPredictor()
