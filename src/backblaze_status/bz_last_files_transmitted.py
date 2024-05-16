import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .constants import Key, MessageTypes
from .qt_backup_status import QTBackupStatus
from .to_do_files import ToDoFiles
from .utils import MultiLogger


@dataclass
class BzLastFilesTransmitted:
    """
    Continuously scan the lastfiletransmitted file to get information about the
    state of the backup
    """

    backup_status: QTBackupStatus

    to_do_files: ToDoFiles | None = field(default=None, init=False)
    _total_lines: int = field(default=0, init=False)
    _dedups: int = field(default=0, init=False)
    _blank_lines: int = field(default=0, init=False)
    _bytes: int = field(default=0, init=False)
    _current_filename: Path | None = field(default=None, init=False)
    _previous_filename: str | None = field(default=None, init=False)
    _current_large_filename: str | None = field(default=None)
    _first_pass: bool = field(default=True, init=False)
    _file_size: int = field(default=0, init=False)
    publish_count: int = field(default=0, init=False)
    BZ_LOG_DIR: str = field(
        default="/Library/Backblaze.bzpkg/bzdata/"
        "bzlogs/bzreports_lastfilestransmitted/",
        init=False,
    )

    def __post_init__(self):
        self._multi_log = MultiLogger(
            "BzLastFilesTransmitted", terminal=True, qt=self.backup_status
        )
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting BzLastFilesTransmitted")

    def get_latest_logfile_name(self) -> Path:
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
        """
        For each line read, this processes it
        :param _line: the line to process
        """
        _filename: str | None = None
        _bytes: int = 0
        _rate: str | None = None
        _timestamp: str = str()

        _line = _line.strip()
        _chunk_number = 0
        chunk: bool = False

        if _line == "":
            self._blank_lines += 1
        else:
            self._total_lines += 1
        if not self._first_pass:
            # If this is the first pass, don't output the line
            self._multi_log.log(_line, level=logging.DEBUG)

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
                _timestamp, _size, _type, _rate, _bytes_str, _filename = _fields

                # Convert bytes to int, if we can
                try:
                    _bytes = int(_bytes_str.strip().split(" ")[0])
                except Exception as exp:
                    _bytes = 0

                match _filename[0:5]:
                    # If it's a chunk, process it that way. Chunks are hex numbers
                    # I convert into ints
                    case "Chunk":
                        _chunk_number = int(_filename[6:11], base=16)
                        _filename = _filename[15:]
                        chunk = True

                    case "Multi":
                        # Since we don't do anything with the multi line, return now
                        return

            case 3:
                # This is a file within the batch, then the file is started and
                # completed within one line, so send a start and a complete
                _timestamp, _, _filename = _fields
                _bytes = 0
                _datetime = datetime.strptime(_timestamp, "%Y-%m-%d %H:%M:%S")
                self.emit_message(
                    MessageTypes.StartNewFile,
                    f"New file is {_filename}",
                    {
                        Key.FileName: _filename,
                        Key.StartTime: _datetime,
                    },
                )
                self.emit_message(
                    MessageTypes.Completed,
                    f"{_filename} Completed",
                    {
                        Key.FileName: _filename,
                        Key.EndTime: _datetime,
                    },
                )
                return

            case _:
                print(f"Unrecognized line: {_line}")
                return

        _datetime = datetime.strptime(_timestamp, "%Y-%m-%d %H:%M:%S")

        if self._previous_filename is None:
            self._previous_filename = _filename

            self.emit_message(
                MessageTypes.StartNewFile,
                f"New file is {_filename}",
                {
                    Key.FileName: _filename,
                    Key.StartTime: _datetime,
                },
            )

        elif self._previous_filename != _filename:
            # The filename has changed, and we are still transmitting

            self.emit_message(
                MessageTypes.Completed,
                f"{self._previous_filename} completed",
                {
                    Key.FileName: self._previous_filename,
                    Key.EndTime: datetime.now(),
                },
            )

            # Now set the new filename tp the previous filename
            self._previous_filename = _filename

        if _rate:
            _rate = _rate.strip()
            if _rate == "dedup":
                dedup = True
            else:
                dedup = False
            # Keep track of how many files and bytes were deduplicated
            if dedup:
                if chunk:
                    self.emit_message(
                        MessageTypes.AddDedupedChunk,
                        f"Add deduped chunk {_chunk_number} to {_filename}",
                        {
                            Key.FileName: _filename,
                            Key.Chunk: _chunk_number,
                        },
                    )
                    # self.backup_status.signals.update_chunk.emit(_chunk_number)

                else:
                    self.emit_message(
                        MessageTypes.IsDeduped,
                        f"Add deduped file {_filename}",
                        {
                            Key.FileName: _filename,
                            Key.IsDeduped: True,
                        },
                    )

            else:  # If it's not a dedup
                if chunk:
                    self.emit_message(
                        MessageTypes.AddTransmittedChunk,
                        f"Add transmitted chunk {_chunk_number} to " f"{_filename}",
                        {
                            Key.FileName: _filename,
                            Key.Chunk: _chunk_number,
                        },
                    )
                    # self.backup_status.signals.update_chunk.emit(_chunk_number)

                else:  # It's not a chunk, then the file was completed in one line
                    self.emit_message(
                        MessageTypes.Completed,
                        f"{_filename} Completed",
                        {
                            Key.FileName: _filename,
                            Key.EndTime: datetime.now(),
                        },
                    )

        return

    def emit_message(self, message_type: str, message_string: str, data: dict) -> None:
        """
        A wrapper method that emits a standardized message
        :param message_type: The message type
        :param message_string: The message string
        :param data: The underlying data to transfer
        """

        self.publish_count += 1
        message = {
            "type": message_type,
            "message": message_string,
            "data": data,
            "timestamp": str(datetime.now()).split(".")[0],
            "publish_count": self.publish_count,
        }
        self.backup_status.signals.get_messages.emit(message)

    def read_file(self) -> None:
        """
        Read a new file
        """
        _log_file = self.get_latest_logfile_name()
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
                    # If this is the first time through the file, go to the end of
                    # the file
                    if self._first_pass:
                        _log_fd.seek(0, 2)

                    for _line in self._tail_file(_log_fd):
                        self._process_line(_line)

                    self._first_pass = False
                    self._multi_log.log("Finished first pass", module=self._module_name)

                    _log_file = self.get_latest_logfile_name()
                    self._current_filename = _log_file

    def _tail_file(self, _file) -> str:
        """
        Continuously reads a file and returns each line
        :param _file: The file to read
        """
        while True:
            _line = _file.readline()

            if not _line:
                time.sleep(1)
                _new_filename = self.get_latest_logfile_name()
                if _new_filename != self._current_filename:
                    return
                continue

            yield _line
