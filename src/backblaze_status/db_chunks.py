from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, Integer

from .db_base import Base


class ChunksPrepared(Base):

    __tablename__ = "ChunksPrepared"

    id: Mapped[int] = mapped_column(primary_key=True)
    backup_file_id: Mapped[int] = mapped_column(ForeignKey("BackupFile.id"))

    def __repr__(self):
        return (
            f"<ChunksPrepared(id={self.id!r}, backup_file_id={self.backup_file_id!r})>"
        )

    def __rich_repr__(self):
        yield "id", self.id
        yield "backup_file_id", self.backup_file_id


class ChunksDeduped(Base):

    __tablename__ = "ChunksDeduped"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    backup_file_id: Mapped[int] = mapped_column(ForeignKey("BackupFile.id"))

    def __repr__(self):
        return (
            f"<ChunksPrepared(id={self.id!r}, backup_file_id={self.backup_file_id!r})>"
        )

    def __rich_repr__(self):
        yield "id", self.id
        yield "backup_file_id", self.backup_file_id


class ChunksTransmitted(Base):

    __tablename__ = "ChunksTransmitted"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    backup_file_id: Mapped[int] = mapped_column(ForeignKey("BackupFile.id"))

    def __repr__(self):
        return (
            f"<ChunksPrepared(id={self.id!r}, backup_file_id={self.backup_file_id!r})>"
        )

    def __rich_repr__(self):
        yield "id", self.id
        yield "backup_file_id", self.backup_file_id
