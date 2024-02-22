import datetime
from typing import Optional, Set
from rich.pretty import pprint
from sqlalchemy import Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm.exc import DetachedInstanceError
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    MappedAsDataclass,
    reconstructor,
)

from .bz_batch import BzBatch
from .configuration import Configuration
from .db_base import Base
from .db_chunks import ChunksPrepared, ChunksTransmitted, ChunksDeduped
from .db_session import DBSession
from .dev_debug import DevDebug
from .locks import lock, Lock


class BackupFile(MappedAsDataclass, Base):
    """
    Class to store To Do File Information
    """

    __tablename__ = "BackupFile"

    file_name: Mapped[str]
    file_size: Mapped[int]

    # Primary key of the table
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False, init=False)

    # This is used for rows that aren't used
    not_valid: Mapped[bool] = mapped_column(default=False, nullable=False, init=False)

    _timestamp: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, nullable=True, init=True, default=datetime.datetime.now()
    )

    completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, init=False
    )

    _current_chunk: Mapped[int] = mapped_column(Integer, default=0, init=False)

    # The rate that the backup is moving at
    _rate: Mapped[Optional[str]] = mapped_column(
        String, init=False, default_factory=str
    )

    # This indicates whether the current item is a dedup
    is_deduped: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, init=False
    )

    # The number of bytes that are deduped. Particularly for large files, there can
    # be files that have some duplicate blocks, but others that are transmitted
    _deduped_bytes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, init=False
    )

    # The number of bytes that are transmitted
    _transmitted_bytes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, init=False
    )

    # The total number of bytes that we have processed
    _total_bytes_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, init=False
    )

    # A flag if this is a large file
    large_file: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, init=False
    )

    # The total number of chunks in a large file
    _chunks_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, init=False
    )

    # If the file is part of a batch, this is the row in the BzBatch table for the batch
    batch_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("BzBatch.id"), init=False, default_factory=list
    )

    batch: Mapped["BzBatch"] = relationship(
        "BzBatch", init=False, default=None, lazy="immediate"
    )

    # These next three set up the relationship between this file and the various
    # chunk counts: prepared, deduped, and transmitted

    chunks_prepared: Mapped[Set["ChunksPrepared"]] = relationship(
        init=False, collection_class=set, lazy="immediate"
    )
    chunks_deduped: Mapped[Set["ChunksDeduped"]] = relationship(
        init=False, collection_class=set, lazy="immediate"
    )
    chunks_transmitted: Mapped[Set["ChunksTransmitted"]] = relationship(
        init=False, collection_class=set, lazy="immediate"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.debug = DevDebug()
        self.debug.disable("lock")
        self.session = DBSession.session

    @reconstructor
    def reconstruct(self):
        self.session = DBSession.session

    def __hash__(self):
        return hash(repr(self))

    def __rich_repr__(self):
        yield "id", self.id
        yield "file_name", self.file_name
        yield "file_size", self.file_size
        yield "id", self.id

        yield "completed", self.completed
        yield "large_file", self.large_file
        yield "not_valid", self.not_valid
        yield "is_deduped", self.is_deduped
        yield "batch_id", self.batch_id

        yield "timestamp", self.timestamp

        yield "total_chunk_count", self.chunks_total
        yield "current_chunk", self.current_chunk

        yield "chunks_prepared", self.chunks_prepared
        yield "chunks_deduped", self.chunks_deduped
        yield "chunks_transmited", self.chunks_transmitted

        yield "deduped_bytes", self.deduped_bytes
        yield "transmitted_bytes", self.transmitted_bytes
        yield "total_bytes_processed", self.total_bytes_processed

        yield "rate", self.rate

    @lock(Lock.DB_LOCK)
    def add_prepared(self, chunk_number: int) -> None:
        with DBSession.session as session:
            try:
                new_chunk: ChunksPrepared = ChunksPrepared(id=chunk_number)
                self.chunks_prepared.add(new_chunk)
                self.current_chunk = chunk_number
                session.flush()
            except IntegrityError as e:
                pass
            # try:
            #     self.session.refresh(self)
            # except InvalidRequestError as e:
            #     pass

    @lock(Lock.DB_LOCK)
    def add_deduped(self, chunk_number: int):
        with DBSession.session as session:
            try:
                new_chunk: ChunksDeduped = ChunksDeduped(id=chunk_number)
                self.chunks_deduped.add(new_chunk)
                self.current_chunk = chunk_number
                session.flush()
            except IntegrityError as e:
                pass
            # try:
            #     self.session.refresh(self)
            # except InvalidRequestError as e:
            #     pass

    @lock(Lock.DB_LOCK)
    def add_transmitted(self, chunk_number: int):
        with DBSession.session as session:
            try:
                new_chunk: ChunksTransmitted = ChunksTransmitted(id=chunk_number)
                self.chunks_transmitted.add(new_chunk)
                self.current_chunk = chunk_number
                session.flush()
            except IntegrityError as e:
                pass
            # try:
            #     self.session.refresh(self)
            # except InvalidRequestError as e:
            #     pass

    @property
    def deduped_count(self) -> int:
        return len(self.chunks_deduped)

    @property
    def max_prepared(self) -> int:
        chunks = [chunk.id for chunk in self.chunks_prepared]
        if len(chunks) > 0:
            return max(chunks)
        else:
            return 0

    @property
    def max_deduped(self) -> int:
        chunks = [chunk.id for chunk in self.chunks_deduped]
        if len(chunks) > 0:
            return max(chunks)
        else:
            return 0

    @property
    def max_transmitted(self) -> int:
        chunks = [chunk.id for chunk in self.chunks_transmitted]
        if len(chunks) > 0:
            return max(chunks)
        else:
            return 0

    @property
    def total_chunk_size(self) -> int:
        return (
            len(self.chunks_transmitted) + len(self.chunks_deduped)
        ) * Configuration.default_chunk_size

    @property
    def transmitted_chunk_size(self) -> int:
        return len(self.chunks_transmitted) * Configuration.default_chunk_size

    @property
    def total_deduped_size(self) -> int:
        return len(self.chunks_deduped) * Configuration.default_chunk_size

    @property
    def current_chunk(self) -> int:
        return self._current_chunk

    @current_chunk.setter
    @lock(Lock.DB_LOCK)
    def current_chunk(self, current_chunk: int):
        self._current_chunk = current_chunk
        DBSession.session.flush()
        # try:
        #     self.session.refresh(self)
        # except InvalidRequestError as e:
        #     pass

    @property
    def rate(self) -> str:
        with Lock.DB_LOCK:
            return self._rate

    @rate.setter
    @lock(Lock.DB_LOCK)
    def rate(self, rate: str):
        self._rate = rate
        DBSession.session.flush()
        # try:
        #     self.session.refresh(self)
        # except InvalidRequestError as e:
        #     pass

    @property
    def deduped_bytes(self) -> int:
        with Lock.DB_LOCK:
            return self._deduped_bytes

    @deduped_bytes.setter
    @lock(Lock.DB_LOCK)
    def deduped_bytes(self, deduped_bytes: int):
        self._deduped_bytes = deduped_bytes
        DBSession.session.flush()
        # try:
        #     self.session.refresh(self)
        # except InvalidRequestError as e:
        #     pass

    @property
    def transmitted_bytes(self) -> int:
        with Lock.DB_LOCK:
            return self._transmitted_bytes

    @transmitted_bytes.setter
    @lock(Lock.DB_LOCK)
    def transmitted_bytes(self, transmitted_bytes: int):
        self._transmitted_bytes = transmitted_bytes
        DBSession.session.flush()
        # try:
        #     self.session.refresh(self)
        # except InvalidRequestError as e:
        #     pass

    @property
    def deduped_chunks(self) -> list:
        with Lock.DB_LOCK:
            chunks = [chunk.id for chunk in self.chunks_deduped]
            return chunks

    @property
    def transmitted_chunks(self) -> list:
        with Lock.DB_LOCK:
            chunks = [chunk.id for chunk in self.chunks_transmitted]
            return chunks

    @property
    def prepared_chunks(self) -> list:
        with Lock.DB_LOCK:
            chunks = [chunk.id for chunk in self.chunks_prepared]
            return chunks

    @property
    def timestamp(self) -> datetime.datetime:
        with Lock.DB_LOCK:
            return self._timestamp

    @timestamp.setter
    @lock(Lock.DB_LOCK)
    def timestamp(self, timestamp: datetime.datetime):
        self._timestamp = timestamp
        DBSession.session.flush()
        # try:
        #     self.session.refresh(self)
        # except InvalidRequestError as e:
        #     pass

    @property
    def total_bytes_processed(self) -> int:
        with Lock.DB_LOCK:
            return self._total_bytes_processed

    @total_bytes_processed.setter
    @lock(Lock.DB_LOCK)
    def total_bytes_processed(self, total_bytes_processed: int):
        self._total_bytes_processed = total_bytes_processed
        DBSession.session.flush()
        # try:
        #     self.session.refresh(self)
        # except InvalidRequestError as e:
        #     pass

    @property
    def chunks_total(self) -> int:
        with Lock.DB_LOCK:
            return self._chunks_total

    @chunks_total.setter
    @lock(Lock.DB_LOCK)
    def chunks_total(self, chunks_total: int):
        self._chunks_total = chunks_total
        DBSession.session.flush()
        # try:
        #     self.session.refresh(self)
        # except InvalidRequestError as e:
        #     pass
