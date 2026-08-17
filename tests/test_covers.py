from pathlib import Path
import tempfile
import unittest

from romstore.covers import CoverService
from romstore.models import CatalogItem


class CoverHttpClient:
    def __init__(self, thegamesdb_url: str):
        self.thegamesdb_url = thegamesdb_url
        self.requests: list[str] = []

    def get_bytes(self, url: str, *, max_bytes: int, accept: str = "*/*") -> tuple[bytes, str]:
        self.requests.append(url)
        if url == self.thegamesdb_url:
            return b"jpeg", "image/jpeg"
        raise OSError("source cover unavailable")


class CoverLookup:
    enabled = True

    def __init__(self, url: str):
        self.url = url

    def cover_url(self, item: CatalogItem) -> str:
        return self.url


def item_with_source_cover() -> CatalogItem:
    return CatalogItem(
        provider="Fixture",
        system="nes",
        title="Matching Cover",
        kind="Spiel",
        download_url="https://raw.githubusercontent.com/example/project/HEAD/game.nes",
        filename="game.nes",
        source_url="https://github.com/example/project",
        cover_url="https://raw.githubusercontent.com/example/project/HEAD/missing.png",
    )


class CoverServiceTests(unittest.TestCase):
    def test_falls_back_to_thegamesdb_when_the_source_cover_fails(self) -> None:
        thegamesdb_url = "https://cdn.thegamesdb.net/images/original/front.jpg"
        http = CoverHttpClient(thegamesdb_url)
        with tempfile.TemporaryDirectory() as directory:
            service = CoverService(Path(directory), api_key="fixture", http=http)
            service.thegamesdb = CoverLookup(thegamesdb_url)

            data, content_type, suffix = service.cached_or_fetch(item_with_source_cover())

            self.assertEqual(data, b"jpeg")
            self.assertEqual(content_type, "image/jpeg")
            self.assertEqual(suffix, ".jpg")
            self.assertEqual(
                http.requests,
                [
                    "https://raw.githubusercontent.com/example/project/HEAD/missing.png",
                    thegamesdb_url,
                ],
            )


if __name__ == "__main__":
    unittest.main()
