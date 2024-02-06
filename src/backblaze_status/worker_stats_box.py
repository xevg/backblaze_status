from PyQt6.QtCore import QObject, pyqtSignal, QThread

from .main_backup_status import BackupStatus
from .utils import file_size_string


class StatsBoxWorker(QObject):
    update_stats_box = pyqtSignal(str)

    # class Signals(QObject):
    #     update_stats_box = pyqtSignal(str)

    def __init__(self, backup_status: BackupStatus):
        super(StatsBoxWorker, self).__init__()

        self.backup_status = backup_status
        # self.signals = StatsBoxWorker.Signals()

    def run(self):
        """
        Update the data in the stats box. This is in a separate thread because it can take a while to do
        """
        from .to_do_files import ToDoFiles

        to_do: ToDoFiles | None = None
        while True:
            if to_do is None:
                QThread.sleep(1)
                to_do = self.backup_status.to_do
                continue

            total_files = f"Total Files: {to_do.total_files:,d} / {file_size_string(to_do.total_size)}"
            transmitted_files = (
                f"Transmitted: {to_do.transmitted_files:,}"
                f" / {file_size_string(to_do.transmitted_size)}"
            )

            combined_files = to_do.duplicate_files + to_do.transmitted_files
            if combined_files == 0:
                percentage_file_duplicate = 0
            else:
                percentage_file_duplicate = to_do.duplicate_files / combined_files

            combined_size = to_do.duplicate_size + to_do.transmitted_size
            if combined_size == 0:
                percentage_size_duplicate = 0
            else:
                percentage_size_duplicate = to_do.duplicate_size / combined_size

            file_duplicate_files = (
                f"Duplicates: {to_do.duplicate_files}"
                f" / {file_size_string(to_do.duplicate_size)} "
            )

            percentage_duplicates_string = (
                f"Percentage Duplicate: {percentage_file_duplicate:.2%}"
                f" / {percentage_size_duplicate:.2%}"
            )

            text = (
                f"{total_files}"
                f"       {transmitted_files}"
                f"       {file_duplicate_files}"
                f"       {percentage_duplicates_string}"
            )
            self.update_stats_box.emit(text)
            QThread.sleep(10)
