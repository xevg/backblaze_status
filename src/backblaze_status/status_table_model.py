from __future__ import annotations

from datetime import datetime
from enum import Enum, auto, IntEnum
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, pyqtSlot, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QAbstractItemView

from .constants import Key, ToDoColumns
from .current_state import CurrentState
from .utils import file_size_string


class ColumnNames(IntEnum):
    TIMESTAMP = 0
    FILE_NAME = 1
    CHUNKS_TRANSMITTED = 2
    CHUNKS_DEDUPED = 3
    FILE_SIZE = 4
    INTERVAL = 5
    RATE = 6


class StatusTableModel(QAbstractTableModel):
    """

    There are two data tables used for the display, the first one is the BackupResult
    list of what has been backed up, and the second is the ToDoFile list of what
    will be backed up
    """

    def __init__(self):

        super(StatusTableModel, self).__init__()

        self.column_names = [
            "Time",
            "File Name",
            "Chunks Transmitted",
            "Chunks Deduped",
            "File Size",
            "Interval",
            "Rate",
        ]

    def rowCount(self, index: QModelIndex) -> int:
        return 2

    def columnCount(self, index: QModelIndex) -> int:
        return 10

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        return

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        row = index.row()
        column = index.column()

        match role:
            # case Qt.ItemDataRole.FontRole:
            #     return self.fixed_font

            case Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter

            case Qt.ItemDataRole.DisplayRole:
                return f"{row}: {column}"

            case _:
                return
