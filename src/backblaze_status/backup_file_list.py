from dataclasses import dataclass, field
from .backup_file import BackupFile

from typing import List, Optional, Iterator


@dataclass
class BackupFileList:
    _file_list: List[BackupFile] = field(default_factory=list, init=False)
    _file_dict: dict[str, BackupFile] = field(default_factory=dict, init=False)

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
        return next(self.file_list)

    def __add__(self, other):
        if isinstance(other, BackupFileList):
            return self._file_list + other.file_list
        elif isinstance(other, list):
            return self._file_list + other
        else:
            raise TypeError("Invalid argument type")

    def append(self, file: BackupFile) -> None:
        index = len(self._file_list)
        file.list_index = index
        self._file_list.append(file)
        self._file_dict[str(file.file_name)] = file

    def remove(self, item) -> None:
        if isinstance(item, BackupFile):
            self._file_list.remove(item)
            del self._file_dict[str(item.file_name)]
        elif isinstance(item, int):
            item_instance: BackupFile = self._file_list[item]
            del self._file_dict[str(item_instance.file_name)]
            del self._file_list[item]
        else:
            raise TypeError("Invalid argument type")

    def exists(self, item: str) -> bool:
        return item in self._file_dict.keys()

    def clear(self):
        self._file_list.clear()
        self._file_dict.clear()

    def get(self, file_name: str) -> Optional[BackupFile]:
        return self._file_dict.get(file_name)

    @property
    def file_list(self) -> list[BackupFile]:
        return self._file_list

    @property
    def file_dict(self) -> dict[str, BackupFile]:
        return self._file_dict
