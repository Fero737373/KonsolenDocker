from pathlib import Path
import tempfile
import threading
import time
import unittest

from romstore.downloader import BusyError, DownloadManager
from romstore.models import CatalogItem
from romstore.security import DownloadCancelled


class BlockingInstaller:
    def __init__(self):
        self.started = threading.Event()

    def install(self, item: CatalogItem, callbacks) -> None:  # noqa: ANN001
        callbacks.download_started()
        self.started.set()
        while not callbacks.is_cancelled():
            time.sleep(0.005)
        raise DownloadCancelled("cancelled")


def item(title: str) -> CatalogItem:
    slug = title.lower().replace(" ", "-")
    return CatalogItem(
        provider="Fixture",
        system="nes",
        title=title,
        kind="Spiel",
        download_url=f"https://raw.githubusercontent.com/example/project/HEAD/{slug}.nes",
        filename=f"{slug}.nes",
        source_url="https://github.com/example/project",
    )


def wait_for_state(manager: DownloadManager, job_id: str, state: str) -> dict:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        snapshot = manager.snapshot(job_id)
        if snapshot and snapshot["state"] == state:
            return snapshot
        time.sleep(0.005)
    raise AssertionError(f"Job {job_id} did not reach {state}")


class DownloadManagerTests(unittest.TestCase):
    def test_allows_only_one_download_and_cancels_it_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DownloadManager(Path(directory), covers=object())
            installer = BlockingInstaller()
            manager.installer = installer

            first_job = manager.start(item("First Game"))
            self.assertTrue(installer.started.wait(timeout=1))
            with self.assertRaises(BusyError):
                manager.start(item("Second Game"))
            manager.cancel(first_job["id"])

            cancelled = wait_for_state(manager, first_job["id"], "cancelled")
            self.assertEqual(cancelled["message"], "Download abgebrochen.")


if __name__ == "__main__":
    unittest.main()
