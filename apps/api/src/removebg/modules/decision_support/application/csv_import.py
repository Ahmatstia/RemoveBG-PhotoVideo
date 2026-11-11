import csv
import hashlib
import io
import math
import re
from datetime import datetime, timezone

from removebg.modules.decision_support.domain.text import normalize_text

MAX_CSV_BYTES = 20 * 1024 * 1024
MAX_ROWS = 20_000


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_timestamp(value, default=None):
    if not value:
        return default or utc_now()
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        parsed_date = datetime.strptime(raw, "%Y-%m-%d").date()
        parsed = datetime.combine(parsed_date, datetime.min.time(), timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_csv(content):
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("CSV harus memakai encoding UTF-8.") from error
    reader = csv.DictReader(io.StringIO(text))
    headers = {str(item or "").strip().lower() for item in (reader.fieldnames or [])}
    missing = {"brand", "model"} - headers
    if missing:
        raise ValueError("Kolom wajib tidak ditemukan: " + ", ".join(sorted(missing)))
    rows = []
    for index, raw in enumerate(reader, 2):
        if index > MAX_ROWS + 1:
            raise ValueError(f"Maksimal {MAX_ROWS} baris per import.")
        row = {str(key or "").strip().lower(): str(value or "").strip() for key, value in raw.items()}
        brand, model = row.get("brand", ""), row.get("model", "")
        problems = []
        if not brand or not model:
            problems.append("brand dan model wajib diisi")
        try:
            price = float(row["price"].replace(",", "")) if row.get("price") else None
            if price is not None and (not math.isfinite(price) or price <= 0):
                raise ValueError
        except ValueError:
            price, problems = None, problems + ["price harus angka positif"]
        try:
            rating = float(row["rating"]) if row.get("rating") else None
            if rating is not None and (not math.isfinite(rating) or not 0 <= rating <= 5):
                raise ValueError
        except ValueError:
            rating, problems = None, problems + ["rating harus antara 0 dan 5"]
        review_text = row.get("review_text", "")
        if len(review_text) > 10_000:
            problems.append("review_text maksimal 10.000 karakter")
        raw_category = row.get("category", "tws").lower()
        category = re.sub(r"[^a-z0-9_-]", "", raw_category) or "tws"
        if raw_category and not re.fullmatch(r"[a-z0-9_-]+", raw_category):
            problems.append("category hanya boleh memakai huruf kecil, angka, _ atau -")
        if category != "tws":
            problems.append("kategori yang tersedia saat ini hanya pilot TWS")
        raw_currency = row.get("currency", "IDR")
        if raw_currency and not re.fullmatch(r"[A-Za-z]{3}", raw_currency):
            problems.append("currency harus berupa kode tiga huruf seperti IDR")
        try:
            observed_at = normalize_timestamp(row.get("observed_at"))
            review_date = normalize_timestamp(row.get("review_date"), default="") if row.get("review_date") else ""
        except ValueError:
            observed_at, review_date = utc_now(), ""
            problems.append("observed_at/review_date harus berupa tanggal ISO seperti 2026-10-31")
        specs = {key[5:]: value for key, value in row.items() if key.startswith("spec_") and len(key) > 5 and value}
        fingerprint = hashlib.sha256(normalize_text(review_text).encode("utf-8")).hexdigest() if review_text else ""
        rows.append({
            "line": index, "category": category, "brand": brand[:120], "model": model[:180],
            "variant": row.get("variant", "")[:120], "price": price,
            "currency": (raw_currency or "IDR").upper()[:3], "rating": rating,
            "review_text": review_text, "review_date": review_date[:40],
            "source_name": (row.get("source_name") or "CSV import")[:160],
            "source_url": row.get("source_url", "")[:2000], "observed_at": observed_at,
            "specs": specs, "fingerprint": fingerprint, "problems": problems,
        })
    return rows


def inspect_rows(rows, existing):
    product_keys, seen = set(), set()
    accepted = duplicates = rejected = 0
    details = []
    for row in rows:
        key = (row["category"], row["brand"].casefold(), row["model"].casefold(), row["variant"].casefold())
        fingerprint = row["fingerprint"]
        reason = "; ".join(row["problems"])
        if not reason and fingerprint and (key, fingerprint) in seen:
            reason, duplicates = "review duplikat dalam file", duplicates + 1
        elif not reason and fingerprint and (key, fingerprint) in existing:
            reason, duplicates = "review sudah pernah diimpor", duplicates + 1
        if reason:
            rejected += 1 if row["problems"] else 0
        else:
            accepted += 1
            product_keys.add(key)
            if fingerprint:
                seen.add((key, fingerprint))
        details.append({"line": row["line"], "status": "valid" if not reason else "duplicate" if "duplikat" in reason or "pernah diimpor" in reason else "rejected", "reason": reason})
    return {"rows_seen": len(rows), "accepted": accepted, "duplicates": duplicates,
            "rejected": rejected, "distinct_products": len(product_keys), "rows": details[:250],
            "_row_status": {item["line"]: item["status"] for item in details}}
