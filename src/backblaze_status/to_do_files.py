import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PyQt6.QtGui import QColor

from .backup_file import BackupFile
from .backup_file_list import BackupFileList
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

    # An instance of the QTBackupStatus
    qt: "QTBackupStatus" = field(default=None, init=True)

    # These two hold the list of to do files. The _file_list is a list in order,
    # and the _file_dict contains a dictionary of the files by file_name. The
    # BackupFile class has a pointer to the list, so that it can be retrieved that
    # way as well.

    _to_do_file_list: BackupFileList = field(default_factory=BackupFileList, init=False)

    # The _completed_files class contains the list of completed files
    _completed_file_list: BackupFileList = field(
        default_factory=BackupFileList, init=False
    )

    _invalid_file_list: BackupFileList = field(
        default_factory=BackupFileList, init=False
    )

    # Storage for the modification time of the current to do file
    _file_modification_time: float = field(default=0.0, init=False)

    # Flag for if the backup is currently running
    _backup_running: bool = field(default=False, init=False)

    # The current file that is being backed up
    _current_file: BackupFile = field(default=None, init=False)

    # The current run
    _current_run: int = 1

    # Storage for the current to_do file
    _todo_file_name: str = field(default_factory=str, init=False)

    # To save processing time, this is a cache for values so they don't need to be
    # recalculated each time
    cache: dict = field(default_factory=dict, init=False)

    # The directory where the to_do files live
    BZ_DIR: str = field(
        default="/Library/Backblaze.bzpkg/bzdata/bzbackup/bzdatacenter/", init=False
    )

    def __post_init__(self):
        # Set up the logger and debugging
        self._multi_log = MultiLogger("ToDoFiles", terminal=True)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Creating ToDoFiles")
        self.debug = DevDebug()

        if self.qt:
            self.qt.signals.files_updated.connect(lambda: self.cache.clear())

        # Do the initial read of the to_do file
        self._read()

        # Start a thread that checks to see if the to_do file has changed, and if it
        # has, re-read it
        self._reread_file_thread = threading.Thread(
            target=self.reread_to_do_list,
            daemon=True,
            name="reread_to_do_list",
        )
        self._reread_file_thread.start()

    def __len__(self) -> int:
        return len(self._to_do_file_list.file_list)

    def __getitem__(self, index) -> BackupFile:
        if isinstance(index, int):
            return self._to_do_file_list.file_list[index]
        elif isinstance(index, str):
            return self._to_do_file_list.file_dict.get(index)
        else:
            raise TypeError("Invalid argument type")

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
                for todo_line in tdf:
                    todo_fields = todo_line.strip().split("\t")
                    todo_filename = Path(todo_fields[5])
                    if self.exists(todo_filename):
                        continue

                    todo_file_size = int(todo_fields[4])
                    backup = BackupFile(todo_filename, todo_file_size)
                    if todo_file_size > Configuration.default_chunk_size:
                        backup.chunks_total = int(
                            todo_file_size / Configuration.default_chunk_size
                        )
                        backup.large_file = True
                    self._to_do_file_list.append(backup)

            self._backup_running = True
            if self.qt is not None:
                self.qt.signals.backup_running.emit(True)
                self.qt.signals.files_updated.emit()
                self.qt.result_data.layoutChanged.emit()

    def reread_to_do_list(self):
        """
        Checks to see if there is a new to_do file, and if there is, reread it
        """
        while True:
            time.sleep(60.0)  # Check the file every minute
            if not self._backup_running:
                # If the backup isn't running, check to see if there is a to_do file.
                # If there is not, then loop and wait till there is
                self._todo_file_name = self.get_to_do_file()
                if self._todo_file_name is not None:
                    # If there is a new to_do file, then read it, after incrementing the
                    # run number
                    self._current_run += 1
                    self._read()
                    self._backup_running = True
                    if self.qt:
                        self.qt.signals.backup_running.emit(True)
                continue

            try:
                file = Path(self._todo_file_name)
                stat = file.stat()
            except FileNotFoundError:
                # If the backup is complete, then clear out the to_do list
                self._multi_log.log("Backup Complete")
                self._backup_running = False
                self._to_do_file_list.clear()
                self.cache.clear()
                if self.qt:
                    self.qt.signals.backup_running.emit(False)
                    self.qt.signals.files_updated.emit()
                continue

            # Check to see if the modification time has changed. If it has,
            # then reread the file. I'm not sure if this is really necessary. Check
            # the logs for it
            if self._file_modification_time != stat.st_mtime:
                self._multi_log.log("To Do file changed, rereading")
                self._read()

    def get_to_do_file(self) -> str:
        """
        Get the name of the current to_do file
        """
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
                time.sleep(60)

            else:
                break
        return to_do_file

    @property
    def current_file(self) -> BackupFile:
        """
        Return the file currently being backed up
        """
        return self._current_file

    @current_file.setter
    def current_file(self, value: BackupFile) -> None:
        """
        Set the file that is currently being backed up
        """
        with Lock.DB_LOCK:
            self._current_file = value
            # while self._to_do_file_list.file_list[0] != self._current_file:
            #     item: BackupFile = self._to_do_file_list[0]
            #     item.completed_run = self._current_run
            #     self._invalid_file_list.append(item)
            #     self._to_do_file_list.remove(item)

    @property
    def to_do_file_list(self) -> BackupFileList:  #  list[BackupFile]:
        """
        Return all the files that are remaining on the to_do list
        """
        # return self._to_do_file_list.file_list
        return self._to_do_file_list

    def get_file(self, filename: str) -> Optional[BackupFile]:
        """
        Get the backup file with the given filename
        """
        return self._to_do_file_list.get(filename)

    def exists(self, filename) -> bool:
        """
        Returns whether the file is in the list
        :param filename:
        :return:
        """
        return filename in self._to_do_file_list.file_dict

    # No one is using this function
    # def get_index(self, filename) -> int:
    #     if filename in self._file_dict:
    #         return self._file_dict[filename].list_index
    #     else:
    #         raise NotFound

    def mark_completed(self, filename: str) -> None:
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
            completed_file.completed_run = self._current_run

            # Move the completed items to the completed file list

            self._completed_file_list.append(completed_file)
            # self._to_do_file_list.remove(completed_file)

            # Define the color based on whether it is deduped or not
            # TODO: Should this color selection move to the model?
            if completed_file.is_deduped:
                completed_file.row_color = QColor("orange")

        if self.qt is not None:
            self.qt.signals.files_updated.emit()
            self.qt.result_data.layoutChanged.emit()

    def add_file(
        self,
        filename: Path,
        is_chunk: bool = False,
        timestamp: datetime = datetime.now(),
    ):
        """
        Add a file that isn't on the to_do list
        """
        if not self.exists(str(filename)):
            # invalidate the cache
            self.cache = dict()

            with Lock.DB_LOCK:
                try:
                    _stat = filename.stat()
                    file_size = _stat.st_size
                except:
                    file_size = 0

                backup_file = BackupFile(
                    filename,
                    file_size,
                    timestamp=timestamp,
                )

                # file_size > self.default_chunk_size:
                # this is the size of the backblaze chunks
                if is_chunk:
                    backup_file.chunks_total = int(
                        file_size / Configuration.default_chunk_size
                    )
                    backup_file.large_file = True

                self._to_do_file_list.append(backup_file)

    # This doesn't seem to be being used
    # def get_remaining_files(
    #     self, start_index: int = 0, number_of_rows: int = 0
    # ) -> list:
    #     start_index += 1
    #     count_of_rows = 0
    #     with Lock.DB_LOCK:
    #         result_list = []
    #         for item in self._file_list[start_index:]:  # type: BackupFile
    #             if not item.completed:
    #                 count_of_rows += 1
    #                 if count_of_rows > number_of_rows:
    #                     break
    #                 result_list.append(item)
    #
    #         return result_list

    # @property
    # def previous_files(self) -> list:
    #     result = [
    #         backup_file for backup_file in self._file_list if backup_file.previous_run
    #     ]
    #     return result

    @property
    def completed_files(self) -> list:
        return self._completed_file_list.file_list

    # This is not being used
    # def todo_files(self, count=1000000000, filename: str = None):
    #     """
    #     Retrieve the next N filenames. If no filename is specified, just start from
    #     the beginning of the list. If a filename is specified, start from the one
    #     after that.
    #
    #     This is a generator function.
    #
    #     :param count:
    #     :param filename:
    #     :return:
    #     """
    #     starting_index = 0
    #     counter = 1
    #     with Lock.DB_LOCK:
    #         if filename is not None:
    #             starting_index = self._file_dict[filename].list_index
    #
    #         result_list = []
    #         for item in self._file_list[starting_index:]:
    #             if not item.completed:
    #                 result_list.append(item)
    #                 counter += 1
    #                 if counter > count:
    #                     break
    #
    #         return result_list

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
                backup_file.file_size for backup_file in self._to_do_file_list.file_list
            )
            self.cache["remaining_size"] = size
            return size

    # @property
    # def remaining_files(self) -> list:
    #     return self._file_list

    @property
    def completed_size(self) -> int:
        cached = self.cache.get("completed_size")
        if cached:
            return cached

        if self._to_do_file_list is not None and self.current_file is not None:
            current_index = self._to_do_file_list.index(
                str(self.current_file.file_name)
            )
            size = sum(
                [
                    backup_file.file_size
                    for backup_file in self._to_do_file_list.file_list[
                        : current_index - 1
                    ]
                ]
            )
            return size

        size = sum(
            backup_file.file_size
            for backup_file in self._completed_file_list.file_list
            if backup_file.completed_run == self._current_run
        )

        size += sum(
            len(backup_file.chunks_deduped) * Configuration.default_chunk_size
            for backup_file in self._completed_file_list.file_list
            if backup_file.large_file and backup_file.completed_run == self._current_run
        )

        size += sum(
            len(backup_file.chunks_transmitted) * Configuration.default_chunk_size
            for backup_file in self._completed_file_list.file_list
            if backup_file.large_file and backup_file.completed_run == self._current_run
        )
        self.cache["completed_size"] = size
        return size

    @property
    def transmitted_size(self) -> int:
        cached = self.cache.get("transmitted_size")
        if cached:
            return cached

        size = sum(
            backup_file.file_size
            for backup_file in self._completed_file_list.file_list
            if backup_file.completed_run == self._current_run
            and not backup_file.is_deduped
        )

        size += sum(
            len(backup_file.chunks_transmitted) * Configuration.default_chunk_size
            for backup_file in self._completed_file_list.file_list
            if backup_file.large_file and backup_file.completed_run == self._current_run
        )

        self.cache["transmitted_size"] = size
        return size

    @property
    def duplicate_size(self) -> int:
        cached = self.cache.get("duplicate_size")
        if cached:
            return cached

        size = sum(
            backup_file.file_size
            for backup_file in self._completed_file_list.file_list
            if backup_file.completed_run == self._current_run and backup_file.is_deduped
        )

        size += sum(
            len(backup_file.chunks_deduped) * Configuration.default_chunk_size
            for backup_file in self._completed_file_list.file_list
            if backup_file.large_file and backup_file.completed_run == self._current_run
        )
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
                for backup_file in self._completed_file_list.file_list
                if backup_file.completed_run == self._current_run
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
                backup_file.file_size for backup_file in self._to_do_file_list.file_list
            )
            size += sum(
                backup_file.file_size
                for backup_file in self._completed_file_list
                if backup_file.completed_run == self._current_run
            )

        self.cache["total_size"] = size
        return size

    @property
    def total_file_count(self) -> int:
        cached = self.cache.get("total_file_count")
        if cached:
            return cached

        with Lock.DB_LOCK:
            file_count = len(self._to_do_file_list.file_list)
            file_count += sum(
                1
                for backup_file in self._completed_file_list
                if backup_file.completed_run == self._current_run
            )
            self.cache["total_file_count"] = file_count
            return file_count

    @property
    def duplicate_file_count(self) -> int:
        cached = self.cache.get("duplicate_file_count")
        if cached:
            return cached

        with Lock.DB_LOCK:
            files = sum(
                1
                for backup_file in self._completed_file_list.file_list
                if backup_file.is_deduped
                and backup_file.completed_run == self._current_run
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
                for backup_file in self._completed_file_list.file_list
                if not backup_file.is_deduped
                and backup_file.completed_run == self._current_run
            )
            self.cache["transmitted_file_count"] = files
            return files

    @property
    def completed_file_list(self) -> BackupFileList:
        return self._completed_file_list

    @property
    def invalid_file_list(self) -> BackupFileList:
        return self._invalid_file_list

    @property
    def current_run(self) -> int:
        return self._current_run
