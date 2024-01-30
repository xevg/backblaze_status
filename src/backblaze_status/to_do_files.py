import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
from datetime import datetime

from .backup_file import BackupFile
from .utils import file_size_string, MultiLogger, get_lock, return_lock
from .configuration import Configuration
from .dev_debug import DevDebug


class NotFound(Exception):
    pass


@dataclass
class ToDoFiles:
    """
    Class to store the list and status of To Do files
    """

    todo_file_name: str
    _file_list: List[BackupFile] = field(default_factory=list, init=False)
    _file_dict: dict[str, BackupFile] = field(default_factory=dict, init=False)
    _total_size: int = field(default=0, init=False)
    _total_files: int = field(default=0, init=False)
    _remaining_size: int = field(default=0, init=False)
    _remaining_files: int = field(default=0, init=False)
    _completed_size: int = field(default=0, init=False)
    _completed_transmitted: int = field(default=0, init=False)
    _completed_files: int = field(default=0, init=False)
    _file_modification_time: float = field(default=0.0, init=False)
    _current_file: BackupFile = field(default=None, init=False)
    lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    current_file_lock: threading.Lock = field(
        default_factory=threading.Lock, init=False
    )
    cache: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        self._multi_log = MultiLogger("ToDoFiles", terminal=True)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Creating ToDoFiles")
        self.debug = DevDebug()

        self._file_dict = dict()
        self._file_list = list()

        self._read()
        self._start_reread_thread()

    def start_reread_thread(self):
        pass

    @property
    def current_file(self) -> BackupFile:
        return self._current_file

    @current_file.setter
    def current_file(self, value: BackupFile) -> None:
        self.debug.print(
            "lock.to_do", f"acquiring current_file lock for {value.file_name}"
        )
        self.current_file_lock.acquire()
        self._current_file = value
        self.current_file_lock.release()
        self.debug.print(
            "lock.to_do", f"released current_file lock for {value.file_name}"
        )

    def _read(self) -> None:
        """
        This reads the to_do file and stores it in two data structures,
          - a dictionary so that I can find the file, and
          - a list, so that I can see what the next files are

          The structure of the file that I care about are the 6th field, which is the filename,
          and the fifth field, which is the file size.
        :return:
        """
        start_lock = get_lock(self.lock, "todo", "to_do_files:51")

        # print("Todo: Lock Acquired")
        file = Path(self.todo_file_name)
        stat = file.stat()
        self._file_modification_time = stat.st_mtime
        with open(self.todo_file_name, "r") as tdf:
            list_index = 0
            for todo_line in tdf:
                todo_fields = todo_line.strip().split("\t")
                todo_filename = Path(todo_fields[5])
                todo_file_size = int(todo_fields[4])
                self._remaining_size += todo_file_size
                self._remaining_files += 1
                backup = BackupFile(todo_filename, todo_file_size, list_index)
                if todo_file_size > Configuration.default_chunk_size:
                    backup.chunks_total = int(
                        todo_file_size / Configuration.default_chunk_size
                    )
                    backup.large_file = True
                self._file_list.append(backup)
                self._file_dict[str(todo_filename)] = backup

                list_index += 1
        self._total_size = self._remaining_size
        self._total_files = self._remaining_files
        return_lock(self.lock, "todo", "to_do_files:77", start_lock)
        # print("Todo: Lock Released")

    def reread_to_do_list(self):
        # TODO: This should re-read the file, and skip any of the lines that we already have, but add any new ones
        pass

    @property
    def file_list(self) -> list[BackupFile]:
        return self._file_list

    @property
    def file_dict(self) -> dict[str, BackupFile]:
        return self._file_dict

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
        todo_file: BackupFile = self._file_dict.get(filename)
        if todo_file is None:
            return

        # invalidate the cache
        self.cache = dict()

        if todo_file.completed:
            return
        todo_file.completed = True

        self._completed_size += todo_file.file_size
        self._remaining_size -= todo_file.file_size
        self._completed_files += 1
        self._remaining_files -= 1

    def add_completed_file(self, update_file_size: int) -> None:
        """
        If the done_file finds a file that isn't in the to_do list, add those statistics to the lists

        :param update_file_size:
        :return:
        """
        self._total_size += update_file_size
        self._total_files += 1
        self._completed_size += update_file_size
        self._completed_files += 1

    def add_file(
        self,
        _filename: Path,
        is_chunk: bool = False,
        timestamp: datetime = datetime.now(),
    ):
        if not self.exists(str(_filename)):
            # invalidate the cache
            self.cache = dict()

            list_index = len(self.file_list)
            try:
                _stat = _filename.stat()
                _file_size = _stat.st_size
            except:
                _file_size = 0

            self._remaining_files += 1
            self._remaining_size += _file_size

            _backup = BackupFile(
                _filename,
                _file_size,
                list_index,
                timestamp=timestamp,
            )

            # _file_size > self.default_chunk_size:  # this is the size of the backblaze chunks
            if is_chunk:
                _backup.chunks_total = int(
                    _file_size / Configuration.default_chunk_size
                )
                _backup.large_file = True

            self.file_list.append(_backup)
            self.file_dict[str(_filename)] = _backup

    def get_remaining(self, start_index: int = 0, number_of_rows: int = 0) -> list:
        start_index += 1
        count_of_rows = 0
        for item in self._file_list[start_index:]:  # type: BackupFile
            if not item.completed:
                count_of_rows += 1
                if count_of_rows > number_of_rows:
                    return
                yield item

    def todo_files(self, count=1000000000, filename: str = None):
        """
        Retrieve the next N filenames. If no filename is specified, just start from the beginning of the list.
        If a filename is specified, start from the one after that.

        This is a generator function.

        :param count:
        :param filename:
        :return:
        """
        starting_index = 0
        counter = 1
        if filename is not None:
            starting_index = self._file_dict[filename].list_index

        for item in self._file_list[starting_index : starting_index + count + 1]:
            if not item.completed:
                yield item
                counter += 1

    @property
    def remaining_size(self) -> int:
        return self._remaining_size

    @property
    def remaining_files(self) -> int:
        return self._remaining_files

    @property
    def completed_size(self) -> int:
        cached = self.cache.get("completed_size")
        if cached:
            return cached

        total = 0
        for item in self._file_list:  # type: BackupFile
            if item.large_file:
                total += (
                    len(item.chunks_deduped) + len(item.chunks_transmitted)
                ) * Configuration.default_chunk_size
            elif item.completed:
                total += item.file_size
        self.cache["completed_size"] = total
        return total

    @property
    def transmitted_size(self) -> int:
        cached = self.cache.get("transmitted_size")
        if cached:
            return cached

        total = 0
        for item in self._file_list:  # type: BackupFile
            if item.large_file:
                total += (
                    len(item.chunks_transmitted)
                ) * Configuration.default_chunk_size
            elif item.completed and not item.dedup_current:
                total += item.file_size
        self.cache["transmitted_size"] = total
        return total

    @property
    def completed_files(self) -> int:
        cached = self.cache.get("completed_files")
        if cached:
            return cached

        total = 0
        for item in self._file_list:  # type: BackupFile
            if item.completed:
                total += 1
        self.cache["completed_files"] = total
        return total

    @property
    def total_size(self) -> int:
        cached = self.cache.get("total_size")
        if cached:
            return cached

        total = 0
        for item in self._file_list:  # type: BackupFile
            total += item.file_size
        self.cache["total_size"] = total
        return total

    @property
    def total_files(self) -> int:
        return len(self._file_list)

    @property
    def total_duplicate_files(self) -> int:
        cached = self.cache.get("total_duplicate_files")
        if cached:
            return cached
        total = 0
        for item in self._file_list:  # type: BackupFile
            if item.dedup_count > 0:
                total += 1

        self.cache["total_duplicate_files"] = total
        return total

    @property
    def total_duplicate_size(self) -> int:
        cached = self.cache.get("total_duplicate_size")
        if cached:
            return cached

        total = 0
        for item in self._file_list:  # type: BackupFile
            if item.large_file:
                if len(item.chunks_deduped) > 0:
                    total += len(item.chunks_deduped) * Configuration.default_chunk_size
            else:
                if item.dedup_count > 0:
                    total += item.deduped_bytes

        self.cache["total_duplicate_size"] = total
        return total

    @property
    def total_transmitted_files(self) -> int:
        cached = self.cache.get("total_transmitted_files")
        if cached:
            return cached
        total = 0
        for item in self._file_list:
            if item.completed and item.dedup_count == 0:
                total += 1

        self.cache["total_transmitted_files"] = total
        return total

    @property
    def total_transmitted_size(self) -> int:
        cached = self.cache.get("total_transmitted_size")
        if cached:
            return cached
        total = 0
        for item in self._file_list:
            if item.large_file:
                if len(item.chunks_transmitted) > 0:
                    total += (
                        len(item.chunks_transmitted) * Configuration.default_chunk_size
                    )
            else:
                if item.completed and item.dedup_count == 0:
                    total += item.file_size

        self.cache["total_transmitted_size"] = total
        return total
