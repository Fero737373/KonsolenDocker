from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

from romstore.archives import extract_safe_zip, prepare_primary_file


def write_zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


class ArchiveSafetyTests(unittest.TestCase):
    def test_extracts_a_valid_disc_archive_and_selects_the_cue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            staging = Path(directory)
            archive = staging / "game.zip"
            write_zip(archive, {"disc/game.bin": b"disc", "disc/game.cue": b"FILE game.bin"})

            primary = prepare_primary_file("ps1", archive, staging)

            self.assertEqual(primary.relative_to(staging).as_posix(), "content/disc/game.cue")
            self.assertFalse(archive.exists())

    def test_rejects_directory_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "unsafe.zip"
            target = root / "content"
            target.mkdir()
            write_zip(archive, {"../outside.nes": b"bad"})

            with self.assertRaisesRegex(ValueError, "Unsicherer Pfad"):
                extract_safe_zip(archive, target)

            self.assertFalse((root / "outside.nes").exists())

    def test_rejects_symbolic_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "unsafe.zip"
            target = root / "content"
            target.mkdir()
            link = zipfile.ZipInfo("link.nes")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr(link, "target.nes")

            with self.assertRaisesRegex(ValueError, "Symlinks"):
                extract_safe_zip(archive, target)

    def test_rejects_an_unsupported_download_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            downloaded = Path(directory) / "game.exe"
            downloaded.write_bytes(b"not a NES ROM")

            with self.assertRaisesRegex(ValueError, "passt nicht"):
                prepare_primary_file("nes", downloaded, Path(directory))


if __name__ == "__main__":
    unittest.main()
