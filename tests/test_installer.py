from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from romstore.installer import InstallCallbacks, ItemInstaller
from romstore.models import CatalogItem
from romstore.security import DownloadCancelled


class InMemoryDownloadClient:
    def __init__(self, content: bytes):
        self.content = content

    def download(self, request) -> tuple[int, str]:  # noqa: ANN001
        request.target.write(self.content)
        request.on_progress(len(self.content), len(self.content), 4096.0)
        return len(self.content), "application/octet-stream"


class FixtureCoverService:
    def materialize(self, item: CatalogItem, directory: Path) -> str:
        filename = "cover.png"
        (directory / filename).write_bytes(b"png")
        return filename


def callbacks() -> InstallCallbacks:
    return InstallCallbacks(
        download_started=lambda: None,
        download_progressed=lambda received, total, speed: None,
        installation_started=lambda: None,
        is_cancelled=lambda: False,
    )


def catalog_item(content: bytes, *, checksum: str | None = None) -> CatalogItem:
    return CatalogItem(
        provider="Test Catalog",
        system="nes",
        title="Clean Homebrew",
        kind="Spiel",
        download_url="https://raw.githubusercontent.com/example/project/HEAD/game.nes",
        filename="game.nes",
        source_url="https://github.com/example/project",
        description="A legal test fixture.",
        developer="Fixture Author",
        license="Public Domain",
        size=len(content),
        sha256=checksum if checksum is not None else sha256(content).hexdigest(),
    )


class ItemInstallerTests(unittest.TestCase):
    def test_installs_rom_cover_receipt_and_pegasus_metadata_as_one_unit(self) -> None:
        content = b"NES\x1a clean test ROM"
        with tempfile.TemporaryDirectory() as directory:
            games_dir = Path(directory)
            item = catalog_item(content)
            installer = ItemInstaller(
                games_dir,
                FixtureCoverService(),
                http=InMemoryDownloadClient(content),
                max_download_bytes=1024,
            )

            installer.install(item, callbacks())

            destination = item.install_dir(games_dir)
            receipt = json.loads((destination / "receipt.json").read_text())
            metadata = (
                games_dir
                / "config/pegasus-frontend/metafiles/romstore-nes.metadata.pegasus.txt"
            ).read_text()
            self.assertEqual((destination / "game.nes").read_bytes(), content)
            self.assertEqual((destination / "cover.png").read_bytes(), b"png")
            self.assertEqual(receipt["catalog_id"], item.id)
            self.assertEqual(receipt["download_sha256"], sha256(content).hexdigest())
            self.assertIn(f"file: {destination / 'game.nes'}", metadata)
            self.assertIn(f"assets.box_front: {destination / 'cover.png'}", metadata)

    def test_checksum_failure_leaves_no_partial_installation(self) -> None:
        content = b"unexpected content"
        with tempfile.TemporaryDirectory() as directory:
            games_dir = Path(directory)
            item = catalog_item(content, checksum="0" * 64)
            installer = ItemInstaller(
                games_dir,
                FixtureCoverService(),
                http=InMemoryDownloadClient(content),
                max_download_bytes=1024,
            )

            with self.assertRaisesRegex(IOError, "Prüfsumme"):
                installer.install(item, callbacks())

            destination = item.install_dir(games_dir)
            self.assertFalse(destination.exists())
            self.assertEqual(list(destination.parent.glob(".*.staging-*")), [])

    def test_cancellation_before_installation_leaves_no_partial_files(self) -> None:
        content = b"NES\x1a cancelled test ROM"
        cancelled = False

        def cancel_installation() -> None:
            nonlocal cancelled
            cancelled = True

        install_callbacks = InstallCallbacks(
            download_started=lambda: None,
            download_progressed=lambda received, total, speed: None,
            installation_started=cancel_installation,
            is_cancelled=lambda: cancelled,
        )
        with tempfile.TemporaryDirectory() as directory:
            games_dir = Path(directory)
            item = catalog_item(content)
            installer = ItemInstaller(
                games_dir,
                FixtureCoverService(),
                http=InMemoryDownloadClient(content),
                max_download_bytes=1024,
            )

            with self.assertRaises(DownloadCancelled):
                installer.install(item, install_callbacks)

            destination = item.install_dir(games_dir)
            self.assertFalse(destination.exists())
            self.assertEqual(list(destination.parent.glob(".*.staging-*")), [])

    def test_rejects_control_characters_in_download_filenames(self) -> None:
        content = b"NES\x1a invalid filename"
        with tempfile.TemporaryDirectory() as directory:
            games_dir = Path(directory)
            item = replace(catalog_item(content), filename="invalid\nname.nes")
            installer = ItemInstaller(
                games_dir,
                FixtureCoverService(),
                http=InMemoryDownloadClient(content),
                max_download_bytes=1024,
            )

            with self.assertRaisesRegex(ValueError, "Dateiname"):
                installer.install(item, callbacks())

            self.assertFalse(item.install_dir(games_dir).exists())


if __name__ == "__main__":
    unittest.main()
