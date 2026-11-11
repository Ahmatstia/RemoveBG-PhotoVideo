import json
from removebg.modules.decision_support.domain.taxonomy import ASPECTS
from removebg.modules.decision_support.domain.text import normalize_text
from removebg.modules.decision_support.infrastructure.database import database


def list_categories():
    with database() as db:
        rows = db.execute("""SELECT c.key, c.name, COUNT(p.id) product_count
            FROM categories c LEFT JOIN products p ON p.category_key=c.key
            GROUP BY c.key ORDER BY c.name""").fetchall()
    return [dict(row) for row in rows]


def list_products(category, search):
    query = """SELECT p.id, p.category_key, p.brand, p.model, p.variant, p.specs_json,
        COUNT(DISTINCT r.id) review_count, AVG(r.rating) average_rating,
        (SELECT price FROM price_observations po WHERE po.product_id=p.id ORDER BY observed_at DESC, id DESC LIMIT 1) latest_price,
        (SELECT currency FROM price_observations po WHERE po.product_id=p.id ORDER BY observed_at DESC, id DESC LIMIT 1) currency,
        (SELECT observed_at FROM price_observations po WHERE po.product_id=p.id ORDER BY observed_at DESC, id DESC LIMIT 1) price_observed_at
        FROM products p LEFT JOIN reviews r ON r.product_id=p.id WHERE p.category_key=?"""
    args = [category]
    if search.strip():
        query += " AND (p.brand LIKE ? OR p.model LIKE ? OR p.variant LIKE ?)"
        term = f"%{search.strip()}%"
        args += [term, term, term]
    query += " GROUP BY p.id ORDER BY p.brand, p.model LIMIT 300"
    with database() as db:
        found = db.execute(query, args).fetchall()
    result = []
    for row in found:
        item = dict(row)
        item["specs"] = json.loads(item.pop("specs_json"))
        item["average_rating"] = round(item["average_rating"], 2) if item["average_rating"] is not None else None
        result.append(item)
    return result


def product_detail(product_id):
    with database() as db:
        row = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if not row:
            return None
        product = dict(row)
        product["specs"] = json.loads(product.pop("specs_json"))
        product["prices"] = [dict(item) for item in db.execute(
            "SELECT source_name, source_url, price, currency, observed_at FROM price_observations WHERE product_id=? ORDER BY observed_at DESC LIMIT 30",
            (product_id,),
        )]
        product["specification_sources"] = [dict(item) for item in db.execute(
            "SELECT attribute_key, value, source_name, source_url, observed_at FROM product_spec_observations WHERE product_id=? ORDER BY observed_at DESC",
            (product_id,),
        )]
        product["reviews"] = [dict(item) for item in db.execute(
            "SELECT id, source_name, source_url, text, rating, review_date, imported_at FROM reviews WHERE product_id=? ORDER BY review_date DESC, id DESC LIMIT 100",
            (product_id,),
        )]
        product["aspect_insights"] = [dict(item) for item in db.execute("""
            SELECT pred.aspect_key, pred.sentiment, COUNT(*) evidence_count,
                AVG(pred.confidence) confidence
            FROM review_aspect_predictions pred JOIN reviews r ON r.id=pred.review_id
            WHERE r.product_id=? AND pred.model_version=(SELECT model_version FROM review_aspect_predictions
                WHERE review_id IN (SELECT id FROM reviews WHERE product_id=?) ORDER BY analyzed_at DESC LIMIT 1)
            GROUP BY pred.aspect_key, pred.sentiment ORDER BY pred.aspect_key, pred.sentiment
        """, (product_id, product_id))]
    return product


def existing_fingerprints(rows):
    keys = {(row["category"], row["brand"], row["model"], row["variant"]) for row in rows if row["fingerprint"]}
    if not keys:
        return set()
    result = set()
    with database() as db:
        for key in keys:
            product = db.execute("""SELECT id FROM products WHERE category_key=? AND brand=? COLLATE NOCASE
                AND model=? COLLATE NOCASE AND variant=? COLLATE NOCASE""", key).fetchone()
            if product:
                fingerprints = db.execute("SELECT fingerprint FROM reviews WHERE product_id=?", (product["id"],)).fetchall()
                result.update((tuple(part.casefold() if isinstance(part, str) else part for part in key), item["fingerprint"])
                              for item in fingerprints)
    return result


def import_rows(rows, row_status, batch_id, source_name, imported_at):
    products_added = reviews_added = prices_added = 0
    with database() as db:
        try:
            for row in rows:
                if row_status.get(row["line"]) != "valid":
                    continue
                db.execute("INSERT OR IGNORE INTO categories(key, name, aspects_json) VALUES (?, ?, ?)",
                           (row["category"], row["category"].replace("_", " ").title(), json.dumps(ASPECTS)))
                before = db.total_changes
                db.execute("""INSERT OR IGNORE INTO products(category_key, brand, model, variant, specs_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)""", (row["category"], row["brand"], row["model"], row["variant"], json.dumps(row["specs"]), imported_at))
                product = db.execute("""SELECT id, specs_json FROM products WHERE category_key=? AND brand=? COLLATE NOCASE
                    AND model=? COLLATE NOCASE AND variant=? COLLATE NOCASE""",
                    (row["category"], row["brand"], row["model"], row["variant"])).fetchone()
                if db.total_changes > before:
                    products_added += 1
                specs = json.loads(product["specs_json"])
                specs.update(row["specs"])
                db.execute("UPDATE products SET specs_json=? WHERE id=?", (json.dumps(specs, ensure_ascii=False), product["id"]))
                for attribute_key, value in row["specs"].items():
                    db.execute("""INSERT INTO product_spec_observations
                        (product_id, attribute_key, value, source_name, source_url, observed_at)
                        VALUES (?, ?, ?, ?, ?, ?)""", (product["id"], attribute_key, value,
                        row["source_name"], row["source_url"], row["observed_at"]))
                if row["price"] is not None:
                    db.execute("""INSERT INTO price_observations(product_id, source_name, source_url, price, currency, observed_at)
                        VALUES (?, ?, ?, ?, ?, ?)""", (product["id"], row["source_name"], row["source_url"], row["price"], row["currency"], row["observed_at"]))
                    prices_added += 1
                if row["review_text"]:
                    cursor = db.execute("""INSERT OR IGNORE INTO reviews(product_id, source_name, source_url, text,
                        normalized_text, rating, review_date, imported_at, fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (product["id"], row["source_name"], row["source_url"], row["review_text"],
                         normalize_text(row["review_text"]), row["rating"], row["review_date"], imported_at, row["fingerprint"]))
                    reviews_added += cursor.rowcount
            db.execute("""INSERT INTO import_batches(id, source_name, imported_at, rows_seen, products_added, reviews_added, prices_added)
                VALUES (?, ?, ?, ?, ?, ?, ?)""", (batch_id, source_name, imported_at, len(rows), products_added, reviews_added, prices_added))
            db.commit()
        except Exception:
            db.rollback()
            raise
    return {"batch_id": batch_id, "source_name": source_name, "imported_at": imported_at,
            "rows_seen": len(rows), "products_added": products_added,
            "reviews_added": reviews_added, "prices_added": prices_added}


def recommendation_candidates(category):
    with database() as db:
        rows = db.execute("""SELECT p.id, p.category_key, p.brand, p.model, p.variant, p.specs_json,
            AVG(r.rating) average_rating,
            (SELECT price FROM price_observations po WHERE po.product_id=p.id ORDER BY observed_at DESC, id DESC LIMIT 1) latest_price,
            (SELECT currency FROM price_observations po WHERE po.product_id=p.id ORDER BY observed_at DESC, id DESC LIMIT 1) currency,
            (SELECT observed_at FROM price_observations po WHERE po.product_id=p.id ORDER BY observed_at DESC, id DESC LIMIT 1) price_observed_at,
            COUNT(DISTINCT r.id) review_count FROM products p LEFT JOIN reviews r ON r.product_id=p.id
            WHERE p.category_key=? GROUP BY p.id""", (category,)).fetchall()
        candidates = []
        for raw in rows:
            product = dict(raw)
            product["specs"] = json.loads(product.pop("specs_json"))
            preds = db.execute("""SELECT pred.aspect_key, pred.sentiment, COUNT(*) n
                FROM review_aspect_predictions pred JOIN reviews r ON r.id=pred.review_id
                WHERE r.product_id=? AND pred.model_version=(SELECT model_version FROM review_aspect_predictions
                    WHERE review_id IN (SELECT id FROM reviews WHERE product_id=?) ORDER BY analyzed_at DESC LIMIT 1)
                GROUP BY pred.aspect_key, pred.sentiment""", (product["id"], product["id"])).fetchall()
            grouped = {}
            for pred in preds:
                grouped.setdefault(pred["aspect_key"], {"positive": 0, "neutral": 0, "negative": 0, "n": 0})
                grouped[pred["aspect_key"]][pred["sentiment"]] += pred["n"]
                grouped[pred["aspect_key"]]["n"] += pred["n"]
            product["aspect_scores"] = {
                key: round(100 * (value["positive"] + 0.5 * value["neutral"]) / value["n"], 1)
                for key, value in grouped.items() if value["n"] >= 3
            }
            candidates.append(product)
    return candidates


def pending_reviews(model_version, limit):
    with database() as db:
        return [dict(row) for row in db.execute("""SELECT r.id, r.text FROM reviews r WHERE NOT EXISTS (
            SELECT 1 FROM review_analysis_runs run WHERE run.review_id=r.id AND run.model_version=?)
            ORDER BY r.id LIMIT ?""", (model_version, limit))]


def save_analysis(reviews, predictions, model_version, analyzed_at):
    with database() as db:
        db.executemany("""INSERT OR REPLACE INTO review_aspect_predictions
            (review_id, aspect_key, sentiment, confidence, model_version, analyzed_at) VALUES (?, ?, ?, ?, ?, ?)""",
            [(rid, key, label, confidence, model_version, analyzed_at) for rid, key, label, confidence in predictions])
        db.executemany("INSERT OR REPLACE INTO review_analysis_runs(review_id, model_version, analyzed_at) VALUES (?, ?, ?)",
                       [(review["id"], model_version, analyzed_at) for review in reviews])
        db.commit()
