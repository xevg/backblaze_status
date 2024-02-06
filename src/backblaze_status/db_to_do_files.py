import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.exc import InvalidRequestError
from rich.pretty import pprint

from .configuration import Configuration
from .db_backup_file import BackupFile
from .db_chunks import ChunksDeduped, ChunksTransmitted
from .db_session import DBSession
from .dev_debug import DevDebug
from .locks import lock, Lock
from .utils import MultiLogger
from .db_base import Base


class NotFound(Exception):
    pass


@dataclass
class ToDoFiles:

    """
    Class to store the list and status of To Do files
    """

    _todo_file_name: str = field(default_factory=str, init=False)
    _file_modification_time: float = field(default=0.0, init=False)
    _backup_running: bool = field(default=False, init=False)
    _current_file: int = field(default=None, init=False)

    BZ_DIR: str = field(
        default="/Library/Backblaze.bzpkg/bzdata/bzbackup/bzdatacenter/", init=False
    )

    def __post_init__(self):
        self._multi_log = MultiLogger("ToDoFiles", terminal=True)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Creating ToDoFiles")
        self.debug = DevDebug()

        # We need:
        # from .db_bz_batch import BzBatch
        # Add it back if it's deleted
        from .db_bz_batch import BzBatch

        Base.metadata.create_all(DBSession.engine)
        self.session = DBSession.session

        self._read()
        self._reread_file_thread = threading.Thread(
            target=self.reread_to_do_list,
            daemon=True,
            name="reread_to_do_list",
        )
        self._reread_file_thread.start()

    @lock(Lock.DB_LOCK)
    def _read(self) -> None:
        """
        This reads the to_do file and stores it in two data structures,
          - a dictionary so that I can find the file, and
          - a list, so that I can see what the next files are

          The structure of the file that I care about are the 6th field, which is the filename,
          and the fifth field, which is the file size.
        :return:
        """
        self.todo_file_name = self.get_to_do_file_list()

        file = Path(self.todo_file_name)
        stat = file.stat()
        self._file_modification_time = stat.st_mtime
        with open(self.todo_file_name, "r") as tdf:
            for todo_line in tdf:
                todo_fields = todo_line.strip().split("\t")
                todo_filename = todo_fields[5]
                if self.exists(todo_filename):
                    continue

                todo_file_size = int(todo_fields[4])
                backup_file = BackupFile(
                    file_name=todo_filename,
                    file_size=todo_file_size,
                )
                if todo_file_size > Configuration.default_chunk_size:
                    backup_file.chunks_total = int(
                        todo_file_size / Configuration.default_chunk_size
                    )
                    backup_file.large_file = True
                self.session.add(backup_file)

        self.session.flush()
        self._backup_running = True
        # try:
        #     self.session.refresh(backup_file)
        # except InvalidRequestError as e:
        #     pass

    def reread_to_do_list(self):
        while True:
            time.sleep(60.0)  # Check the file every minute
            try:
                file = Path(self.todo_file_name)
                stat = file.stat()
            except FileNotFoundError:
                self._multi_log.log("Backup Complete")
                self._backup_running = False
                self._todo_file_name = self.get_to_do_file_list()
                file = Path(self.todo_file_name)
                stat = file.stat()

            if self._file_modification_time != stat.st_mtime:
                self._multi_log.log("To Do file changed, rereading")
                self._read()

                # TODO: How do I let them know it is?

    def get_to_do_file_list(self):
        while True:
            to_do_file = None
            # Get the list of to_do and done files in the directory
            bz_files = sorted(os.listdir(self.BZ_DIR))
            for file in bz_files:
                if file[:7] == "bz_todo":
                    to_do_file = f"{self.BZ_DIR}/{file}"

            # If there is no to_do file, that is because the backup process is not
            # running, so we will sleep and try again.
            if not to_do_file:
                self._multi_log.log(
                    f"Backup not running. Waiting for 1 minute and trying again ..."
                )

                # TODO: Make this a progress bar ...
                time.sleep(60)

            else:
                break
        return to_do_file

    @property
    def current_file(self) -> Optional[BackupFile]:
        if self._current_file is None:
            return None

        return self.get_file(self._current_file)

    @current_file.setter
    def current_file(self, value: BackupFile) -> None:
        with Lock.DB_LOCK:
            self._current_file = value.file_name

    @property
    @lock(Lock.DB_LOCK)
    def file_list(self) -> list[BackupFile]:
        result = list(self.session.scalars(select(BackupFile)))
        return result

    @lock(Lock.DB_LOCK)
    def get_file(self, filename) -> BackupFile:
        """
        Returns whether the file is in the list
        :param filename:
        :return:
        """
        result = (
            self.session.query(BackupFile)
            .filter(BackupFile.file_name == filename)
            .scalar()
        )
        # pprint(result)
        return result

    @lock(Lock.DB_LOCK)
    def exists(self, filename) -> bool:
        """
        Returns whether the file is in the list
        :param filename:
        :return:
        """
        result = (
            self.session.query(BackupFile.file_name)
            .filter(BackupFile.file_name == filename)
            .first()
        )
        if result is None:
            return False
        else:
            return True

    @lock(Lock.DB_LOCK)
    def get_index(self, filename) -> int:
        result: int = (
            self.session.query(BackupFile.id)
            .filter(BackupFile.file_name == filename)
            .scalar()
        )
        if result is not None:
            return result
        else:
            raise NotFound

    @lock(Lock.DB_LOCK)
    def completed(self, filename: str) -> None:
        """
        Mark a file as completed

        :param filename:
        :return:
        """
        backup_file = (
            self.session.query(BackupFile.file_name)
            .filter(BackupFile.file_name == filename)
            .scalar()
        )
        if backup_file is None:
            return

        if backup_file.completed:
            return

        backup_file.completed = True
        self.session.flush()
        # try:
        #     self.session.refresh(backup_file)
        # except InvalidRequestError as e:
        #     pass

    @lock(Lock.DB_LOCK)
    def add_file(
        self,
        _filename: Path,
        is_chunk: bool = False,
        timestamp: datetime = datetime.now(),
    ) -> None:
        todo_file_exists = (
            self.session.query(BackupFile.file_name)
            .filter(BackupFile.file_name == str(_filename))
            .first()
        )
        if not todo_file_exists:
            try:
                _stat = _filename.stat()
                _file_size = _stat.st_size
            except:
                _file_size = 0

            backup_file = BackupFile(
                file_name=str(_filename),
                file_size=_file_size,
                timestamp=timestamp,
            )

            # _file_size > self.default_chunk_size:
            # this is the size of the backblaze chunks
            if is_chunk:
                backup_file.chunks_total = int(
                    _file_size / Configuration.default_chunk_size
                )
                backup_file.large_file = True

            self.session.add(backup_file)
            self.session.flush()
            # try:
            #     self.session.refresh(backup_file)
            # except InvalidRequestError as e:
            #     pass

    @lock(Lock.DB_LOCK)
    def get_remaining(self, start_index: int = 0, number_of_rows: int = 0) -> list:
        # start_index += 1
        # count_of_rows = 0
        query_iter = (
            self.session.query(BackupFile)
            .filter(BackupFile.completed.is_(False))
            .order_by(BackupFile.id)[start_index : start_index + number_of_rows]
        )
        yield query_iter
        # for item in self._file_list[start_index:]:  # type: BackupFile
        #     if not item.completed:
        #         count_of_rows += 1
        #         if count_of_rows > number_of_rows:
        #             return
        #        yield item

    @lock(Lock.DB_LOCK)
    def todo_files(self, count=1000000000, filename: str = None):
        """
        Retrieve the next N filenames. If no filename is specified, just start from
        the beginning of the list. If a filename is specified, start from the one
        after that.

        This is a generator function.

        :param count:
        :param filename:
        :return:
        """
        # starting_index = 0
        # counter = 1
        if filename is not None:
            starting_index: int = (
                self.session.query(BackupFile.id)
                .filter(BackupFile.file_name == filename)
                .scalar()
            )
            # starting_index = self._file_dict[filename].list_index

            result = (
                self.session.query(BackupFile)
                .filter(BackupFile.completed.is_(False))
                .order_by(BackupFile.id)[starting_index : starting_index + count + 1]
            )

            yield result

    @property
    def backup_running(self) -> bool:
        with Lock.DB_LOCK:
            result = self._backup_running
            return result

    @property
    def remaining_size(self) -> int:
        with Lock.DB_LOCK:
            remaining_size = (
                self.session.query(func.sum(BackupFile.file_size))
                .where(BackupFile.completed.is_(False))
                .scalar()
            )
            if remaining_size is None:
                return 0
            else:
                return remaining_size

    @property
    def remaining_files(self) -> int:
        with Lock.DB_LOCK:
            remaining_files = (
                self.session.query(func.count(BackupFile.id))
                .where(BackupFile.completed.is_(False))
                .scalar()
            )
            if remaining_files is None:
                return 0
            else:
                return remaining_files

    @lock(Lock.DB_LOCK)
    def _completed_size(
        self, _transmitted_size: bool = True, _deduped_size: bool = True
    ) -> int:
        completed_size = (
            self.session.query(func.sum(BackupFile.file_size))
            .where(BackupFile.completed.is_(True))
            .where(BackupFile.large_file.is_(False))
            .scalar()
        )
        if completed_size is None:
            completed_size = 0

        if _deduped_size:
            deduped_files = (
                self.session.query(func.count(ChunksDeduped.id))
                .where(BackupFile.completed.is_(True))
                .where(BackupFile.large_file.is_(True))
                .where(ChunksDeduped.backup_file_id == BackupFile.id)
                .scalar()
            )
            if deduped_files is not None:
                completed_size += deduped_files * Configuration.default_chunk_size

        if _transmitted_size:
            transmitted_files = (
                self.session.query(func.count(ChunksTransmitted.id))
                .where(BackupFile.completed.is_(True))
                .where(BackupFile.large_file.is_(True))
                .where(ChunksTransmitted.backup_file_id == BackupFile.id)
                .scalar()
            )
            if transmitted_files is not None:
                completed_size += transmitted_files * Configuration.default_chunk_size

        return completed_size

    @property
    def completed_size(self) -> int:
        return self._completed_size(_transmitted_size=True, _deduped_size=True)

    @property
    def transmitted_size(self) -> int:
        return self._completed_size(_transmitted_size=True, _deduped_size=False)

    @property
    def duplicate_size(self) -> int:
        return self._completed_size(_transmitted_size=False, _deduped_size=True)

    @property
    def completed_files(self) -> int:
        with Lock.DB_LOCK:
            completed_files = (
                self.session.query(func.count(BackupFile.id))
                .where(BackupFile.completed.is_(True))
                .scalar()
            )
            if completed_files is None:
                return 0
            else:
                return completed_files

    @property
    def total_size(self) -> int:
        with Lock.DB_LOCK:
            total_size = self.session.query(func.sum(BackupFile.file_size)).scalar()
            if total_size is None:
                return 0
            else:
                return total_size

    @property
    def total_files(self) -> int:
        with Lock.DB_LOCK:
            total_files = self.session.query(func.count(BackupFile.id)).scalar()
            if total_files is None:
                return 0
            else:
                return total_files

    @property
    def duplicate_files(self) -> int:
        with Lock.DB_LOCK:
            duplicate_files = (
                self.session.query(func.count(BackupFile.id))
                .where(BackupFile.is_deduped.is_(True))
                .scalar()
            )
            if duplicate_files is None:
                return 0
            else:
                return duplicate_files

    @property
    def transmitted_files(self) -> int:
        with Lock.DB_LOCK:
            duplicate_files = (
                self.session.query(func.count(BackupFile.id))
                .where(BackupFile.completed.is_(True))
                .where(BackupFile.deduped_count == 0)
                .scalar()
            )
            if duplicate_files is None:
                return 0
            else:
                return duplicate_files
