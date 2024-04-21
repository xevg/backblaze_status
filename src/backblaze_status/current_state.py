from datetime import datetime
from typing import Optional
from .constants import States


class CurrentState:
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
    CompletedFiles: int = 0
    CompletedBytes: float = 0.0
    CompletedChunks: int = 0
    TotalFilesToProcess: int = 0
    TotalBytesToProcess: float = 0.0
    TotalChunksToProcess: int = 0
    TotalFilesPreCompleted: int = 0
    TotalBytesPreCompleted: float = 0.0
    TotalChunksPreCompleted: int = 0

    RegularFileCount: int = 0
    RegularBytesCount: float = 0.0
    DuplicateFileCount: int = 0
    DuplicateBytesCount: float = 0.0

    FilesPercentage: float = 0.0
    BytesPercentage: float = 0.0
    ChunksPercentage: float = 0.0
    Rate: float = 0.0
    TimeRemaining: int = 0
    EstimatedCompletionTime: Optional[datetime] = None
    MaxProgressValue: int = 2147483647
