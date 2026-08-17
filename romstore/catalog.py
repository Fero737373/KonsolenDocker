from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import threading
import time

from .models import CatalogItem, SUPPORTED_SYSTEMS
from .providers import HomebrewHubProvider, LibretroContentProvider
from .security import SafeHttpClient, atomic_write_json


@dataclass(slots=True)
class CatalogResult:
    items: list[CatalogItem]
    warnings: list[str]
    stale: bool = False


class CatalogService:
    def __init__(self, games_dir: Path, *, ttl_seconds: int = 6 * 60 * 60, http=None):
        self.games_dir = games_dir
        self.cache_dir = games_dir / "cache" / "romstore" / "catalog"
        self.ttl_seconds = ttl_seconds
        self.http = http or SafeHttpClient()
        self.providers = [HomebrewHubProvider(self.http), LibretroContentProvider(self.http)]
        self._items: dict[str, CatalogItem] = {}
        self._lock = threading.RLock()
        self._refresh_lock = threading.Lock()

    def list(self, system: str) -> CatalogResult:
        return self._collect(system, refresh=False)

    def refresh(self, system: str) -> CatalogResult:
        with self._refresh_lock:
            return self._collect(system, refresh=True)

    def _collect(self, system: str, *, refresh: bool) -> CatalogResult:
        if system not in SUPPORTED_SYSTEMS:
            raise ValueError("Unbekannte Konsole.")
        warnings: list[str] = []
        combined: list[CatalogItem] = []
        stale = False
        for provider in self.providers:
            cache_path = self._cache_path(provider.name, system)
            cached, fresh = self._read_cache(cache_path)
            if cached is not None and fresh and not refresh:
                combined.extend(cached)
                continue
            try:
                loader = (
                    provider.list
                    if refresh
                    else getattr(provider, "bundled_list", provider.list)
                )
                items = loader(system)
                self._write_cache(cache_path, items)
                combined.extend(items)
            except Exception as exc:
                if cached is not None:
                    combined.extend(cached)
                    stale = True
                    warnings.append(f"{provider.name}: alter Cache wird verwendet ({exc})")
                else:
                    warnings.append(f"{provider.name}: {exc}")

        unique_items = {item.id: item for item in combined}
        items = sorted(unique_items.values(), key=lambda item: item.title.casefold())
        with self._lock:
            self._items = {
                item_id: existing
                for item_id, existing in self._items.items()
                if existing.system != system
            }
            self._items.update({item.id: item for item in items})
        return CatalogResult(items=items, warnings=warnings, stale=stale)

    def get(self, item_id: str) -> CatalogItem | None:
        with self._lock:
            return self._items.get(item_id)

    def is_installed(self, item: CatalogItem) -> bool:
        receipt = item.install_dir(self.games_dir) / "receipt.json"
        try:
            data = json.loads(receipt.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return data.get("catalog_id") == item.id

    def _cache_path(self, provider: str, system: str) -> Path:
        slug = provider.lower().replace(" ", "-")
        return self.cache_dir / f"{slug}-{system}.json"

    def _read_cache(self, path: Path) -> tuple[list[CatalogItem] | None, bool]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw_items = payload["items"]
            fetched_at = float(payload["fetched_at"])
            if not isinstance(raw_items, list):
                return None, False
            items = [CatalogItem.from_cache(item) for item in raw_items if isinstance(item, dict)]
            return items, time.time() - fetched_at < self.ttl_seconds
        except (OSError, ValueError, KeyError, TypeError):
            return None, False

    def _write_cache(self, path: Path, items: list[CatalogItem]) -> None:
        atomic_write_json(
            path,
            {"fetched_at": time.time(), "items": [item.to_cache() for item in items]},
        )
