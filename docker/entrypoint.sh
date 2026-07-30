#!/usr/bin/env bash
set -euo pipefail

mkdir -p \
  "$HOME" \
  "$XDG_CACHE_HOME" \
  "$XDG_CONFIG_HOME/pegasus-frontend" \
  "$XDG_CONFIG_HOME/retroarch" \
  /games/bios \
  /games/saves \
  /games/states

retroarch_config="$XDG_CONFIG_HOME/retroarch/retroarch.cfg"
if [[ ! -e "$retroarch_config" ]]; then
  install -m 0644 /opt/konsolen/retroarch.cfg "$retroarch_config"
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
  --silent \
  --no-menu-reboot \
  --no-menu-shutdown \
  --no-menu-suspend

