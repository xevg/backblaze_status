from dataclasses import dataclass, field
from pathlib import Path
from .bz_batch import BzBatch
from _datetime import datetime
from .dev_debug import DevDebug
from .locks import Lock
from .configuration import Configuration
from PyQt6.QtGui import QColor
from typing import Optional


@dataclass
class BackupFile:
    """
    Class to store To Do File Information
    """

    file_name: Path
    file_size: int
    list_index: int = 0

    completed: bool = False
    is_deduped: bool = False
    is_deduped_chunks: bool = False
    previous_run: bool = False
    _deduped_bytes: int = 0
    _transmitted_bytes: int = 0
    _total_bytes_processed: int = 0
    is_large_file: bool = False
    _chunks_total: int = 0
    _prepared_chunks: set = field(default_factory=set)
    _deduped_chunks: set = field(default_factory=set)
    _transmitted_chunks: set = field(default_factory=set)
    _current_chunk: int = 0
    batch: BzBatch = None
    _rate: str = str()
    completed_run: int = 0

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    row_color: Optional[QColor] = field(default=None)
    file_name_color: Optional[QColor] = field(default=None)
    file_size_color: Optional[QColor] = field(default=None)
    start_time_color: Optional[QColor] = field(default=None)
    rate_color: Optional[QColor] = field(default=None)

    def __post_init__(self):
        self.debug = DevDebug()
        self.debug.disable("lock")
        if self.row_color is None:
            self.row_color = QColor("White")

    def __hash__(self):
        return hash(repr(self))

    def __rich_repr__(self):
        yield "file_name", self.file_name
        yield "file_size", self.file_size
        yield "completed", self.completed
        yield "large_file", self.is_large_file
        yield "is_deduped", self.is_deduped
        yield "batch_id", self.batch

        yield "total_chunk_count", self.total_chunk_count
        yield "current_chunk", self.current_chunk

        yield "chunks_prepared", self._prepared_chunks
        yield "chunks_deduped", self._deduped_chunks
        yield "chunks_transmitted", self._transmitted_chunks

        yield "deduped_bytes", self.deduped_bytes
        yield "transmitted_bytes", self.transmitted_bytes
        yield "total_bytes_processed", self.total_bytes_processed

        yield "rate", self.rate

    def add_prepared(self, chunk_number: int):
        with Lock.DB_LOCK:
            self._prepared_chunks.add(chunk_number)
            self.current_chunk = chunk_number

    def add_deduped(self, chunk_number: int):
        with Lock.DB_LOCK:
            self._deduped_chunks.add(chunk_number)
            self.current_chunk = chunk_number

    def add_transmitted(self, chunk_number: int):
        with Lock.DB_LOCK:
            if chunk_number not in self._deduped_chunks:
                self._transmitted_chunks.add(chunk_number)
                self.current_chunk = chunk_number

    @property
    def deduped_count(self) -> int:
        with Lock.DB_LOCK:
            return len(self._deduped_chunks)

    @property
    def max_prepared(self) -> int:
        with Lock.DB_LOCK:
            if len(self._prepared_chunks) > 0:
                return max(self._prepared_chunks)
            else:
                return 0

    @property
    def max_deduped(self) -> int:
        with Lock.DB_LOCK:
            if len(self._deduped_chunks) > 0:
                return max(self._deduped_chunks)
            else:
                return 0

    @property
    def max_transmitted(self) -> int:
        with Lock.DB_LOCK:
            if len(self._transmitted_chunks) > 0:
                return max(self._transmitted_chunks)
            else:
                return 0

    @property
    def total_chunk_size(self) -> int:
        with Lock.DB_LOCK:
            return (
                len(self._transmitted_chunks) + len(self._deduped_chunks)
            ) * Configuration.default_chunk_size

    @property
    def transmitted_chunk_size(self) -> int:
        with Lock.DB_LOCK:
            return len(self._transmitted_chunks) * Configuration.default_chunk_size

    @property
    def total_deduped_size(self) -> int:
        with Lock.DB_LOCK:
            return len(self._deduped_chunks) * Configuration.default_chunk_size

    @property
    def current_chunk(self) -> int:
        with Lock.DB_LOCK:
            return self._current_chunk

    @current_chunk.setter
    def current_chunk(self, current_chunk: int):
        with Lock.DB_LOCK:
            self._current_chunk = current_chunk

    @property
    def rate(self) -> str:
        with Lock.DB_LOCK:
            return self._rate

    @rate.setter
    def rate(self, rate: str):
        with Lock.DB_LOCK:
            self._rate = rate

    @property
    def deduped_bytes(self) -> int:
        with Lock.DB_LOCK:
            return self._deduped_bytes

    @deduped_bytes.setter
    def deduped_bytes(self, deduped_bytes: int):
        with Lock.DB_LOCK:
            self._deduped_bytes = deduped_bytes

    @property
    def transmitted_bytes(self) -> int:
        with Lock.DB_LOCK:
            return self._transmitted_bytes

    @transmitted_bytes.setter
    def transmitted_bytes(self, transmitted_bytes: int):
        with Lock.DB_LOCK:
            self._transmitted_bytes = transmitted_bytes

    @property
    def deduped_chunks(self) -> list:
        with Lock.DB_LOCK:
            chunks = list(self._deduped_chunks)
            return chunks

    @property
    def transmitted_chunks(self) -> list:
        with Lock.DB_LOCK:
            chunks = list(self._transmitted_chunks)
            return chunks

    @property
    def prepared_chunks(self) -> list:
        with Lock.DB_LOCK:
            chunks = list(self._prepared_chunks)
            return chunks

    @property
    def total_bytes_processed(self) -> int:
        with Lock.DB_LOCK:
            return self._total_bytes_processed

    @total_bytes_processed.setter
    def total_bytes_processed(self, total_bytes_processed: int):
        with Lock.DB_LOCK:
            self._total_bytes_processed = total_bytes_processed

    @property
    def total_chunk_count(self) -> int:
        with Lock.DB_LOCK:
            return self._chunks_total

    @total_chunk_count.setter
    def total_chunk_count(self, chunks_total: int):
        with Lock.DB_LOCK:
            self._chunks_total = chunks_total
