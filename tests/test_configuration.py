import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def configured_project(directory: Path) -> tuple[Path, Path]:
    bin_dir = directory / "bin"
    bin_dir.mkdir()
    script = bin_dir / "configure-romstore"
    shutil.copy2(ROOT / "bin" / "configure-romstore", script)
    environment_file = directory / ".env"
    environment_file.write_text("HOST_UID=1000\nTHEGAMESDB_API_KEY=old-key\n")
    return script, environment_file


class RomStoreConfigurationTests(unittest.TestCase):
    def test_replaces_the_key_without_printing_it_and_protects_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            script, environment_file = configured_project(Path(directory))
            environment = os.environ.copy()
            environment["THEGAMESDB_API_KEY"] = "new-secret-key"

            result = subprocess.run(
                ["bash", script, "--quiet"],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("THEGAMESDB_API_KEY=new-secret-key", environment_file.read_text())
            self.assertNotIn("old-key", environment_file.read_text())
            self.assertNotIn("new-secret-key", result.stdout + result.stderr)
            self.assertEqual(stat.S_IMODE(environment_file.stat().st_mode), 0o600)

    def test_rejects_keys_with_shell_metacharacters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            script, environment_file = configured_project(Path(directory))
            original = environment_file.read_text()
            environment = os.environ.copy()
            environment["THEGAMESDB_API_KEY"] = "bad;key"

            result = subprocess.run(
                ["bash", script, "--quiet"],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(environment_file.read_text(), original)


if __name__ == "__main__":
    unittest.main()
