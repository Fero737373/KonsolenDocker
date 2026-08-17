from __future__ import annotations

from dataclasses import dataclass
from http.client import HTTPResponse
import json
from pathlib import Path
import ssl
import time
from typing import BinaryIO, Callable
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener


ALLOWED_HOSTS = frozenset(
    {
        "api.github.com",
        "api.thegamesdb.net",
        "cdn.thegamesdb.net",
        "hh3.gbdev.io",
        "raw.githubusercontent.com",
    }
)
USER_AGENT = "KonsolenDocker-RomStore/1.0 (+https://github.com/Fero737373/KonsolenDocker)"


class UnsafeUrl(ValueError):
    pass


class DownloadCancelled(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DownloadRequest:
    url: str
    target: BinaryIO
    max_bytes: int
    on_progress: Callable[[int, int | None, float], None]
    is_cancelled: Callable[[], bool]


def validate_remote_url(url: str) -> str:
    parts = urlsplit(url)
    hostname = (parts.hostname or "").lower().rstrip(".")
    if parts.scheme != "https":
        raise UnsafeUrl("Nur HTTPS-Downloads sind erlaubt.")
    if parts.username or parts.password or parts.fragment:
        raise UnsafeUrl("Die Download-URL enthält unzulässige Bestandteile.")
    if parts.port not in (None, 443):
        raise UnsafeUrl("Der Download-Port ist nicht erlaubt.")
    if hostname not in ALLOWED_HOSTS:
        raise UnsafeUrl(f"Download-Host nicht erlaubt: {hostname or 'unbekannt'}")
    return url


class SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        validated = validate_remote_url(urljoin(req.full_url, newurl))
        return super().redirect_request(req, fp, code, msg, headers, validated)


class SafeHttpClient:
    def __init__(self, *, timeout: float = 20.0):
        context = ssl.create_default_context()
        self.timeout = timeout
        self._opener = build_opener(HTTPSHandler(context=context), SafeRedirectHandler())

    def open(self, url: str, *, accept: str = "*/*") -> HTTPResponse:
        validate_remote_url(url)
        request = Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
        return self._opener.open(request, timeout=self.timeout)

    def get_bytes(self, url: str, *, max_bytes: int, accept: str = "*/*") -> tuple[bytes, str]:
        with self.open(url, accept=accept) as response:
            length = _content_length(response)
            if length is not None and length > max_bytes:
                raise ValueError("Antwort überschreitet das Größenlimit.")
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError("Antwort überschreitet das Größenlimit.")
            return data, response.headers.get_content_type()

    def get_json(self, url: str, *, max_bytes: int = 10 * 1024 * 1024) -> dict:
        data, _ = self.get_bytes(url, max_bytes=max_bytes, accept="application/json")
        decoded = json.loads(data.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("Die API-Antwort ist kein JSON-Objekt.")
        return decoded

    def download(self, request: DownloadRequest) -> tuple[int, str]:
        started = time.monotonic()
        received = 0
        with self.open(request.url) as response:
            total = _content_length(response)
            if total is not None and total > request.max_bytes:
                raise ValueError("Download überschreitet das Größenlimit.")
            while True:
                if request.is_cancelled():
                    raise DownloadCancelled("Download abgebrochen.")
                chunk = response.read(128 * 1024)
                if not chunk:
                    break
                received += len(chunk)
                if received > request.max_bytes:
                    raise ValueError("Download überschreitet das Größenlimit.")
                request.target.write(chunk)
                elapsed = max(time.monotonic() - started, 0.001)
                request.on_progress(received, total, received / elapsed)
            if total is not None and received != total:
                raise IOError("Der Download ist unvollständig.")
            return received, response.headers.get_content_type()


def _content_length(response: HTTPResponse) -> int | None:
    raw = response.headers.get("Content-Length")
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value >= 0 else None


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
