from datetime import datetime
from typing import Optional

from readerwriterlock import rwlock
from .constants import States


class CurrentState:
    """
    This is a class with all static variables to manage global state.
    """

    CurrentFile: Optional[str] = None
    CurrentFileState: str = States.Unknown
    StartTime: Optional[datetime] = None
    ToDoList: dict = {}
    ToDoListLength: int = 0
    FileIndex: dict = {}
    BackupRunning: bool = False

    TotalFiles: int = 0
    TotalBytes: float = 0.0
    TotalChunks: int = 0

    CurrentCompletedChunks = 0
    CurrentTransmittedChunks = 0
    CurrentDedupedChunks: int = 0

    CompletedFiles: int = 0
    CompletedBytes: float = 0.0
    CompletedChunks: int = 0

    SkippedFiles: int = 0
    SkippedBytes: float = 0.0
    SkippedChunks: int = 0

    TotalFilesToProcess: int = 0
    TotalBytesToProcess: float = 0.0
    TotalChunksToProcess: int = 0

    TotalFilesPreCompleted: int = 0
    TotalBytesPreCompleted: float = 0.0
    TotalChunksPreCompleted: int = 0

    TransmittedFiles: int = 0
    TransmittedBytes: float = 0.0
    TransmittedChunks: int = 0

    DuplicateFiles: int = 0
    DuplicateBytes: float = 0.0
    DuplicateChunks: int = 0

    RemainingFiles: int = 0
    RemainingBytes: float = 0.0
    RemainingChunks: int = 0

    CompletedFilesPercentage: float = 0.0
    CompletedBytesPercentage: float = 0.0
    CompletedChunksPercentage: float = 0.0

    Rate: float = 0.0
    TimeRemaining: int = 0
    EstimatedCompletionTime: Optional[datetime] = None
    MaxProgressValue: int = 2147483647

    StatsString: str = "Calculating ..."
    StatsTotalFileString: str = ""
    StatsTotalChunksString: str = ""
    StatsTransmittedFilesString: str = ""
    StatsTransmittedChunksString: str = ""
    StatsDuplicateFilesString: str = ""
    StatsDuplicateChunksString: str = ""
    StatsPercentageDuplicateFilesString: str = ""
    StatsPercentageDuplicateChunksString: str = ""

    StatsCompletedChunksCount: int = 0

    def __setattr__(self, attr, value):
        """
        Sets up a setter for every attribute
        """
        original_setter = super().__setattr__
        if not hasattr(self, "_lock"):
            original_setter("_lock", rwlock.RWLockFair())
        with self._lock.gen_wlock():
            original_setter(attr, value)

    def __getattr__(self, attr):
        original_getter = super().__getattribute__
        original_setter = super().__setattr__
        if not hasattr(self, "_lock"):
            original_setter("_lock", rwlock.RWLockFair())
        with self._lock.gen_wlock():
            return original_getter(attr)
