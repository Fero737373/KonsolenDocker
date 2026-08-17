# KonsolenDocker

Pegasus Frontend und Emulatoren für den Raspberry Pi 5. Pegasus läuft in
Docker auf dem HDMI-Fernseher; die StorchCam bleibt auf dem DSI-Display.
Spiele, BIOS-Dateien, Spielstände und Konfiguration liegen unabhängig vom
Container unter `/home/fero/Games`.

Der integrierte ROM Store zeigt ausschließlich frei weitergebbare Homebrew-,
Public-Domain-, Demo-, Test- und Utility-Inhalte direkt in der jeweiligen
Pegasus-Konsole an. Download, Cover und Metadaten werden gemeinsam installiert.

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
laufende grafische X11-Sitzung. Für den Bluetooth-Button muss zusätzlich
BlueZ mit `bluetoothctl` installiert und der Dienst `bluetooth` aktiv sein.

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

Bei der Einrichtung fragt `setup` optional und verdeckt nach dem TheGamesDB-
API-Key. Der Key wird nur lokal in `.env` mit Dateirechten `0600` gespeichert,
nicht in ein Image eingebaut und nicht in Git aufgenommen. Ohne Key funktionieren
Quellen-Cover und automatisch erzeugte Platzhalter weiterhin.

Nach späteren Aktualisierungen genügt:

```bash
git pull
./bin/setup
```

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

## ROM Store in Pegasus

1. Im Pegasus-Hauptbildschirm eine Konsole auswählen.
2. Die Filter-/`Y`-Taste drücken. Der Download-Katalog öffnet sich innerhalb
   dieser Konsole im bestehenden Pegasus-Grid-Design.
3. Mit dem Steuerkreuz einen Inhalt wählen und mit `A` laden. `X` aktualisiert
   den Katalog live über die offiziellen APIs.
4. Der Dialog zeigt Fortschritt, Datenmenge und Geschwindigkeit. `B` bricht
   einen laufenden Download ab oder schließt einen fertigen Dialog.

Die bisherigen Pegasus-Filter bleiben über `X` (Details) und anschließend `Y`
erreichbar.

Nach erfolgreicher Installation lädt Pegasus seine Datenquellen neu. ROM und
Cover erscheinen dadurch direkt in derselben Konsolensammlung. Installationen
liegen getrennt unter:

```text
/home/fero/Games/roms/<system>/romstore/<titel-id>/
```

Der Katalog verbindet zwei explizite Quellen:

- **[Homebrew Hub](https://hh.gbdev.io/)** für GB, GBC, GBA und NES. Die
  [offizielle API](https://github.com/gbdev/homebrewhub/blob/main/API.md) ist
  die Quelle; Hack-ROM-Einträge werden bewusst ausgeschlossen.
- **[Libretro Content](https://github.com/libretro/libretro-content)** für die
  unterstützten V1-Systeme. Spiele, Demos, Tests und Utilities bleiben sichtbar.
  Ein gepinnter Katalog-Snapshot dient als Fallback, falls die anonyme GitHub-API
  gerade nicht erreichbar ist.

**[TheGamesDB](https://api.thegamesdb.net/) liefert nur Cover-Metadaten und
niemals ROM-Dateien.** Gibt weder eine Quelle noch TheGamesDB ein Cover zurück,
erzeugt der Store ein neutrales Platzhalter-Cover. Romifleur/Myrient wurde nicht
angebunden, weil es keine stabile, rechtmäßige ROM-API für diesen Zweck
bereitstellt.

Die lokale API ist nur im internen Docker-Netz erreichbar. Pegasus selbst hat
keinen Internetzugang; nur der eingeschränkte `romstore`-Dienst besitzt Egress.
Er akzeptiert ausschließlich HTTPS-Ziele auf einer festen Host-Allowlist,
prüft Weiterleitungen, Größen und vorhandene SHA-256-Werte und installiert über
einen temporären Ordner. ZIP-Pfadtraversierung, Symlinks und auffällige
Kompressionsverhältnisse werden abgewiesen.

## Bluetooth-Controller

Setze genau einen neuen Controller in den Pairing-Modus und starte dann die
Kopplung über den StorchCam-Button oder direkt auf dem Pi:

```bash
./bin/console-control bluetooth
```

Bereits gekoppelte Controller werden zuerst wieder verbunden. Ein neuer
Controller wird nur automatisch ausgewählt, wenn genau ein passendes Gamepad
gefunden wurde. Nach erfolgreicher Kopplung wird das Gerät von BlueZ als
vertrauenswürdig gespeichert und verbindet sich künftig automatisch.

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

## Cover in Pegasus

Pegasus erkennt Cover ohne zusätzliche Metadaten, wenn sie unter
`media/<ROM-Dateiname ohne Endung>/boxFront.jpg` oder `boxFront.png` liegen.
Für `Super Mario World (Europe).sfc` ist der vollständige Pfad:

```text
/home/fero/Games/roms/snes/media/Super Mario World (Europe)/boxFront.jpg
```

Alternativ kann ein Cover in `metadata.pegasus.txt` einem Spiel ausdrücklich
zugeordnet werden:

```text
game: Super Mario World (Europe)
file: Super Mario World (Europe).sfc
assets.box_front: media/Super Mario World (Europe)/boxFront.jpg
```

Nach Änderungen die Konsole einmal beenden und neu starten, damit Pegasus die
Bibliothek und Medien erneut einliest.

## Entwicklung und Tests

Der gesamte lokale Testlauf hat genau einen Einstiegspunkt und benötigt keine
zusätzlichen Python-Pakete:

```bash
./bin/test
```

Die verbindlichen Qualitätsregeln und Review-Kriterien stehen in
[`CONTRIBUTING.md`](CONTRIBUTING.md). Sie übertragen die im Projekt geforderten
Clean-Code-Prinzipien auf Python, QML, Shell und Container-Konfiguration.

## Noch unbekannte Bildschirm-/Audio-Daten

Vor der ersten Inbetriebnahme kann die Diagnose gespeichert werden:

```bash
./bin/diagnose | tee diagnose.txt
```

Falls die automatische Erkennung nicht passt, lassen sich in `.env`
`HDMI_OUTPUT`, `DSI_OUTPUT`, `DISPLAY` und `XAUTHORITY` korrigieren. Das
Standard-Audioziel ist ALSA; die Diagnose zeigt, ob am Pi noch ein explizites
HDMI-Gerät gewählt werden muss.
