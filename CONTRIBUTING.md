# Beitragen zu KonsolenDocker

Dieses Projekt behandelt Lesbarkeit, Sicherheit und Testbarkeit als
Funktionsanforderungen. Die Regeln gelten für Python, QML, Shell, Docker und
Dokumentation.

## Entwurfsregeln

- Namen beschreiben Absicht und Domänenbegriff. Abkürzungen und generische Namen
  wie `data`, `manager` oder `helper` sind nur zulässig, wenn der Kontext sie
  eindeutig macht.
- Eine Funktion erledigt eine Aufgabe auf einer Abstraktionsebene. Wenn eine
  Beschreibung ein „und“ benötigt, wird geprüft, ob zwei Funktionen gemeint
  sind.
- Module besitzen einen klaren Änderungsgrund. Katalogquellen, Netzwerkgrenze,
  Coverauflösung, Downloadsteuerung, Installation und Pegasus-Metadaten bleiben
  voneinander getrennt.
- Seiteneffekte sind an den Rändern sichtbar. Dateisystem- und Netzwerkzugriffe
  werden über kleine Adapter geführt und in Tests durch Fakes ersetzt.
- Fehler werden als konkrete Ausnahmen weitergereicht und einmal an der API-
  Grenze in eine verständliche Meldung übersetzt. Teilzustände sind kein
  gültiges Ergebnis.
- Wiederholung wird entfernt, ohne unterschiedliche Domänenbegriffe künstlich
  zusammenzufassen. Ein kleiner, klarer Duplikatblock ist besser als eine
  undurchsichtige Universalabstraktion.
- Kommentare erklären Entscheidungen, Risiken oder nicht offensichtliche
  Randbedingungen. Sie wiederholen nicht den Code.

## UI-Regeln

- Neue Pegasus-Ansichten verwenden die bestehende Grid-Theme-Sprache:
  `globalFonts.sans`, vorhandene Abstände, Fokusanimation und die Farben
  `#111`, `#222`, `#0074da`, `#4ae`, `#ff4035` und `#eee`.
- Controller-Bedienung ist der primäre Pfad. Mausunterstützung darf sie ergänzen,
  aber niemals vorausgesetzt werden.
- Controllerlogik, Zustandsdarstellung, Grid, Informationspanel und Dialog
  bleiben getrennte QML-Komponenten.
- Neue visuelle Muster benötigen einen begründeten Designentscheid. Ein ROM
  Store darf nicht wie eine eingebettete Fremdanwendung wirken.

## Sicherheitsregeln

- ROM-Quellen müssen freie Weitergabe ausdrücklich erlauben. Kommerzielle ROM-
  Archive, Scraper und unklare Spiegel werden nicht integriert.
- Netzwerkzugriff erfolgt nur über HTTPS und die zentrale exakte Host-Allowlist.
  Jede Weiterleitung wird erneut geprüft.
- API-Keys gehören ausschließlich in eine lokale Secret-Datei; niemals in
  `.env`, Logs, Commits, Images, URLs oder Testdaten.
- Downloads erhalten Größenlimits. Wo die Quelle eine Prüfsumme liefert, ist
  deren Prüfung verpflichtend.
- Installationen sind atomar: erst Inhalt, Cover und Receipt vollständig in
  einem Staging-Ordner aufbauen, dann veröffentlichen. Fehler müssen aufräumen.
- Archivpfade, Symlinks, Kompressionsverhältnis und startbare Dateiendung werden
  vor der Veröffentlichung geprüft.

## Tests

Tests folgen dem Muster **Aufbauen – Ausführen – Prüfen** und prüfen Verhalten
statt Implementierungsdetails. Namen beschreiben Szenario und erwartetes
Ergebnis.

Vor jedem Commit läuft:

```bash
./bin/test
```

Der Befehl kompiliert alle Python-Module, führt die Standardbibliothek-Tests aus,
prüft Shell-Syntax und beendet sich bei Whitespace-Fehlern. Neue Fehlerfälle
erhalten nach Möglichkeit zuerst einen reproduzierenden Test. Externe APIs
werden in Unit-Tests nicht kontaktiert.

## Review-Checkliste

- Ist jede Änderung für das gewünschte Verhalten notwendig?
- Sind Namen, Verantwortlichkeiten und Fehlerpfade ohne Zusatzwissen verständlich?
- Bleiben Geheimnisse, Netzwerk und Dateisystem an klaren Grenzen?
- Ist ein abgebrochener Vorgang vollständig wiederholbar?
- Bleibt die Pegasus-Oberfläche visuell und per Controller konsistent?
- Decken Tests Erfolgsfall, relevante Grenzfälle und Rückabwicklung ab?
- Funktioniert Installation weiterhin mit `git pull && ./bin/setup`?
