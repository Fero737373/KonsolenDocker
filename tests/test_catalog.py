from pathlib import Path
import tempfile
import unittest

from romstore.catalog import CatalogService
from romstore.models import CatalogItem


class CatalogProvider:
    def __init__(self, name: str, items: list[CatalogItem]):
        self.name = name
        self.items = items
        self.calls = 0

    def list(self, system: str) -> list[CatalogItem]:
        self.calls += 1
        return self.items


def item(provider: str, *, cover_url: str = "") -> CatalogItem:
    return CatalogItem(
        provider=provider,
        system="nes",
        title="Same Homebrew",
        kind="Spiel",
        download_url=f"https://raw.githubusercontent.com/example/{provider}/HEAD/game.nes",
        filename="game.nes",
        source_url=f"https://github.com/example/{provider}",
        cover_url=cover_url,
    )


class CatalogServiceTests(unittest.TestCase):
    def test_preserves_same_title_entries_from_distinct_legal_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            games_dir = Path(directory)
            first = CatalogProvider("First", [item("first")])
            second_item = item(
                "second",
                cover_url="https://raw.githubusercontent.com/example/second/HEAD/cover.png",
            )
            second = CatalogProvider("Second", [second_item])
            catalog = CatalogService(games_dir)
            catalog.providers = [first, second]

            result = catalog.list("nes")

            self.assertEqual(result.items, [first.items[0], second_item])
            self.assertIs(catalog.get(first.items[0].id), first.items[0])
            self.assertIs(catalog.get(second_item.id), second_item)
            self.assertEqual(result.warnings, [])

    def test_reuses_a_fresh_provider_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider_item = item("cached")
            provider = CatalogProvider("Cached", [provider_item])
            catalog = CatalogService(Path(directory), ttl_seconds=3600)
            catalog.providers = [provider]

            first_result = catalog.list("nes")
            second_result = catalog.list("nes")

            self.assertEqual(first_result.items, [provider_item])
            self.assertEqual(second_result.items, [provider_item])
            self.assertEqual(provider.calls, 1)

    def test_explicit_refresh_bypasses_a_fresh_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = CatalogProvider("Refreshable", [item("refreshable")])
            catalog = CatalogService(Path(directory), ttl_seconds=3600)
            catalog.providers = [provider]
            catalog.list("nes")

            catalog.refresh("nes")

            self.assertEqual(provider.calls, 2)

    def test_rejects_unknown_systems_before_calling_providers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = CatalogService(Path(directory))

            with self.assertRaisesRegex(ValueError, "Unbekannte Konsole"):
                catalog.list("not-a-console")


if __name__ == "__main__":
    unittest.main()
