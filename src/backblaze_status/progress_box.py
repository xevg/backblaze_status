import threading
import time
from datetime import datetime, timedelta

from .configuration import Configuration
from .locks import lock, Lock
from .to_do_files import ToDoFiles
from .utils import file_size_string

gb_divisor = Configuration.gb_divisor
tb_divisor = Configuration.tb_divisor


class ProgressBox:
    def __init__(self, backup_status):
        from .main_backup_status import BackupStatus

        self._backup_status: BackupStatus = backup_status

        self._total_size: int = 0
        self._total_size_completed: int = 0
        self._total_size_processed: int = 0
        self._total_size_transmitted: int = 0

        self._total_chunks_transmitted: int = 0
        self._total_chunks_deduped: int = 0
        self._total_chunks_completed: int = 0
        self._total_chunks: int = 0

        self._total_files: int = 0
        self._total_files_completed: float = 0.0

        self._start_size: int = 0
        self._start_size_completed: int = 0
        self._start_files: int = 0
        self._start_files_completed: int = 0

        self._start_time: datetime = datetime.now()

        self._remaining_size: int = 0
        self._time_remaining: int = 0
        self._estimated_completion_time: str = "Calculating ..."

        self._progress_string = "No progress yet"

        self._rate = 0

        self._files_percentage = 0
        self._size_percentage = 0
        self._chunks_percentage = 0

        self.last_calculated: datetime = datetime.now()

        timer_thread = threading.Thread(
            target=self.timer, name="ProgressUpdateTimer", daemon=True
        )
        timer_thread.name = "ProgressUpdateTimer"
        timer_thread.start()

    def timer(self) -> None:
        while True:
            time.sleep(15)
            if (datetime.now() - self.last_calculated).total_seconds() > 15:
                self.calculate()

    @lock(Lock.DB_LOCK)
    def calculate(self):
        self.last_calculated = datetime.now()
        to_do: ToDoFiles = self._backup_status.to_do
        if to_do is None:
            return

        current_file = to_do.current_file
        if current_file is None:
            return

        self._total_size = to_do.total_size
        self._total_size_completed = to_do.completed_size
        self._total_size_processed = to_do.processed_size  # to_do.completed_size
        self._total_size_transmitted = to_do.transmitted_size
        self._total_files = to_do.total_file_count
        self._total_files_completed = to_do.completed_file_count

        # Chunk calculation

        self._total_chunks_transmitted = to_do.transmitted_chunk_count
        self._total_chunks_deduped = to_do.duplicate_chunk_count
        self._total_chunks = to_do.total_chunk_count
        self._total_chunks_completed = (
            self._total_chunks_transmitted + self._total_chunks_deduped
        )
        if self._total_chunks == 0:
            self._chunks_percentage = 0
        else:
            self._chunks_percentage = self._total_chunks_completed / self._total_chunks

        # to_do.completed_size returns all the completed items, this adds the
        # currently processing file as well
        if current_file.is_large_file:
            self._total_size_completed += current_file.total_chunk_size
            self._total_size_transmitted += current_file.transmitted_chunk_size

        now = datetime.now()

        # Files Percentage
        if to_do.total_file_count == 0:
            self._files_percentage = 0
        else:
            self._files_percentage = self.total_files_completed / self._total_files

        if self._total_size == 0:
            self._size_percentage = 0
        else:
            self._size_percentage = self._total_size_completed / self._total_size

        # Calculate the total rate
        seconds_difference = (datetime.now() - self._start_time).total_seconds()
        if seconds_difference == 0:
            self._rate = 0
        else:
            self._rate = self._total_size_completed / seconds_difference

        # Calculate time remaining

        if self._rate == 0:
            self._time_remaining = 0
            self._estimated_completion_time = "Calculating ..."
        else:
            self._remaining_size = to_do.remaining_size
            # Was: total_size - to_do.completed_size
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
        return self._total_size_processed

    @property
    def files_percentage(self) -> float:
        return self._files_percentage

    @property
    def size_percentage(self) -> float:
        return self._size_percentage

    @property
    def total_processed(self) -> int:
        return (
            self._backup_status.to_do.current_file.completed_size
            - self._start_size_completed
        )

    @property
    def total_size_gb(self) -> float:
        return self._total_size / gb_divisor

    @property
    def total_size_completed_gb(self) -> float:
        return self._total_size_processed / gb_divisor

    @property
    def progress_value(self) -> int:
        return int(self.size_percentage * 100)

    @property
    def elapsed_time(self) -> str:
        return str(datetime.now() - self._start_time).split(".")[0]

    @property
    def progress_string(self) -> str:
        progress_string = (
            f'<span style="color: yellow">{file_size_string(self._total_size_processed)} '
            f"</span> /"
            f' <span style="color: yellow">{file_size_string(self._total_size)} </span> '
            f' (Files: <span style="color: yellow">{self._total_files_completed:,} </span> /'
            f' <span style="color: yellow">{self._total_files:,}</span>'
            f' [<span style="color: magenta">{self._files_percentage:.1%}</span>],'
            f' Chunks: <span style="color: yellow">'
            f" {self._total_chunks_completed:,}</span> /"
            f' <span style="color: yellow">{self._total_chunks:,}</span>'
            f' [<span style="color: magenta">{self._chunks_percentage:.1%}</span>])'
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
        return (
            f'Estimated Completion Time:  <span style="color:cyan">'
            f" {self._estimated_completion_time} </span>"
        )

    @property
    def rate(self) -> str:
        if self._rate == 0:
            return 'Rate: <span style="color:cyan">  Calculating ... </span>'
        else:
            return (
                f'Rate:  <span style="color:cyan">'
                f" {file_size_string(self._rate)}</span> / second"
            )

    @property
    def estimated_completion_time(self) -> str:
        return self._estimated_completion_time
