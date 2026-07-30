# KonsolenDocker

Pegasus Frontend und Emulatoren für den Raspberry Pi 5. Pegasus läuft in
Docker auf dem HDMI-Fernseher; die StorchCam bleibt auf dem DSI-Display.
Spiele, BIOS-Dateien, Spielstände und Konfiguration liegen unabhängig vom
Container unter `/home/fero/Games`.

## V1-Systeme

| Ordner | System | Emulator |
|---|---|---|
| `arcade` | Arcade | MAME |
| `atari2600` | Atari 2600 | Stella |
| `nes` | Nintendo Entertainment System | Nestopia |
| `snes` | Super Nintendo | Snes9x |
| `gb`, `gbc` | Game Boy / Game Boy Color | Gambatte |
| `gba` | Game Boy Advance | mGBA |
| `sg1000`, `mastersystem`, `gamegear`, `megadrive`, `segacd` | Sega-Klassiker | Genesis Plus GX |
| `pcengine` | PC Engine / TurboGrafx-16 und CD | Mednafen |
| `ps1` | PlayStation 1 | PCSX-ReARMed |

Neuere Systeme wie N64, Saturn, Dreamcast und PS2 sind bewusst nicht Teil
von V1.

## Installation auf dem Pi

Voraussetzungen: Docker Engine mit Compose-Plugin, `xrandr` aus
`x11-xserver-utils`, Zugriff des Benutzers `fero` auf Docker sowie eine
laufende grafische X11-Sitzung.

```bash
git clone https://github.com/Fero737373/KonsolenDocker.git \
  /home/fero/KonsolenDocker
cd /home/fero/KonsolenDocker
./bin/setup
```

`setup` erzeugt die Ordnerstruktur in `/home/fero/Games`, erkennt DSI,
X11-Berechtigung und Geräte-Gruppen und baut das Image. HDMI wird übernommen,
wenn es dabei bereits verbunden ist; der Start prüft es in jedem Fall erneut.
Es werden keine ROMs oder BIOS-Dateien mitgeliefert.

Anschließend:

```bash
./bin/console-control start
./bin/console-control status
./bin/console-control stop
```

`start` aktiviert ausschließlich einen verbundenen HDMI-Ausgang und setzt
ihn für Pegasus auf „primary“. Ohne erkannten HDMI-Ausgang startet der
Container nicht. `stop` beendet ihn, schaltet HDMI wieder ab und setzt DSI auf
„primary“.

## Spiele und BIOS

ROMs kommen in den passenden Unterordner:

```text
/home/fero/Games/
├── bios/
├── roms/
│   ├── arcade/
│   ├── atari2600/
│   ├── nes/
│   ├── snes/
│   ├── gb/
│   ├── gbc/
│   ├── gba/
│   ├── sg1000/
│   ├── mastersystem/
│   ├── gamegear/
│   ├── megadrive/
│   ├── segacd/
│   ├── pcengine/
│   └── ps1/
├── saves/
├── states/
├── config/
└── cache/
```

Für Disc-Systeme möglichst `.cue`, `.chd` oder `.m3u` verwenden. Benötigte
BIOS-Dateien müssen aus eigenen, legalen Quellen in `bios/` abgelegt werden.
Die PS1-BIOS-Suche folgt dabei den Dateinamen des PCSX-ReARMed-Cores.

## Noch unbekannte Bildschirm-/Audio-Daten

Vor der ersten Inbetriebnahme kann die Diagnose gespeichert werden:

```bash
./bin/diagnose | tee diagnose.txt
```

Falls die automatische Erkennung nicht passt, lassen sich in `.env`
`HDMI_OUTPUT`, `DSI_OUTPUT`, `DISPLAY` und `XAUTHORITY` korrigieren. Das
Standard-Audioziel ist ALSA; die Diagnose zeigt, ob am Pi noch ein explizites
HDMI-Gerät gewählt werden muss.
