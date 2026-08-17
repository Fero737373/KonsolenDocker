import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from romstore.server import load_thegamesdb_api_key


ROOT = Path(__file__).resolve().parents[1]


def configured_project(directory: Path) -> tuple[Path, Path, Path]:
    bin_dir = directory / "bin"
    bin_dir.mkdir()
    script = bin_dir / "configure-romstore"
    shutil.copy2(ROOT / "bin" / "configure-romstore", script)
    environment_file = directory / ".env"
    environment_file.write_text("HOST_UID=1000\nTHEGAMESDB_API_KEY=old-key\n")
    secret_file = directory / ".runtime" / "thegamesdb-api-key"
    return script, environment_file, secret_file


class RomStoreConfigurationTests(unittest.TestCase):
    def test_replaces_the_key_without_printing_it_and_protects_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            script, environment_file, secret_file = configured_project(Path(directory))
            environment = os.environ.copy()
            environment["THEGAMESDB_API_KEY"] = "new+secret/key==$literal;value"

            result = subprocess.run(
                ["bash", script, "--quiet"],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("THEGAMESDB_API_KEY", environment_file.read_text())
            self.assertEqual(secret_file.read_text(), "new+secret/key==$literal;value")
            self.assertNotIn("old-key", result.stdout + result.stderr)
            self.assertNotIn("new+secret/key", result.stdout + result.stderr)
            self.assertEqual(stat.S_IMODE(environment_file.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(secret_file.stat().st_mode), 0o600)

    def test_removes_a_trailing_carriage_return_from_pasted_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            script, _, secret_file = configured_project(Path(directory))
            environment = os.environ.copy()
            environment["THEGAMESDB_API_KEY"] = "pasted-key\r"

            result = subprocess.run(
                ["bash", script, "--quiet"],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(secret_file.read_text(), "pasted-key")

    def test_rejects_multiline_keys_without_modifying_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            script, environment_file, secret_file = configured_project(Path(directory))
            original = environment_file.read_text()
            environment = os.environ.copy()
            environment["THEGAMESDB_API_KEY"] = "bad\nkey"

            result = subprocess.run(
                ["bash", script, "--quiet"],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(environment_file.read_text(), original)
            self.assertFalse(secret_file.exists())

    def test_loads_thegamesdb_key_from_the_secret_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            secret_file = Path(directory) / "thegamesdb-api-key"
            secret_file.write_text("key+with/special=characters$")

            with patch.dict(
                os.environ,
                {"THEGAMESDB_API_KEY_FILE": str(secret_file)},
                clear=False,
            ):
                self.assertEqual(
                    load_thegamesdb_api_key(),
                    "key+with/special=characters$",
                )


if __name__ == "__main__":
    unittest.main()
