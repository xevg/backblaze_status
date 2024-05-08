import logging
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from PyQt6.QtCore import QTimer, QReadWriteLock, QObject, pyqtSignal, pyqtSlot, QThread
from pandas import DataFrame

from .configuration import Configuration
from .constants import ToDoColumns, Key, MessageTypes, States
from .current_state import CurrentState
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
    BZ_DIR: str = "/Library/Backblaze.bzpkg/bzdata/bzbackup/bzdatacenter"

    def __init__(self, backup_status):
        from .qt_backup_status import QTBackupStatus

        super(ToDoFiles, self).__init__()

        # Set up the logger and debugging
        self._multi_log = MultiLogger("ToDoFiles", terminal=True)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Creating ToDoFiles")

        # An instance of the QTBackupStatus
        self.backup_status: "QTBackupStatus" = backup_status

        # Lock object
        self.lock: QReadWriteLock = QReadWriteLock(
            recursionMode=QReadWriteLock.RecursionMode.Recursive
        )

        self.to_do_list: Optional[DataFrame] = None

        # The _completed_files class contains the list of completed files
        # self._completed_file_list: BackupFileList = BackupFileList()

        # Storage for the modification time of the current to do file
        self._file_modification_time: float = 0.0

        # The current run
        self._current_run: int = 1

        # Storage for the current to_do file
        self._to_do_file_name: str = ""

        # The first file I process off the to do list. This is so that I can accurately
        # assess the rate

        self._reread_file_timer: Optional[QTimer] = None
        self._stats_timer: Optional[QTimer] = None

        self.first_pass = True

        self.total_files: int = 0
        self.total_bytes: float = 0.0
        self.total_files_to_process: int = 0
        self.total_bytes_to_process: float = 0.0

        self.backup_status.signals.get_messages.connect(self.get_emit_messages)

        CurrentState.StartTime = datetime.now()

        self.previous_file = None

    def run(self):
        threading.current_thread().name = QThread.currentThread().objectName()

        # Setup signals

        # Do the initial read of the to_do file
        self.read()

        # Start a thread that checks to see if the to_do file has changed, and if it
        # has, re-read it

        self._reread_file_timer = QTimer(self)
        self._reread_file_timer.timeout.connect(self.reread_to_do_list)
        self._reread_file_timer.start(60000)  # Fire every 60 seconds

        self.backup_status.signals.to_do_available.emit()

    def __len__(self) -> int:
        if self.to_do_list is None:
            return 0
        else:
            return self.to_do_list.shape[0]

    def read(self, read_existing_file: bool = False) -> None:
        """
        This reads the to_do file and stores it in two data structures,
          - a dictionary so that I can find the file, and
          - a list, so that I can see what the next files are

          The structure of the file that I care about are the 6th field,
          which is the filename, and the fifth field, which is the file size.
        :return:
        """

        self._to_do_file_name = self.get_to_do_file()
        file_index = {}
        with Lock.DB_LOCK:
            try:
                file = Path(self._to_do_file_name)
                stat = file.stat()
                self._file_modification_time = stat.st_mtime
            except FileNotFoundError:
                self._mark_backup_not_running()
                self._file_modification_time = 0
                return

            CurrentState.BackupRunning = True
            self.backup_status.signals.backup_running.emit(True)

            count = -1
            to_do_list = []
            try:
                with open(file, "r") as tdf:
                    for todo_line in tdf:
                        count += 1
                        todo_fields = todo_line.strip().split("\t")
                        todo_filename = todo_fields[5]
                        file_path = Path(todo_filename)
                        try:
                            if not file_path.exists():
                                state = Key.Skipped
                            else:
                                state = Key.Unprocessed
                        except PermissionError:
                            state = Key.Unprocessed
                        # if self.exists(str(todo_filename)):
                        #     continue

                        todo_file_size = int(todo_fields[4])

                        # backup = BackupFile(todo_filename, todo_file_size)
                        total_chunk_count = 0
                        is_large_file = False
                        if todo_file_size > Configuration.default_chunk_size:
                            total_chunk_count = int(
                                todo_file_size / Configuration.default_chunk_size
                            )
                            is_large_file = True
                        to_do_list.append(
                            [
                                count,
                                todo_filename,
                                todo_file_size,
                                is_large_file,
                                pd.NA,  # IsDeduped
                                total_chunk_count,
                                state,  # State
                                None,  # StartTime
                                None,  # EndTime
                                0,  # DedupedBytes
                                set(),  # DedupedChunks,
                                0,  # DedupedChunksCount,
                                0,  # TransmittedBytes,
                                set(),  # TransmittedChunks
                                0,  # TransmittedChunksCount
                                0,  # PreparedBytes
                                set(),  # PreparedChunks
                                0,  # PreparedChunksCount
                            ]
                        )
                        file_index[count] = todo_filename

                self.to_do_list = DataFrame(
                    to_do_list,
                    columns=[
                        ToDoColumns.IndexCount,
                        ToDoColumns.FileName,
                        ToDoColumns.FileSize,
                        ToDoColumns.IsLargeFile,
                        ToDoColumns.IsDeduped,
                        ToDoColumns.ChunkCount,
                        ToDoColumns.State,
                        ToDoColumns.StartTime,
                        ToDoColumns.EndTime,
                        ToDoColumns.DedupedBytes,
                        ToDoColumns.DedupedChunks,
                        ToDoColumns.DedupedChunksCount,
                        ToDoColumns.TransmittedBytes,
                        ToDoColumns.TransmittedChunks,
                        ToDoColumns.TransmittedChunksCount,
                        ToDoColumns.PreparedBytes,
                        ToDoColumns.PreparedChunks,
                        ToDoColumns.PreparedChunksCount,
                    ],
                ).set_index(ToDoColumns.FileName)
                CurrentState.FileIndex = file_index

                # Remove duplicates, keeping only the last one
                self.to_do_list = self.to_do_list[
                    ~self.to_do_list.index.duplicated(keep="last")
                ]

                # if read_existing_file:
                #     self._multi_log.log(
                #         f"Added {count:,} lines from To Do file after"
                #         f" re-reading {self._to_do_file_name}"
                #     )
                # else:
                self._multi_log.log(
                    f"Read {count:,} lines from To Do file" f" {self._to_do_file_name}"
                )
                CurrentState.ToDoList = self.to_do_list.to_dict(orient="index")
                CurrentState.ToDoListLength = len(self.to_do_list.index)

                self.backup_status.signals.backup_running.emit(True)

                self.backup_status.signals.to_do_available.emit()
            except Exception as exp:
                print(exp)
                pass

    def reread_to_do_list(self):
        """
        Checks to see if there is a new to_do file, and if there is, reread it
        """
        self._to_do_file_name = self.get_to_do_file()
        if not CurrentState.BackupRunning and self._to_do_file_name is not None:
            # If the backup is not running already, and there is a new to_do
            # file, then read it after incrementing the run number
            self._current_run += 1
            self.read()
            return

        if not CurrentState.BackupRunning and self._to_do_file_name is None:
            self._multi_log.log(
                f"Backup not running. Waiting for 1 minute and trying again ..."
            )
            return

        # If the backup is running and the to_do file name is not None, then see
        # if we need to re-read the file because there is new data in it
        if CurrentState.BackupRunning and self._to_do_file_name is not None:
            try:
                file = Path(self._to_do_file_name)
                stat = file.stat()
            except FileNotFoundError:
                # If there is no file, then the backup is complete, then mark it
                # as complete
                if CurrentState.BackupRunning:
                    self._mark_backup_not_running()
                return

            # Check to see if the modification time has changed. If it has,
            # then reread the file.

            if self._file_modification_time != stat.st_mtime:
                self._multi_log.log("To Do file changed, rereading")
                self.read(read_existing_file=True)
            else:
                self._multi_log.log("To Do file has not changed")

    @pyqtSlot(dict)
    def get_emit_messages(self, message_data: dict):
        self.process_received_message(message_data)

    def process_received_message(self, message_data: dict) -> None:
        prefix = f"Message Received ({message_data['publish_count']:>8,}):"

        if (
            CurrentState.CurrentFile is None
            and message_data["data"].get(Key.FileName) is not None
        ):
            CurrentState.CurrentFile = message_data["data"][Key.FileName]
            self.post_initialize_to_do_list(CurrentState.CurrentFile)

        match message_data["type"]:

            case MessageTypes.StartNewFile:
                # This lets me know that new file has started, and it is now
                # the current file
                file_name = message_data["data"][Key.FileName]
                start_time = message_data["data"][Key.StartTime]
                self._multi_log.log(
                    f"{prefix} File Started: " f"{file_name}",
                    module=self._module_name,
                )
                self.start_new_file(file_name, start_time)

            case MessageTypes.Completed:
                # When the files are completed, mark it as completed
                file_name = message_data["data"][Key.FileName]
                end_time = message_data["data"][Key.EndTime]
                file_size = CurrentState.ToDoList[file_name][ToDoColumns.FileSize]

                self._multi_log.log(
                    f"{prefix} File Completed: "
                    f"{file_name} ({file_size_string(file_size)})",
                    module=self._module_name,
                    # level=logging.DEBUG,
                )
                self.complete_file(file_name, end_time)

            case MessageTypes.IsDeduped:
                # When the files are completed, mark it as completed
                file_name = message_data["data"][Key.FileName]
                self._multi_log.log(
                    f"{prefix} File Deduped: {file_name}",
                    module=self._module_name,
                    # level=logging.DEBUG,
                )
                self.set_value(file_name, ToDoColumns.IsDeduped, True)

            case MessageTypes.AddTransmittedChunk:
                # When the files are completed, mark it as completed
                file_name = message_data["data"][Key.FileName]
                chunk = message_data["data"][Key.Chunk]
                self._multi_log.log(
                    f"{prefix} Transmitted chunk {chunk} for {file_name}",
                    module=self._module_name,
                    # level=logging.DEBUG,
                )
                CurrentState.CurrentFileState = States.Transmitting
                self.append_value(file_name, ToDoColumns.TransmittedChunks, chunk)

                CurrentState.CurrentTransmittedChunks = len(
                    CurrentState.ToDoList[file_name][ToDoColumns.TransmittedChunks]
                )
                CurrentState.ToDoList[CurrentState.CurrentFile][
                    ToDoColumns.TransmittedChunksCount
                ] = len(CurrentState.ToDoList[file_name][ToDoColumns.TransmittedChunks])
                CurrentState.CurrentTransmittedChunks += 1
                CurrentState.CurrentCompletedChunks += 1

                self.add_to_value(
                    file_name,
                    ToDoColumns.TransmittedBytes,
                    Configuration.default_chunk_size,
                )

                self.backup_status.signals.update_chunk_progress.emit()
                self.backup_status.signals.update_stats_box.emit()

            case MessageTypes.AddDedupedChunk:
                # When the files are completed, mark it as completed
                file_name = message_data["data"][Key.FileName]
                chunk = message_data["data"][Key.Chunk]
                self._multi_log.log(
                    f"{prefix} Deduped chunk {chunk} for {file_name}",
                    module=self._module_name,
                    # level=logging.DEBUG,
                )
                CurrentState.CurrentFileState = States.Transmitting
                self.set_value(file_name, ToDoColumns.IsDeduped, True)
                self.append_value(file_name, ToDoColumns.DedupedChunks, chunk)
                CurrentState.CurrentDedupedChunks += 1
                CurrentState.CurrentCompletedChunks += 1

                CurrentState.ToDoList[CurrentState.CurrentFile][
                    ToDoColumns.DedupedChunksCount
                ] = len(CurrentState.ToDoList[file_name][ToDoColumns.DedupedChunks])

                self.add_to_value(
                    file_name,
                    ToDoColumns.DedupedBytes,
                    Configuration.default_chunk_size,
                )

                self.backup_status.signals.update_chunk_progress.emit()
                self.backup_status.signals.update_stats_box.emit()

            case MessageTypes.AddPreparedChunk:
                # When the files are completed, mark it as completed
                file_name = message_data["data"][Key.FileName]
                chunk = message_data["data"][Key.Chunk]
                self._multi_log.log(
                    f"{prefix} Prepared chunk {chunk} for {file_name}",
                    module=self._module_name,
                    # level=logging.DEBUG,
                )
                CurrentState.CurrentFileState = States.Preparing
                self.append_value(file_name, ToDoColumns.PreparedChunks, chunk)

                CurrentState.ToDoList[CurrentState.CurrentFile][
                    ToDoColumns.PreparedChunksCount
                ] = len(CurrentState.ToDoList[file_name][ToDoColumns.PreparedChunks])

                self.add_to_value(
                    file_name,
                    ToDoColumns.PreparedBytes,
                    Configuration.default_chunk_size,
                )

                self.backup_status.signals.update_chunk_progress.emit()

            case _:
                self._multi_log.log(
                    f"Received unexpected message: {message_data}",
                    module=self._module_name,
                    level=logging.WARN,
                )

    def post_initialize_to_do_list(self, file_name: str):
        index_count = self.to_do_list.at[file_name, ToDoColumns.IndexCount]
        self.to_do_list[ToDoColumns.State] = self.to_do_list.apply(
            lambda row: (
                Key.PreCompleted
                if row[ToDoColumns.IndexCount] < index_count
                else (
                    Key.Skipped
                    if row[ToDoColumns.State] == Key.Skipped
                    else Key.Unprocessed
                )
            ),
            axis=1,
        )

        self.update_stats()

        self.backup_status.signals.go_to_current_row.emit()

    @pyqtSlot()
    def update_to_do_list(self):
        current_index = self.to_do_list.at[
            CurrentState.CurrentFile, ToDoColumns.IndexCount
        ]
        self.to_do_list[ToDoColumns.State] = self.to_do_list.apply(
            lambda row: (
                Key.Skipped
                if row[ToDoColumns.IndexCount] < current_index
                and row[ToDoColumns.State] == Key.Unprocessed
                else row[ToDoColumns.State]
            ),
            axis=1,
        )
        # skipped = self.to_do_list[
        #     (self.to_do_list[ToDoColumns.IndexCount] < current_index)
        #     & (self.to_do_list[ToDoColumns.State] == Key.Unprocessed)
        # ]
        # for filename in skipped.index:
        #     self.set_value(filename, ToDoColumns.State, Key.Skipped)
        self.update_stats()

    def update_stats(self):
        CurrentState.TotalFilesPreCompleted = int(
            self.to_do_list[self.to_do_list[ToDoColumns.State] == Key.PreCompleted][
                ToDoColumns.IndexCount
            ].count()
        )
        CurrentState.TotalBytesPreCompleted = float(
            self.to_do_list[self.to_do_list[ToDoColumns.State] == Key.PreCompleted][
                ToDoColumns.FileSize
            ].sum()
        )
        CurrentState.TotalChunksPreCompleted = int(
            self.to_do_list[self.to_do_list[ToDoColumns.State] == Key.PreCompleted][
                ToDoColumns.ChunkCount
            ].sum()
        )

        CurrentState.SkippedFiles = int(
            self.to_do_list[self.to_do_list[ToDoColumns.State] == Key.Skipped][
                ToDoColumns.IndexCount
            ].count()
        )
        CurrentState.SkippedBytes = float(
            self.to_do_list[self.to_do_list[ToDoColumns.State] == Key.Skipped][
                ToDoColumns.FileSize
            ].sum()
        )
        CurrentState.SkippedChunks = int(
            self.to_do_list[self.to_do_list[ToDoColumns.State] == Key.Skipped][
                ToDoColumns.ChunkCount
            ].sum()
        )

        CurrentState.RemainingFiles = int(
            self.to_do_list[self.to_do_list[ToDoColumns.State] == Key.Unprocessed][
                ToDoColumns.IndexCount
            ].count()
        )
        CurrentState.RemainingBytes = float(
            self.to_do_list[self.to_do_list[ToDoColumns.State] == Key.Unprocessed][
                ToDoColumns.FileSize
            ].sum()
        )
        CurrentState.RemainingChunks = int(
            self.to_do_list[self.to_do_list[ToDoColumns.State] == Key.Unprocessed][
                ToDoColumns.ChunkCount
            ].sum()
        )

        self.total_files = int(self.to_do_list[ToDoColumns.IndexCount].count())
        # self.backblaze_redis.total_files = self.total_files
        CurrentState.TotalFiles = self.total_files

        self.total_bytes = float(self.to_do_list[ToDoColumns.FileSize].sum())
        # self.backblaze_redis.total_size = self.total_bytes
        CurrentState.TotalBytes = self.total_bytes

        CurrentState.TotalChunks = int(self.to_do_list[ToDoColumns.ChunkCount].sum())

        self.total_files_to_process = int(
            self.to_do_list[self.to_do_list[ToDoColumns.State] == Key.Unprocessed][
                ToDoColumns.IndexCount
            ].count()
        )
        # self.backblaze_redis.total_files_to_process = self.total_files_to_process
        CurrentState.TotalFilesToProcess = self.total_files_to_process

        self.total_bytes_to_process = float(
            self.to_do_list[self.to_do_list[ToDoColumns.State] == Key.Unprocessed][
                ToDoColumns.FileSize
            ].sum()
        )
        # self.backblaze_redis.total_size_to_process = self.total_bytes_to_process
        CurrentState.TotalBytesToProcess = self.total_bytes_to_process

        CurrentState.ToDoList = self.to_do_list.to_dict(orient="index")
        CurrentState.ToDoListLength = self.to_do_list.shape[0]

    def start_new_file(self, file_name: str, start_time: datetime) -> None:
        if self.previous_file is not None and self.previous_file != file_name:
            self.complete_file(self.previous_file, datetime.now())

        self.previous_file = file_name
        self.set_value(file_name, ToDoColumns.StartTime, start_time)
        self.set_value(file_name, ToDoColumns.IsDeduped, False)

        CurrentState.CurrentFile = file_name
        CurrentState.CurrentTransmittedChunks = 0
        CurrentState.CurrentDedupedChunks = 0
        CurrentState.CurrentCompletedChunks = 0

        self.backup_status.signals.go_to_current_row.emit()
        self.backup_status.signals.start_new_file.emit(file_name)

    def complete_file(self, file_name: str, end_time: datetime):
        self.update_to_do_list()

        if self.previous_file is not None and self.previous_file == file_name:
            self.previous_file = None
        self.set_value(file_name, ToDoColumns.EndTime, end_time)
        self.set_value(file_name, ToDoColumns.State, Key.Completed)

        deduped_chunks = CurrentState.ToDoList[file_name][ToDoColumns.DedupedChunks]
        self.set_value(
            file_name,
            ToDoColumns.DedupedChunksCount,
            len(deduped_chunks),
        )
        transmitted_chunks = CurrentState.ToDoList[file_name][
            ToDoColumns.TransmittedChunks
        ]
        self.set_value(
            file_name,
            ToDoColumns.TransmittedChunksCount,
            len(transmitted_chunks),
        )
        if len(deduped_chunks) + len(transmitted_chunks) > 0:
            if len(deduped_chunks) > len(transmitted_chunks):
                deduped = True
            else:
                deduped = False

            self.set_value(
                file_name,
                ToDoColumns.IsDeduped,
                deduped,
            )

        CurrentState.CompletedFiles = int(
            self.to_do_list[self.to_do_list[ToDoColumns.State] == Key.Completed][
                ToDoColumns.IndexCount
            ].count()
        )

        CurrentState.CompletedBytes = float(
            self.to_do_list[self.to_do_list[ToDoColumns.State] == Key.Completed][
                ToDoColumns.FileSize
            ].sum()
        )

        CurrentState.CompletedChunks = int(
            self.to_do_list[self.to_do_list[ToDoColumns.State] == Key.Completed][
                ToDoColumns.ChunkCount
            ].sum()
        )

        CurrentState.TransmittedFiles = int(
            self.to_do_list[
                (self.to_do_list[ToDoColumns.IsDeduped] == False)
                & (self.to_do_list[ToDoColumns.State] == Key.Completed)
            ][ToDoColumns.FileSize].count()
        )

        CurrentState.TransmittedBytes = float(
            self.to_do_list[
                (self.to_do_list[ToDoColumns.IsDeduped] == False)
                & (self.to_do_list[ToDoColumns.State] == Key.Completed)
            ][ToDoColumns.FileSize].sum()
        )

        CurrentState.TransmittedChunks = float(
            self.to_do_list[ToDoColumns.TransmittedChunksCount].sum()
        )

        CurrentState.DuplicateFiles = int(
            self.to_do_list[
                (self.to_do_list[ToDoColumns.IsDeduped] == True)
                & (self.to_do_list[ToDoColumns.State] == Key.Completed)
            ][ToDoColumns.IsDeduped].count()
        )

        CurrentState.DuplicateBytes = float(
            self.to_do_list[
                (self.to_do_list[ToDoColumns.IsDeduped] == True)
                & (self.to_do_list[ToDoColumns.State] == Key.Completed)
            ][ToDoColumns.FileSize].sum()
        )

        CurrentState.DuplicateChunks = float(
            self.to_do_list[ToDoColumns.DedupedChunksCount].sum()
        )

        # Calculate Progress

        start_time = CurrentState.StartTime
        completed_files = (
            CurrentState.CompletedFiles
            + CurrentState.TotalFilesPreCompleted
            + CurrentState.SkippedFiles
        )
        completed_bytes = (
            CurrentState.CompletedBytes
            + CurrentState.TotalBytesPreCompleted
            + CurrentState.SkippedBytes
        )
        completed_chunks = (
            CurrentState.CompletedChunks
            + CurrentState.TotalChunksPreCompleted
            + CurrentState.SkippedChunks
        )

        remaining_size = float(
            self.to_do_list[self.to_do_list[ToDoColumns.State] == Key.Unprocessed][
                ToDoColumns.FileSize
            ].sum()
        )

        # Calculate percentages

        if self.total_files == 0:
            CurrentState.CompletedFilesPercentage = 0.0
        else:
            CurrentState.CompletedFilesPercentage = (
                completed_files / CurrentState.TotalFiles
            )

        if self.total_bytes == 0:
            CurrentState.CompletedBytesPercentage = 0.0
        else:
            CurrentState.CompletedBytesPercentage = (
                completed_bytes / CurrentState.TotalBytes
            )

        if CurrentState.TotalChunks == 0:
            CurrentState.CompletedChunksPercentage = 0.0
        else:
            CurrentState.CompletedChunksPercentage = (
                completed_chunks / CurrentState.TotalChunks
            )

        # Calculate Rate

        now = datetime.now()
        seconds_difference = (now - start_time).total_seconds()
        if seconds_difference == 0:
            CurrentState.Rate = 0.0
        else:
            CurrentState.Rate = CurrentState.CompletedBytes / seconds_difference

        # Calculate time remaining

        if CurrentState.Rate == 0:
            CurrentState.TimeRemaining = 0
        else:
            CurrentState.TimeRemaining = remaining_size / CurrentState.Rate
            try:
                CurrentState.EstimatedCompletionTime = now + timedelta(
                    seconds=CurrentState.TimeRemaining
                )  # .strftime("%a %m/%d %-I:%M %p")
            except OverflowError:
                CurrentState.EstimatedCompletionTime = None

        self.backup_status.data_model_table.resizeRowToContents(
            CurrentState.ToDoList[file_name][ToDoColumns.IndexCount]
        )

        self.backup_status.signals.update_stats_box.emit()

    def set_value(self, file_name: str, column: str, value):
        try:
            self.to_do_list.at[file_name, column] = value
            CurrentState.ToDoList[file_name][column] = value
        except KeyError:
            # If it's a bad filename, I'm just going to ignore it
            pass

    def append_value(self, file_name: str, column: str, value):
        try:
            self.to_do_list.at[file_name, column].add(value)
            CurrentState.ToDoList[file_name][column].add(value)
        except Exception as exp:
            pass

    def add_to_value(self, file_name: str, column: str, value):
        self.to_do_list.at[file_name, column] += value
        CurrentState.ToDoList[file_name][column] += value

    def _mark_backup_not_running(self):
        self._multi_log.log("Backup Complete")
        CurrentState.BackupRunning = False
        CurrentState.CurrentFile = None
        self.backup_status.signals.backup_running.emit(False)

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
