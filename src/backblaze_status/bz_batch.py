from PyQt6.QtCore import QReadWriteLock


class BzBatch:
    def __init__(self, size: int, timestamp: str) -> None:
        self.size: int = size
        self.timestamp: str = timestamp
        self.files: set = set()
        self.lock = QReadWriteLock(recursionMode=QReadWriteLock.RecursionMode.Recursive)

    def add_file(self, filename: str):
        self.lock.lockForWrite()
        self.files.add(filename)
        self.lock.unlock()
