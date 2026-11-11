import json
import sqlite3
from contextlib import contextmanager

from removebg.config import ROOT

DB_PATH = ROOT / "data" / "decision-support.sqlite3"


@contextmanager
def database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    try:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS categories (
                key TEXT PRIMARY KEY, name TEXT NOT NULL, aspects_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY, category_key TEXT NOT NULL REFERENCES categories(key),
                brand TEXT NOT NULL, model TEXT NOT NULL, variant TEXT NOT NULL DEFAULT '',
                specs_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
                UNIQUE(category_key, brand COLLATE NOCASE, model COLLATE NOCASE, variant COLLATE NOCASE)
            );
            CREATE TABLE IF NOT EXISTS import_batches (
                id TEXT PRIMARY KEY, source_name TEXT NOT NULL, imported_at TEXT NOT NULL,
                rows_seen INTEGER NOT NULL, products_added INTEGER NOT NULL,
                reviews_added INTEGER NOT NULL, prices_added INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                source_name TEXT NOT NULL, source_url TEXT NOT NULL DEFAULT '', text TEXT NOT NULL,
                normalized_text TEXT NOT NULL, rating REAL, review_date TEXT NOT NULL DEFAULT '',
                imported_at TEXT NOT NULL, fingerprint TEXT NOT NULL,
                UNIQUE(product_id, fingerprint)
            );
            CREATE TABLE IF NOT EXISTS price_observations (
                id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                source_name TEXT NOT NULL, source_url TEXT NOT NULL DEFAULT '', price REAL NOT NULL,
                currency TEXT NOT NULL, observed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS product_spec_observations (
                id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                attribute_key TEXT NOT NULL, value TEXT NOT NULL, source_name TEXT NOT NULL,
                source_url TEXT NOT NULL DEFAULT '', observed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS review_aspect_predictions (
                review_id INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
                aspect_key TEXT NOT NULL, sentiment TEXT NOT NULL, confidence REAL NOT NULL,
                model_version TEXT NOT NULL, analyzed_at TEXT NOT NULL,
                PRIMARY KEY(review_id, aspect_key, model_version)
            );
            CREATE TABLE IF NOT EXISTS review_analysis_runs (
                review_id INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
                model_version TEXT NOT NULL, analyzed_at TEXT NOT NULL,
                PRIMARY KEY(review_id, model_version)
            );
            CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_key, brand, model);
            CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id, review_date);
            CREATE INDEX IF NOT EXISTS idx_prices_product ON price_observations(product_id, observed_at);
            CREATE INDEX IF NOT EXISTS idx_aspects_review ON review_aspect_predictions(review_id, aspect_key);
        """)
        from removebg.modules.decision_support.domain.taxonomy import ASPECTS

        connection.execute(
            "INSERT OR IGNORE INTO categories(key, name, aspects_json) VALUES (?, ?, ?)",
            ("tws", "TWS / True Wireless Stereo", json.dumps(ASPECTS)),
        )
        connection.commit()
        yield connection
    finally:
        connection.close()
