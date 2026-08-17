from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

from .catalog import CatalogService
from .covers import CoverService
from .downloader import AlreadyInstalled, BusyError, DownloadManager
from .models import SUPPORTED_SYSTEMS


MAX_REQUEST_BYTES = 16 * 1024
JOB_PATH = re.compile(r"^/api/v1/jobs/([0-9a-f]{32})(/cancel)?$")


class RomStoreApp:
    def __init__(self, games_dir: Path, *, thegamesdb_api_key: str = ""):
        self.games_dir = games_dir
        self.catalog = CatalogService(games_dir)
        self.covers = CoverService(games_dir, api_key=thegamesdb_api_key)
        self.downloads = DownloadManager(games_dir, self.covers)


class RomStoreHandler(BaseHTTPRequestHandler):
    server_version = "KonsolenDocker-RomStore/1.0"
    protocol_version = "HTTP/1.1"

    @property
    def app(self) -> RomStoreApp:
        return self.server.app  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path == "/health":
            self._json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "thegamesdb": self.app.covers.thegamesdb_enabled,
                },
            )
            return
        if parsed.path == "/api/v1/catalog":
            self._get_catalog(parse_qs(parsed.query))
            return
        if parsed.path == "/api/v1/cover":
            self._get_cover(parse_qs(parsed.query))
            return
        match = JOB_PATH.fullmatch(parsed.path)
        if match and not match.group(2):
            job = self.app.downloads.snapshot(match.group(1))
            if not job:
                self._error(HTTPStatus.NOT_FOUND, "Download nicht gefunden.")
            else:
                self._json(HTTPStatus.OK, {"job": job})
            return
        self._error(HTTPStatus.NOT_FOUND, "API-Endpunkt nicht gefunden.")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path == "/api/v1/download":
            self._start_download()
            return
        match = JOB_PATH.fullmatch(parsed.path)
        if match and match.group(2):
            job = self.app.downloads.cancel(match.group(1))
            if not job:
                self._error(HTTPStatus.NOT_FOUND, "Download nicht gefunden.")
            else:
                self._json(HTTPStatus.ACCEPTED, {"job": job})
            return
        self._error(HTTPStatus.NOT_FOUND, "API-Endpunkt nicht gefunden.")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:
        # Query strings could contain sensitive upstream parameters in future.
        # The local UI needs no access log, so only sanitized protocol errors are emitted.
        if args and str(args[0]).startswith("4"):
            super().log_message("client error: %s", args[0])

    def _get_catalog(self, query: dict[str, list[str]]) -> None:
        system = query.get("system", [""])[0]
        if system not in SUPPORTED_SYSTEMS:
            self._error(HTTPStatus.BAD_REQUEST, "Unbekannte oder fehlende Konsole.")
            return
        refresh = query.get("refresh", ["0"])[0] == "1"
        result = self.app.catalog.refresh(system) if refresh else self.app.catalog.list(system)
        api_base = "http://romstore:8080"
        items = [
            item.to_public(
                installed=self.app.catalog.is_installed(item),
                api_base=api_base,
            )
            for item in result.items
        ]
        self._json(
            HTTPStatus.OK,
            {
                "system": system,
                "items": items,
                "count": len(items),
                "warnings": result.warnings,
                "stale": result.stale,
            },
        )

    def _get_cover(self, query: dict[str, list[str]]) -> None:
        item_id = query.get("id", [""])[0]
        if not re.fullmatch(r"[0-9a-f]{24}", item_id):
            self._error(HTTPStatus.BAD_REQUEST, "Ungültige Cover-ID.")
            return
        item = self.app.catalog.get(item_id)
        if not item:
            self._error(HTTPStatus.NOT_FOUND, "Cover nicht gefunden. Katalog zuerst laden.")
            return
        data, content_type, _ = self.app.covers.cached_or_fetch(item)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _start_download(self) -> None:
        body = self._read_json_body()
        if body is None:
            return
        item_id = body.get("id")
        if not isinstance(item_id, str) or not re.fullmatch(r"[0-9a-f]{24}", item_id):
            self._error(HTTPStatus.BAD_REQUEST, "Ungültige Katalog-ID.")
            return
        item = self.app.catalog.get(item_id)
        if not item:
            self._error(HTTPStatus.NOT_FOUND, "Inhalt nicht gefunden. Katalog bitte neu laden.")
            return
        try:
            job = self.app.downloads.start(item)
        except BusyError as exc:
            self._error(HTTPStatus.CONFLICT, str(exc))
            return
        except AlreadyInstalled as exc:
            self._error(HTTPStatus.CONFLICT, str(exc))
            return
        self._json(HTTPStatus.ACCEPTED, {"job": job})

    def _read_json_body(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_REQUEST_BYTES:
            self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Anfrage ist zu groß.")
            return None
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._error(HTTPStatus.BAD_REQUEST, "Ungültiges JSON.")
            return None
        if not isinstance(payload, dict):
            self._error(HTTPStatus.BAD_REQUEST, "JSON-Objekt erwartet.")
            return None
        return payload

    def _json(self, status: HTTPStatus, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json(status, {"error": message})


class RomStoreServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, app: RomStoreApp):
        super().__init__(address, RomStoreHandler)
        self.app = app


def load_thegamesdb_api_key() -> str:
    secret_path = os.environ.get("THEGAMESDB_API_KEY_FILE", "")
    if not secret_path:
        return os.environ.get("THEGAMESDB_API_KEY", "")
    try:
        api_key = Path(secret_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit("TheGamesDB-Secret konnte nicht gelesen werden.") from exc
    if "\n" in api_key or "\r" in api_key or len(api_key) > 4096:
        raise SystemExit("TheGamesDB-Secret hat ein ungültiges Format.")
    return api_key


def main() -> None:
    games_dir = Path(os.environ.get("GAMES_DIR", "/games")).resolve()
    if games_dir != Path("/games") and os.environ.get("ROMSTORE_ALLOW_CUSTOM_GAMES_DIR") != "1":
        raise SystemExit("GAMES_DIR außerhalb des Container-Mounts ist nicht erlaubt.")
    app = RomStoreApp(
        games_dir,
        thegamesdb_api_key=load_thegamesdb_api_key(),
    )
    host = os.environ.get("ROMSTORE_BIND", "0.0.0.0")
    port = int(os.environ.get("ROMSTORE_PORT", "8080"))
    server = RomStoreServer((host, port), app)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
