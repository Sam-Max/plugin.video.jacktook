import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DownloadEntry:
    id: str
    name: str
    dest_path: str
    url: str
    status: str = "downloading"
    progress: int = 0
    speed: int = 0
    eta: int = 0
    size: int = 0
    downloaded: int = 0
    thread: Optional[threading.Thread] = None
    cancel_flag: bool = False


class DownloadManager:
    _instance: Optional["DownloadManager"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._registry: Dict[str, DownloadEntry] = {}
        self._registry_lock = threading.Lock()

    @property
    def registry(self) -> Dict[str, DownloadEntry]:
        with self._registry_lock:
            return dict(self._registry)

    def register(
        self,
        name: str,
        dest_path: str,
        url: str,
        thread: Optional[threading.Thread] = None,
    ) -> Optional[DownloadEntry]:
        with self._registry_lock:
            existing = self._registry.get(dest_path)
            if existing and existing.status == "downloading":
                return None
            entry = DownloadEntry(
                id=dest_path,
                name=name,
                dest_path=dest_path,
                url=url,
                thread=thread,
            )
            self._registry[dest_path] = entry
            return entry

    def update_progress(
        self,
        dest_path: str,
        downloaded: int,
        speed: int,
        eta: int,
        progress: int,
        size: int,
    ):
        with self._registry_lock:
            entry = self._registry.get(dest_path)
            if entry:
                entry.downloaded = downloaded
                entry.speed = speed
                entry.eta = eta
                entry.progress = progress
                entry.size = size

    def set_status(self, dest_path: str, status: str):
        with self._registry_lock:
            entry = self._registry.get(dest_path)
            if entry:
                entry.status = status

    def set_thread(self, dest_path: str, thread: Optional[threading.Thread]):
        with self._registry_lock:
            entry = self._registry.get(dest_path)
            if entry:
                entry.thread = thread

    def get_entry(self, dest_path: str) -> Optional[DownloadEntry]:
        with self._registry_lock:
            return self._registry.get(dest_path)

    def remove_entry(self, dest_path: str):
        with self._registry_lock:
            self._registry.pop(dest_path, None)

    def list_entries(self) -> List[DownloadEntry]:
        with self._registry_lock:
            return list(self._registry.values())

    def clear(self):
        with self._registry_lock:
            self._registry.clear()
