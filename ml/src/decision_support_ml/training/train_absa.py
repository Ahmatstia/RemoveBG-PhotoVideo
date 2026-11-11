"""Fine-tune IndoBERT for aspect-conditioned TWS review sentiment."""

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path

import torch
from torch.utils.data import DataLoader, TensorDataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[4]
BASE_MODEL = "indobenchmark/indobert-base-p1"
LABELS = ("not_mentioned", "negative", "neutral", "positive")
ASPECT_NAMES = {
    "sound_quality": "Kualitas suara", "battery": "Baterai", "comfort": "Kenyamanan",
    "connectivity": "Konektivitas", "microphone": "Mikrofon", "anc_transparency": "ANC / transparansi",
    "build_quality": "Kualitas material", "controls_app": "Kontrol / aplikasi",
    "price_value": "Harga / value", "warranty_support": "Garansi / dukungan",
}
ASPECT_KEYS_BY_NAME = {value.casefold(): key for key, value in ASPECT_NAMES.items()}


def read_examples(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = {"review_text", "aspect", "sentiment"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: kolom wajib: {', '.join(sorted(missing))}")
        rows = []
        for line, row in enumerate(reader, 2):
            text, aspect = (row.get("review_text") or "").strip(), (row.get("aspect") or "").strip()
            label = (row.get("sentiment") or "").strip().lower()
            if not text or not aspect or label not in LABELS:
                raise ValueError(f"{path}:{line}: review_text/aspect kosong atau sentiment tidak valid")
            key = aspect.casefold()
            if key not in ASPECT_NAMES and key not in ASPECT_KEYS_BY_NAME:
                raise ValueError(f"{path}:{line}: aspect harus key taxonomy TWS yang dikenal")
            aspect = ASPECT_NAMES[key] if key in ASPECT_NAMES else ASPECT_NAMES[ASPECT_KEYS_BY_NAME[key]]
            rows.append((text, aspect, LABELS.index(label)))
    if not rows:
        raise ValueError(f"Dataset kosong: {path}")
    if {row[2] for row in rows} != set(range(len(LABELS))):
        raise ValueError(f"{path}: train dan eval masing-masing wajib memiliki keempat label {LABELS}")
    return rows


def tensor_data(rows, tokenizer, max_length):
    encoded = tokenizer([row[0] for row in rows], [row[1] for row in rows],
                        truncation=True, padding="max_length", max_length=max_length, return_tensors="pt")
    return TensorDataset(encoded["input_ids"], encoded["attention_mask"],
                         encoded.get("token_type_ids", torch.zeros_like(encoded["input_ids"])),
                         torch.tensor([row[2] for row in rows], dtype=torch.long))


def evaluate(model, loader, device):
    model.eval()
    matrix = [[0] * len(LABELS) for _ in LABELS]
    with torch.inference_mode():
        for ids, mask, types, labels in loader:
            logits = model(input_ids=ids.to(device), attention_mask=mask.to(device),
                           token_type_ids=types.to(device)).logits
            for expected, predicted in zip(labels.tolist(), logits.argmax(dim=-1).cpu().tolist()):
                matrix[expected][predicted] += 1
    per_class = {}
    for index, label in enumerate(LABELS):
        tp = matrix[index][index]
        fp = sum(matrix[actual][index] for actual in range(len(LABELS)) if actual != index)
        fn = sum(matrix[index][predicted] for predicted in range(len(LABELS)) if predicted != index)
        precision = tp / (tp + fp) if tp + fp else 0
        recall = tp / (tp + fn) if tp + fn else 0
        per_class[label] = {"precision": precision, "recall": recall,
                            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0}
    return {"macro_f1": sum(item["f1"] for item in per_class.values()) / len(LABELS),
            "per_class": per_class, "confusion_matrix": matrix, "labels": LABELS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True, help="CSV anotasi train")
    parser.add_argument("--eval", required=True, help="CSV anotasi eval yang terpisah per produk")
    parser.add_argument("--output", default=str(ROOT / "ml" / "artifacts" / "decision-support-absa"))
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=192)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or not 32 <= args.max_length <= 512:
        parser.error("epochs/batch-size harus positif; max-length antara 32 dan 512")

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    train_rows, eval_rows = read_examples(args.train), read_examples(args.eval)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=len(LABELS), id2label=dict(enumerate(LABELS)),
        label2id={label: index for index, label in enumerate(LABELS)},
    ).to(device)
    train_loader = DataLoader(tensor_data(train_rows, tokenizer, args.max_length),
                              batch_size=args.batch_size, shuffle=True)
    eval_loader = DataLoader(tensor_data(eval_rows, tokenizer, args.max_length),
                             batch_size=args.batch_size)
    counts = torch.bincount(torch.tensor([row[2] for row in train_rows]), minlength=len(LABELS)).float()
    if torch.any(counts == 0):
        raise ValueError("Semua kelas sentimen harus memiliki contoh train.")
    class_weights = (len(train_rows) / (len(LABELS) * counts)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    best_score, best_metrics = -1.0, None
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    for epoch in range(args.epochs):
        model.train()
        for ids, mask, types, labels in train_loader:
            ids, mask, types, labels = (item.to(device) for item in (ids, mask, types, labels))
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
                logits = model(input_ids=ids, attention_mask=mask, token_type_ids=types).logits
                loss = torch.nn.functional.cross_entropy(logits.float(), labels, weight=class_weights)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        metrics = evaluate(model, eval_loader, device)
        print(f"epoch {epoch + 1}/{args.epochs}: eval macro-F1={metrics['macro_f1']:.4f}")
        if metrics["macro_f1"] > best_score:
            best_score, best_metrics = metrics["macro_f1"], metrics
            model.save_pretrained(output, safe_serialization=True)
            tokenizer.save_pretrained(output)

    report = {"base_model": BASE_MODEL, "labels": LABELS, "train_rows": len(train_rows),
              "eval_rows": len(eval_rows), "seed": args.seed, "epochs": args.epochs,
              "batch_size": args.batch_size, "max_length": args.max_length,
              "best_eval": best_metrics,
              "warning": "Eval hanya representatif jika deduplikasi dan product-group split dilakukan sebelum training."}
    (output / "evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    weight_file = output / "model.safetensors"
    if weight_file.is_file():
        digest = hashlib.sha256()
        with weight_file.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        model_version = digest.hexdigest()[:16]
        (output / "MODEL_VERSION.txt").write_text(f"decision-support-indobert-{model_version}\n", encoding="utf-8")
    (output / "MODEL_CARD.md").write_text(
        "# Decision Support · TWS ABSA\n\n"
        f"Fine-tuned from `{BASE_MODEL}`. Labels: {', '.join(LABELS)}.\n\n"
        "Evaluation is only meaningful when the held-out products and duplicate groups were kept out of training. "
        "Review the dataset license, annotation guide, and evaluation.json before using these predictions.\n",
        encoding="utf-8",
    )
    print(f"Model dan evaluasi tersimpan di {output}")


if __name__ == "__main__":
    main()
