from qt_backup_status import QTBackupStatus
from dataclasses import dataclass, field
from datetime import datetime, timedelta

gb_divisor = 1000000000
tb_divisor = 1000000000000


class ProgressBox:
    def __init__(self, qt: QTBackupStatus):
        self.qt = qt

        self._total_size: int = 0
        self._total_size_completed: int = 0
        self._total_files: int = 0
        self._total_files_completed: int = 0

        self._start_size: int = 0
        self._start_size_completed: int = 0
        self._start_files: int = 0
        self._start_files_completed: int = 0

        self._start_time: datetime = datetime.now()

        self._time_remaining: int = 0
        self._time_till_completion: int = 0

    def update_progress_bar(self):
        self.qt.progressBar.setValue(self.size_percentage * 100)

    @property
    def total_size(self) -> int:
        return self._total_size

    @total_size.setter
    def total_size(self, total_size: int):
        self._total_size = total_size
        self.update_progress_bar()

    @property
    def total_files(self) -> int:
        return self._total_files

    @total_files.setter
    def total_files(self, total_files: int):
        self._total_files = total_files
        self.update_progress_bar()

    @property
    def total_files_completed(self) -> int:
        return self._total_files_completed

    @total_files_completed.setter
    def total_files_completed(self, total_files_completed: int):
        self._total_files_completed = total_files_completed
        self.update_progress_bar()

    @property
    def files_percentage(self) -> float:
        return self._total_files_completed / self._total_files

    @property
    def rate(self) -> float:
        seconds_difference = (datetime.now() - self._start_time).seconds
        if seconds_difference == 0:
            return 0
        else:
            return self.total_processed / seconds_difference

    @property
    def size_percentage(self) -> float:
        return self._total_size_completed / self._total_size

    @property
    def total_processed(self) -> int:
        return self.qt.backup_status.to_do.completed_size - self._start_size_completed

    @property
    def total_size_gb(self) -> float:
        return self._total_size / gb_divisor

    @property
    def total_size_completed_gb(self) -> float:
        return self._total_size_completed / gb_divisor

    @@property
    def progress_value (self) -> int:
        return int(self.size_percentage * 100)



