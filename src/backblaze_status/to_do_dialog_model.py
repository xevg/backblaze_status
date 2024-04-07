from __future__ import annotations
import threading
from datetime import datetime
from enum import Enum, auto, IntEnum
from typing import Any, Optional, Dict
from pathlib import Path
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, pyqtSlot, QTimer
from PyQt6.QtGui import QColor, QFont
from itertools import chain
from typing import List

from docutils.parsers.rst.directives.misc import Role

from .backup_file import BackupFile
from .utils import file_size_string
from rich.pretty import pprint
from .backup_file_list import BackupFileList
from .to_do_files import ToDoFiles
from dataclasses import dataclass


class ColumnNames(IntEnum):
    FILE_SIZE = 0
    FILE_NAME = 1
    TOTAL_BACKUP_SIZE = 2


class RowType(Enum):
    TRANSMITTED = auto()
    CURRENT = auto()
    TO_DO = auto()
    DUPLICATED = auto()
    PREVIOUS_RUN = auto()
    UNKNOWN = auto()


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
        RowType.TRANSMITTED: QColor("white"),
        RowType.CURRENT: QColor("green"),
        RowType.TO_DO: QColor("grey"),
        RowType.DUPLICATED: QColor("orange"),
        RowType.PREVIOUS_RUN: QColor("black"),
        RowType.UNKNOWN: QColor("mediumslateblue"),
    }

    def __init__(self, backup_status):
        from .qt_backup_status import QTBackupStatus

        super(ToDoDialogModel, self).__init__()
        self.backup_status: QTBackupStatus = backup_status

        #        self.fixed_font = QFont(".SF NS Mono")

        self.to_do: ToDoFiles = self.backup_status.to_do
        self.display_cache: List[ToDoDialogFile] = []
        self.update_display_cache()
        self.current_index: int = 0

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
        return len(self.display_cache)

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
        row_data: ToDoDialogFile = self.display_cache[row]
        to_do_data: BackupFile = self.to_do.to_do_file_list.file_list[row_data.index]

        match role:
            # case Qt.ItemDataRole.FontRole:
            #     return self.fixed_font

            case Qt.ItemDataRole.TextAlignmentRole:
                return self.column_alignment[column]

            case Qt.ItemDataRole.DisplayRole:
                match column:
                    case ColumnNames.FILE_SIZE:
                        return file_size_string(row_data.file_size)
                    case ColumnNames.FILE_NAME:
                        return str(row_data.file_name)
                    case ColumnNames.TOTAL_BACKUP_SIZE:
                        return file_size_string(row_data.total_backup_size)
                    case _:
                        return

            case Qt.ItemDataRole.ForegroundRole:
                return self.RowForegroundColors[self.row_type(row, to_do_data)]

            case Qt.ItemDataRole.TextAlignmentRole:
                return self.column_alignment[column]

            case Qt.ItemDataRole.BackgroundRole:
                if self.row_type(row) == RowType.PREVIOUS_RUN:
                    return QColor("PowderBlue")

                if self.row_type(row) == RowType.CURRENT:
                    return QColor("papayawhip")

                return QColor("black")

            case _:
                return

    def update_display_cache(self):
        if self.to_do is None:
            return

        result_list = []
        total_backup_size = 0
        for index, file in enumerate(
            self.to_do.to_do_file_list
        ):  # type: int, BackupFile
            total_backup_size += file.file_size
            to_do_file = ToDoDialogFile(
                index, file.file_size, str(file.file_name), total_backup_size
            )
            result_list.append(to_do_file)
        self.display_cache = result_list

        if self.to_do.current_file is None:
            self.current_index = 0
        else:
            current_index_item = self.to_do.to_do_file_list.file_dict.get(
                str(self.to_do.current_file.file_name)
            )
            if current_index_item is None:
                self.current_index = 0
            else:
                self.current_index = self.to_do.to_do_file_list.file_list.index(
                    current_index_item
                )
        self.layoutChanged.emit()

    def row_type(self, row: int, row_data: Optional[BackupFile] = None) -> RowType:
        if self.to_do is None:
            return RowType.UNKNOWN

        if (
            row_data is not None
            and row_data.completed_run != 0
            and row_data.completed_run != self.to_do.current_run
        ):
            return RowType.PREVIOUS_RUN

        if (
            row_data is not None
            and row_data.completed_run == 0
            and row < self.current_index
        ):
            return RowType.UNKNOWN

        if row_data is not None and (row_data.is_deduped or row_data.is_deduped_chunks):
            return RowType.DUPLICATED

        if row < self.current_index:
            return RowType.TRANSMITTED

        return RowType.TO_DO
