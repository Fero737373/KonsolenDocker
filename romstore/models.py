from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import re
import unicodedata


SUPPORTED_SYSTEMS = {
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

SYSTEM_COLLECTIONS = {
    "arcade": "Arcade",
    "atari2600": "Atari 2600",
    "nes": "Nintendo Entertainment System",
    "snes": "Super Nintendo",
    "gb": "Game Boy",
    "gbc": "Game Boy Color",
    "gba": "Game Boy Advance",
    "sg1000": "Sega SG-1000",
    "mastersystem": "Sega Master System",
    "gamegear": "Sega Game Gear",
    "megadrive": "Sega Mega Drive",
    "segacd": "Sega Mega-CD",
    "pcengine": "PC Engine und TurboGrafx-16",
    "ps1": "Sony PlayStation",
}

SYSTEM_EXTENSIONS = {
    "arcade": {"zip", "7z"},
    "atari2600": {"a26", "bin", "rom", "zip", "7z"},
    "nes": {"nes", "fds", "zip", "7z"},
    "snes": {"smc", "sfc", "fig", "bs", "zip", "7z"},
    "gb": {"gb", "zip", "7z"},
    "gbc": {"gbc", "zip", "7z"},
    "gba": {"gba", "zip", "7z"},
    "sg1000": {"sg", "sc", "bin", "zip", "7z"},
    "mastersystem": {"sms", "bin", "zip", "7z"},
    "gamegear": {"gg", "bin", "zip", "7z"},
    "megadrive": {"md", "gen", "bin", "smd", "zip", "7z"},
    "segacd": {"cue", "chd", "iso", "zip"},
    "pcengine": {"pce", "sgx", "cue", "chd", "zip"},
    "ps1": {"cue", "chd", "pbp", "m3u", "ccd", "iso", "exe", "zip"},
}


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def safe_name(value: str, fallback: str = "download") -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^A-Za-z0-9._ -]+", "", value).strip(" .")
    value = re.sub(r"\s+", " ", value)
    return value[:120] or fallback


@dataclass(frozen=True, slots=True)
class CatalogItem:
    provider: str
    system: str
    title: str
    kind: str
    download_url: str
    filename: str
    source_url: str
    description: str = ""
    developer: str = ""
    license: str = ""
    cover_url: str = ""
    size: int | None = None
    sha256: str = ""

    @property
    def id(self) -> str:
        material = f"{self.provider}\0{self.system}\0{self.download_url}".encode()
        return sha256(material).hexdigest()[:24]

    def to_cache(self) -> dict:
        return asdict(self)

    @classmethod
    def from_cache(cls, data: dict) -> "CatalogItem":
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: data[key] for key in allowed if key in data})

    def to_public(self, *, installed: bool, api_base: str) -> dict:
        return {
            "id": self.id,
            "system": self.system,
            "title": self.title,
            "kind": self.kind,
            "source": self.provider,
            "source_url": self.source_url,
            "description": self.description,
            "developer": self.developer,
            "license": self.license,
            "size": self.size,
            "installed": installed,
            "cover": f"{api_base}/api/v1/cover?id={self.id}",
        }

    def install_dir(self, games_dir: Path) -> Path:
        slug = safe_name(self.title, self.system).replace(" ", "-").lower()
        return games_dir / "roms" / self.system / "romstore" / f"{slug}-{self.id[:8]}"
