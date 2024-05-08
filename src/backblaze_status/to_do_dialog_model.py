from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto, IntEnum
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PyQt6.QtGui import QColor

from .constants import ToDoColumns, Key
from .current_state import CurrentState
from .utils import file_size_string


class ColumnNames(IntEnum):
    """
    Enumeration of column names
    """

    FILE_SIZE = 0
    FILE_NAME = 1
    TOTAL_BACKUP_SIZE = 2


class RowType(Enum):
    """
    Enumeration of row types
    """

    TRANSMITTED = auto()
    CURRENT = auto()
    COMPLETED = auto()
    TO_DO = auto()
    DUPLICATED = auto()
    PREVIOUS_RUN = auto()
    UNKNOWN = auto()
    SKIPPED = auto()


@dataclass
class ToDoDialogFile:
    index: int
    file_size: int
    file_name: str
    total_backup_size: int


class ToDoDialogModel(QAbstractTableModel):
    """

    There are two data tables used for the display, the first one is the BackupResult
    list of what has been backed up, and the second is the ToDoFile list of what
    will be backed up
    """

    RowForegroundColors: dict[RowType, QColor] = {
        RowType.COMPLETED: QColor("white"),
        RowType.CURRENT: QColor("green"),
        RowType.TO_DO: QColor("grey"),
        RowType.DUPLICATED: QColor("orange"),
        RowType.PREVIOUS_RUN: QColor("magenta"),
        RowType.SKIPPED: QColor("darkMagenta"),
    }

    def __init__(self, backup_status):
        from .qt_backup_status import QTBackupStatus

        super(ToDoDialogModel, self).__init__()
        self.backup_status: QTBackupStatus = backup_status

        self.column_names = [
            "File Size",
            "File Name",
            "Total Backup Size",
        ]

        self.column_alignment = [
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        ]

    def rowCount(self, index: QModelIndex) -> int:
        return CurrentState.ToDoListLength

    def columnCount(self, index: QModelIndex) -> int:
        return len(self.column_names)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        match role:
            case Qt.ItemDataRole.DisplayRole:
                match orientation:
                    case Qt.Orientation.Horizontal:
                        return self.column_names[section]
                    case _:
                        return section + 1
            case _:
                return

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        row = index.row()
        column = index.column()

        try:
            file_name = CurrentState.FileIndex[row]
            row_data = CurrentState.ToDoList[file_name]
        except KeyError:
            return

        match role:
            # case Qt.ItemDataRole.FontRole:
            #     return self.fixed_font

            case Qt.ItemDataRole.TextAlignmentRole:
                return self.column_alignment[column]

            case Qt.ItemDataRole.DisplayRole:
                match column:
                    case ColumnNames.FILE_SIZE:
                        return file_size_string(row_data[ToDoColumns.FileSize])
                    case ColumnNames.FILE_NAME:
                        return file_name
                    case ColumnNames.TOTAL_BACKUP_SIZE:
                        return  # file_size_string(row_data.total_backup_size)
                    case _:
                        return

            case Qt.ItemDataRole.ForegroundRole:
                if file_name == CurrentState.CurrentFile:
                    return self.RowForegroundColors[RowType.CURRENT]

                if row_data[ToDoColumns.IsDeduped]:
                    return self.RowForegroundColors[RowType.DUPLICATED]

                if row_data[ToDoColumns.State] == Key.PreCompleted:
                    return self.RowForegroundColors[RowType.PREVIOUS_RUN]

                if row_data[ToDoColumns.State] == Key.Completed:
                    return self.RowForegroundColors[RowType.COMPLETED]

                if row_data[ToDoColumns.State] == Key.Skipped:
                    return self.RowForegroundColors[RowType.SKIPPED]

                return self.RowForegroundColors[RowType.TO_DO]

            case Qt.ItemDataRole.TextAlignmentRole:
                return self.column_alignment[column]

            case Qt.ItemDataRole.BackgroundRole:
                # Mark the currently processing line with a different background
                if file_name == CurrentState.CurrentFile:
                    return QColor("papayawhip")

                return QColor("black")

            case _:
                return
