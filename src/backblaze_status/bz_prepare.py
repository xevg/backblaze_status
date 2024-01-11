import re
import select
import time
from dataclasses import dataclass, field
from datetime import datetime
from io import TextIOWrapper
from pathlib import Path

from icecream import ic

from .backup_file import BackupFile
from .bz_log_file_watcher import BzLogFileWatcher
from .main_backup_status import BackupStatus
from .qt_backup_status import QTBackupStatus
from .to_do_files import ToDoFiles
from .utils import MultiLogger, get_lock, return_lock


@dataclass
class BzPrepare(BzLogFileWatcher):
    backup_status: BackupStatus
    qt: QTBackupStatus | None = field(default=None)
    backup_list: ToDoFiles | None = field(default=None, init=False)
    BZ_LOG_DIR: str = field(
        default="/Library/Backblaze.bzpkg/bzdata/bzbackup/bzdatacenter/bzcurrentlargefile",
        init=False,
    )
    file_size: int = field(default=0, init=False)
    previous_file: str = field(default=None, init=False)
    first_pass: bool = field(default=True, init=False)

    def __post_init__(self):
        self._multi_log = MultiLogger("BzPrepare", terminal=True, qt=self.qt)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting BzPrepare")

        # Compile the chunk search regular expression
        self.chunk_search_re = re.compile(r"seq([0-9a-f]+).dat")

        # 1       +       00000000026c7d44        0000018c0f260c68        10485760        /Library/Backblaze.bzpkg/bzdata/bzbackup/bzdatacenter/bzcurrentlargefile/onechunk_seq00000.dat

    def _get_latest_logfile_name(self) -> Path:
        """
        Scan the log directory for any files that end in .log, and return the one with the newest modification time

        :return:
        """
        return Path(self.BZ_LOG_DIR) / "bz_todo_for_chunks.dat"

    def _tail_file(self, _file: TextIOWrapper) -> str:
        _log_file = self._get_latest_logfile_name()
        while True:
            if not _log_file.exists():
                return

            if _log_file.stat().st_size < self.file_size:
                self.file_size = 0
                return

            # TODO: Change this from a readline to a select, and then check the file each time
            # You can do a select() on sys.stdin, and put a timeout on the select, ie:
            #
            # rfds, wfds, efds = select.select( [sys.stdin], [], [], 5)
            #
            # would give you a five second timeout. If the timeout expired, then rfds
            # would be an empty list. If the user entered something within five
            # seconds, then rfds will be a list containing sys.stdin.

            readable, _, _ = select.select([_file], [], [], 0.5)
            if not readable:
                time.sleep(0.5)
                continue

            _line = _file.readline()
            ic(_line)
            if not _line:
                time.sleep(1)
                continue
            self.file_size = _log_file.stat().st_size
            yield _line

    def read_file(self) -> None:
        while True:
            if not self.backup_list:
                # Give the main program time to start up and scan the disks
                time.sleep(10)
                self.backup_list = self.backup_status.to_do
            else:
                break

        _log_file = self._get_latest_logfile_name()
        while True:
            if not _log_file.exists():
                id(f"{str(_log_file)} not found")
                time.sleep(1)
                continue
            try:
                pre_stat = _log_file.stat()
                self.file_size = pre_stat.st_size

                ic(f"Starting to read {_log_file}")
                backup_file: BackupFile = self.backup_list.current_file
                while not backup_file:
                    time.sleep(1)
                    backup_file: BackupFile = self.backup_list.current_file

                while str(backup_file.file_name) == self.previous_file:
                    time.sleep(1)
                    backup_file: BackupFile = self.backup_list.current_file

                self.previous_file = str(backup_file.file_name)
                # TODO: Do soemthing to determine that the current file is not the previous file, and if it
                #  is, then wait for it to be the current?
                with _log_file.open("r") as _log_fd:
                    self._multi_log.log(f"Reading file {_log_file}")
                    for _line in self._tail_file(_log_fd):
                        tell = _log_fd.tell()
                        self._process_line(_line, tell)
                self.first_pass = False

                ic(f"Log file ended")
                _log_file = self._get_latest_logfile_name()
            except FileNotFoundError:
                # This is expected
                time.sleep(1)

    def _process_line(self, _line: str, tell: int) -> None:
        #         # 1       +       00000000026c7d44        0000018c0f260c68        10485760        /Library/Backblaze.bzpkg/bzdata/bzbackup/bzdatacenter/bzcurrentlargefile/onechunk_seq00000.dat
        results = self.chunk_search_re.search(_line.strip())
        if results is not None:
            chunk_hex = results.group(1)
            chunk_num: int = int(chunk_hex, base=16)

            # TODO: Do soemthing to determine that the current file is not the previous file, and if it
            #  is, then wait for it to be the current?

            backup_file: BackupFile = self.backup_list.current_file
            while backup_file is None:
                time.sleep(1)
                backup_file: BackupFile = self.backup_list.current_file

            lock_start = get_lock(backup_file.lock, "backup_file", "bz_prepare:82")
            backup_file.chunks_prepared.add(chunk_num)
            return_lock(backup_file.lock, "backup_file", "bz_prepare:84", lock_start)
            # ic(f"Preparing {str(backup_file.file_name)} chunk {chunk_num}")
            if self.first_pass:
                if tell < self.file_size:
                    return
            time.sleep(0.1)
            self.backup_status.qt.signals.update_prepare.emit(
                str(backup_file.file_name), chunk_num
            )
