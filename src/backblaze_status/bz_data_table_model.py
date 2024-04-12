from __future__ import annotations

import threading
from datetime import datetime
from enum import Enum, auto, IntEnum
from typing import Any, Optional
from rich.pretty import pprint

from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, pyqtSlot, QTimer
from PyQt6.QtGui import QColor, QFont

from .backup_file import BackupFile
from .backup_file_list import BackupFileList
from .to_do_files import ToDoFiles
from .utils import file_size_string


class ColumnNames(IntEnum):
    TIMESTAMP = 0
    FILE_NAME = 1
    CHUNKS_TRANSMITTED = 2
    CHUNKS_DEDUPED = 3
    FILE_SIZE = 4
    INTERVAL = 5
    RATE = 6


class RowType(Enum):
    COMPLETED = auto()
    CURRENT = auto()
    TO_DO = auto()
    DUPLICATED = auto()
    PREVIOUS_RUN = auto()
    UNKNOWN = auto()


class BzDataTableModel(QAbstractTableModel):
    """

    There are two data tables used for the display, the first one is the BackupResult
    list of what has been backed up, and the second is the ToDoFile list of what
    will be backed up
    """

    ToDoDisplayCount: int = 52
    RowForegroundColors: dict[RowType, QColor] = {
        RowType.COMPLETED: QColor("white"),
        RowType.CURRENT: QColor("green"),
        RowType.TO_DO: QColor("grey"),
        RowType.DUPLICATED: QColor("orange"),
        RowType.PREVIOUS_RUN: QColor("black"),
    }

    def __init__(self, backup_status):
        from .qt_backup_status import QTBackupStatus

        super(BzDataTableModel, self).__init__()
        self.backup_status: QTBackupStatus = backup_status
        self.display_cache: list[BackupFile] = []

        self.lock: threading.Lock = threading.Lock()

        self.in_progress_file: Optional[BackupFile] = None

        self.fixed_font = QFont(".SF NS Mono")

        self.to_do: ToDoFiles = self.backup_status.to_do
        if self.to_do is None:
            # If to_do isn't available yet, get a signal when it is
            self.backup_status.signals.to_do_available.connect(self.to_do_loaded)
            self.backup_status.signals.backup_running.connect(self.backup_state_changed)

            self.completed_files_list: Optional[BackupFileList] = None
            self.to_do_files_list: Optional[BackupFileList] = None
        else:
            self.completed_files_list: BackupFileList = self.to_do.completed_file_list
            self.to_do_files_list: BackupFileList = self.to_do.completed_file_list

            self.update_display_cache()

        self.backup_status.signals.files_updated.connect(self.update_display_cache)

        self.column_names = [
            "Time",
            "File Name",
            "Chunks Transmitted",
            "Chunks Deduped",
            "File Size",
            "Interval",
            "Rate",
        ]

        self.column_alignment = [
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        ]

    @pyqtSlot()
    def to_do_loaded(self):
        self.to_do: ToDoFiles = self.backup_status.to_do
        self.completed_files_list: BackupFileList = self.to_do.completed_file_list
        self.to_do_files_list: BackupFileList = self.to_do.completed_file_list
        self.update_display_cache()

    @pyqtSlot(bool)
    def backup_state_changed(self, state: bool):
        if not state:
            self.in_progress_file = None

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
        if self.to_do is None:
            return

        row = index.row()
        column = index.column()
        if self.row_type(row) == RowType.CURRENT:
            row_data: BackupFile = self.in_progress_file
        else:
            row_data: BackupFile = self.display_cache[row]

        match role:
            case Qt.ItemDataRole.FontRole:
                return self.fixed_font

            case Qt.ItemDataRole.TextAlignmentRole:
                return self.column_alignment[column]

            case Qt.ItemDataRole.DisplayRole:
                match column:
                    case ColumnNames.TIMESTAMP:
                        # No timestamp for future items
                        if self.row_type(row) == RowType.TO_DO:
                            return

                        return (
                            row_data.start_time.strftime("%m/%d/%Y %I:%M:%S %p")
                            if row_data.start_time
                            else None
                        )
                    case ColumnNames.FILE_NAME:
                        return str(row_data.file_name)
                    case ColumnNames.CHUNKS_TRANSMITTED:
                        if self.row_type(row) == RowType.TO_DO:
                            return

                        count = len(row_data.transmitted_chunks)
                        if count == 0:
                            return
                        else:
                            return count
                    case ColumnNames.CHUNKS_DEDUPED:
                        if self.row_type(row) == RowType.TO_DO:
                            return

                        count = len(row_data.deduped_chunks)
                        if count == 0:
                            return
                        else:
                            return count
                    case ColumnNames.FILE_SIZE:
                        return file_size_string(row_data.file_size)
                    case ColumnNames.INTERVAL:
                        if self.row_type(row) == RowType.CURRENT:
                            if row_data.start_time is None:
                                return

                            time_diff = datetime.now() - row_data.start_time
                            return str(time_diff).split(".")[0]

                        if row_data.end_time is None or row_data.start_time is None:
                            return

                        time_diff = row_data.end_time - row_data.start_time
                        return str(time_diff).split(".")[0]
                    case ColumnNames.RATE:
                        if self.row_type(row) == RowType.COMPLETED:
                            return row_data.rate
                        else:
                            return
                    case _:
                        return

            case Qt.ItemDataRole.ForegroundRole:
                return self.RowForegroundColors[self.row_type(row, row_data)]

            case Qt.ItemDataRole.TextAlignmentRole:
                return self.column_alignment[column]

            case Qt.ItemDataRole.BackgroundRole:
                if (
                    self.row_type(row) == RowType.COMPLETED
                    or self.row_type(row) == RowType.DUPLICATED
                ) and row_data.completed_run != self.to_do.current_run:
                    return QColor("PowderBlue")

                if self.row_type(row) == RowType.CURRENT:
                    return QColor("papayawhip")

                return QColor("black")

            case _:
                return

    def show_new_file(self, file: BackupFile):
        # Set up the new in_progress file
        file.start_time = datetime.now()
        self.in_progress_file = file

        self.update_display_cache()

    def update_interval(self):
        # Refresh the interval column on the currently progressing item
        if self.in_progress_file is not None:
            start_index = self.createIndex(
                len(self.to_do.completed_file_list), ColumnNames.CHUNKS_TRANSMITTED
            )
            end_index = self.createIndex(
                len(self.to_do.completed_file_list), ColumnNames.INTERVAL
            )
            self.dataChanged.emit(start_index, end_index, [Qt.ItemDataRole.DisplayRole])

    def update_display_cache(self):
        if self.to_do is None:
            return

        if self.to_do.completed_file_list is not None:
            completed_file_list = self.to_do.completed_file_list
        else:
            completed_file_list = BackupFileList()

        new_file_list = BackupFileList()
        if self.in_progress_file:
            new_file_list.append(self.in_progress_file)

        if self.to_do.to_do_file_list is not None:
            to_do_file_list = self.to_do.to_do_file_list[: self.ToDoDisplayCount]
            if self.in_progress_file is not None:
                try:
                    index_number = self.to_do.to_do_file_list.file_list.index(
                        self.in_progress_file
                    )
                    to_do_file_list = self.to_do.to_do_file_list[
                        index_number + 1 : index_number + self.ToDoDisplayCount
                    ]
                except ValueError:
                    pass

            elif len(completed_file_list) > 0:
                last_complete_file = completed_file_list[-1]
                try:
                    index_number = self.to_do.to_do_file_list.file_list.index(
                        last_complete_file
                    )
                    to_do_file_list = self.to_do.to_do_file_list[
                        index_number : index_number + self.ToDoDisplayCount
                    ]
                except ValueError:
                    pass
        else:
            to_do_file_list = BackupFileList()

        self.display_cache = completed_file_list + new_file_list + to_do_file_list
        self.layoutChanged.emit()
        self.backup_status.reposition_table()

    def row_type(self, row: int, row_data: Optional[BackupFile] = None) -> RowType:
        if self.to_do is None:
            return RowType.UNKNOWN

        if row < len(self.completed_files_list):
            if (
                row_data is not None
                and row_data.completed_run != self.to_do.current_run
            ):
                return RowType.PREVIOUS_RUN

            if row_data is not None and (
                row_data.is_deduped or row_data.is_deduped_chunks
            ):
                return RowType.DUPLICATED

            return RowType.COMPLETED

        if self.in_progress_file and row == len(self.completed_files_list):
            return RowType.CURRENT

        return RowType.TO_DO
