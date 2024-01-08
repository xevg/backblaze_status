from pathlib import Path


class BzBatch:
    def __init__(self, size: int, timestamp: str) -> None:
        self.size: int = size
        self.timestamp: str = timestamp
        self.files: set = set()

    def add_file(self, filename: Path):
        self.files.add(filename)
