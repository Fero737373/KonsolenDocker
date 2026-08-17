from pathlib import Path
import tempfile
import unittest

from romstore.security import UnsafeUrl, atomic_write_json, validate_remote_url


class RemoteUrlValidationTests(unittest.TestCase):
    def test_accepts_exact_allowlisted_https_hosts(self) -> None:
        urls = (
            "https://hh3.gbdev.io/api/search",
            "https://raw.githubusercontent.com/libretro/libretro-content/master/demo.gb",
            "https://cdn.thegamesdb.net/images/original/boxart/front/1-1.jpg",
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(validate_remote_url(url), url)

    def test_rejects_urls_that_can_escape_the_allowlist(self) -> None:
        urls = (
            "http://hh3.gbdev.io/api/search",
            "https://evil.example/download.nes",
            "https://hh3.gbdev.io.evil.example/download.nes",
            "https://user@hh3.gbdev.io/download.nes",
            "https://hh3.gbdev.io:444/download.nes",
            "https://hh3.gbdev.io/download.nes#fragment",
        )

        for url in urls:
            with self.subTest(url=url):
                with self.assertRaises(UnsafeUrl):
                    validate_remote_url(url)


class AtomicJsonTests(unittest.TestCase):
    def test_replaces_the_target_with_complete_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested" / "receipt.json"

            atomic_write_json(target, {"title": "Äpfel", "complete": True})

            self.assertEqual(target.read_text(), '{\n  "title": "Äpfel",\n  "complete": true\n}\n')
            self.assertFalse(target.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
