from dataclasses import dataclass, field
from pathlib import Path
from .bz_batch import BzBatch
from _datetime import datetime
from .dev_debug import DevDebug
from .locks import Lock
from .configuration import Configuration


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
    is_deduped: bool = False
    _deduped_bytes: int = 0
    _transmitted_bytes: int = 0
    _total_bytes_processed: int = 0
    large_file = False
    _chunks_total: int = 0
    chunks_prepared: set = field(default_factory=set)
    chunks_deduped: set = field(default_factory=set)
    chunks_transmitted: set = field(default_factory=set)
    _current_chunk: int = 0
    batch: BzBatch = None
    _rate: str = str()

    def __post_init__(self):
        self.debug = DevDebug()
        self.debug.disable("lock")

    def __hash__(self):
        return hash(repr(self))

    def __rich_repr__(self):
        yield "file_name", self.file_name
        yield "file_size", self.file_size
        yield "completed", self.completed
        yield "large_file", self.large_file
        yield "is_deduped", self.is_deduped
        yield "batch_id", self.batch

        yield "timestamp", self.timestamp

        yield "chunks_total", self.chunks_total
        yield "current_chunk", self.current_chunk

        yield "chunks_prepared", self.chunks_prepared
        yield "chunks_deduped", self.chunks_deduped
        yield "chunks_transmitted", self.chunks_transmitted

        yield "deduped_bytes", self.deduped_bytes
        yield "transmitted_bytes", self.transmitted_bytes
        yield "total_bytes_processed", self.total_bytes_processed

        yield "rate", self.rate

    def add_prepared(self, chunk_number: int):
        with Lock.DB_LOCK:
            self.chunks_prepared.add(chunk_number)
            self.current_chunk = chunk_number

    def add_deduped(self, chunk_number: int):
        with Lock.DB_LOCK:
            self.chunks_deduped.add(chunk_number)
            self.current_chunk = chunk_number

    def add_transmitted(self, chunk_number: int):
        with Lock.DB_LOCK:
            self.chunks_transmitted.add(chunk_number)
            self.current_chunk = chunk_number

    @property
    def deduped_count(self) -> int:
        with Lock.DB_LOCK:
            return len(self.chunks_deduped)

    @property
    def max_prepared(self) -> int:
        with Lock.DB_LOCK:
            if len(self.chunks_prepared) > 0:
                return max(self.chunks_prepared)
            else:
                return 0

    @property
    def max_deduped(self) -> int:
        with Lock.DB_LOCK:
            if len(self.chunks_deduped) > 0:
                return max(self.chunks_deduped)
            else:
                return 0

    @property
    def max_transmitted(self) -> int:
        with Lock.DB_LOCK:
            if len(self.chunks_transmitted) > 0:
                return max(self.chunks_transmitted)
            else:
                return 0

    @property
    def total_chunk_size(self) -> int:
        with Lock.DB_LOCK:
            return (
                len(self.chunks_transmitted) + len(self.chunks_deduped)
            ) * Configuration.default_chunk_size

    @property
    def transmitted_chunk_size(self) -> int:
        with Lock.DB_LOCK:
            return len(self.chunks_transmitted) * Configuration.default_chunk_size

    @property
    def total_deduped_size(self) -> int:
        with Lock.DB_LOCK:
            return len(self.chunks_deduped) * Configuration.default_chunk_size

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
            chunks = list(self.chunks_deduped)
            return chunks

    @property
    def transmitted_chunks(self) -> list:
        with Lock.DB_LOCK:
            chunks = list(self.chunks_transmitted)
            return chunks

    @property
    def prepared_chunks(self) -> list:
        with Lock.DB_LOCK:
            chunks = list(self.chunks_prepared)
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
    def chunks_total(self) -> int:
        with Lock.DB_LOCK:
            return self._chunks_total

    @chunks_total.setter
    def chunks_total(self, chunks_total: int):
        with Lock.DB_LOCK:
            self._chunks_total = chunks_total
