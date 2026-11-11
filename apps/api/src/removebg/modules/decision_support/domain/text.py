def normalize_text(value):
    return " ".join(str(value or "").split()).casefold()
