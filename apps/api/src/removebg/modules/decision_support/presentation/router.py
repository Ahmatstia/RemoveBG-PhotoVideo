import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from removebg.modules.decision_support.application.csv_import import MAX_CSV_BYTES, inspect_rows, parse_csv
from removebg.modules.decision_support.application.recommendations import recommend
from removebg.modules.decision_support.application.review_analysis import analyze_reviews
from removebg.modules.decision_support.infrastructure.repository import (
    existing_fingerprints,
    import_rows,
    list_categories,
    list_products,
    product_detail,
)
from removebg.modules.decision_support.integrations.ml.indobert_predictor import predictor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/decision-support", tags=["decision-support"])


@router.get("/categories")
def categories():
    return {"categories": list_categories()}


@router.get("/products")
def products(category: str = "tws", search: str = Query(default="", max_length=160)):
    return {"products": list_products(category, search)}


@router.get("/products/{product_id}")
def product(product_id: int):
    result = product_detail(product_id)
    if result is None:
        raise HTTPException(404, "Data pembanding tidak ditemukan.")
    return result


async def read_csv_upload(file):
    name = Path(file.filename or "dataset.csv").name
    if Path(name).suffix.lower() != ".csv":
        await file.close()
        raise HTTPException(400, "Unggah file CSV.")
    content = await file.read(MAX_CSV_BYTES + 1)
    await file.close()
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(413, "Ukuran CSV maksimal 20 MB.")
    try:
        return name, parse_csv(content)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.post("/imports/preview")
async def preview_import(file: UploadFile = File(...)):
    name, rows = await read_csv_upload(file)
    report = inspect_rows(rows, existing_fingerprints(rows))
    report.pop("_row_status", None)
    return {"source_name": name, **report}


@router.post("/imports")
async def commit_import(file: UploadFile = File(...)):
    name, rows = await read_csv_upload(file)
    report = inspect_rows(rows, existing_fingerprints(rows))
    if report["accepted"] == 0:
        raise HTTPException(400, "Tidak ada baris valid untuk disimpan.")
    row_status = report.pop("_row_status")
    try:
        result = import_rows(rows, row_status, uuid.uuid4().hex, name,
                             datetime.now(timezone.utc).isoformat(timespec="seconds"))
    except Exception as error:
        logger.exception("Decision support CSV import failed")
        raise HTTPException(500, "Import gagal; tidak ada perubahan yang disimpan.") from error
    return {**result, "duplicates_skipped": report["duplicates"], "rejected": report["rejected"]}


class RecommendationInput(BaseModel):
    category: str = "tws"
    budget_max: float | None = Field(default=None, gt=0)
    weights: dict[str, float]


@router.post("/recommendations")
def recommendations(payload: RecommendationInput):
    try:
        return recommend(payload.category, payload.budget_max, payload.weights)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.get("/model")
def model_status():
    result = predictor.health()
    if not result["ready"]:
        result["message"] = "Model ABSA belum dilatih. Siapkan data anotasi dan jalankan ml/src/decision_support_ml/training/train_absa.py."
    return result


@router.post("/analyze")
def analyze(limit: int = Query(default=100, ge=1, le=500)):
    try:
        return analyze_reviews(limit)
    except RuntimeError as error:
        raise HTTPException(409, str(error)) from error
    except Exception as error:
        raise HTTPException(500, "Analisis ulasan gagal.") from error
