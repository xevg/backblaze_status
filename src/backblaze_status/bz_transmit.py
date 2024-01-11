import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import logging

from .backup_file import BackupFile
from .bz_log_file_watcher import BzLogFileWatcher
from .main_backup_status import BackupStatus
from .qt_backup_status import QTBackupStatus
from .to_do_files import ToDoFiles
from .utils import MultiLogger, get_lock, return_lock


@dataclass
class BzTransmit(BzLogFileWatcher):
    """
    The bztransmit log contains a lot of information about the backup process. I ignore most of it, but there are
    certain key lines that give insights into what is happening in the backup
    """

    backup_status: BackupStatus
    qt: QTBackupStatus | None = field(default=None)
    backup_list: ToDoFiles | None = field(default=None, init=False)

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

    def _get_latest_logfile_name(self) -> Path:
        """
        Scan the log directory for any files that end in .log, and return the one with the newest modification time

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

            if not self.backup_list.exists(_filename):
                self.backup_list.add_file(
                    Path(_filename),
                    is_chunk=chunk,
                    timestamp=_datetime,
                )
            lock_start = get_lock(
                self.backup_list.lock, "backup_list", "bz_transmit:134"
            )
            self.backup_list.current_file = self.backup_list.file_dict[str(_filename)]
            return_lock(
                self.backup_list.lock, "backup_list", "bz_transmit:136", lock_start
            )
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
                _datetime = (
                    datetime.strptime(_timestamp, "%Y%m%d%H%M%S")
                    .replace(tzinfo=timezone.utc)
                    .astimezone(tz=None)
                )

            if not self.backup_list.exists(str(_filename)):
                self.backup_list.add_file(
                    Path(_filename),
                    is_chunk=chunk,
                    timestamp=_datetime,
                )  # add_file locks the backup list itself

            file_info = self.backup_list.file_dict[str(_filename)]  # type: BackupFile
            lock_start = get_lock(file_info.lock, "file_info", "bz_transmit:167")
            file_info.dedup_count += 1
            file_info.chunks_deduped.add(chunk_number)
            file_info.chunk_current = chunk_number
            file_info.rate = "bztransmit"
            return_lock(file_info.lock, "file_info", "bz_transmit:172", lock_start)

        _new_to_do_file_search_results = self.new_to_do_file_re.search(_line)
        if _new_to_do_file_search_results is not None:
            # TODO: We need to re-read the to_do file
            self._multi_log.log(f"There is a new ToDo file. Reread it ({_timestamp})")
            pass
