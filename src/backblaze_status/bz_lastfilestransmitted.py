import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .backup_file import BackupFile
from .bz_batch import BzBatch
from .bz_log_file_watcher import BzLogFileWatcher
from .main_backup_status import BackupStatus
from .qt_backup_status import QTBackupStatus
from .to_do_files import ToDoFiles
from .utils import MultiLogger
from .configuration import Configuration
from .dev_debug import DevDebug
from rich.pretty import pprint
@dataclass
class BzLastFilesTransmitted(BzLogFileWatcher):
    """
    Continuously scan the lastfiletransmitted file to get information about the state of the backup
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
    _previous_filename: str | None = field(default=None, init=False)
    _current_large_filename: str | None = field(default=None)
    _first_pass: bool = field(default=True, init=False)
    _batch: BzBatch | None = field(default=None, init=False)
    _file_size: int = field(default=0, init=False)
    BZ_LOG_DIR: str = field(
        default="/Library/Backblaze.bzpkg/bzdata/bzlogs/bzreports_lastfilestransmitted/",
        init=False,
    )

    def __post_init__(self):
        self._multi_log = MultiLogger(
            "BzLastFilesTransmitted", terminal=True, qt=self.qt
        )
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting BzLastFilesTransmitted")

        self.go_to_end = True
        self.debug = self.qt.debug

    def _get_latest_logfile_name(self) -> Path:
        """
        Scan the log directory for any files that end in .log, and return the one with the newest modification time

        :return:
        """
        # return Path(self.BZ_LOG_DIR) / "28.log"
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

    def _process_line(self, _line: str, _tell: int) -> None:
        _filename: str | None = None
        _bytes: int = 0
        _rate: str | None = None
        _timestamp: str = str()

        _line = _line.strip()
        _chunk_number = 0
        chunk: bool = False
        multiple_flag: bool = False

        if _line == "":
            self._blank_lines += 1
        else:
            self._total_lines += 1
        if not self._first_pass:
            self._multi_log.log(_line, level=logging.DEBUG)

        self.debug.print("lastfilestransmitted.show_line", _line)

        """
        The format of the file are fixed length fields, separated by "-" characters
        Backblaze backs up files in one of three ways
         1) The file is transmitted on its own
         2) The file is large enough to need to be split up
         3) The file is small enough to be transmitted in a batch with other files

        For the first case, the typical line is 6 fields:
         1) Timestamp
         2) The tee-shirt size
         3) They type of throttling
         4) The rate the file was transmitted at. This field can also have "dedup", 
              which means that it has deduplicated this file or chunk, and not 
              transmitted it over. That is very efficient.
         5) The number of bytes in the file
         6) The filename

        2024-01-03 00:00:10 -  large  - throttle auto     11 - 19780 kBits/sec 
            - 10485760 bytes - /Volumes/CameraHDD4/SecuritySpy/Bedroom 
            Foot/2023-11-06/2023-11-06 00 C Bedroom Foot.m4v
        (Above line is a single line, split for readability)

        The second case is just like the first, but instead of just filename, 
        it specifies which chunk of the file it is

        2024-01-03 00:00:10 -  large  - throttle auto     11 - 32091 kBits/sec 
           - 10485760 bytes
           - Chunk 00012 of /Volumes/CameraHDD4/SecuritySpy/Bedroom Foot/2023-11-06
           /2023-11-06 00 C Bedroom Foot.m4v
        (Above line is a single line, split for readability)

        The third case batches multiple files together. The first line is similar to 
        the first case, but it says how many of the files were batched together

        2024-01-01 19:42:53 -  large  - throttle auto     11 - 30985 kBits/sec 
          -  6859241 bytes
          - Multiple small files batched in one request, the 17 files are listed below:
        (Above line is a single line, split for readability)

        The next lines in the file are the batched files, 17 of them in this example. 
        It is only three fields, a timestamp, a blank field, and the name of the 
        file 2024-01-01 19:42:53 - - /Users/xev/Qt/QtDesignStudio/Qt Design 
        Studio.app/Contents/Frameworks/libGLSL.4.3.2.dylib (Above line is a single 
        line, split for readability)
        
        
        The flow is:
          If the previous filename is None, set the previous filename to the current 
          filename
          
        """

        _fields = _line.split(" - ")
        # Sometimes filenames will have hyphens in them, and in that case treat it as
        # a single filename
        if len(_fields) > 6:
            new_field = _fields[:5]
            new_field.append(" - ".join(_fields[5:]))
            _fields = new_field

        match len(_fields):
            case 6:
                self._batch = None  # Since it's not just 3 fields, reset the batch
                _timestamp, _size, _type, _rate, _bytes_str, _filename = _fields

                # Convert bytes to int, if we can
                try:
                    _bytes = int(_bytes_str.strip().split(" ")[0])
                except:
                    _bytes = 0

                match _filename[0:5]:
                    # If it's a chunk, process it that way. Chunks are hex numbers I convert into ints
                    case "Chunk":
                        _chunk_number = int(_filename[6:11], base=16)
                        _filename = _filename[15:]
                        chunk = True
                        self._is_batch = False

                    # If it's a multiple file batch, create a new batch construct
                    #  I don't think that I'm actually using this for anything,
                    case "Multi":
                        self._batch = BzBatch(size=_bytes, timestamp=_timestamp)
                        self._batch_count += 1
                        self._is_batch = True
                        # Since we don't do anything with the multi line, return now
                        return
            case 3:
                # This is a file within the batch
                _timestamp, _, _filename = _fields
                _bytes = 0
                self._batch.add_file(_filename)
            case _:
                print(f"Unrecognized line: {_line}")

        # At this point we have a filename. I take a look at the timestamp, because when I start up the monitor,
        #  there can be a lot of older information that I don't care about, so I discard anything over 4 hours old

        _datetime = datetime.strptime(_timestamp, "%Y-%m-%d %H:%M:%S")

        # If it's a while ago, don't add it to the to do list
        now = datetime.now()
        if (now - _datetime).seconds > 60 * 60 * 4:
            return

        # If the file we are backing up is not on the to_do list, then we add it
        if not self.backup_list.exists(_filename):
            print(f"Unexpected file {_filename} being backed up")
            self.backup_list.add_file(
                Path(_filename),
                is_chunk=chunk,
                timestamp=_datetime,
            )  # No lock here because add_file locks

        if self._previous_filename is None:
            self._previous_filename = _filename

            # We have started transmitting, so set the marker for that
            self.qt.signals.transmitting.emit(_filename)

        elif self._previous_filename != _filename:
            # First complete the previous filename
            # self.qt.signals.completed_file.emit(self._previous_filename)

            # Now set the new filename tp the previous filename
            self._previous_filename = _filename

            # We have started transmitting, so set the marker for that
            self.qt.signals.transmitting.emit(_filename)

        if _rate == "dedup":
            dedup = True
        else:
            dedup = False

        # Get the file off of the to_list. I have to lock it so no other thread
        # reads/writes from it while I do
        backup_file = self.backup_list.get_file(str(_filename))  # type: BackupFile
        if backup_file is None:
            return

        if _rate:
            _rate = _rate.strip()
            # Keep track of how many files and bytes were deduplicated
            if dedup:
                if chunk:
                    backup_file.add_deduped(_chunk_number)
                else:
                    file = Path(_filename[15:])
                    backup_file.deduped_bytes += file.stat().st_size

                backup_file.is_deduped = True
            else:
                if chunk:
                    backup_file.add_transmitted(_chunk_number)
                else:
                    backup_file.transmitted_bytes += _bytes
                    backup_file.is_deduped = False

            if _rate != "dedup" and _rate != "":
                _rate = f"{int(_rate[:-10]):,}{_rate[-10:]}"

            backup_file.rate = _rate
            backup_file.total_bytes_processed += _bytes

        if self._batch:
            backup_file.batch = self._batch
        self._bytes += _bytes
        backup_file.timestamp = _datetime

        return
        # Send a notification to the display to let it output the data. Since there can be a *lot* of output,
        #  especially if I'm catching up on the file, I throw a little delay in so that I don't overwhelm
        #  the GUI event loop
        if self.qt:
            if _tell < self._file_size:
                return
            time.sleep(0.1)
            self.qt.signals.update_log_line.emit(_filename)

    def read_file(self) -> None:
        while True:
            if not self.backup_list:
                # Give the main program time to start up and scan the disks
                time.sleep(10)
                self.backup_list = self.backup_status.to_do
            else:
                break

        _log_file = self._get_latest_logfile_name()
        pre_stat = _log_file.stat()
        self._file_size = pre_stat.st_size
        self._current_filename = _log_file
        while True:
            if _log_file is None:
                self._multi_log.log(
                    "No lasttransmitted file, sleeping and trying later",
                    level=logging.ERROR,
                )
                time.sleep(60)
            else:
                with _log_file.open("r") as _log_fd:
                    self._multi_log.log(f"Reading file {_log_file}")
                    if self._first_pass:
                        _log_fd.seek(0, 2)

                    for _line in self._tail_file(_log_fd):
                        tell = _log_fd.tell()
                        self._process_line(_line, tell)

                    self._first_pass = False
                    self._multi_log.log("Finished first pass", module=self._module_name)

                    _log_file = self._get_latest_logfile_name()
                    self._current_filename = _log_file

    def _tail_file(self, _file) -> str:
        while True:
            _line = _file.readline()

            if not _line:
                time.sleep(1)
                _new_filename = self._get_latest_logfile_name()
                if _new_filename != self._current_filename:
                    return
                continue

            yield _line
