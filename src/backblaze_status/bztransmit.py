from .to_do_files import ToDoFiles
from dataclasses import dataclass, field
from pathlib import Path
import os
import time
from .backup_file import BackupFile


@dataclass
class BzTransmit:
    backup_list: ToDoFiles
    total: int = field(default=0, init=False)
    dedups: int = field(default=0, init=False)
    blanks: int = field(default=0, init=False)
    bytes: int = field(default=0, init=False)
    current_filename: Path | None = field(default=None, init=False)

    BZ_LOG_DIR: str = field(
        default="/Library/Backblaze.bzpkg/bzdata/bzlogs/bzreports_lastfilestransmitted/",
        init=False,
    )

    @property
    def percentage(self) -> float:
        if self.total == 0:
            return 0.0
        return self.dedups / self.total

    def _check_for_new_transmit_files(self) -> Path:
        last_file = None
        _dir = Path(self.BZ_LOG_DIR)
        for _file in _dir.iterdir():
            if _file.suffix == ".log":
                if not last_file:
                    last_file = _file
                else:
                    if _file.stat().st_mtime > last_file.stat().st_mtime:
                        last_file = _file
        return last_file

    def tail_file(self, _file) -> str:
        sleep_count: int = 0
        _file.seek(os.SEEK_END)
        while True:
            _line = _file.readline()

            if not _line:
                time.sleep(0.1)
                sleep_count += 1
                if sleep_count == 1000:
                    sleep_count = 0
                    _new_filename = self._check_for_new_transmit_files()
                    if _new_filename.name != self.current_filename.name:
                        # raise NewFileStarted()
                        return
                continue

            yield _line

    def process_line(self, _line: str) -> None:
        _filename: str | None = None
        _bytes: int = 0
        _rate: str | None = None

        _line = _line.strip()
        chunk: bool = False
        if _line == "":
            print("Blank line")
            self.blanks += 1
        else:
            self.total += 1
            print(_line)
        _fields = _line.split(" - ")
        match len(_fields):
            case 6:
                _timestamp, _size, _type, _rate, _bytes_str, _filename = _fields
                try:
                    _bytes = int(_bytes_str.strip().split(" ")[0])
                except:
                    pass
                if _filename[0:5] == "Chunk":
                    _filename = _filename[15:]
                    chunk = True
            case 3:
                _timestamp, _, _filename = _fields
                _bytes = 0
            case _:
                pass

        self.backup_list.lock.acquire()
        if not self.backup_list.exists(_filename):
            self.backup_list.add_file(Path(_filename))

        file_info = self.backup_list.file_dict[str(_filename)]  # type: BackupFile
        if _rate.strip() == "dedup":
            self.dedups += 1
            file_info.dedup_count += 1
        if chunk:
            file_info.chunk_count += 1
        file_info.bytes += _bytes
        self.bytes += _bytes
        self.backup_list.lock.release()

    def read_transmit_file(self) -> None:
        _log_file = self._check_for_new_transmit_files()
        self.current_filename = _log_file
        while True:
            with self.current_filename.open("r") as _file:
                with _log_file.open("r") as _log_fd:
                    for _line in _log_fd:
                        self.process_line(_line)

                    for _line in self.tail_file(_log_fd):
                        self.process_line(_line)

            pass
