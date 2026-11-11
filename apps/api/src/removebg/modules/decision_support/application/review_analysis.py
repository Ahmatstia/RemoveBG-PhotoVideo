import logging
from datetime import datetime, timezone

from removebg.modules.decision_support.infrastructure.repository import pending_reviews, save_analysis
from removebg.modules.decision_support.integrations.ml.indobert_predictor import predictor

logger = logging.getLogger(__name__)


def analyze_reviews(limit):
    if not predictor.health()["ready"]:
        raise RuntimeError("Model ABSA belum tersedia. Latih model dengan data anotasi yang sah terlebih dahulu.")
    try:
        version = predictor.model_version()
        reviews = pending_reviews(version, limit)
        predictions, version = predictor.analyze(reviews)
    except Exception:
        logger.exception("Decision support ABSA failed")
        raise
    analyzed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_analysis(reviews, predictions, version, analyzed_at)
    return {"reviews_analyzed": len(reviews), "aspect_predictions": len(predictions), "model_version": version}
