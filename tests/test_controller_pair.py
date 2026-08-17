import os
import subprocess
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAIR_SCRIPT = ROOT / "bin" / "pair-controller"

FAKE_BLUETOOTHCTL = r"""#!/usr/bin/env bash
set -euo pipefail

args="$*"
mode="${FAKE_BLUETOOTH_MODE:?}"
state="${FAKE_BLUETOOTH_STATE:?}"
address="${!#}"

case "$args" in
  *" list")
    printf 'Controller AA:BB:CC:DD:EE:FF Pi [default]\n'
    ;;
  *" show")
    printf 'Controller AA:BB:CC:DD:EE:FF\n\tPowered: yes\n'
    ;;
  *" devices")
    case "$mode" in
      multiple)
        printf 'Device 11:22:33:44:55:66 8BitDo Pro 2\n'
        printf 'Device 22:33:44:55:66:77 Xbox Wireless Controller\n'
        ;;
      *)
        printf 'Device 11:22:33:44:55:66 8BitDo Pro 2\n'
        ;;
    esac
    ;;
  *" info "*)
    printf 'Device %s\n\tName: Game Controller\n\tIcon: input-gaming\n' "$address"
    if [[ "$mode" == known ]]; then
      printf '\tPaired: yes\n'
    elif [[ -e "$state" ]]; then
      printf '\tPaired: yes\n'
    else
      printf '\tPaired: no\n'
    fi
    if [[ -e "$state" ]]; then
      printf '\tConnected: yes\n'
    else
      printf '\tConnected: no\n'
    fi
    ;;
  *" connect "*|*" pair "*)
    : >"$state"
    ;;
  *" trust "*|*" scan "*|*" power on")
    ;;
  *)
    printf 'unexpected bluetoothctl call: %s\n' "$args" >&2
    exit 2
    ;;
esac
"""


def run_pairing(tmp_path: Path, mode: str) -> subprocess.CompletedProcess[str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    bluetoothctl = fake_bin / "bluetoothctl"
    bluetoothctl.write_text(FAKE_BLUETOOTHCTL)
    bluetoothctl.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "BLUETOOTH_SCAN_SECONDS": "1",
            "FAKE_BLUETOOTH_MODE": mode,
            "FAKE_BLUETOOTH_STATE": str(tmp_path / "connected"),
        }
    )
    return subprocess.run(PAIR_SCRIPT, capture_output=True, text=True, env=env, timeout=5, check=False)


class ControllerPairingTests(unittest.TestCase):
    def test_reconnects_known_controller_without_pairing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_pairing(Path(directory), "known")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout.splitlines(),
            ["connected", "Controller verbunden: 8BitDo Pro 2"],
        )

    def test_pairs_exactly_one_new_controller(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_pairing(Path(directory), "new")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout.splitlines(),
            ["connected", "Controller verbunden: 8BitDo Pro 2"],
        )

    def test_refuses_ambiguous_new_controllers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_pairing(Path(directory), "multiple")

        self.assertEqual(result.returncode, 1)
        self.assertIn("Mehrere neue Controller gefunden", result.stderr)


if __name__ == "__main__":
    unittest.main()
