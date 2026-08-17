from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
import shutil
import time
from typing import Callable
import uuid

from .archives import prepare_primary_file
from .covers import CoverService
from .models import CatalogItem
from .pegasus_metadata import rebuild_system_metadata
from .security import DownloadCancelled, DownloadRequest, SafeHttpClient, atomic_write_json


MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024 * 1024
FALLBACK_SPACE_RESERVATION = 512 * 1024 * 1024
INSTALLATION_OVERHEAD = 64 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class InstallCallbacks:
    download_started: Callable[[], None]
    download_progressed: Callable[[int, int | None, float], None]
    installation_started: Callable[[], None]
    is_cancelled: Callable[[], bool]


@dataclass(frozen=True, slots=True)
class DownloadedFile:
    path: Path
    bytes_received: int
    sha256: str


class ItemInstaller:
    def __init__(
        self,
        games_dir: Path,
        covers: CoverService,
        *,
        http=None,
        max_download_bytes: int = MAX_DOWNLOAD_BYTES,
    ):
        self.games_dir = games_dir
        self.covers = covers
        self.http = http or SafeHttpClient(timeout=45)
        self.max_download_bytes = max_download_bytes

    def install(self, item: CatalogItem, callbacks: InstallCallbacks) -> None:
        destination = item.install_dir(self.games_dir)
        staging_dir = self._create_staging_dir(destination, item)
        try:
            downloaded_file = self._download(item, staging_dir, callbacks)
            callbacks.installation_started()
            _raise_if_cancelled(callbacks)
            primary_file = prepare_primary_file(item.system, downloaded_file.path, staging_dir)
            _raise_if_cancelled(callbacks)
            cover_filename = self.covers.materialize(item, staging_dir)
            _raise_if_cancelled(callbacks)
            self._write_receipt(item, staging_dir, primary_file, cover_filename, downloaded_file)
            self._commit(staging_dir, destination, item.system)
        finally:
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)

    def _create_staging_dir(self, destination: Path, item: CatalogItem) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileExistsError("Installationsordner ist bereits vorhanden.")
        _remove_stale_staging_directories(destination)
        _require_available_space(destination.parent, item.size, self.max_download_bytes)
        unique_suffix = uuid.uuid4().hex[:8]
        staging_dir = destination.parent / f".{destination.name}.staging-{unique_suffix}"
        staging_dir.mkdir(mode=0o700)
        return staging_dir

    def _download(
        self,
        item: CatalogItem,
        staging_dir: Path,
        callbacks: InstallCallbacks,
    ) -> DownloadedFile:
        callbacks.download_started()
        target_path = staging_dir / _safe_download_filename(item.filename)
        digest = sha256()
        with target_path.open("xb") as output:
            request = DownloadRequest(
                url=item.download_url,
                target=_HashingWriter(output, digest),
                max_bytes=self.max_download_bytes,
                on_progress=callbacks.download_progressed,
                is_cancelled=callbacks.is_cancelled,
            )
            bytes_received, _ = self.http.download(request)
            output.flush()
        checksum = digest.hexdigest()
        _verify_download(item, bytes_received, checksum)
        return DownloadedFile(target_path, bytes_received, checksum)

    def _write_receipt(
        self,
        item: CatalogItem,
        staging_dir: Path,
        primary_file: Path,
        cover_filename: str,
        download: DownloadedFile,
    ) -> None:
        receipt = {
            "schema": 1,
            "catalog_id": item.id,
            "provider": item.provider,
            "source_url": item.source_url,
            "system": item.system,
            "title": item.title,
            "kind": item.kind,
            "license": item.license,
            "developer": item.developer,
            "description": item.description,
            "primary_file": primary_file.relative_to(staging_dir).as_posix(),
            "cover_file": cover_filename,
            "download_sha256": download.sha256,
            "downloaded_bytes": download.bytes_received,
            "installed_at": int(time.time()),
        }
        # A receipt is the commit marker: write it only after ROM and cover exist.
        atomic_write_json(staging_dir / "receipt.json", receipt)

    def _commit(self, staging_dir: Path, destination: Path, system: str) -> None:
        staging_dir.replace(destination)
        try:
            rebuild_system_metadata(self.games_dir, system)
        except Exception:
            destination.replace(staging_dir)
            raise


class _HashingWriter:
    def __init__(self, target, digest):
        self.target = target
        self.digest = digest

    def write(self, data: bytes) -> int:
        self.digest.update(data)
        return self.target.write(data)


def _verify_download(item: CatalogItem, received_bytes: int, checksum: str) -> None:
    if item.size is not None and received_bytes != item.size:
        raise IOError("Die Dateigröße stimmt nicht mit dem Katalog überein.")
    if item.sha256 and checksum != item.sha256:
        raise IOError("Die SHA-256-Prüfsumme stimmt nicht.")


def _raise_if_cancelled(callbacks: InstallCallbacks) -> None:
    if callbacks.is_cancelled():
        raise DownloadCancelled("Download abgebrochen.")


def _safe_download_filename(filename: str) -> str:
    basename = PurePosixPath(filename).name
    contains_control_character = any(ord(character) < 32 or ord(character) == 127 for character in basename)
    if (
        not basename
        or basename in {".", ".."}
        or contains_control_character
        or len(basename.encode("utf-8")) > 240
    ):
        raise ValueError("Ungültiger Dateiname im Katalog.")
    return basename


def _remove_stale_staging_directories(destination: Path) -> None:
    pattern = f".{destination.name}.staging-*"
    for stale_directory in destination.parent.glob(pattern):
        if stale_directory.is_dir() and not stale_directory.is_symlink():
            shutil.rmtree(stale_directory)


def _require_available_space(target: Path, expected_bytes: int | None, maximum: int) -> None:
    reserved_download_bytes = expected_bytes or min(maximum, FALLBACK_SPACE_RESERVATION)
    if shutil.disk_usage(target).free < reserved_download_bytes + INSTALLATION_OVERHEAD:
        raise OSError("Nicht genügend freier Speicherplatz für den Download.")
