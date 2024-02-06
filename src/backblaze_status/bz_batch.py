from pathlib import Path
from .locks import Lock


class BzBatch:
    def __init__(self, size: int, timestamp: str) -> None:
        self.size: int = size
        self.timestamp: str = timestamp
        self.files: set = set()

    def add_file(self, filename: str):
        with Lock.DB_LOCK:
            self.files.add(filename)
