from dataclasses import dataclass
from pathlib import Path


@dataclass
class BackupFile:
    """
    Class to store To Do File Information
    """

    file_name: Path
    file_size: int
    list_index: int
    completed: bool = False
    dedup_count: int = 0
    chunk_count: int = 0
    bytes: int = 0
