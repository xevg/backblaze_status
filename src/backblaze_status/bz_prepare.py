import re
import select
import time
from dataclasses import dataclass, field
from pathlib import Path

from .backblaze_redis import BackBlazeRedis
from .constants import RedisKeys, RedisMessageTypes
from .dev_debug import DevDebug
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
    previous_file: str = field(default=None, init=False)

    def __post_init__(self):
        self._multi_log = MultiLogger("BzPrepare", terminal=True, qt=self.backup_status)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting BzPrepare")
        self.debug: DevDebug = self.backup_status.debug

        self.backblaze_redis = BackBlazeRedis()

        # Compile the chunk search regular expression
        self.chunk_search_re = re.compile(r"seq([0-9a-f]+).dat")

        # 1       +       00000000026c7d44        0000018c0f260c68        10485760        /Library/Backblaze.bzpkg/bzdata/bzbackup/bzdatacenter/bzcurrentlargefile/onechunk_seq00000.dat

    def get_latest_logfile_name(self) -> Path:
        """
        Scan the log directory for any files that end in .log, and return the one with the newest modification time

        :return:
        """
        return Path(self.BZ_LOG_DIR) / "bz_todo_for_chunks.dat"

    def tail_file(self, _file, log_file: Path) -> str:
        while True:
            # This log file can be deleted and overwritten, so I need to check if it
            # still exists, and if it does, make sure that the file isn't shorter
            # than the last time I checked

            if not log_file.exists():
                return

            if log_file.stat().st_size < self.file_size:
                self.file_size = 0
                return

            # You can do a select() on sys.stdin, and put a timeout on the select, ie:
            #
            # rfds, wfds, efds = select.select( [sys.stdin], [], [], 5)
            #
            # would give you a five-second timeout. If the timeout expired, then rfds
            # would be an empty list. If the user entered something within five
            # seconds, then rfds will be a list containing sys.stdin.

            readable, _, _ = select.select([_file], [], [], 0.5)
            if not readable:
                # If no new line is available, wait a half second then try again
                time.sleep(0.5)
                continue

            # I know there is a line waiting for me, so read it
            _line = _file.readline()
            if not _line:
                time.sleep(1)
                continue

            # Save the size of the file, so I can compare it next time
            self.file_size = log_file.stat().st_size
            yield _line

    def read_file(self) -> None:
        log_file = self.get_latest_logfile_name()
        while True:
            if not log_file.exists():
                time.sleep(1)
                continue
            try:
                # Because there is no file name in this file, pull the name of the
                # current file that is set in bz_transmit
                current_file: str = self.backblaze_redis.current_file
                while current_file is None:
                    # If there is no current file set, then wait till there is one
                    time.sleep(1)
                    current_file: str = self.backblaze_redis.current_file

                # Why am I doing this?
                while current_file == self.previous_file:
                    time.sleep(1)
                    current_file: str = self.backblaze_redis.current_file

                self.previous_file = current_file

                with log_file.open("r") as log_fd:
                    for line in self.tail_file(log_fd, log_file):
                        # Read until the tail returns rather than yields. If it
                        # returns, then I need to check for a new file, and start again
                        self.process_line(line)

                log_file = self.get_latest_logfile_name()
                self._multi_log.log(f"Log file ended, opening new log file {log_file}")

            except FileNotFoundError:
                # This is expected
                time.sleep(1)

    def process_line(self, line: str) -> None:
        #         # 1       +       00000000026c7d44        0000018c0f260c68        10485760        /Library/Backblaze.bzpkg/bzdata/bzbackup/bzdatacenter/bzcurrentlargefile/onechunk_seq00000.dat
        results = self.chunk_search_re.search(line.strip())
        if results is not None:
            chunk_hex = results.group(1)
            chunk_number: int = int(chunk_hex, base=16)

            self.backblaze_redis.publish(
                RedisMessageTypes.AddPreparedChunk,
                f"Add prepared chunk {chunk_number}",
                data={
                    RedisKeys.Chunk: chunk_number,
                },
            )

        return
