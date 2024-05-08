import re
import select
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from icecream import ic

from .constants import Key, MessageTypes
from .current_state import CurrentState
from .qt_backup_status import QTBackupStatus
from .to_do_files import ToDoFiles
from .utils import MultiLogger


@dataclass
class BzPrepare:
    backup_status: QTBackupStatus
    to_do_files: ToDoFiles | None = field(default=None, init=False)
    BZ_LOG_DIR: str = field(
        default=(
            f"/Library/Backblaze.bzpkg/bzdata/bzbackup/"
            f"bzdatacenter/bzcurrentlargefile"
        ),
        init=False,
    )
    file_size: int = field(default=0, init=False)
    current_file: str = field(default=None, init=False)
    previous_file: Optional[str] = field(default=None, init=False)
    publish_count: int = field(default=0, init=False)

    def __post_init__(self):
        self._multi_log = MultiLogger("BzPrepare", terminal=True, qt=self.backup_status)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting BzPrepare")

        # self.backblaze_redis = BackBlazeRedis()

        # Compile the chunk search regular expression
        self.chunk_search_re = re.compile(r"seq([0-9a-f]+).dat")

    def get_latest_logfile_name(self) -> Path:
        """
        Scan the log directory for any files that end in .log, and return the one
        with the newest modification time

        :return:
        """
        return Path(self.BZ_LOG_DIR) / "bz_todo_for_chunks.dat"

    def tail_file(self, _file, log_file: Path):
        while True:
            # This log file can be deleted and overwritten, so I need to check if it
            # still exists, and if it does, make sure that the file isn't shorter
            # than the last time I checked

            if not log_file.exists():
                return

            new_size = log_file.stat().st_size
            if new_size < self.file_size:
                ic(f"Log file shrank from {self.file_size} to {new_size}")
                self.file_size = new_size
                time.sleep(2)
                continue

            # You can do a select() on sys.stdin, and put a timeout on the select, ie:
            #
            # rfds, wfds, efds = select.select( [sys.stdin], [], [], 5)
            #
            # would give you a five-second timeout. If the timeout expired, then rfds
            # would be an empty list. If the user entered something within five
            # seconds, then rfds will be a list containing sys.stdin.

            readable, _, _ = select.select([_file], [], [], 0.5)
            if not readable:
                ic("Waiting for line to become available")
                # If no new line is available, wait a half second then try again
                time.sleep(0.5)
                continue

            # I know there is a line waiting for me, so read it
            _line = _file.readline()
            if not _line:
                ic("No line read")
                break

            # Save the size of the file, so I can compare it next time
            self.file_size = log_file.stat().st_size
            self.process_line(_line)

    def read_file(self) -> None:
        log_file = Path(self.BZ_LOG_DIR) / "bz_todo_for_chunks.dat"
        previous_file = CurrentState.CurrentFile
        while True:
            ic("Checking if log file exists")
            if not log_file.exists():
                time.sleep(1)
                continue

            location = 0
            stat = log_file.stat()
            old_size = stat.st_size
            old_mtime = stat.st_mtime

            def file_check():
                if not log_file.exists():
                    return False
                ic("Checking if CurrentFile is set")
                if CurrentState.CurrentFile is None:
                    # If there is no current file set, then wait till there is one
                    time.sleep(1)
                    return False

                # I don't want to keep rereading the same file over and over again
                ic("Checking if filename has changed")
                if CurrentState.CurrentFile == self.previous_file:
                    time.sleep(1)
                    return True

                ic(f"Preparing {CurrentState.CurrentFile}")
                self.previous_file = CurrentState.CurrentFile

                file_stat = log_file.stat()
                if file_stat.st_size == location and file_stat.st_mtime == old_mtime:
                    ic("No change in file")
                    time.sleep(1)
                    return True
                else:
                    if file_stat.st_size < location:
                        ic(f"File size shrank from {file_stat.st_size} to {location}")
                        return False
                ic("New data available")
                time.sleep(1)
                return True

            try:
                with log_file.open("r") as log_fd:
                    while True:
                        # self.tail_file(log_fd, log_file)
                        # Read until the tail returns rather than yields. If it
                        # returns, then I need to check for a new file, and start again

                        if CurrentState.CurrentFile is None:
                            ic("CurrentFile not set")
                            time.sleep(1)
                            continue

                        readable, _, _ = select.select([log_fd], [], [], 0.5)
                        # print(f"readable = {readable}")
                        if not readable:
                            if file_check():
                                continue
                            else:
                                break
                        line = log_fd.readline()
                        if line is None or line == "":
                            if file_check():
                                continue
                            else:
                                # print(f"Restarting {str(log_file)}")
                                break
                        location = log_fd.tell()
                        # print(f"{line}, now at {location}")
                        self.process_line(line)
                    # I need to make it so that it tries reading the new file

            except FileNotFoundError:
                # This is expected
                time.sleep(1)

    def process_line(self, line: str) -> None:
        ic(f"Processing line {line}")
        results = self.chunk_search_re.search(line.strip())
        if results is not None:
            chunk_hex = results.group(1)
            chunk_number: int = int(chunk_hex, base=16)

            self.publish_count += 1
            message = {
                "type": MessageTypes.AddPreparedChunk,
                "message": f"Add prepared chunk {chunk_number}",
                "data": {
                    Key.FileName: CurrentState.CurrentFile,
                    Key.Chunk: chunk_number,
                },
                "timestamp": str(datetime.now()).split(".")[0],
                "publish_count": self.publish_count,
            }
            ic(f"Emitting chunk {chunk_number}")
            self.backup_status.signals.get_messages.emit(message)

        return
