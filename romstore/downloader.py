from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import threading
import time
import uuid

from .covers import CoverService
from .installer import InstallCallbacks, ItemInstaller, MAX_DOWNLOAD_BYTES
from .models import CatalogItem
from .security import DownloadCancelled


TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})


@dataclass(slots=True)
class DownloadJob:
    id: str
    item_id: str
    title: str
    state: str = "queued"
    message: str = "Wartet auf Download"
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    speed_bps: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    cancellation: threading.Event = field(default_factory=threading.Event, repr=False)

    def public(self) -> dict:
        progress = min(1.0, self.downloaded_bytes / self.total_bytes) if self.total_bytes else None
        return {
            "id": self.id,
            "item_id": self.item_id,
            "title": self.title,
            "state": self.state,
            "message": self.message,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "speed_bps": round(self.speed_bps),
            "progress": progress,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class BusyError(RuntimeError):
    pass


class AlreadyInstalled(RuntimeError):
    pass


class DownloadManager:
    def __init__(
        self,
        games_dir: Path,
        covers: CoverService,
        *,
        http=None,
        max_download_bytes: int = MAX_DOWNLOAD_BYTES,
    ):
        self.games_dir = games_dir
        self.installer = ItemInstaller(
            games_dir,
            covers,
            http=http,
            max_download_bytes=max_download_bytes,
        )
        self.jobs: dict[str, DownloadJob] = {}
        self._lock = threading.RLock()
        self._active_job_id = ""

    def start(self, item: CatalogItem) -> dict:
        with self._lock:
            self._require_idle()
            self._require_not_installed(item)
            job = DownloadJob(id=uuid.uuid4().hex, item_id=item.id, title=item.title)
            self.jobs[job.id] = job
            self._active_job_id = job.id
            threading.Thread(target=self._run, args=(job, item), daemon=True).start()
            return job.public()

    def snapshot(self, job_id: str) -> dict | None:
        with self._lock:
            job = self.jobs.get(job_id)
            return job.public() if job else None

    def cancel(self, job_id: str) -> dict | None:
        with self._lock:
            job = self.jobs.get(job_id)
            if job and job.state not in TERMINAL_STATES:
                job.cancellation.set()
                self._update(job, message="Download wird abgebrochen …")
            return job.public() if job else None

    def _require_idle(self) -> None:
        active = self.jobs.get(self._active_job_id)
        if active and active.state not in TERMINAL_STATES:
            raise BusyError("Es läuft bereits ein Download.")

    def _require_not_installed(self, item: CatalogItem) -> None:
        if (item.install_dir(self.games_dir) / "receipt.json").is_file():
            raise AlreadyInstalled("Dieser Inhalt ist bereits installiert.")

    def _run(self, job: DownloadJob, item: CatalogItem) -> None:
        callbacks = InstallCallbacks(
            download_started=lambda: self._download_started(job),
            download_progressed=lambda received, total, speed: self._progressed(
                job, received, total, speed
            ),
            installation_started=lambda: self._installation_started(job),
            is_cancelled=job.cancellation.is_set,
        )
        try:
            self.installer.install(item, callbacks)
            self._update(job, state="completed", message="Installiert – Pegasus wird neu geladen.")
        except DownloadCancelled:
            self._update(job, state="cancelled", message="Download abgebrochen.")
        except Exception as exc:
            self._update(job, state="failed", message=_safe_error(exc))
        finally:
            self._release(job)

    def _download_started(self, job: DownloadJob) -> None:
        self._update(job, state="downloading", message="ROM wird heruntergeladen …")

    def _installation_started(self, job: DownloadJob) -> None:
        self._update(job, state="installing", message="ROM und Cover werden installiert …")

    def _progressed(
        self,
        job: DownloadJob,
        received_bytes: int,
        total_bytes: int | None,
        speed_bps: float,
    ) -> None:
        with self._lock:
            job.downloaded_bytes = received_bytes
            job.total_bytes = total_bytes
            job.speed_bps = speed_bps
            job.updated_at = time.time()

    def _update(self, job: DownloadJob, **changes) -> None:
        with self._lock:
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = time.time()

    def _release(self, job: DownloadJob) -> None:
        with self._lock:
            if self._active_job_id == job.id:
                self._active_job_id = ""


def _safe_error(error: Exception) -> str:
    text = str(error).strip() or error.__class__.__name__
    if "http://" in text or "https://" in text:
        return "Download fehlgeschlagen. Bitte Netzwerk und Quelle prüfen."
    return text[:240]
