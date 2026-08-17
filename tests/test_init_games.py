import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYSTEMS = {
    "arcade",
    "atari2600",
    "nes",
    "snes",
    "gb",
    "gbc",
    "gba",
    "sg1000",
    "mastersystem",
    "gamegear",
    "megadrive",
    "segacd",
    "pcengine",
    "ps1",
}


def run_init_games(games_dir: Path) -> None:
    environment = os.environ.copy()
    environment["GAMES_DIR"] = str(games_dir)
    subprocess.run(
        ["bash", str(ROOT / "bin" / "init-games")],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


class InitGamesTests(unittest.TestCase):
    def test_creates_a_native_download_entry_for_every_console(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            games_dir = Path(directory)
            run_init_games(games_dir)

            for system in SYSTEMS:
                with self.subTest(system=system):
                    system_dir = games_dir / "roms" / system
                    metadata = (
                        system_dir / "konsolendocker-store.metadata.pegasus.txt"
                    ).read_text()
                    self.assertIn("game: Downloads", metadata)
                    self.assertIn(f"shortname: {system}", metadata)
                    self.assertIn("x-romstore: true", metadata)
                    self.assertTrue(
                        (system_dir / ".konsolendocker" / "downloads.kdstore").is_file()
                    )
                    self.assertTrue(
                        (system_dir / ".konsolendocker" / "downloads.svg").is_file()
                    )

    def test_preserves_existing_console_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            games_dir = Path(directory)
            nes_dir = games_dir / "roms" / "nes"
            nes_dir.mkdir(parents=True)
            existing_metadata = nes_dir / "metadata.pegasus.txt"
            existing_metadata.write_text("collection: Eigene NES Sammlung\n")
            run_init_games(games_dir)

            self.assertEqual(
                existing_metadata.read_text(), "collection: Eigene NES Sammlung\n"
            )


if __name__ == "__main__":
    unittest.main()
