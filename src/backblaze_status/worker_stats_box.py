import threading
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot, QTimer

from .qt_backup_status import QTBackupStatus
from .to_do_files import ToDoFiles
from .utils import file_size_string


class StatsBoxWorker(QObject):
    update_stats_box = pyqtSignal(str)

    # class Signals(QObject):
    #     update_stats_box = pyqtSignal(str)

    def __init__(self, backup_status: QTBackupStatus):
        super(StatsBoxWorker, self).__init__()

        self.backup_status = backup_status
        self.to_do: Optional[ToDoFiles] = None

        # self.signals = StatsBoxWorker.Signals()

    def run(self):
        """
        Update the data in the stats box. This is in a separate thread because it can take a while to do
        """
        threading.current_thread().name = QThread.currentThread().objectName()

        if self.backup_status.to_do is None:
            self.backup_status.signals.to_do_available.connect(self.start_stats_box)
        else:
            self.start_stats_box()

    @pyqtSlot()
    def start_stats_box(self):
        stats_timer = QTimer()
        stats_timer.timeout.connect(self.update_stats)
        stats_timer.start(10000)  # 10 seconds

    @pyqtSlot()
    def update_stats(self):
        total_regular_files_string = (
            f"Total Regular Files:"
            f" <b>{self.to_do.total_current_regular_file_count:,d} /"
            f" {file_size_string(self.to_do.total_current_regular_size)}"
            f" </b>{'&nbsp;' * 2}"
        )

        total_large_files_string = (
            f"Total Chunks:"
            f" <b>{self.to_do.total_current_chunk_count:,d} /"
            f" {file_size_string(self.to_do.total_current_large_size)}"
            f" </b>{'&nbsp;' * 10}"
        )

        transmitted_files_string = (
            f"Transmitted Files: <b>{to_do.transmitted_file_count:,}"
            f" / {file_size_string(to_do.transmitted_file_size)}</b>{'&nbsp;' * 2}"
        )

        transmitted_chunks_string = (
            f"Transmitted Chunks: "
            f"<b>{self.to_do.transmitted_chunk_count:,} / "
            f"{file_size_string(self.to_do.transmitted_chunk_size)}</b"
            f">{'&nbsp;' * 10}"
        )

        duplicate_files_string = (
            f"Duplicate Files: <b>{self.to_do.duplicate_file_count:,}"
            f" / {file_size_string(self.to_do.duplicate_file_size)}</b>{'&nbsp;' * 2}"
        )

        duplicate_chunks_string = (
            f"Duplicate Chunks: <b>{self.to_do.duplicate_chunk_count:,}"
            f" / {file_size_string(self.to_do.duplicate_chunk_size)}</b> {'&nbsp;' * 10}"
        )

        combined_files = self.to_do.completed_file_count
        if combined_files == 0:
            percentage_file_duplicate = 0
        else:
            percentage_file_duplicate = self.to_do.duplicate_file_count / combined_files
            if percentage_file_duplicate > 1:
                percentage_file_duplicate = 1

        combined_size = self.to_do.completed_size
        if combined_size == 0:
            percentage_size_duplicate = 0
        else:
            percentage_size_duplicate = self.to_do.duplicate_file_size / combined_size
            if percentage_size_duplicate > 1:
                percentage_size_duplicate = 1

        combined_chunks = self.to_do.completed_chunk_count
        if combined_chunks == 0:
            percentage_chunk_duplicate = 0
        else:
            percentage_chunk_duplicate = (
                self.to_do.duplicate_chunk_count / combined_chunks
            )
            if percentage_chunk_duplicate > 1:
                percentage_chunk_duplicate = 1

        combined_chunk_size = self.to_do.completed_chunk_size
        if combined_chunk_size == 0:
            percentage_chunk_size_duplicate = 0
        else:
            percentage_chunk_size_duplicate = (
                self.to_do.duplicate_chunk_size / combined_chunk_size
            )
            if percentage_chunk_size_duplicate > 1:
                percentage_chunk_size_duplicate = 1

        percentage_duplicate_files_string = (
            f"Percentage Duplicate Files: <b>{percentage_file_duplicate:.2%}"
            f" / {percentage_size_duplicate:.2%}</b>{'&nbsp;' * 2}"
        )

        percentage_duplicate_chunks_string = (
            f"Percentage Duplicate Chunks: <b>{percentage_chunk_duplicate:.2%}</b>"
        )

        text = (
            f"{total_regular_files_string}  {total_large_files_string}"
            f"       {transmitted_files_string}  {transmitted_chunks_string}"
            f"       {duplicate_files_string}  {duplicate_chunks_string}"
            f"       {percentage_duplicate_files_string}"
            f"  {percentage_duplicate_chunks_string}"
        )
        self.update_stats_box.emit(text)
