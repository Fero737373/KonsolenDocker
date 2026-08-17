from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote

from ..models import CatalogItem, SYSTEM_EXTENSIONS, safe_name
from ..security import SafeHttpClient
from .common import ProviderError, optional_non_negative_int


LIBRETRO_COMMIT_API = "https://api.github.com/repos/libretro/libretro-content/commits/master"
LIBRETRO_TREE_API = "https://api.github.com/repos/libretro/libretro-content/git/trees/{ref}?recursive=1"
LIBRETRO_RAW_BASE = "https://raw.githubusercontent.com/libretro/libretro-content"
PINNED_REF_PATTERN = re.compile(r"[0-9a-f]{40}")


class LibretroContentProvider:
    name = "Libretro Content"
    directory_systems = {
        "Arcade": "arcade",
        "Atari - 2600": "atari2600",
        "NEC - PC Engine - TurboGrafx 16": "pcengine",
        "Nintendo - GameBoy Advance": "gba",
        "Nintendo - GameBoy": "gb",
        "Nintendo - Nintendo Entertainment System": "nes",
        "Nintendo - Super Nintendo Entertainment System": "snes",
        "Sega - Game Gear": "gamegear",
        "Sega - Master System - Mark III": "mastersystem",
        "Sega - Mega Drive - Genesis": "megadrive",
        "Sony - PlayStation": "ps1",
    }

    def __init__(self, http: SafeHttpClient):
        self.http = http
        self._tree: tuple[list[dict], str] | None = None

    def list(self, system: str) -> list[CatalogItem]:
        tree, ref = self._load_tree()
        return self._catalog_items(tree, system, ref)

    def bundled_list(self, system: str) -> list[CatalogItem]:
        payload, ref = self._load_snapshot()
        tree = payload.get("tree")
        if not isinstance(tree, list):
            raise ProviderError("Der gebündelte Libretro-Katalog ist ungültig.")
        return self._catalog_items(
            [node for node in tree if isinstance(node, dict)],
            system,
            ref,
        )

    def _catalog_items(
        self,
        tree: list[dict],
        system: str,
        ref: str,
    ) -> list[CatalogItem]:
        return [
            item
            for node in tree
            if (item := self._to_catalog_item(node, system, ref))
        ]

    def _to_catalog_item(
        self,
        node: dict,
        requested_system: str,
        ref: str,
    ) -> CatalogItem | None:
        path = node.get("path")
        if node.get("type") != "blob" or not isinstance(path, str):
            return None
        directory, separator, filename = path.partition("/")
        if not separator or "/" in filename:
            return None
        system = self._system_for_file(directory, filename)
        extension = PurePosixPath(filename).suffix.lower().lstrip(".")
        if system != requested_system or extension not in SYSTEM_EXTENSIONS[system]:
            return None

        encoded_path = "/".join(quote(part, safe="") for part in path.split("/"))
        title = safe_name(PurePosixPath(filename).stem.replace("_", " "), "Homebrew")
        return CatalogItem(
            provider=self.name,
            system=system,
            title=title,
            kind=_kind_from_title(title),
            download_url=f"{LIBRETRO_RAW_BASE}/{ref}/{encoded_path}",
            filename=filename,
            source_url=f"https://github.com/libretro/libretro-content/blob/{ref}/{encoded_path}",
            description="Freier Inhalt aus dem offiziellen Libretro Content Downloader.",
            developer="Libretro-Community",
            license="Free/Homebrew",
            size=optional_non_negative_int(node.get("size")),
        )

    def _system_for_file(self, directory: str, filename: str) -> str:
        system = self.directory_systems.get(directory, "")
        if system == "megadrive" and "mega_cd" in filename.lower():
            return "segacd"
        return system

    def _load_tree(self) -> tuple[list[dict], str]:
        if self._tree is not None:
            return self._tree
        payload, ref = self._fetch_tree_or_snapshot()
        tree = payload.get("tree")
        if not isinstance(tree, list):
            raise ProviderError("Der Libretro-Katalog ist ungültig.")
        self._tree = ([node for node in tree if isinstance(node, dict)], ref)
        return self._tree

    def _fetch_tree_or_snapshot(self) -> tuple[dict, str]:
        try:
            commit = self.http.get_json(LIBRETRO_COMMIT_API, max_bytes=2 * 1024 * 1024)
            ref = str(commit.get("sha") or "")
            if not PINNED_REF_PATTERN.fullmatch(ref):
                raise ValueError("ungültige GitHub-Revision")
            tree_url = LIBRETRO_TREE_API.format(ref=ref)
            payload = self.http.get_json(tree_url, max_bytes=20 * 1024 * 1024)
            if payload.get("truncated") is True:
                raise ValueError("unvollständiger GitHub-Baum")
            return payload, ref
        except Exception:
            return self._load_snapshot()

    def _load_snapshot(self) -> tuple[dict, str]:
        try:
            payload = json.loads(
                Path(__file__).parents[1].joinpath("libretro_manifest.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            raise ProviderError(f"Libretro Content ist nicht erreichbar: {exc}") from exc
        ref = str(payload.get("ref") or "")
        if not PINNED_REF_PATTERN.fullmatch(ref):
            raise ProviderError("Der gebündelte Libretro-Katalog hat keine gültige Revision.")
        return payload, ref


def _kind_from_title(title: str) -> str:
    normalized = title.lower()
    if any(word in normalized for word in ("utility", "tool")):
        return "Utility"
    if any(word in normalized for word in ("test", "controller", "padtest", "chroma")):
        return "Test"
    if any(word in normalized for word in ("demo", "preview", "prototype")):
        return "Demo"
    return "Spiel"
