import os
import threading
import time
from dataclasses import field
from datetime import datetime
from pathlib import Path
from typing import Optional
from icecream import ic

from PyQt6.QtCore import QTimer, QReadWriteLock, QObject, pyqtSignal, pyqtSlot, QThread

from .backup_file import BackupFile
from .backup_file_list import BackupFileList
from .configuration import Configuration
from .dev_debug import DevDebug
from .exceptions import CompletedFileNotFound
from .locks import Lock
from .utils import MultiLogger, file_size_string


def debug_print(message: str):
    thread_name = threading.current_thread().name
    date = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} <{thread_name}>'

    print(f"{date} {message}")


class NotFound(Exception):
    pass


class ToDoFiles(QObject):
    """
    Class to store the list and status of To Do files
    """

    # Signals

    signal_mark_completed = pyqtSignal(str)
    signal_add_file = pyqtSignal(str, bool)

    # The directory where the to_do files live
    BZ_DIR: str = "/Library/Backblaze.bzpkg/bzdata/bzbackup/bzdatacenter/"

    def __init__(self, backup_status):
        from .qt_backup_status import QTBackupStatus

        super(ToDoFiles, self).__init__()

        # Set up the logger and debugging
        self._multi_log = MultiLogger("ToDoFiles", terminal=True)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Creating ToDoFiles")
        self.debug = DevDebug()

        # An instance of the QTBackupStatus
        self.backup_status: "QTBackupStatus" = backup_status

        # Lock object
        self.lock: QReadWriteLock = QReadWriteLock(
            recursionMode=QReadWriteLock.RecursionMode.Recursive
        )

        # These two hold the list of to do files. The _file_list is a list in order,
        # and the _file_dict contains a dictionary of the files by file_name. The
        # BackupFile class has a pointer to the list, so that it can be retrieved that
        # way as well.

        self._to_do_file_list: BackupFileList = BackupFileList()

        # The _completed_files class contains the list of completed files
        self._completed_file_list: BackupFileList = BackupFileList()

        # Storage for the modification time of the current to do file
        self._file_modification_time: float = 0.0

        # Flag for if the backup is currently running
        self._backup_running: bool = False

        # The current file that is being backed up
        self._current_file: Optional[BackupFile] = None

        # The current run
        self._current_run: int = 1

        # Storage for the current to_do file
        self._to_do_file_name: str = ""

        # The first file I process off the to do list. This is so that I can accurately
        # assess the rate

        self._starting_file: Optional[BackupFile] = None
        self._starting_index: int = 0

        self._reread_file_timer: Optional[QTimer] = None

    def run(self):
        threading.current_thread().name = QThread.currentThread().objectName()

        # Setup signals

        self.signal_add_file.connect(self._add_file)
        self.signal_mark_completed.connect(self._mark_completed)

        # Do the initial read of the to_do file
        self._read()

        # Start a thread that checks to see if the to_do file has changed, and if it
        # has, re-read it
        self._reread_file_timer = QTimer(self)
        self._reread_file_timer.timeout.connect(self.reread_to_do_list)
        self._reread_file_timer.start(60000)  # Fire every 60 seconds

        self.backup_status.signals.to_do_available.emit()

    def __len__(self) -> int:
        return len(self._to_do_file_list.file_list)

    def __getitem__(self, index) -> BackupFile:
        if isinstance(index, int):
            return self._to_do_file_list.file_list[index]
        elif isinstance(index, str):
            return self._to_do_file_list.file_dict.get(index)
        else:
            raise TypeError("Invalid argument type")

    def _read(self, read_existing_file: bool = False) -> None:
        """
        This reads the to_do file and stores it in two data structures,
          - a dictionary so that I can find the file, and
          - a list, so that I can see what the next files are

          The structure of the file that I care about are the 6th field, which is the filename,
          and the fifth field, which is the file size.
        :return:
        """

        self._to_do_file_name = self.get_to_do_file()

        with Lock.DB_LOCK:
            try:
                file = Path(self._to_do_file_name)
                stat = file.stat()
                self._file_modification_time = stat.st_mtime
            except FileNotFoundError:
                self._mark_backup_not_running()
                self._file_modification_time = 0
                return

            count = 0
            try:
                with open(file, "r") as tdf:
                    for todo_line in tdf:
                        count += 1
                        todo_fields = todo_line.strip().split("\t")
                        todo_filename = Path(todo_fields[5])
                        if self.exists(str(todo_filename)):
                            continue

                        todo_file_size = int(todo_fields[4])

                        backup = BackupFile(todo_filename, todo_file_size)
                        if todo_file_size > Configuration.default_chunk_size:
                            backup.total_chunk_count = int(
                                todo_file_size / Configuration.default_chunk_size
                            )
                            backup.is_large_file = True
                        self._to_do_file_list.append(backup)

                self._backup_running = True
                if read_existing_file:
                    self._multi_log.log(
                        f"Added {count:,} lines from To Do file after"
                        f" re-reading {self._to_do_file_name}"
                    )
                else:
                    self._multi_log.log(
                        f"Read {count:,} lines from To Do file"
                        f" {self._to_do_file_name}"
                    )
                self.backup_status.signals.backup_running.emit(True)
                self.backup_status.signals.files_updated.emit()
                self.backup_status.result_data.layoutChanged.emit()
            except:
                pass

    def reread_to_do_list(self):
        """
        Checks to see if there is a new to_do file, and if there is, reread it
        """
        self._to_do_file_name = self.get_to_do_file()
        if not self.backup_running and self._to_do_file_name is not None:
            # If the backup is not running already, and there is a new to_do
            # file, then read it after incrementing the run number
            self._current_run += 1
            self._read()
            return

        if not self.backup_running and self._to_do_file_name is None:
            self._multi_log.log(
                f"Backup not running. Waiting for 1 minute and trying again ..."
            )
            return

        # If the backup is running and the to_do file name is not None, then see
        # if we need to re-read the file because there is new data in it
        if self.backup_running and self._to_do_file_name is not None:
            try:
                file = Path(self._to_do_file_name)
                stat = file.stat()
            except FileNotFoundError:
                # If there is no file, then the backup is complete, then mark it
                # as complete
                if self.backup_running:
                    self._mark_backup_not_running()
                return

            # Check to see if the modification time has changed. If it has,
            # then reread the file.

            if self._file_modification_time != stat.st_mtime:
                self._multi_log.log("To Do file changed, rereading")
                self._read(read_existing_file=True)

    def _mark_backup_not_running(self):
        self._multi_log.log("Backup Complete")
        self._backup_running = False
        self._to_do_file_list.clear()
        self.current_file = None
        self._starting_file = None
        self._starting_index = 0
        self.backup_status.signals.backup_running.emit(False)
        self.backup_status.signals.files_updated.emit()

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
        self.lock.lockForWrite()
        self._current_file = value
        self.lock.unlock()

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
        self.lock.lockForRead()
        result = self._to_do_file_list.get(filename)
        self.lock.unlock()
        return result

    def exists(self, filename: str) -> bool:
        """
        Returns whether the file is in the list
        :param filename:
        :return:
        """

        self.lock.lockForRead()
        result = filename in self._to_do_file_list.file_dict
        self.lock.unlock()

        return result

    # No one is using this function
    # def get_index(self, filename) -> int:
    #     if filename in self._file_dict:
    #         return self._file_dict[filename].list_index
    #     else:
    #         raise NotFound

    def mark_completed(self, filename: str) -> None:
        self.signal_mark_completed.emit(filename)
        debug_print(f"emitted mark_completed({filename})")

    @pyqtSlot(str)
    def _mark_completed(self, filename: str) -> None:
        """
        Mark a file as completed

        :param filename:
        :return:
        """
        debug_print(f"received mark_completed({filename})")

        completed_file: BackupFile = self.get_file(filename)
        if completed_file is None:
            raise CompletedFileNotFound

        if self._starting_file is None:
            self._starting_file = completed_file
            self._starting_index = self._to_do_file_list.file_list.index(completed_file)

        self.lock.lockForWrite()

        completed_file.completed = True
        completed_file.end_time = datetime.now()
        completed_file.completed_run = self._current_run

        if completed_file.start_time is not None:
            completion_time = (
                completed_file.end_time - completed_file.start_time
            ).seconds
            if completion_time == 0:
                completed_file.rate = ""
            else:
                completed_file.rate = (
                    f"{file_size_string(completed_file.file_size / completion_time)}"
                    f" / sec"
                )

        if completed_file.is_large_file:
            chunk_duplicate_percentage = (
                completed_file.deduped_count / completed_file.total_chunk_count
            )
            if chunk_duplicate_percentage > 0.75:
                completed_file.is_deduped_chunks = True

        # Put completed items on the completed file list

        self._completed_file_list.append(completed_file)
        self.lock.unlock()

        self.backup_status.signals.calculate_progress.emit()
        self.backup_status.signals.files_updated.emit()
        self.backup_status.reposition_table()

    def add_file(self, filename: str, is_chunk: bool = False):
        self.signal_add_file.emit(filename, is_chunk)

    @pyqtSlot(str, bool)
    def _add_file(
        self,
        filename: str,
        is_chunk: bool = False,
    ):
        """
        Add a file that isn't on the to_do list
        """
        if not self.exists(filename):
            filename_path = Path(filename)
            self.lock.lockForWrite()
            try:
                _stat = filename_path.stat()
                file_size = _stat.st_size
            except:
                file_size = 0

            backup_file = BackupFile(
                filename_path,
                file_size,
            )

            # file_size > self.default_chunk_size:
            # this is the size of the backblaze chunks
            if is_chunk:
                backup_file.total_chunk_count = int(
                    file_size / Configuration.default_chunk_size
                )
                backup_file.is_large_file = True

            self._to_do_file_list.append(backup_file)
            self.lock.unlock()

    @property
    def completed_files(self) -> list:
        return self._completed_file_list.file_list

    @property
    def backup_running(self) -> bool:
        return self._backup_running

    @property
    def remaining_size(self) -> int:
        to_do_index = self._get_to_do_index()
        size = sum(
            backup_file.file_size
            for backup_file in self._to_do_file_list.file_list[to_do_index:]
        )
        return size

    def remaining_file_count(self) -> int:
        to_do_index = self._get_to_do_index()
        files = len(self._to_do_file_list.file_list[to_do_index:])
        return files

    # @property
    # def remaining_files(self) -> list:
    #     return self._file_list

    def _get_to_do_index(self):
        if self.current_file is not None:
            return self._to_do_file_list.index(str(self.current_file.file_name))

        if len(self._completed_file_list) == 0:
            return 0

        last_completed: BackupFile = self._completed_file_list[-1]
        try:
            index = self._to_do_file_list.file_list.index(last_completed)
            return index + 1
        except ValueError:
            return 0

    @property
    def total_size(self) -> int:
        with Lock.DB_LOCK:
            size = sum(
                backup_file.file_size for backup_file in self._to_do_file_list.file_list
            )

        return size

    @property
    def total_large_size(self) -> int:
        with Lock.DB_LOCK:
            size = sum(
                backup_file.file_size
                for backup_file in self._to_do_file_list.file_list
                if backup_file.is_large_file
            )

        return size

    @property
    def total_current_large_size(self) -> int:
        with Lock.DB_LOCK:
            size = sum(
                backup_file.file_size
                for backup_file in self._to_do_file_list.file_list[
                    self._starting_index :
                ]
                if backup_file.is_large_file
            )

        return size

    @property
    def total_regular_size(self) -> int:
        with Lock.DB_LOCK:
            size = sum(
                backup_file.file_size
                for backup_file in self._to_do_file_list.file_list
                if not backup_file.is_large_file
            )

        return size

    @property
    def total_current_regular_size(self) -> int:
        with Lock.DB_LOCK:
            size = sum(
                backup_file.file_size
                for backup_file in self._to_do_file_list.file_list[
                    self._starting_index :
                ]
                if not backup_file.is_large_file
            )

        return size

    @property
    def total_file_count(self) -> int:
        with Lock.DB_LOCK:
            file_count = len(self._to_do_file_list.file_list)
            return file_count

    @property
    def total_large_file_count(self) -> int:
        files = sum(
            [
                1
                for backup_file in self._to_do_file_list.file_list
                if backup_file.is_large_file
            ]
        )
        return files

    @property
    def total_current_large_file_count(self) -> int:
        files = sum(
            [
                1
                for backup_file in self._to_do_file_list.file_list[
                    self._starting_index :
                ]
                if backup_file.is_large_file
            ]
        )
        return files

    @property
    def total_chunk_count(self) -> int:
        chunks = sum(
            backup_file.total_chunk_count
            for backup_file in self._to_do_file_list.file_list
        )
        return chunks

    @property
    def total_current_chunk_count(self) -> int:
        chunks = sum(
            backup_file.total_chunk_count
            for backup_file in self._to_do_file_list.file_list[self._starting_index :]
        )
        return chunks

    @property
    def total_regular_file_count(self) -> int:
        return sum(
            [
                1
                for backup_file in self._to_do_file_list.file_list
                if not backup_file.is_large_file
            ]
        )

    @property
    def total_current_regular_file_count(self) -> int:
        files = sum(
            [
                1
                for backup_file in self._to_do_file_list.file_list[
                    self._starting_index :
                ]
                if not backup_file.is_large_file
            ]
        )
        return files

    @property
    def completed_file_count(self) -> int:
        if self._to_do_file_list is None:
            return 0

        to_do_index = self._get_to_do_index()
        return to_do_index + 1

    @property
    def completed_chunk_count(self) -> int:
        if self._completed_file_list is None:
            return 0

        chunks = sum(
            len(backup_file.transmitted_chunks) + len(backup_file.deduped_chunks)
            for backup_file in self._completed_file_list.file_list
            if backup_file.is_large_file
            and backup_file.completed_run == self._current_run
        )
        return chunks

    @property
    def completed_size(self) -> int:
        if self._completed_file_list is None:
            return 0

        size = sum(
            backup_file.file_size
            for backup_file in self._completed_file_list.file_list
            if backup_file.completed_run == self._current_run
        )
        return size

    @property
    def processed_size(self) -> int:
        if self._to_do_file_list is None:
            return 0

        to_do_index = self._get_to_do_index()
        size = sum(
            backup_file.file_size
            for backup_file in self._to_do_file_list.file_list[0:to_do_index]
        )
        return size

    @property
    def processed_file_count(self) -> int:
        if self._to_do_file_list is None:
            return 0

        to_do_index = self._get_to_do_index()
        return to_do_index + 1

    @property
    def completed_chunk_size(self) -> int:
        if self._completed_file_list is None:
            return 0

        size = sum(
            (len(backup_file.transmitted_chunks) * Configuration.default_chunk_size)
            + (len(backup_file.deduped_chunks) * Configuration.default_chunk_size)
            for backup_file in self._completed_file_list.file_list
            if backup_file.is_large_file
            and backup_file.completed_run == self._current_run
        )
        return size

    @property
    def transmitted_size(self) -> int:
        return self.transmitted_file_size + self.transmitted_chunk_size

    @property
    def transmitted_file_size(self) -> int:
        if self._completed_file_list is None:
            return 0

        size = sum(
            backup_file.file_size
            for backup_file in self._completed_file_list.file_list
            if backup_file.completed_run == self._current_run
            and not backup_file.is_large_file
            and not backup_file.is_deduped
        )
        return size

    @property
    def transmitted_chunk_size(self) -> int:
        if self._completed_file_list is None:
            return 0

        size = sum(
            len(backup_file.transmitted_chunks) * Configuration.default_chunk_size
            for backup_file in self._completed_file_list.file_list
            if backup_file.is_large_file
            and backup_file.completed_run == self._current_run
        )

        return size

    @property
    def transmitted_file_count(self) -> int:
        if self._completed_file_list is None:
            return 0

        files = sum(
            1
            for backup_file in self._completed_file_list.file_list
            if not backup_file.is_deduped
            and backup_file.completed_run == self._current_run
            and not backup_file.is_large_file
        )
        return files

    @property
    def transmitted_chunk_count(self) -> int:
        if self._completed_file_list is None:
            return 0

        files = sum(
            len(backup_file.transmitted_chunks)
            for backup_file in self._completed_file_list.file_list
            if not backup_file.is_deduped
            and backup_file.completed_run == self._current_run
        )
        return files

    @property
    def duplicate_size(self) -> int:
        return self.duplicate_file_size + self.duplicate_chunk_size

    @property
    def duplicate_file_size(self) -> int:
        if self._completed_file_list is None:
            return 0

        size = sum(
            backup_file.file_size
            for backup_file in self._completed_file_list.file_list
            if backup_file.completed_run == self._current_run
            and backup_file.is_deduped
            and not backup_file.is_large_file
        )

        return size

    @property
    def duplicate_chunk_size(self) -> int:
        if self._completed_file_list is None:
            return 0

        size = sum(
            len(backup_file.deduped_chunks) * Configuration.default_chunk_size
            for backup_file in self._completed_file_list.file_list
            if backup_file.is_large_file
            and backup_file.completed_run == self._current_run
        )
        return size

    @property
    def duplicate_file_count(self) -> int:
        if self._completed_file_list is None:
            return 0

        files = sum(
            1
            for backup_file in self._completed_file_list.file_list
            if backup_file.is_deduped
            and backup_file.completed_run == self._current_run
            and not backup_file.is_large_file
        )
        return files

    @property
    def duplicate_chunk_count(self) -> int:
        if self._completed_file_list is None:
            return 0

        chunks = sum(
            len(backup_file.deduped_chunks)
            for backup_file in self._completed_file_list.file_list
            if backup_file.is_large_file
            and backup_file.completed_run == self._current_run
        )
        return chunks

    @property
    def completed_file_list(self) -> BackupFileList:
        return self._completed_file_list

    @property
    def current_run(self) -> int:
        return self._current_run

    @property
    def starting_index(self) -> int:
        return self._starting_index
