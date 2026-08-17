from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote, urlencode, urlsplit

from ..models import CatalogItem, SYSTEM_EXTENSIONS
from ..security import SafeHttpClient
from .common import ProviderError, optional_non_negative_int, positive_int_or


HOMEBREW_HUB_API = "https://hh3.gbdev.io/api/search"
RESULTS_PER_PAGE = 10
MAX_PAGES = 100
MAX_PARALLEL_REQUESTS = 12
SNAPSHOT_PATH = Path(__file__).parents[1] / "homebrew_manifest.json"
GITHUB_COMMIT_API = "https://api.github.com/repos/{repository}/commits/HEAD"


class HomebrewHubProvider:
    name = "Homebrew Hub"
    platform_for_system = {"gb": "GB", "gbc": "GBC", "gba": "GBA", "nes": "NES"}
    approved_repositories = {
        "gbdev/database",
        "gbadev-org/games",
        "nesdev-org/homebrew-db",
    }

    def __init__(self, http: SafeHttpClient):
        self.http = http

    def list(self, system: str) -> list[CatalogItem]:
        platform = self.platform_for_system.get(system)
        if not platform:
            return []
        manifests = self._fetch_all_manifests(platform)
        repository_refs = self._resolve_repository_refs(manifests)
        return self._catalog_items(manifests, system, repository_refs)

    def bundled_list(self, system: str) -> list[CatalogItem]:
        platform = self.platform_for_system.get(system)
        if not platform:
            return []
        payload = self._load_snapshot()
        systems = payload.get("systems")
        repository_refs = payload.get("repository_refs")
        if not isinstance(systems, dict) or not isinstance(repository_refs, dict):
            raise ProviderError("Der gebündelte Homebrew-Hub-Katalog ist ungültig.")
        manifests = systems.get(platform, [])
        if not isinstance(manifests, list):
            raise ProviderError("Der gebündelte Homebrew-Hub-Katalog ist ungültig.")
        return self._catalog_items(manifests, system, repository_refs)

    def _fetch_all_manifests(self, platform: str) -> list[dict]:
        first_page = self._fetch_page(platform, 1)
        manifests = _page_entries(first_page)
        expected_results = optional_non_negative_int(first_page.get("results"))
        page_count = positive_int_or(first_page.get("page_total"), 1)
        if page_count > MAX_PAGES:
            raise ProviderError("Homebrew-Hub-Paginierung überschreitet das Sicherheitslimit.")
        if page_count == 1:
            _require_complete_page_set(manifests, expected_results)
            return manifests

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as executor:
            requests = {
                executor.submit(self._fetch_page, platform, page): page
                for page in range(2, page_count + 1)
            }
            pages: dict[int, list[dict]] = {}
            for request in as_completed(requests):
                pages[requests[request]] = _page_entries(request.result())
        for page in range(2, page_count + 1):
            manifests.extend(pages[page])
        _require_complete_page_set(manifests, expected_results)
        return manifests

    def _fetch_page(self, platform: str, page: int) -> dict:
        # The production API currently expects the sort column in `sort` and
        # the direction in `order`; using the API.md names duplicates pages.
        query = urlencode(
            {
                "platform": platform,
                "page": page,
                "page_elements": RESULTS_PER_PAGE,
                "sort": "title",
                "order": "asc",
            }
        )
        try:
            return self.http.get_json(f"{HOMEBREW_HUB_API}?{query}")
        except Exception as exc:
            raise ProviderError(f"Homebrew Hub ist nicht erreichbar: {exc}") from exc

    def _catalog_items(
        self,
        manifests: list,
        system: str,
        repository_refs: dict,
    ) -> list[CatalogItem]:
        items = [
            item
            for manifest in manifests
            if isinstance(manifest, dict)
            and (item := self._to_catalog_item(manifest, system, repository_refs))
        ]
        if len({item.download_url for item in items}) != len(items):
            raise ProviderError("Homebrew Hub lieferte doppelte Katalogseiten.")
        return items

    def _to_catalog_item(
        self,
        manifest: dict,
        system: str,
        repository_refs: dict,
    ) -> CatalogItem | None:
        if str(manifest.get("typetag", "game")).lower() == "hackrom":
            return None
        playable_file = _select_playable_file(manifest)
        repository = self._approved_repository(manifest.get("baserepo"))
        repository_ref = str(repository_refs.get(repository) or "")
        slug = str(manifest.get("slug", "")).strip()
        if (
            not playable_file
            or not repository
            or not PINNED_REF_PATTERN.fullmatch(repository_ref)
            or not slug
        ):
            return None

        filename = PurePosixPath(playable_file["filename"]).name
        if PurePosixPath(filename).suffix.lower().lstrip(".") not in SYSTEM_EXTENSIONS[system]:
            return None
        download_url = _raw_entry_url(repository, repository_ref, slug, playable_file["filename"])
        if not download_url:
            return None

        return CatalogItem(
            provider=self.name,
            system=system,
            title=str(manifest.get("title") or slug).strip(),
            kind=_content_kind(manifest),
            download_url=download_url,
            filename=filename,
            source_url=f"https://hh3.gbdev.io/game/{quote(slug, safe='')}",
            description=_description(manifest),
            developer=str(manifest.get("developer") or ""),
            license=str(manifest.get("license") or manifest.get("gameLicense") or "Homebrew"),
            cover_url=_cover_url(manifest, repository, repository_ref, slug),
            size=optional_non_negative_int(playable_file.get("size")),
            sha256=_sha256_or_empty(playable_file.get("sha256")),
        )

    def _approved_repository(self, raw_url: object) -> str:
        if not isinstance(raw_url, str):
            return ""
        parts = urlsplit(raw_url)
        repository = parts.path.strip("/").removesuffix(".git")
        is_github_repository = parts.scheme == "https" and parts.hostname == "github.com"
        return repository if is_github_repository and repository in self.approved_repositories else ""

    def _resolve_repository_refs(self, manifests: list[dict]) -> dict[str, str]:
        repositories = {
            repository
            for manifest in manifests
            if (repository := self._approved_repository(manifest.get("baserepo")))
        }
        refs: dict[str, str] = {}
        for repository in sorted(repositories):
            url = GITHUB_COMMIT_API.format(repository=repository)
            payload = self.http.get_json(url, max_bytes=2 * 1024 * 1024)
            ref = str(payload.get("sha") or "")
            if not PINNED_REF_PATTERN.fullmatch(ref):
                raise ProviderError(f"{repository} lieferte keine gültige Git-Revision.")
            refs[repository] = ref
        return refs

    def _load_snapshot(self) -> dict:
        try:
            payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ProviderError(f"Gebündelter Homebrew-Hub-Katalog fehlt: {exc}") from exc
        return payload if isinstance(payload, dict) else {}


def _select_playable_file(manifest: dict) -> dict | None:
    files = manifest.get("files")
    if not isinstance(files, list):
        return None
    playable_files = [
        entry
        for entry in files
        if isinstance(entry, dict)
        and entry.get("playable") is True
        and _safe_relative_parts(entry.get("filename"))
    ]
    return (
        next((entry for entry in playable_files if entry.get("default") is True), None)
        or next(iter(playable_files), None)
    )


PINNED_REF_PATTERN = re.compile(r"[0-9a-f]{40}")


def _page_entries(payload: dict) -> list[dict]:
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        raise ProviderError("Homebrew Hub lieferte ein ungültiges Katalogformat.")
    return [entry for entry in entries if isinstance(entry, dict)]


def _require_complete_page_set(manifests: list[dict], expected_results: int | None) -> None:
    if expected_results is not None and len(manifests) != expected_results:
        raise ProviderError("Homebrew Hub lieferte eine unvollständige Seitennavigation.")


def _raw_entry_url(
    repository: str,
    repository_ref: str,
    slug: str,
    relative_path: object,
) -> str:
    path_parts = _safe_relative_parts(relative_path)
    if not path_parts:
        return ""
    encoded_path = "/".join(quote(part, safe="") for part in ("entries", slug, *path_parts))
    return f"https://raw.githubusercontent.com/{repository}/{repository_ref}/{encoded_path}"


def _cover_url(manifest: dict, repository: str, repository_ref: str, slug: str) -> str:
    screenshots = manifest.get("screenshots")
    if not isinstance(screenshots, list):
        return ""
    screenshot = next((value for value in screenshots if _safe_relative_parts(value)), "")
    return _raw_entry_url(repository, repository_ref, slug, screenshot) if screenshot else ""


def _safe_relative_parts(value: object) -> tuple[str, ...]:
    if not isinstance(value, str) or not value:
        return ()
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        return ()
    return path.parts


def _content_kind(manifest: dict) -> str:
    return {
        "demo": "Demo",
        "homebrew": "Utility",
        "music": "Musik",
    }.get(str(manifest.get("typetag", "game")).lower(), "Spiel")


def _description(manifest: dict) -> str:
    description = str(manifest.get("description") or "").strip()
    tags = manifest.get("tags")
    if description or not isinstance(tags, list):
        return description
    return ", ".join(str(tag) for tag in tags[:8])


def _sha256_or_empty(value: object) -> str:
    checksum = str(value or "")
    return checksum.lower() if re.fullmatch(r"[0-9a-fA-F]{64}", checksum) else ""
