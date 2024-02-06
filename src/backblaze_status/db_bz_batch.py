from typing import Set
from typing import Set

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db_base import Base
from .locks import lock, Lock


class BzBatch(Base):

    from .db_backup_file import BackupFile

    __tablename__ = "BzBatch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    size: Mapped[int]
    timestamp: Mapped[str]
    files: Mapped[Set["BackupFile"]] = relationship(back_populates="batch")

    @lock(Lock.DB_LOCK)
    def add_file(self, filename: str) -> None:
        self._files.add(filename)
