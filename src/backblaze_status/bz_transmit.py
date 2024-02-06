import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import logging
import time

from .backup_file import BackupFile
from .bz_log_file_watcher import BzLogFileWatcher
from .main_backup_status import BackupStatus
from .qt_backup_status import QTBackupStatus
from .to_do_files import ToDoFiles
from .utils import MultiLogger


@dataclass
class BzTransmit(BzLogFileWatcher):
    """
    The bztransmit log contains a lot of information about the backup process. I ignore most of it, but there are
    certain key lines that give insights into what is happening in the backup
    """

    backup_status: BackupStatus
    qt: QTBackupStatus | None = field(default=None)
    to_do: ToDoFiles | None = field(default=None, init=False)

    _total_lines: int = field(default=0, init=False)
    _dedups: int = field(default=0, init=False)
    _blank_lines: int = field(default=0, init=False)
    _bytes: int = field(default=0, init=False)
    _batch_count: int = field(default=0, init=False)
    _is_batch: bool = field(default=False, init=False)
    _current_filename: Path | None = field(default=None, init=False)
    _first_pass: bool = field(default=True, init=False)
    BZ_LOG_DIR: str = field(
        default="/Library/Backblaze.bzpkg/bzdata/bzlogs/bztransmit",
        init=False,
    )

    def __post_init__(self):
        self._multi_log = MultiLogger("BzTransmit", terminal=True, qt=self.qt)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting BzTransmit")

        self.go_to_end = True

        # Compile the match for prepare large file search
        self.prepare_match_re = re.compile(
            ".*Entering PrepareBzLargeFileDirWithLargeFile.*"
        )
        # Compile the search for dedup
        self.dedup_search_re = re.compile("chunk ([^ ]*) for this largefile")

        # Compile the search for new to_do file
        self.new_to_do_file_re = re.compile("Leaving MakeBzDoneFileToDataCenter")

        # Compile duplicate chunk
        self.duplicate_encrypted = re.compile(
            "noCopy code path VERY SUCCESSFUL,.*largeFileName=([^,]*).*_seq([^\.]*)"
        )

    def _get_latest_logfile_name(self) -> Path:
        """
        Scan the log directory for any files that end in .log, and return the one
        with the newest modification time

        :return:
        """
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

    def _process_line(self, _line: str) -> None:
        _filename: Path | None = None
        _bytes: int = 0
        _rate: str | None = None
        _timestamp: str | None = None
        _datetime: datetime | None = None

        _line = _line.strip()
        self._multi_log.log(_line, level=logging.DEBUG)

        # When this matches it means that there a new large file being backed up
        match_result = self.prepare_match_re.match(_line)
        if match_result is not None:
            if _line[4] == "-":
                # The transmit file uses UTC time
                _timestamp = _line[0:19]
                _datetime = (
                    datetime.strptime(_timestamp, "%Y-%m-%d %H:%M:%S")
                    .replace(tzinfo=timezone.utc)
                    .astimezone(tz=None)
                )
            else:
                _timestamp = _line[0:14]
                _datetime = (
                    datetime.strptime(_timestamp, "%Y%m%d%H%M%S")
                    .replace(tzinfo=timezone.utc)
                    .astimezone(tz=None)
                )
            chunk = True
            _filename = Path(_line.split(": ")[-1].rstrip())

            if not self.to_do.exists(str(_filename)):
                self.to_do.add_file(
                    _filename,
                    is_chunk=chunk,
                    timestamp=_datetime,
                )
            self.to_do.current_file = self.to_do.get_file(str(_filename))
            self.qt.signals.start_new_file.emit(str(_filename))

        _dedup_search_results = self.dedup_search_re.search(_line)
        if _dedup_search_results is not None:
            chunk = True
            chunk_number = int(_dedup_search_results.group(1))
            _filename = Path(_line.split(": ")[-1].rstrip())
            _timestamp = _line[0:19]
            if _timestamp[4] == "-":
                # The transmit file uses UTC time
                _datetime = (
                    datetime.strptime(_timestamp, "%Y-%m-%d %H:%M:%S")
                    .replace(tzinfo=timezone.utc)
                    .astimezone(tz=None)
                )
            else:
                _timestamp = _line[0:14]
                _datetime = (
                    datetime.strptime(_timestamp, "%Y%m%d%H%M%S")
                    .replace(tzinfo=timezone.utc)
                    .astimezone(tz=None)
                )

            if not self.to_do.exists(str(_filename)):
                self.to_do.add_file(
                    Path(_filename),
                    is_chunk=chunk,
                    timestamp=_datetime,
                )  # add_file locks the backup list itself

            backup_file = self.to_do.get_file(str(_filename))  # type: BackupFile
            backup_file.add_deduped(chunk_number)
            backup_file.current_chunk = chunk_number
            backup_file.rate = "bztransmit"

        _dedup_encrypted_search_results = self.duplicate_encrypted.search(_line)
        if _dedup_encrypted_search_results is not None:
            chunk = True
            chunk_number = int(_dedup_encrypted_search_results.group(2), base=16)
            _filename = Path(_dedup_encrypted_search_results.group(1))
            _timestamp = _line[0:19]
            if _timestamp[4] == "-":
                # The transmit file uses UTC time
                _datetime = (
                    datetime.strptime(_timestamp, "%Y-%m-%d %H:%M:%S")
                    .replace(tzinfo=timezone.utc)
                    .astimezone(tz=None)
                )
            else:
                _timestamp = _line[0:14]
                _datetime = (
                    datetime.strptime(_timestamp, "%Y%m%d%H%M%S")
                    .replace(tzinfo=timezone.utc)
                    .astimezone(tz=None)
                )

            if not self.to_do.exists(str(_filename)):
                self.to_do.add_file(
                    Path(_filename),
                    is_chunk=chunk,
                    timestamp=_datetime,
                )  # add_file locks the backup list itself

            backup_file = self.to_do.get_file(str(_filename))  # type: BackupFile
            backup_file.add_deduped(chunk_number)
            backup_file.current_chunk = chunk_number
            backup_file.rate = "bztransmit"

        _new_to_do_file_search_results = self.new_to_do_file_re.search(_line)
        if _new_to_do_file_search_results is not None:
            # TODO: We need to re-read the to_do file
            self._multi_log.log(f"There is a new ToDo file. Reread it ({_timestamp})")
            pass

    def read_file(self) -> None:
        while True:
            if not self.to_do:
                # Give the main program time to start up and scan the disks
                time.sleep(10)
                self.to_do = self.backup_status.to_do
            else:
                break

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
