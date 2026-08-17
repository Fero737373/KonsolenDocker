from __future__ import annotations

from pathlib import Path, PurePosixPath
import shutil
import zipfile

from .models import SYSTEM_EXTENSIONS


MAX_EXTRACTED_BYTES = 4 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
DISC_SYSTEMS = {"pcengine", "ps1", "segacd"}
PRIMARY_FILE_PRIORITIES = {
    "segacd": (".cue", ".chd", ".iso"),
    "pcengine": (".cue", ".chd", ".pce", ".sgx"),
    "ps1": (".cue", ".chd", ".pbp", ".m3u", ".ccd", ".iso", ".exe"),
}


def prepare_primary_file(system: str, downloaded_file: Path, staging_dir: Path) -> Path:
    requires_extraction = downloaded_file.suffix.lower() == ".zip" and system in DISC_SYSTEMS
    if not requires_extraction:
        _require_supported_extension(system, downloaded_file)
        return downloaded_file
    extracted_dir = staging_dir / "content"
    extracted_dir.mkdir()
    extract_safe_zip(downloaded_file, extracted_dir)
    downloaded_file.unlink()
    return _find_primary_file(system, extracted_dir)


def extract_safe_zip(archive: Path, target: Path) -> None:
    extracted_bytes = 0
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            if entry.is_dir():
                continue
            _require_safe_entry(entry)
            extracted_bytes += entry.file_size
            if extracted_bytes > MAX_EXTRACTED_BYTES:
                raise ValueError("Entpackter Inhalt überschreitet das Größenlimit.")
            output = target.joinpath(*PurePosixPath(entry.filename).parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            with source.open(entry) as input_file, output.open("xb") as output_file:
                shutil.copyfileobj(input_file, output_file, length=128 * 1024)


def _require_safe_entry(entry: zipfile.ZipInfo) -> None:
    path = PurePosixPath(entry.filename)
    unix_mode = entry.external_attr >> 16
    is_symbolic_link = unix_mode & 0o170000 == 0o120000
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Unsicherer Pfad im ZIP-Archiv.")
    if is_symbolic_link:
        raise ValueError("Symlinks in ZIP-Archiven sind nicht erlaubt.")
    if entry.compress_size and entry.file_size / entry.compress_size > MAX_COMPRESSION_RATIO:
        raise ValueError("Verdächtiges Kompressionsverhältnis im ZIP-Archiv.")


def _find_primary_file(system: str, extracted_dir: Path) -> Path:
    files = [path for path in extracted_dir.rglob("*") if path.is_file()]
    for suffix in PRIMARY_FILE_PRIORITIES[system]:
        if matching_files := sorted(path for path in files if path.suffix.lower() == suffix):
            return matching_files[0]
    raise ValueError("Das Archiv enthält keine für diese Konsole startbare Datei.")


def _require_supported_extension(system: str, path: Path) -> None:
    extension = path.suffix.lower().lstrip(".")
    if extension not in SYSTEM_EXTENSIONS[system]:
        raise ValueError("Die heruntergeladene Datei passt nicht zur ausgewählten Konsole.")
