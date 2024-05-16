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
    """
    This reads the current large file (if it exists) which contains information about
    all the chunks as it prepares it.
    """

    backup_status: QTBackupStatus
    to_do_files: ToDoFiles | None = field(default=None, init=False)
    BZ_TODO_FOR_CHUNKS: str = field(
        default=(
            f"/Library/Backblaze.bzpkg/bzdata/bzbackup/"
            f"bzdatacenter/bzcurrentlargefile/bz_todo_for_chunks.dat"
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

    def read_file(self) -> None:
        """
        Read the file and process each line, restarting when a new file is being
        processed
        """
        log_file = Path(self.BZ_TODO_FOR_CHUNKS)
        self.previous_file = CurrentState.CurrentFile
        while True:
            ic("Checking if log file exists")
            if not log_file.exists():
                time.sleep(1)
                continue

            location = 0
            stat = log_file.stat()
            old_mtime = stat.st_mtime

            def file_check():
                """
                Check the log file. Return true if it's still the same file,
                false if the file doesn't exist, or it's a different file
                """
                if not log_file.exists():
                    return False
                ic("Checking if CurrentFile is set")
                if CurrentState.CurrentFile is None:
                    # If there is no current file set, then wait till there is one
                    time.sleep(1)
                    return False

                # I don't want to keep rereading the same file over and over again,
                # so check to see if it is the same file
                ic("Checking if filename has changed")
                if CurrentState.CurrentFile == self.previous_file:
                    time.sleep(1)
                    return True

                # At this point, it's a new file, reread it
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
                        if CurrentState.CurrentFile is None:
                            ic("CurrentFile not set")
                            time.sleep(1)
                            continue

                        readable, _, _ = select.select([log_fd], [], [], 0.5)
                        if not readable:
                            # If file_check returns false, restart files
                            if file_check():
                                continue
                            else:
                                break
                        line = log_fd.readline()
                        if line is None or line == "":
                            if file_check():
                                continue
                            else:
                                ic(f"Restarting {str(log_file)}")
                                break
                        location = log_fd.tell()
                        self.process_line(line)

            except FileNotFoundError:
                # This is expected
                time.sleep(1)

    def process_line(self, line: str) -> None:
        """
        Process a single line from the BzPrepare
        :param line: the line to process
        """
        ic(f"Processing line {line}")
        # Scan the line
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
            # self.backup_status.signals.update_chunk.emit(chunk_number)
            ic(f"Emitting chunk {chunk_number}")
            self.backup_status.signals.get_messages.emit(message)

        return
