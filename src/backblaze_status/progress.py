from datetime import datetime, timedelta

from .utils import file_size_string
from .configuration import Configuration

gb_divisor = Configuration.gb_divisor
tb_divisor = Configuration.tb_divisor


class ProgressBox:
    def __init__(self, backup_status):
        from .main_backup_status import BackupStatus

        self._backup_status: BackupStatus = backup_status

        self._total_size: int = 0
        self._total_size_completed: int = 0
        self._total_files: int = 0
        self._total_files_completed: float = 0.0

        self._start_size: int = 0
        self._start_size_completed: int = 0
        self._start_files: int = 0
        self._start_files_completed: int = 0

        self._start_time: datetime = datetime.now()

        self._remaining_size: int = 0
        self._time_remaining: int = 0
        self._estimated_completion_time: str = (
            "Estimated Completion Time: Calculating ..."
        )

        self._start_time = datetime.now()

        self._progress_string = "No progress yet"

        self._rate = 0

        self._files_percentage = 0
        self._size_percentage = 0

    def calculate(self):
        to_do = self._backup_status.to_do
        if to_do is None:
            return
        self._total_size = to_do.total_size
        self._total_size_completed = to_do.completed_size
        self._total_files = to_do.total_files
        self._total_files_completed = to_do.completed_files

        now = datetime.now()
        # Files Percentage
        if to_do.total_files == 0:
            self._files_percentage = 0
        else:
            self._files_percentage = to_do.completed_files / to_do.total_files

        if to_do.total_size == 0:
            self._size_percentage = 0
        else:
            self._size_percentage = to_do.completed_size / to_do.total_size

        # Calculate the total rate
        seconds_difference = (datetime.now() - self._start_time).seconds
        if seconds_difference == 0:
            self._rate = 0
        else:
            self._rate = to_do.completed_size / seconds_difference

        # Calculate time remaining

        if self._rate == 0:
            self._time_remaining = 0
            self._estimated_completion_time = (
                "Estimated Completion Time: Calculating ..."
            )
        else:
            self._remaining_size = to_do.total_size - to_do.completed_size
            self._time_remaining = self._remaining_size / self._rate
            try:
                self._estimated_completion_time = (
                    now + timedelta(seconds=self._time_remaining)
                ).strftime("%a %m/%d %-I:%M %p")
            except OverflowError:
                self._estimated_completion_time = "Unknown"

    @property
    def total_size(self) -> int:
        return self._total_size

    @property
    def total_files(self) -> int:
        return self._total_files

    @property
    def total_files_completed(self) -> float:
        return self._total_files_completed

    @property
    def total_size_completed(self) -> int:
        return self._total_size_completed

    @property
    def files_percentage(self) -> float:
        return self._files_percentage

    @property
    def size_percentage(self) -> float:
        return self._size_percentage

    @property
    def total_processed(self) -> int:
        return self.qt.backup_status.to_do.completed_size - self._start_size_completed

    @property
    def total_size_gb(self) -> float:
        return self._total_size / gb_divisor

    @property
    def total_size_completed_gb(self) -> float:
        return self._total_size_completed / gb_divisor

    @property
    def progress_value(self) -> int:
        return int(self.size_percentage * 100)

    @property
    def elapsed_time(self) -> str:
        return str(datetime.now() - self._start_time).split(".")[0]

    @property
    def progress_string(self) -> str:
        progress_string = (
            f'<span style="color: yellow">{file_size_string(self._total_size_completed)} </span> /'
            f' <span style="color: yellow">{file_size_string(self._total_size)} </span> '
            f' (Files: <span style="color: yellow">{self._total_files_completed:,} </span> /'
            f' <span style="color: yellow">{self._total_files:,}</span>'
            f' [<span style="color: magenta">{self._files_percentage:.1%}</span>])'
        )
        return progress_string

    @property
    def time_remaining(self) -> str:
        if self._time_remaining == 0:
            return 'Time Remaining: <span style="color:cyan"> Calculating ...</span>'
        else:
            return (
                f'Time Remaining: <span style="color:cyan">'
                f' {str(timedelta(seconds=self._time_remaining)).split(".")[0]}</span>'
            )

    @property
    def completion_time(self) -> str:
        return f'Estimated Completion Time:  <span style="color:cyan"> {self._estimated_completion_time} </span>'

    @property
    def rate(self) -> str:
        if self._rate == 0:
            return 'Rate: <span style="color:cyan">  Calculating ... </span>'
        else:
            return f'Rate:  <span style="color:cyan"> {file_size_string(self._rate)}</span> / second'

    @property
    def estimated_completion_time(self) -> str:
        return self._estimated_completion_time
