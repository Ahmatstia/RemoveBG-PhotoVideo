import math
import re

from removebg.modules.decision_support.domain.taxonomy import ASPECTS
from removebg.modules.decision_support.infrastructure.repository import recommendation_candidates

CRITERIA_DIRECTIONS = {
    "price": "cost", "rating": "benefit", "spec:battery_hours": "benefit",
    "spec:warranty_months": "benefit", "spec:weight_g": "cost",
}
CRITERIA_DIRECTIONS.update({f"aspect:{key}": "benefit" for key in ASPECTS})


def criteria_value(key, product):
    if key == "price":
        return product["latest_price"] if product["currency"] == "IDR" else None
    if key == "rating":
        return product["average_rating"]
    if key.startswith("aspect:"):
        return product["aspect_scores"].get(key[7:])
    spec_key = key[5:] if key.startswith("spec:") else ""
    value = product["specs"].get(spec_key)
    try:
        parsed = float(re.sub(r"[^0-9.+-]", "", str(value))) if value is not None else None
        return parsed if parsed is not None and math.isfinite(parsed) else None
    except ValueError:
        return None


def recommend(category, budget_max, weights):
    if not weights or any(not math.isfinite(weight) or weight < 0 for weight in weights.values()):
        raise ValueError("Bobot harus angka positif dan minimal satu kriteria dipilih.")
    total_weight = sum(weights.values())
    if not math.isfinite(total_weight) or total_weight <= 0:
        raise ValueError("Jumlah bobot harus lebih dari nol.")
    if budget_max is not None and (not math.isfinite(budget_max) or budget_max <= 0):
        raise ValueError("Budget harus berupa angka positif yang valid.")
    if set(weights) - CRITERIA_DIRECTIONS.keys():
        raise ValueError("Kriteria rekomendasi tidak dikenal.")

    normalized = {key: value / total_weight for key, value in weights.items()}
    candidates = recommendation_candidates(category)
    if budget_max is not None:
        candidates = [item for item in candidates if item["currency"] == "IDR"
                     and item["latest_price"] is not None and item["latest_price"] <= budget_max]
    if not candidates:
        return {"items": [], "message": "Tidak ada produk dengan harga yang memenuhi budget. Ubah budget atau impor harga yang valid.", "algorithm": "SAW-1"}

    observed = {key: [criteria_value(key, item) for item in candidates] for key in normalized}
    result = []
    for product in candidates:
        weighted_score = covered_weight = 0.0
        contributions, missing = {}, []
        for key, weight in normalized.items():
            value = criteria_value(key, product)
            valid = [item for item in observed[key] if item is not None]
            if value is None or not valid:
                missing.append(key)
                continue
            if key == "rating":
                utility = max(0.0, min(1.0, value / 5))
            elif key.startswith("aspect:"):
                utility = max(0.0, min(1.0, value / 100))
            elif CRITERIA_DIRECTIONS[key] == "cost":
                positive = [item for item in valid if item > 0]
                utility = min(positive) / value if positive and value > 0 else 0
            else:
                maximum = max(valid)
                utility = value / maximum if maximum > 0 else 0
            contribution = weight * utility
            weighted_score += contribution
            covered_weight += weight
            contributions[key] = round(contribution * 100, 2)
        if covered_weight < 0.5:
            continue
        result.append({
            "id": product["id"], "brand": product["brand"], "model": product["model"],
            "variant": product["variant"], "score": round(weighted_score / covered_weight * 100, 2),
            "coverage": round(covered_weight * 100, 1), "missing_criteria": missing,
            "contributions": contributions, "price": product["latest_price"],
            "currency": product["currency"], "price_observed_at": product["price_observed_at"],
            "review_count": product["review_count"],
            "average_rating": round(product["average_rating"], 2) if product["average_rating"] is not None else None,
        })
    result.sort(key=lambda item: (-item["score"], -item["coverage"], item["id"]))
    return {"items": [{"rank": index + 1, **item} for index, item in enumerate(result)],
            "algorithm": "SAW-1", "normalized_weights": normalized,
            "policy": "Budget memakai harga observasi terakhir dalam IDR; coverage minimal 50%; aspek AI perlu minimal 3 evidence; skor adalah kesesuaian preferensi."}
