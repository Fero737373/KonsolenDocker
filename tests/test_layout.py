import json
import re
import subprocess
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


class ProjectLayoutTests(unittest.TestCase):
    def test_every_system_has_valid_metadata(self) -> None:
        files = {
            path.name.removesuffix(".pegasus.txt")
            for path in (ROOT / "metadata").glob("*.pegasus.txt")
        }
        self.assertEqual(files, SYSTEMS)

        for system in SYSTEMS:
            with self.subTest(system=system):
                content = (ROOT / "metadata" / f"{system}.pegasus.txt").read_text()
                self.assertIn("collection:", content)
                self.assertIn("extension:", content)
                self.assertIn("launch:", content)
                self.assertIn('"{file.path}"', content)

    def test_ps1_accepts_public_domain_executables(self) -> None:
        metadata = (ROOT / "metadata" / "ps1.pegasus.txt").read_text()
        extension_line = next(
            line for line in metadata.splitlines() if line.startswith("extension:")
        )

        self.assertIn("exe", extension_line)

    def test_compose_isolates_pegasus_from_the_internet(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text()

        self.assertIn("${GAMES_DIR:?Run ./bin/setup}:/games:rw", compose)
        self.assertIn("console-internal:\n    internal: true", compose)
        self.assertIn("romstore-egress:", compose)
        self.assertNotIn("network_mode: none", compose)
        self.assertGreaterEqual(compose.count("no-new-privileges:true"), 2)
        self.assertIn("read_only: true", compose)
        self.assertIn("cap_drop:\n      - ALL", compose)

    def test_theme_keeps_the_native_pegasus_visual_language(self) -> None:
        theme_files = list((ROOT / "pegasus-theme").rglob("*.qml"))
        combined = "\n".join(path.read_text() for path in theme_files)

        self.assertEqual(len(theme_files), 6)
        for native_color in ("#111", "#222", "#0074da", "#4ae", "#ff4035", "#eee"):
            with self.subTest(color=native_color):
                self.assertIn(native_color, combined)
        self.assertIn("globalFonts.sans", combined)
        self.assertIn("scale: 1.20", combined)
        self.assertIn('import "layer_romstore"', (ROOT / "pegasus-theme" / "theme.qml").read_text())

    def test_all_rom_store_components_are_bundled(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text()

        for component in (ROOT / "pegasus-theme" / "layer_romstore").glob("*.qml"):
            with self.subTest(component=component.name):
                self.assertIn(component.name, dockerfile)

    def test_sources_are_pinned(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text()
        manifest = (ROOT / "romstore" / "libretro_manifest.json").read_text()
        homebrew_manifest = json.loads(
            (ROOT / "romstore" / "homebrew_manifest.json").read_text()
        )
        workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text()

        self.assertIn("PEGASUS_REF=6b322063a036db60cba5810fda82a3ce38f1e62f", dockerfile)
        self.assertIn("PCSX_REARMED_REF=94f15b3a6b707070aeb0c58cab9bc4eddc1706ff", dockerfile)
        self.assertIn('"ref": "8bd0ddf57bc487edd3e45ddb53dea849a9e8e4a8"', manifest)
        self.assertTrue(
            all(
                re.fullmatch(r"[0-9a-f]{40}", ref)
                for ref in homebrew_manifest["repository_refs"].values()
            )
        )
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", workflow)

    def test_shell_scripts_have_valid_syntax(self) -> None:
        scripts = sorted((ROOT / "bin").iterdir()) + sorted((ROOT / "docker").iterdir())

        for script in scripts:
            if script.is_file() and script.read_bytes().startswith(b"#!/"):
                with self.subTest(script=script.name):
                    subprocess.run(["bash", "-n", script], check=True)

    def test_console_control_exposes_safe_bluetooth_pairing(self) -> None:
        control = (ROOT / "bin" / "console-control").read_text()
        pairing = (ROOT / "bin" / "pair-controller").read_text()

        self.assertIn("start|stop|toggle|bluetooth", control)
        self.assertIn("--agent NoInputNoOutput", pairing)
        self.assertIn("Mehrere neue Controller gefunden", pairing)


if __name__ == "__main__":
    unittest.main()
