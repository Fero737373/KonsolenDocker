from urllib.parse import parse_qs, urlsplit
import unittest

from romstore.providers.common import ProviderError
from romstore.providers.homebrew_hub import HomebrewHubProvider
from romstore.providers.libretro import LibretroContentProvider


class RecordingHttpClient:
    def __init__(self, payload: dict | None = None, *, failure: Exception | None = None):
        self.payload = payload or {}
        self.failure = failure
        self.urls: list[str] = []

    def get_json(self, url: str, *, max_bytes: int = 0) -> dict:
        self.urls.append(url)
        if self.failure:
            raise self.failure
        if "api.github.com" in url:
            return {"sha": "1" * 40}
        return self.payload


class RouteHttpClient:
    def __init__(self, responses: list[dict]):
        self.responses = iter(responses)

    def get_json(self, url: str, *, max_bytes: int = 0) -> dict:
        return next(self.responses)


def manifest(slug: str, typetag: str, filename: str) -> dict:
    return {
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "typetag": typetag,
        "developer": "Homebrew Author",
        "license": "MIT",
        "baserepo": "https://github.com/nesdev-org/homebrew-db",
        "files": [{"filename": filename, "playable": True, "default": True}],
        "screenshots": ["cover.png"],
    }


class HomebrewHubProviderTests(unittest.TestCase):
    def test_bundled_catalog_is_immediately_available_without_network(self) -> None:
        provider = HomebrewHubProvider(
            RecordingHttpClient(failure=AssertionError("network access"))
        )

        items = provider.bundled_list("gb")

        self.assertGreaterEqual(len(items), 800)
        self.assertTrue(all(item.system == "gb" for item in items))
        self.assertTrue(all("/HEAD/" not in item.download_url for item in items))

    def test_maps_all_requested_content_types_but_excludes_hackroms(self) -> None:
        entries = [
            manifest("a-game", "game", "files/game.nes"),
            manifest("a-tool", "homebrew", "files/tool.nes"),
            manifest("a-demo", "demo", "files/demo.nes"),
            manifest("a-song", "music", "files/song.nes"),
            manifest("a-hack", "hackrom", "files/hack.nes"),
            manifest("unsafe", "game", "../escape.nes"),
        ]
        http = RecordingHttpClient(
            {
                "entries": entries,
                "page_current": 1,
                "page_total": 1,
            }
        )

        items = HomebrewHubProvider(http).list("nes")

        self.assertEqual({item.kind for item in items}, {"Spiel", "Utility", "Demo", "Musik"})
        self.assertEqual(len(items), 4)
        self.assertTrue(
            all(
                item.download_url.startswith("https://raw.githubusercontent.com/")
                for item in items
            )
        )
        self.assertTrue(all("/" + "1" * 40 + "/" in item.download_url for item in items))
        self.assertTrue(all("../" not in item.download_url for item in items))

    def test_uses_stable_pagination_and_the_api_supported_sort_parameters(self) -> None:
        http = RecordingHttpClient(
            {"entries": [], "page_current": 1, "page_total": 1}
        )

        HomebrewHubProvider(http).list("nes")

        query = parse_qs(urlsplit(http.urls[0]).query)
        self.assertEqual(query["platform"], ["NES"])
        self.assertEqual(query["page_elements"], ["10"])
        self.assertEqual(query["sort"], ["title"])
        self.assertEqual(query["order"], ["asc"])

    def test_returns_no_entries_for_an_unsupported_homebrew_hub_platform(self) -> None:
        http = RecordingHttpClient()

        items = HomebrewHubProvider(http).list("ps1")

        self.assertEqual(items, [])
        self.assertEqual(http.urls, [])

    def test_rejects_duplicate_entries_from_unstable_pagination(self) -> None:
        duplicate = manifest("same-game", "game", "files/game.nes")
        http = RecordingHttpClient(
            {
                "entries": [duplicate, duplicate],
                "page_current": 1,
                "page_total": 1,
            }
        )

        with self.assertRaisesRegex(ProviderError, "doppelte Katalogseiten"):
            HomebrewHubProvider(http).list("nes")


class LibretroContentProviderTests(unittest.TestCase):
    def test_bundled_catalog_does_not_wait_for_github(self) -> None:
        provider = LibretroContentProvider(
            RecordingHttpClient(failure=AssertionError("network access"))
        )

        items = provider.bundled_list("nes")

        self.assertGreaterEqual(len(items), 20)
        self.assertTrue(all("/master/" not in item.download_url for item in items))

    def test_pins_live_catalog_downloads_to_the_resolved_commit(self) -> None:
        commit = "1" * 40
        provider = LibretroContentProvider(
            RouteHttpClient(
                [
                    {"sha": commit},
                    {
                        "tree": [
                            {
                                "type": "blob",
                                "path": "Nintendo - GameBoy/demo.gb",
                                "size": 4,
                            }
                        ]
                    },
                ]
            )
        )

        items = provider.list("gb")

        self.assertEqual(len(items), 1)
        self.assertIn(commit, items[0].download_url)

    def test_uses_the_pinned_snapshot_when_github_is_unavailable(self) -> None:
        provider = LibretroContentProvider(
            RecordingHttpClient(failure=OSError("offline"))
        )

        items = provider.list("ps1")

        self.assertEqual({item.title for item in items}, {"240pTestSuitePS1-EMU", "PSXTEST"})
        self.assertTrue(all(item.kind == "Test" for item in items))
        self.assertTrue(
            all("8bd0ddf57bc487edd3e45ddb53dea849a9e8e4a8" in item.download_url for item in items)
        )

    def test_includes_utilities_and_tests_instead_of_hiding_them(self) -> None:
        provider = LibretroContentProvider(
            RecordingHttpClient(failure=OSError("offline"))
        )

        gba_items = provider.list("gba")
        nes_items = provider.list("nes")

        self.assertIn("Utility", {item.kind for item in gba_items})
        self.assertIn("Test", {item.kind for item in nes_items})


if __name__ == "__main__":
    unittest.main()
