from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from io import TextIOWrapper
import os
import time
from .utils import MultiLogger


class BzLogFileWatcher(ABC):
    @staticmethod
    def _get_timestamp() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @abstractmethod
    def _get_latest_logfile_name(self) -> Path:
        pass

    def _tail_file(self, _file: TextIOWrapper) -> str:
        while True:
            _line = _file.readline()

            if not _line:
                if self._first_pass:
                    self._multi_log.log("Finished first pass", module=self._module_name)
                self._first_pass = False
                time.sleep(1)
                _new_filename = self._get_latest_logfile_name()
                if _new_filename != self._current_filename:
                    return
                continue

            yield _line

    @abstractmethod
    def _process_line(self, _line) -> None:
        pass

    def read_file(self) -> None:
        _log_file = self._get_latest_logfile_name()
        self._current_filename = _log_file
        while True:
            with _log_file.open("r") as _log_fd:
                self._multi_log.log(f"Reading file {_log_file}")
                if self._first_pass:
                    _log_fd.seek(0, 2)
                for _line in self._tail_file(_log_fd):
                    self._process_line(_line)

                self._first_pass = False
                _log_file = self._get_latest_logfile_name()
                self._current_filename = _log_file
