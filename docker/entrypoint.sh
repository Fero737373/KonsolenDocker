#!/usr/bin/env bash
set -euo pipefail

runtime_dir="${XDG_RUNTIME_DIR:-/tmp/runtime-$(id -u)}"
install -d -m 0700 "$runtime_dir"
export XDG_RUNTIME_DIR="$runtime_dir"

mkdir -p \
  "$HOME" \
  "$XDG_CACHE_HOME" \
  "$XDG_CONFIG_HOME/pegasus-frontend" \
  "$XDG_CONFIG_HOME/retroarch" \
  /games/bios \
  /games/saves \
  /games/states

# Das Container-Image ist die Quelle der Wahrheit. Dadurch bleiben keine alten
# RetroArch-Werte für Controller oder Audio aus früheren Builds aktiv.
retroarch_config="$XDG_CONFIG_HOME/retroarch/retroarch.cfg"
install -m 0644 /opt/konsolen/retroarch.cfg "$retroarch_config"

# Raspberry Pi stellt mehrere ALSA-Karten bereit. Bevorzugt wird der erste
# HDMI/MAI-Wiedergabeausgang; andernfalls der erste verfügbare Playback-Port.
audio_endpoint=""
if [[ -r /proc/asound/pcm ]]; then
  audio_endpoint="$(awk -F: '
    /playback/ && tolower($0) ~ /(hdmi|vc4|mai)/ { gsub(/[[:space:]]/, "", $1); print $1; exit }
  ' /proc/asound/pcm)"
  if [[ -z "$audio_endpoint" ]]; then
    audio_endpoint="$(awk -F: '
      /playback/ { gsub(/[[:space:]]/, "", $1); print $1; exit }
    ' /proc/asound/pcm)"
  fi
fi

if [[ "$audio_endpoint" =~ ^([0-9]+)-([0-9]+)$ ]]; then
  card="$((10#${BASH_REMATCH[1]}))"
  device="$((10#${BASH_REMATCH[2]}))"
  cat >"$HOME/.asoundrc" <<EOF
pcm.!default {
  type plug
  slave.pcm "hw:${card},${device}"
}
ctl.!default {
  type hw
  card ${card}
}
EOF
fi

pegasus_config="$XDG_CONFIG_HOME/pegasus-frontend"
game_dirs="$pegasus_config/game_dirs.txt"
find /games/roms -mindepth 1 -maxdepth 1 -type d -print \
  | LC_ALL=C sort >"$game_dirs"

settings="$pegasus_config/settings.txt"
if [[ ! -e "$settings" ]]; then
  {
    printf '%s\n' \
      'general.fullscreen: true' \
      'general.locale: de' \
      'general.scan-on-launch: true' \
      'general.input-mouse-support: false'
  } >"$settings"
fi

exec /usr/local/bin/pegasus-fe \
  --kiosk \
  --silent
