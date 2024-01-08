from dataclasses import dataclass, field
from pathlib import Path
from .bz_batch import BzBatch
from _datetime import datetime
import threading


@dataclass
class BackupFile:
    """
    Class to store To Do File Information
    """

    file_name: Path
    file_size: int
    list_index: int

    timestamp: datetime = field(default=datetime.now())
    completed: bool = False
    dedup_count: int = 0
    dedup_current: bool = False
    deduped_bytes: int = 0
    transmitted_bytes: int = 0
    total_bytes_processed: int = 0
    large_file = False
    chunks_total: int = 0
    chunks_prepared: set = field(default_factory=set)
    chunks_deduped: set = field(default_factory=set)
    chunks_transmitted: set = field(default_factory=set)
    chunk_current: int = 0
    batch: BzBatch = None
    rate: str = str()
    lock: threading.Lock = field(default_factory=threading.Lock, init=False)
