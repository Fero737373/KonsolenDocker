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


def test_every_system_has_valid_metadata() -> None:
    files = {path.name.removesuffix(".pegasus.txt") for path in (ROOT / "metadata").glob("*.pegasus.txt")}
    assert files == SYSTEMS

    for system in SYSTEMS:
        content = (ROOT / "metadata" / f"{system}.pegasus.txt").read_text()
        assert "collection:" in content
        assert "extension:" in content
        assert 'launch:' in content
        assert '"{file.path}"' in content


def test_compose_keeps_games_external() -> None:
    compose = (ROOT / "docker-compose.yml").read_text()
    assert "${GAMES_DIR:?Run ./bin/setup}:/games:rw" in compose
    assert "network_mode: none" in compose
    assert "no-new-privileges:true" in compose


def test_sources_are_pinned() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "PEGASUS_REF=6b322063a036db60cba5810fda82a3ce38f1e62f" in dockerfile
    assert "PCSX_REARMED_REF=94f15b3a6b707070aeb0c58cab9bc4eddc1706ff" in dockerfile
