from dataclasses import dataclass, field
from .backup_file import BackupFile

from typing import List


class CompletedFiles:
    _file_list: List[BackupFile] = field(default_factory=list, init=False)
    _file_dict: dict[str, BackupFile] = field(default_factory=dict, init=False)

    def __len__(self) -> int:
        return len(self._file_list)

    def __getitem__(self, index) -> BackupFile:
        if isinstance(index, int):
            return self._file_list[index]
        elif isinstance(index, str):
            return self._file_dict.get(index)
        else:
            raise TypeError("Invalid argument type")

    def append(self, file: BackupFile) -> None:
        index = len(self._file_list)
        file.list_index = index
        self._file_list.append(file)
        self._file_dict[str(file.file_name)] = file
