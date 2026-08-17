from pathlib import Path
import tempfile
import unittest

from romstore.models import CatalogItem
from romstore.thegamesdb import TheGamesDbClient, _extract_cover_url, _matching_platform_id


class FailingHttpClient:
    def get_json(self, url: str) -> dict:
        raise AssertionError("TheGamesDB must not be called without an API key")


def game_item() -> CatalogItem:
    return CatalogItem(
        provider="Fixture",
        system="nes",
        title="Homebrew Game",
        kind="Spiel",
        download_url="https://raw.githubusercontent.com/example/project/HEAD/game.nes",
        filename="game.nes",
        source_url="https://github.com/example/project",
    )


class TheGamesDbTests(unittest.TestCase):
    def test_builds_the_front_boxart_url_for_the_matching_title(self) -> None:
        payload = {
            "data": {
                "games": [
                    {"id": 7, "game_title": "Different Game"},
                    {"id": 42, "game_title": "Homebrew Game"},
                ]
            },
            "include": {
                "boxart": {
                    "base_url": {"original": "https://cdn.thegamesdb.net/images/original/"},
                    "data": {
                        "42": [
                            {"side": "back", "filename": "back.jpg"},
                            {"side": "front", "filename": "front.jpg"},
                        ]
                    },
                }
            },
        }

        cover_url = _extract_cover_url(payload, "Homebrew Game")

        self.assertEqual(
            cover_url,
            "https://cdn.thegamesdb.net/images/original/front.jpg",
        )

    def test_resolves_platform_aliases_without_partial_word_punctuation(self) -> None:
        platforms = [
            {"id": 7, "name": "Nintendo Entertainment System (NES)"},
            {"id": 8, "name": "Super Nintendo Entertainment System"},
        ]

        platform_id = _matching_platform_id(
            platforms,
            ("nintendo entertainment system", "nes"),
        )

        self.assertEqual(platform_id, "7")

    def test_does_not_contact_thegamesdb_without_a_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = TheGamesDbClient(
                api_key="",
                cache_path=Path(directory) / "thegamesdb.json",
                http=FailingHttpClient(),
            )

            cover_url = client.cover_url(game_item())

            self.assertEqual(cover_url, "")
            self.assertFalse(client.enabled)

    def test_does_not_use_boxart_from_a_different_game(self) -> None:
        payload = {
            "data": {"games": [{"id": 7, "game_title": "Different Game"}]},
            "include": {
                "boxart": {
                    "base_url": {"original": "https://cdn.thegamesdb.net/images/original/"},
                    "data": {"7": [{"side": "front", "filename": "wrong.jpg"}]},
                }
            },
        }

        cover_url = _extract_cover_url(payload, "Homebrew Game")

        self.assertEqual(cover_url, "")


if __name__ == "__main__":
    unittest.main()
