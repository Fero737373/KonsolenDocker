from __future__ import annotations

from hashlib import sha256
from html import escape
import mimetypes
from pathlib import Path
import re

from .models import CatalogItem
from .security import SafeHttpClient
from .thegamesdb import TheGamesDbClient


MAX_COVER_BYTES = 12 * 1024 * 1024
SUPPORTED_IMAGE_SUFFIXES = (".jpg", ".png", ".webp", ".svg")


class CoverService:
    def __init__(self, games_dir: Path, *, api_key: str = "", http=None):
        self.cache_dir = games_dir / "cache" / "romstore" / "covers"
        self.http = http or SafeHttpClient()
        self.thegamesdb = TheGamesDbClient(
            api_key=api_key,
            cache_path=games_dir / "cache" / "romstore" / "thegamesdb.json",
            http=self.http,
        )

    @property
    def thegamesdb_enabled(self) -> bool:
        return self.thegamesdb.enabled

    def cached_or_fetch(self, item: CatalogItem) -> tuple[bytes, str, str]:
        cached_cover = self._cached_cover(item.id)
        if cached_cover:
            return cached_cover.read_bytes(), _mime_for(cached_cover), cached_cover.suffix
        remote_cover = self._fetch_remote_cover(item)
        if remote_cover:
            return remote_cover
        return _placeholder_svg(item), "image/svg+xml", ".svg"

    def materialize(self, item: CatalogItem, directory: Path) -> str:
        data, _, suffix = self.cached_or_fetch(item)
        filename = f"cover{suffix}"
        (directory / filename).write_bytes(data)
        return filename

    def _cached_cover(self, item_id: str) -> Path | None:
        return next(
            (
                path
                for suffix in SUPPORTED_IMAGE_SUFFIXES
                if (path := self.cache_dir / f"{item_id}{suffix}").is_file()
            ),
            None,
        )

    def _fetch_remote_cover(self, item: CatalogItem) -> tuple[bytes, str, str] | None:
        if item.cover_url:
            source_cover = self._download_cover(item, item.cover_url)
            if source_cover:
                return source_cover
        thegamesdb_url = self._thegamesdb_cover_url(item)
        return self._download_cover(item, thegamesdb_url) if thegamesdb_url else None

    def _download_cover(
        self,
        item: CatalogItem,
        remote_url: str,
    ) -> tuple[bytes, str, str] | None:
        try:
            data, content_type = self.http.get_bytes(remote_url, max_bytes=MAX_COVER_BYTES)
            suffix = _image_suffix(content_type, remote_url)
            if not suffix:
                return None
            cached_cover = self.cache_dir / f"{item.id}{suffix}"
            _atomic_write(cached_cover, data)
            return data, _mime_for(cached_cover), suffix
        except Exception:
            return None

    def _thegamesdb_cover_url(self, item: CatalogItem) -> str:
        try:
            return self.thegamesdb.cover_url(item)
        except Exception:
            return ""


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _image_suffix(content_type: str, url: str) -> str:
    suffix_by_type = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    if content_type in suffix_by_type:
        return suffix_by_type[content_type]
    suffix = Path(url.split("?", 1)[0]).suffix.lower()
    return suffix if suffix in SUPPORTED_IMAGE_SUFFIXES[:-1] else ""


def _mime_for(path: Path) -> str:
    if path.suffix == ".svg":
        return "image/svg+xml"
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _placeholder_svg(item: CatalogItem) -> bytes:
    initials = "".join(
        word[0] for word in re.findall(r"[A-Za-z0-9]+", item.title)[:3]
    ).upper() or "ROM"
    digest = sha256(f"{item.title}{item.system}".encode("utf-8")).digest()
    hue = int.from_bytes(digest[:2], "big") % 360
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800" viewBox="0 0 600 800">
<rect width="600" height="800" fill="hsl({hue},45%,18%)"/>
<rect x="36" y="36" width="528" height="728" rx="28" fill="none" stroke="#fff" stroke-opacity=".45" stroke-width="5"/>
<text x="300" y="365" text-anchor="middle" fill="#fff" font-family="sans-serif" font-size="128" font-weight="bold">{escape(initials)}</text>
<text x="300" y="470" text-anchor="middle" fill="#fff" font-family="sans-serif" font-size="30">{escape(item.system.upper())}</text>
<text x="300" y="720" text-anchor="middle" fill="#fff" fill-opacity=".7" font-family="sans-serif" font-size="22">HOME BREW</text>
</svg>"""
    return svg.encode("utf-8")
