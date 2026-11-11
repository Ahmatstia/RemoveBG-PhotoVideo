from urllib.parse import urlparse


def youtube_url(value):
    parsed = urlparse(str(value or "").strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not (host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")):
        raise ValueError("Masukkan URL video YouTube yang valid.")
    return parsed.geturl()
