"""
These classes provide constants that are used throughout the program
"""


class ToDoColumns:
    FileName: str = "FileName"
    FileSize: str = "FileSize"
    IndexCount: str = "IndexCount"
    IsLargeFile: str = "IsLargeFile"
    IsDeduped: str = "IsDeduped"
    ChunkCount: str = "ChunkCount"
    State: str = "State"
    StartTime: str = "StartTime"
    EndTime: str = "EndTime"
    CompletionTime: str = "CompletionTime"
    Rate: str = "Rate"
    DedupedBytes: str = "DedupedBytes"
    DedupedChunks: str = "DedupedChunks"
    DedupedChunksCount: str = "DedupedChunksCount"
    TransmittedBytes: str = "TransmittedBytes"
    TransmittedChunks: str = "TransmittedChunks"
    TransmittedChunksCount: str = "TransmittedChunksCount"
    PreparedChunks: str = "PreparedChunks"
    PreparedBytes: str = "PreparedBytes"
    PreparedChunksCount: str = "PreparedChunksCount"
    Batch: str = "Batch"
    Interval: str = "Interval"


class Key:
    BackBlazeCurrent: str = "BackBlazeCurrent"
    BackBlazeInstanceStarted: str = "BackBlazeInstanceStarted"
    BackBlazeProgress: str = "BackBlazeProgress"
    BackBlazeStartTime: str = "BackBlazeStartTime"
    BackBlazeUpdateChannel: str = "BackBlazeUpdateChannel"
    Batch: str = "Batch"
    Chunk: str = "Chunk"
    Completed: str = "Completed"
    CompletedFiles: str = "CompletedFiles"
    CompletedSize: str = "CompletedSize"
    CurrentFile: str = "CurrentFile"
    DedupedBytes: str = "DedupedBytes"
    DedupedChunks: str = "DedupedChunks"
    EndTime: str = "EndTime"
    FileName: str = "FileName"
    IsDeduped: str = "IsDeduped"
    NewFileName: str = "CurrentFileName"
    PID: str = "PID"
    PreCompleted: str = "PreCompleted"
    RemainingBytes: str = "TransmittedBytes"
    RemainingChunks: str = "TransmittedChunks"
    Remaining: str = "Transmitting"
    Skipped: str = "Skipped"
    StartTime: str = "StartTime"
    State: str = "State"
    ToDoList: str = "ToDoList"
    TotalFiles: str = "TotalFiles"
    TotalFilesToProcess: str = "TotalFilesToProcess"
    TotalSize: str = "TotalSize"
    TotalSizeToProcess: str = "TotalSizeToProcess"
    TransmittedBytes: str = "TransmittedBytes"
    TransmittedChunks: str = "TransmittedChunks"
    Transmitting: str = "Transmitting"
    Unknown: str = "Unknown"
    Unprocessed: str = "Unprocessed"


class MessageTypes:
    AddDedupedChunk: str = "AddDedupedChunk"
    AddPreparedChunk: str = "AddPreparedChunk"
    AddTransmittedChunk: str = "AddTransmittedChunk"
    BackBlazeIsRunning: str = "BackBlazeIsRunning"
    Batch: str = "Batch"
    Completed: str = "Completed"
    CurrentFile: str = "CurrentFile"
    IsDeduped: str = "IsDeduped"
    RereadToDoList: str = "RereadToDoList"
    SetState: str = "SetState"
    StartNewFile: str = "StartNewFile"
    StartTime: str = "StartTime"


class States:
    Transmitting: str = "Transmitting"
    Preparing: str = "Preparing"
    Completed: str = "Completed"
    Unknown: str = "Unknown"
