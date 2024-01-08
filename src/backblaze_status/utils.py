import inspect
import logging
import os
import sys
import threading
from datetime import datetime
from math import floor
from pathlib import Path

# from flipper import FeatureFlagClient, MemoryFeatureFlagStore
from rich.console import Console
from rich.text import Text
from datetime import datetime
from .configuration import Configuration

DIVISOR_SIZE = 1024


def file_size_string(size, sign=False) -> str:
    """
    Take a size in bytes and return the size as a string in a more readable form

    param size: Number of bytes
    return: A string with a human-readable format
    """

    units = ["KB", "MB", "GB", "TB"]
    result = size / DIVISOR_SIZE
    format_string = "{:.2f} {}" if not sign else "{:+,.2f} {}"

    for unit in units:
        if abs(result) < DIVISOR_SIZE:
            # Truncate to 2 decimal places
            result = floor(result * 10**2) / 10**2
            return format_string.format(result, unit)
        result /= DIVISOR_SIZE


class MultiLogger:
    def __init__(
        self,
        app_name: str,
        logfile_dir: str = None,
        default_log_level=logging.INFO,
        terminal: bool = False,
        rich_log=None,
        qt=None,
        log_format: str = "%(asctime)s [%(process)d] <%(name)s> %(message)s",
        date_format: str = "%Y-%m-%d %H:%M:%S",
    ):
        """
        Initialize the MultiLogger class.

        Args:
            app_name (str): The name of the application.
            logfile_dir (str, optional): The directory to store log files. Defaults to None.
            default_log_level (int, optional): The default log level. Defaults to logging.INFO.
            terminal (bool, optional): Whether to print log messages to the terminal. Defaults to False.
        """
        self._app_name = app_name
        if logfile_dir is None:
            logfile_dir = str(Path.home() / "logs")
        self._logfile_dir = logfile_dir
        self._default_log_level = default_log_level
        self._terminal = terminal
        self.rich_log = rich_log
        self.qt = qt
        self._log_format = log_format
        self._date_format = date_format

        self._initialize_logger()
        self.logger = logging.getLogger(app_name)

    def _initialize_logger(
        self,
    ):
        """
        Initialize the logger for the application.

        Args:
            app_name (str): The name of the application.
            logfile_dir (str): The directory where the log file will be created.
            default_log_level: The default log level to be used.

        Raises:
            FileNotFoundError: If the logfile_dir does not exist.
            PermissionError: If the logfile_dir is not writable.
        """
        if (
            not Path(self._logfile_dir).exists()
            or not Path(self._logfile_dir).is_dir()
            or not os.access(self._logfile_dir, os.W_OK)
        ):
            raise FileNotFoundError(
                f"Logfile directory does not exist or is not writable: {self._logfile_dir}"
            )

        logger = logging.getLogger(self._app_name)
        logger.setLevel(self._default_log_level)  # Set the log level of the logger

        if not logger.handlers:
            try:
                file_handler = logging.FileHandler(
                    f"{str(Path(self._logfile_dir) / self._app_name)}.log", mode="a"
                )
                file_handler.setFormatter(
                    logging.Formatter(self._log_format, datefmt=self._date_format)
                )
                logger.addHandler(file_handler)
                if self._terminal:
                    stream_handler = logging.StreamHandler(sys.stdout)
                    stream_handler.setFormatter(
                        logging.Formatter(self._log_format, datefmt=self._date_format)
                    )
                    logger.addHandler(stream_handler)
            except (PermissionError, FileNotFoundError) as e:
                print(f"Error initializing logger: {e}")

    def log(
        self,
        message: str | Text,
        level=logging.INFO,
        module: str = None,
    ):
        """
        Log a message.

        Args:
            message (str): The log message.
            level (int, optional): The log level. Defaults to logging.INFO.
            module (str, optional): The name of the module. Defaults to None.
        """
        if not module:
            module = inspect.stack()[1].function

        timestamp = datetime.now().strftime("%-I:%M:%S %p")
        if self.qt:
            html_log_string = (
                f'<span style="color:yellow">{timestamp}</span> '
                f'<span style="color:magenta"> ({module})</span> '
                f'<span style="color:white"> {str(message)} </span> '
            )
            # self.qt.signals.update_log.emit(html_log_string)

        elif self.rich_log:
            rich_log_text = (
                Text()
                .from_markup(f"[yellow]{timestamp}[/] [purple] <{module}>[/] ")
                .append(message)
            )
            self.rich_log.write(rich_log_text)

        message = str(message)
        log_message = f"<{module}> {message}"
        self.logger.log(level, log_message)


def remove_directory(
    directory: Path, console: Console
) -> None:  # , logger: logging.Logger) -> None:
    """
    Try removing a directory. Because macOS puts in the .FF_Index file, it won't remove the directory, so first
      try and delete the file, then try and delete the directory. In all cases it's ok to fail, so just don't return
      anything
    """
    ff_index = directory / ".FF_Index"
    ff_index.unlink(missing_ok=True)

    try:
        directory.rmdir()
        # logger.info(f"Directory '{directory} has been removed successfully")
        console.print(f"Directory '{directory} has been removed successfully")
    except OSError:
        # I don't care if it fails
        pass

    return


def gb_divisor():
    return Configuration.gb_divisor


def tb_divisor():
    return Configuration.tb_divisor


_multi_log = MultiLogger(
    "BzLastFilesTransmitted",
    terminal=True,
)


def get_lock(lock: threading.Lock, name: str, where: str) -> datetime:
    # if where.startswith("qt_b") or where.startswith("to"):
    #    _multi_log.log(f"Getting lock for {name} from {where}", module="lock")
    lock.acquire()
    return datetime.now()


def return_lock(lock: threading.Lock, name: str, where: str, start_time: datetime):
    # if where.startswith("qt_b") or where.startswith("to"):
    #    _multi_log.log(
    #        f"Returning lock for {name} from {where} {datetime.now() - start_time}",
    #        module="lock",
    #    )
    lock.release()
