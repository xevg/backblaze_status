import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PyQt6.QtGui import QColor

from .backup_file import BackupFile
from .completed_files import CompletedFiles
from .configuration import Configuration
from .dev_debug import DevDebug
from .exceptions import CompletedFileNotFound
from .locks import Lock
from .utils import MultiLogger


class NotFound(Exception):
    pass


@dataclass
class ToDoFiles:
    """
    Class to store the list and status of To Do files
    """

    qt: "QTBackupStatus" = field(default=None, init=True)
    _todo_file_name: str = field(default_factory=str, init=False)
    _file_list: List[BackupFile] = field(default_factory=list, init=False)
    _file_dict: dict[str, BackupFile] = field(default_factory=dict, init=False)
    _completed_files: CompletedFiles = field(default_factory=CompletedFiles, init=False)

    _file_modification_time: float = field(default=0.0, init=False)
    _backup_running: bool = field(default=False, init=False)
    _current_file: BackupFile = field(default=None, init=False)

    cache: dict = field(default_factory=dict, init=False)
    BZ_DIR: str = field(
        default="/Library/Backblaze.bzpkg/bzdata/bzbackup/bzdatacenter/", init=False
    )

    def __post_init__(self):
        self._multi_log = MultiLogger("ToDoFiles", terminal=True)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Creating ToDoFiles")
        self.debug = DevDebug()

        self._file_dict = dict()
        self._file_list = list()

        self._read()
        self._reread_file_thread = threading.Thread(
            target=self.reread_to_do_list,
            daemon=True,
            name="reread_to_do_list",
        )
        self._reread_file_thread.start()

    def _read(self) -> None:
        """
        This reads the to_do file and stores it in two data structures,
          - a dictionary so that I can find the file, and
          - a list, so that I can see what the next files are

          The structure of the file that I care about are the 6th field, which is the filename,
          and the fifth field, which is the file size.
        :return:
        """

        self._todo_file_name = self.get_to_do_file()

        with Lock.DB_LOCK:
            file = Path(self._todo_file_name)
            stat = file.stat()
            self._file_modification_time = stat.st_mtime
            with open(file, "r") as tdf:
                list_index = 0
                for todo_line in tdf:
                    todo_fields = todo_line.strip().split("\t")
                    todo_filename = Path(todo_fields[5])
                    if self.exists(todo_filename):
                        continue

                    todo_file_size = int(todo_fields[4])
                    backup = BackupFile(todo_filename, todo_file_size, list_index)
                    if todo_file_size > Configuration.default_chunk_size:
                        backup.chunks_total = int(
                            todo_file_size / Configuration.default_chunk_size
                        )
                        backup.large_file = True
                    self._file_list.append(backup)
                    self._file_dict[str(todo_filename)] = backup

                    list_index += 1
            self._backup_running = True
            if self.qt is not None:
                self.qt.result_data.layoutChanged.emit()

    def reread_to_do_list(self):
        while True:
            time.sleep(60.0)  # Check the file every minute
            try:
                file = Path(self._todo_file_name)
                stat = file.stat()
            except FileNotFoundError:
                self._multi_log.log("Backup Complete")
                self._backup_running = False
                self._file_list.clear()
                self._file_dict.clear()
                self._todo_file_name = self.get_to_do_file()
                file = Path(self._todo_file_name)
                stat = file.stat()

            if self._file_modification_time != stat.st_mtime:
                self._multi_log.log("To Do file changed, rereading")
                self._read()

    def get_to_do_file(self) -> str:
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
    def current_file(self) -> BackupFile:
        with Lock.DB_LOCK:
            return self._current_file

    @current_file.setter
    def current_file(self, value: BackupFile) -> None:
        with Lock.DB_LOCK:
            self._current_file = value

    @property
    def file_list(self) -> list[BackupFile]:
        return self._file_list

    def get_file(self, filename: str) -> Optional[BackupFile]:
        return self._file_dict.get(filename)

    def exists(self, filename) -> bool:
        """
        Returns whether the file is in the list
        :param filename:
        :return:
        """
        return filename in self._file_dict

    def get_index(self, filename) -> int:
        if filename in self._file_dict:
            return self._file_dict[filename].list_index
        else:
            raise NotFound

    def completed(self, filename: str) -> None:
        """
        Mark a file as completed

        :param filename:
        :return:
        """
        completed_file: BackupFile = self.get_file(filename)
        if completed_file is None:
            raise CompletedFileNotFound

        # invalidate the parts of the cache we care about
        for key in [
            "remaining_files",
            "remaining_size",
            "completed_file_count",
            "completed_size",
        ]:
            try:
                del self.cache[key]
            except KeyError:
                pass

        with Lock.DB_LOCK:
            completed_file.completed = True
            completed_file.end_time = datetime.now()
            self.completed_files.append(completed_file)

            # Define the color based on whether it is deduped or not
            # TODO: Should this color selection move to the model?
            if completed_file.is_deduped:
                completed_file.row_color = QColor("orange")

        if self.qt is not None:
            self.qt.result_data.layoutChanged.emit()

    def add_file(
        self,
        filename: Path,
        is_chunk: bool = False,
        timestamp: datetime = datetime.now(),
    ):
        if not self.exists(str(filename)):
            # invalidate the cache
            self.cache = dict()

            with Lock.DB_LOCK:
                list_index = len(self.file_list)
                try:
                    _stat = filename.stat()
                    file_size = _stat.st_size
                except:
                    file_size = 0

                backup_file = BackupFile(
                    filename,
                    file_size,
                    list_index,
                    timestamp=timestamp,
                )

                # file_size > self.default_chunk_size:
                # this is the size of the backblaze chunks
                if is_chunk:
                    backup_file.chunks_total = int(
                        file_size / Configuration.default_chunk_size
                    )
                    backup_file.large_file = True

                self._file_list.append(backup_file)
                self._file_dict[str(filename)] = backup_file

    def get_remaining_files(
        self, start_index: int = 0, number_of_rows: int = 0
    ) -> list:
        start_index += 1
        count_of_rows = 0
        with Lock.DB_LOCK:
            result_list = []
            for item in self._file_list[start_index:]:  # type: BackupFile
                if not item.completed:
                    count_of_rows += 1
                    if count_of_rows > number_of_rows:
                        break
                    result_list.append(item)

            return result_list

    @property
    def previous_files(self) -> list:
        result = [
            backup_file for backup_file in self._file_list if backup_file.previous_run
        ]
        return result

    @property
    def completed_files(self) -> list:
        result = [
            backup_file
            for backup_file in self._file_list
            if backup_file.completed and backup_file.previous_run
        ]
        return result

    @property
    def remaining_files(self) -> list:
        result = [
            backup_file
            for backup_file in self._file_list
            if not backup_file.completed and not backup_file.previous_run
        ]
        return result

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
        starting_index = 0
        counter = 1
        with Lock.DB_LOCK:
            if filename is not None:
                starting_index = self._file_dict[filename].list_index

            result_list = []
            for item in self._file_list[starting_index:]:
                if not item.completed:
                    result_list.append(item)
                    counter += 1
                    if counter > count:
                        break

            return result_list

    @property
    def backup_running(self) -> bool:
        return self._backup_running

    @property
    def remaining_size(self) -> int:
        cached = self.cache.get("remaining_size")
        if cached:
            return cached

        with Lock.DB_LOCK:
            size = sum(
                backup_file.file_size
                for backup_file in self._file_list
                if not backup_file.completed
            )
            self.cache["remaining_size"] = size
            return size

    @property
    def remaining_files(self) -> int:
        cached = self.cache.get("remaining_files")
        if cached:
            return cached

        with Lock.DB_LOCK:
            files = sum(
                1 for backup_file in self._file_list if not backup_file.completed
            )
            self.cache["remaining_files"] = files
            return files

    def _completed_size(
        self, _transmitted_size: bool = True, _deduped_size: bool = True
    ) -> int:
        with Lock.DB_LOCK:
            size = sum(
                backup_file.file_size
                for backup_file in self._file_list
                if backup_file.completed and not backup_file.previous_run
            )

            if _deduped_size:
                size += sum(
                    len(backup_file.chunks_deduped) * Configuration.default_chunk_size
                    for backup_file in self._file_list
                    if backup_file.large_file
                    and backup_file.completed
                    and not backup_file.previous_run
                )

            if _transmitted_size:
                size += sum(
                    len(backup_file.chunks_transmitted)
                    * Configuration.default_chunk_size
                    for backup_file in self._file_list
                    if backup_file.large_file
                    and backup_file.completed
                    and not backup_file.previous_run
                )

            return size

    @property
    def completed_size(self) -> int:
        cached = self.cache.get("completed_size")
        if cached:
            return cached

        size = self._completed_size(_transmitted_size=True, _deduped_size=True)
        self.cache["completed_size"] = size
        return size

    @property
    def transmitted_size(self) -> int:
        cached = self.cache.get("transmitted_size")
        if cached:
            return cached

        size = self._completed_size(_transmitted_size=True, _deduped_size=False)
        self.cache["transmitted_size"] = size
        return size

    @property
    def duplicate_size(self) -> int:
        cached = self.cache.get("transmitted_size")
        if cached:
            return cached

        size = self._completed_size(_transmitted_size=False, _deduped_size=True)
        self.cache["duplicate_size"] = size
        return size

    @property
    def completed_file_count(self) -> int:
        cached = self.cache.get("completed_file_count")
        if cached:
            return cached

        with Lock.DB_LOCK:
            files = sum(
                1
                for backup_file in self._file_list
                if backup_file.completed and not backup_file.previous_run
            )

        self.cache["completed_file_count"] = files
        return files

    @property
    def total_size(self) -> int:
        cached = self.cache.get("total_size")
        if cached:
            return cached

        with Lock.DB_LOCK:
            size = sum(
                backup_file.file_size
                for backup_file in self._file_list
                if not backup_file.previous_run
            )

        self.cache["total_size"] = size
        return size

    @property
    def total_file_count(self) -> int:
        with Lock.DB_LOCK:
            return sum(
                1 for backup_file in self._file_list if not backup_file.previous_run
            )

    @property
    def duplicate_file_count(self) -> int:
        cached = self.cache.get("duplicate_file_count")
        if cached:
            return cached

        with Lock.DB_LOCK:
            files = sum(
                1
                for backup_file in self._file_list
                if backup_file.is_deduped and not backup_file.previous_run
            )
            self.cache["duplicate_file_count"] = files
            return files

    @property
    def transmitted_file_count(self) -> int:
        cached = self.cache.get("transmitted_file_count")
        if cached:
            return cached

        with Lock.DB_LOCK:
            files = sum(
                1
                for backup_file in self._file_list
                if not backup_file.is_deduped
                and backup_file.completed
                and not backup_file.previous_run
            )
            self.cache["transmitted_file_count"] = files
            return files
