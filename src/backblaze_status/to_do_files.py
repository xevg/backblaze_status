from dataclasses import dataclass, field
from typing import List
from backup_file import BackupFile
import threading
from pathlib import Path
from utils import file_size_string


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
    _completed_files: int = field(default=0, init=False)
    lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self):
        self._read()

    def _read(self) -> None:
        """
        This reads the to_do file and stores it in two data structures,
          - a dictionary so that I can find the file, and
          - a list, so that I can see what the next files are

          The structure of the file that I care about are the 6th field, which is the filename,
          and the fifth field, which is the file size.
        :return:
        """
        with open(self.todo_file_name, "r") as tdf:
            list_index = 0
            for todo_line in tdf:
                todo_fields = todo_line.strip().split("\t")
                todo_filename = Path(todo_fields[5])
                todo_filesize = int(todo_fields[4])
                self._remaining_size += todo_filesize
                self._remaining_files += 1
                backup = BackupFile(todo_filename, todo_filesize, list_index)
                self._file_list.append(backup)
                self._file_dict[str(todo_filename)] = backup

                list_index += 1
        self._total_size = self._remaining_size
        self._total_files = self._remaining_files

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

    def completed(self, filename) -> None:
        """
        Mark a file as completed

        :param filename:
        :return:
        """
        if filename in self._file_dict:
            todo_file: BackupFile = self._file_dict[filename]

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

    def add_file(self, _filename: Path):
        if not self.exists(_filename):
            self.lock.acquire()
            list_index = len(self.file_list)
            _stat = _filename.stat()
            _file_size = _stat.st_size
            _backup = BackupFile(_filename, _file_size, list_index)
            self.file_list.append(_backup)
            self.file_dict[str(_filename)] = _backup
            self.lock.release()

    def get_remaining(self, start_index: int = 0, number_of_rows: int = 0) -> list:
        start_index += 1
        count_of_rows = 0
        for item in self._file_list[start_index:]:  # type: BackupFile
            if not item.completed:
                count_of_rows += 1
                if count_of_rows > number_of_rows:
                    return
                yield item

    def todo_files(self, count=20, filename=None):
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
                yield f"{counter:>2d}: {item.file_name} ({file_size_string(item.file_size)})"
                counter += 1

    @property
    def remaining_size(self) -> int:
        return self._remaining_size

    @property
    def remaining_files(self) -> int:
        return self._remaining_files

    @property
    def completed_size(self) -> int:
        return self._completed_size

    @property
    def completed_files(self) -> int:
        return self._completed_files

    @property
    def total_size(self) -> int:
        return self._total_size

    @property
    def total_files(self) -> int:
        return self._total_files
