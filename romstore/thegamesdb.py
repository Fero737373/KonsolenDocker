from __future__ import annotations

import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlencode, urljoin

from .models import CatalogItem, normalize_title
from .security import SafeHttpClient, atomic_write_json, validate_remote_url


GAMES_API = "https://api.thegamesdb.net/v1.1/Games/ByGameName"
PLATFORMS_API = "https://api.thegamesdb.net/v1/Platforms"
COVER_CACHE_SECONDS = 30 * 24 * 60 * 60
NEGATIVE_CACHE_SECONDS = 7 * 24 * 60 * 60
PLATFORM_CACHE_SECONDS = 90 * 24 * 60 * 60

PLATFORM_ALIASES = {
    "arcade": ("arcade",),
    "atari2600": ("atari 2600",),
    "nes": ("nintendo entertainment system", "nes"),
    "snes": ("super nintendo", "snes"),
    "gb": ("nintendo game boy", "game boy"),
    "gbc": ("nintendo game boy color", "game boy color"),
    "gba": ("nintendo game boy advance", "game boy advance"),
    "sg1000": ("sega sg 1000", "sg 1000"),
    "mastersystem": ("sega master system", "master system"),
    "gamegear": ("sega game gear", "game gear"),
    "megadrive": ("sega genesis", "mega drive"),
    "segacd": ("sega cd", "mega cd"),
    "pcengine": ("turbografx 16", "pc engine"),
    "ps1": ("sony playstation", "playstation"),
}


class TheGamesDbClient:
    def __init__(self, *, api_key: str, cache_path: Path, http: SafeHttpClient):
        self.api_key = api_key.strip()
        self.cache_path = cache_path
        self.http = http
        self._lock = threading.RLock()
        self._cache = self._read_cache()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def cover_url(self, item: CatalogItem) -> str:
        if not self.enabled:
            return ""
        cached_url = self._cached_cover_url(item.id)
        if cached_url is not None:
            return cached_url
        remote_url = self._search_cover(item)
        self._remember_cover_url(item.id, remote_url)
        return remote_url

    def _search_cover(self, item: CatalogItem) -> str:
        parameters = {
            "apikey": self.api_key,
            "name": _search_title(item.title),
            "include": "boxart",
            "fields": "overview",
        }
        if platform_id := self._platform_id(item.system):
            parameters["filter[platform]"] = platform_id
        payload = self.http.get_json(f"{GAMES_API}?{urlencode(parameters)}")
        cover_url = _extract_cover_url(payload, item.title)
        if cover_url:
            validate_remote_url(cover_url)
        return cover_url

    def _cached_cover_url(self, item_id: str) -> str | None:
        with self._lock:
            entry = self._cache.setdefault("covers", {}).get(item_id)
            if not isinstance(entry, dict):
                return None
            age = time.time() - float(entry.get("checked_at", 0))
            url = str(entry.get("url") or "")
            lifetime = COVER_CACHE_SECONDS if url else NEGATIVE_CACHE_SECONDS
            return url if age < lifetime else None

    def _remember_cover_url(self, item_id: str, url: str) -> None:
        with self._lock:
            self._cache.setdefault("covers", {})[item_id] = {
                "checked_at": time.time(),
                "url": url,
            }
            self._write_cache()

    def _platform_id(self, system: str) -> str:
        with self._lock:
            platforms = self._cache.get("platforms")
            age = time.time() - float(self._cache.get("platforms_checked_at", 0))
            if isinstance(platforms, dict) and age < PLATFORM_CACHE_SECONDS:
                return str(platforms.get(system, ""))
            resolved = self._fetch_platform_ids()
            self._cache["platforms"] = resolved
            self._cache["platforms_checked_at"] = time.time()
            self._write_cache()
            return resolved.get(system, "")

    def _fetch_platform_ids(self) -> dict[str, str]:
        query = urlencode({"apikey": self.api_key})
        payload = self.http.get_json(f"{PLATFORMS_API}?{query}")
        platforms = payload.get("data", {}).get("platforms", [])
        if not isinstance(platforms, list):
            return {}
        return {
            system: _matching_platform_id(platforms, aliases)
            for system, aliases in PLATFORM_ALIASES.items()
        }

    def _read_cache(self) -> dict:
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write_cache(self) -> None:
        atomic_write_json(self.cache_path, self._cache)


def _matching_platform_id(platforms: list, aliases: tuple[str, ...]) -> str:
    for platform in platforms:
        if not isinstance(platform, dict):
            continue
        normalized_name = _words(str(platform.get("name", "")))
        if any(_words(alias) == normalized_name or _words(alias) in normalized_name for alias in aliases):
            return str(platform.get("id", ""))
    return ""


def _extract_cover_url(payload: dict, requested_title: str) -> str:
    game = _matching_game(payload, requested_title)
    if not game:
        return ""
    boxart = payload.get("include", {}).get("boxart", {})
    images = boxart.get("data", {}).get(str(game.get("id", "")), [])
    if not isinstance(images, list):
        return ""
    front_image = next(
        (image for image in images if isinstance(image, dict) and image.get("side") == "front"),
        next((image for image in images if isinstance(image, dict)), None),
    )
    if not front_image or not isinstance(front_image.get("filename"), str):
        return ""
    base_urls = boxart.get("base_url", {})
    base_url = base_urls.get("original", "") if isinstance(base_urls, dict) else ""
    return urljoin(str(base_url).rstrip("/") + "/", front_image["filename"])


def _matching_game(payload: dict, requested_title: str) -> dict | None:
    games = payload.get("data", {}).get("games", [])
    if not isinstance(games, list):
        return None
    requested = normalize_title(_search_title(requested_title))
    return next(
        (
            game
            for game in games
            if isinstance(game, dict)
            and normalize_title(str(game.get("game_title", ""))) == requested
        ),
        None,
    )


def _search_title(title: str) -> str:
    qualifiers = r"\s*\([^)]*(demo|preview|prototype|v?\d|usa|europe|japan)[^)]*\)"
    return re.sub(qualifiers, "", title, flags=re.I).strip()


def _words(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
