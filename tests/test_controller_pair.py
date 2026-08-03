import os
import subprocess
from pathlib import Path

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


def test_reconnects_known_controller_without_pairing(tmp_path: Path) -> None:
    result = run_pairing(tmp_path, "known")

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["connected", "Controller verbunden: 8BitDo Pro 2"]


def test_pairs_exactly_one_new_controller(tmp_path: Path) -> None:
    result = run_pairing(tmp_path, "new")

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["connected", "Controller verbunden: 8BitDo Pro 2"]


def test_refuses_ambiguous_new_controllers(tmp_path: Path) -> None:
    result = run_pairing(tmp_path, "multiple")

    assert result.returncode == 1
    assert "Mehrere neue Controller gefunden" in result.stderr
