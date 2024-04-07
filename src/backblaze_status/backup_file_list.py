from dataclasses import dataclass, field
from typing import List, Optional, Iterator

from PyQt6.QtCore import QReadWriteLock

from .backup_file import BackupFile


@dataclass
class BackupFileList:
    _file_list: List[BackupFile] = field(default_factory=list, init=False)
    _file_dict: dict[str, BackupFile] = field(default_factory=dict, init=False)
    _current_index: int = field(default=0, init=False)
    _lock: QReadWriteLock = field(default_factory=QReadWriteLock, init=False)

    def __repr__(self) -> str:
        return str([str(file.file_name) for file in self._file_list])

    def __len__(self) -> int:
        return len(self._file_list)

    def __getitem__(self, index) -> BackupFile | None | list[BackupFile]:
        if isinstance(index, int):
            return self._file_list[index]
        elif isinstance(index, str):
            return self._file_dict.get(index)
        elif isinstance(index, slice):
            return self._file_list[index]
        else:
            raise TypeError("Invalid argument type")

    def __iter__(self) -> Iterator[BackupFile]:
        return iter(self._file_list)

    def __next__(self):
        if self._current_index < len(self._file_list):
            item = self._file_list[self._current_index]
            self._current_index += 1
            return item
        raise StopIteration

    def __add__(self, other):
        if isinstance(other, BackupFileList):
            return self._file_list + other.file_list
        elif isinstance(other, list):
            return self._file_list + other
        else:
            raise TypeError("Invalid argument type")

    def append(self, file: BackupFile) -> None:
        self._lock.lockForWrite()
        index = len(self._file_list)
        file.list_index = index
        self._file_list.append(file)
        self._file_dict[str(file.file_name)] = file
        self._lock.unlock()

    def remove(self, item) -> None:
        if isinstance(item, BackupFile):
            self._lock.lockForWrite()
            self._file_list.remove(item)
            del self._file_dict[str(item.file_name)]
            self._lock.unlock()
        elif isinstance(item, int):
            self._lock.lockForWrite()
            item_instance: BackupFile = self._file_list[item]
            del self._file_dict[str(item_instance.file_name)]
            del self._file_list[item]
            self._lock.unlock()
        else:
            raise TypeError("Invalid argument type")

    def index(self, file: str) -> int:
        backup_file = self._file_dict.get(file)
        if backup_file is None:
            raise ValueError(f"'{file}' is not in list")
        backup_index = self._file_list.index(backup_file)
        return backup_index

    def exists(self, item: str) -> bool:
        self._lock.lockForRead()
        result = item in self._file_dict.keys()
        self._lock.unlock()
        return result

    def clear(self):
        self._lock.lockForWrite()
        self._file_list.clear()
        self._file_dict.clear()
        self._lock.unlock()

    def get(self, file_name: str) -> Optional[BackupFile]:
        return self._file_dict.get(file_name)

    @property
    def file_list(self) -> list[BackupFile]:
        return self._file_list

    @property
    def file_dict(self) -> dict[str, BackupFile]:
        return self._file_dict
