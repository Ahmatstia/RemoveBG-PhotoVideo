import ipaddress
import os
import shutil
import socket
import threading
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError, sync_playwright


def public_http_url_error(url):
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return "Masukkan URL website yang valid dan diawali http:// atau https://."
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith((".localhost", ".local")):
        return "Link umum hanya menerima alamat website publik."
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(result[4][0])
                for result in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
            }
        except OSError:
            return "Domain tidak bisa ditemukan melalui DNS. Periksa koneksi atau VPN, lalu coba lagi."
        except ValueError:
            return "Port URL tidak valid."
        if not addresses:
            return "Domain tidak mengarah ke alamat IP yang bisa dijangkau."
    if not all(address.is_global for address in addresses):
        return "Link umum hanya menerima alamat website publik."
    return None


def is_public_http_url(url):
    return public_http_url_error(url) is None


def find_chrome():
    for name in ("chrome", "chrome.exe", "msedge", "msedge.exe"):
        path = shutil.which(name)
        if path:
            return path
    for path in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ):
        if os.path.isfile(path):
            return path
    return None


def run_browser_capture(url, session, cancel):
    url_error = public_http_url_error(url)
    if url_error:
        raise ValueError(url_error)
    chrome = find_chrome()
    if not chrome:
        raise ValueError("Google Chrome atau Microsoft Edge tidak ditemukan.")

    candidates = {}
    session.update(state="opening", message="Membuka halaman di browser sementara…")
    browser = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=chrome,
                headless=False,
                args=["--no-first-run", "--no-default-browser-check"],
            )
            context = browser.new_context(accept_downloads=False, service_workers="block")

            def protect_private_network(route):
                request_url = route.request.url
                if request_url.startswith(("data:", "blob:", "about:")):
                    route.continue_()
                elif is_public_http_url(request_url):
                    route.continue_()
                else:
                    route.abort()

            context.route("**/*", protect_private_network)

            def inspect_response(response):
                if response.status >= 400:
                    return
                media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                path = urlparse(response.url).path.lower()
                if path.endswith(".mpd") or not (
                    path.endswith((".mp4", ".m3u8", ".webm", ".mov", ".m4v"))
                    or media_type.startswith("video/")
                    or media_type in {"application/vnd.apple.mpegurl", "application/x-mpegurl"}
                ):
                    return
                candidates[response.url] = {
                    "url": response.url,
                    "type": media_type or "Media stream",
                    "status": response.status,
                }
                session["candidates"] = list(candidates.values())[:20]
                session["state"] = "found"
                session["message"] = "Sumber media ditemukan. Pilih salah satu untuk mencoba mengunduhnya."

            context.on("page", lambda page: page.on("response", inspect_response))
            page = context.new_page()
            try:
                response = page.goto(url, wait_until="commit", timeout=20_000)
            except PlaywrightError as error:
                if cancel.is_set():
                    return
                detail = str(error)
                if any(code in detail for code in ("ERR_CONNECTION_TIMED_OUT", "ERR_TUNNEL_CONNECTION_FAILED", "ERR_NAME_NOT_RESOLVED")):
                    raise ValueError(
                        "Situs tidak merespons melalui koneksi saat ini. Pastikan VPN tersambung di Windows dan uji URL sumber di Chrome biasa."
                    ) from error
                if not page.url or page.url == "about:blank":
                    raise ValueError(f"Halaman tidak dapat dibuka: {error}") from error
            if response and response.status >= 400:
                raise ValueError(
                    f"Situs membalas HTTP {response.status}; halaman sumber menolak permintaan atau tautannya sudah tidak berlaku."
                )
            session.update(state="waiting", message="Halaman terbuka. Tekan Play di jendela browser untuk mencari video.")
            for _ in range(600):
                if cancel.wait(0.5):
                    return
                try:
                    if not context.pages:
                        break
                except PlaywrightError:
                    break
            if not cancel.is_set() and not candidates:
                session.update(
                    state="failed",
                    message="Tidak ditemukan MP4 atau HLS publik. Situs mungkin memakai pemutar/format yang tidak didukung atau membutuhkan akses khusus.",
                )
            elif not cancel.is_set():
                session["state"] = "found"
    finally:
        if browser:
            try:
                browser.close()
            except PlaywrightError:
                pass
