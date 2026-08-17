#!/usr/bin/env python3
from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from romstore.providers.homebrew_hub import HomebrewHubProvider  # noqa: E402
from romstore.security import SafeHttpClient, atomic_write_json  # noqa: E402


OUTPUT = ROOT / "romstore" / "homebrew_manifest.json"
SYSTEM_FOR_PLATFORM = {"GB": "gb", "GBC": "gbc", "GBA": "gba", "NES": "nes"}
SNAPSHOT_FIELDS = (
    "slug",
    "title",
    "screenshots",
    "typetag",
    "files",
    "developer",
    "license",
    "gameLicense",
    "description",
    "tags",
    "baserepo",
)


def repository_head(repository: str) -> str:
    result = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{repository}.git", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    ref = result.stdout.partition("\t")[0].strip()
    if len(ref) != 40 or any(character not in "0123456789abcdef" for character in ref):
        raise ValueError(f"Ungültige Revision für {repository}")
    return ref


def repository_refs(provider: HomebrewHubProvider) -> dict[str, str]:
    return {
        repository: repository_head(repository)
        for repository in sorted(provider.approved_repositories)
    }


def snapshot_manifest(manifest: dict) -> dict:
    return {field: manifest[field] for field in SNAPSHOT_FIELDS if field in manifest}


def eligible_manifests(
    provider: HomebrewHubProvider,
    manifests: list[dict],
    system: str,
    refs: dict[str, str],
) -> list[dict]:
    return [
        snapshot_manifest(manifest)
        for manifest in manifests
        if provider._to_catalog_item(manifest, system, refs) is not None
    ]


def build_snapshot() -> dict:
    provider = HomebrewHubProvider(SafeHttpClient(timeout=45))
    refs = repository_refs(provider)
    systems = {}
    for platform, system in SYSTEM_FOR_PLATFORM.items():
        manifests = provider._fetch_all_manifests(platform)
        systems[platform] = eligible_manifests(provider, manifests, system, refs)
    return {
        "schema": 1,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source": "https://hh3.gbdev.io/api",
        "repository_refs": refs,
        "systems": systems,
    }


def main() -> None:
    payload = build_snapshot()
    atomic_write_json(OUTPUT, payload)
    counts = {platform: len(entries) for platform, entries in payload["systems"].items()}
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
