from __future__ import annotations
import threading
from datetime import datetime
from enum import Enum, auto, IntEnum
from typing import Any, Optional, Dict
from pathlib import Path
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, pyqtSlot
from PyQt6.QtGui import QColor
from itertools import chain

from .backup_file import BackupFile
from .backup_results import BackupResults
from .utils import file_size_string
from rich.pretty import pprint
from .backup_file_list import BackupFileList
from .to_do_files import ToDoFiles


class ColumnNames(IntEnum):
    TIMESTAMP = 0
    FILE_NAME = 1
    FILE_SIZE = 2
    INTERVAL = 3
    RATE = 4


class RowType(Enum):
    COMPLETED = auto()
    CURRENT = auto()
    TO_DO = auto()
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
    }

    def __init__(self, qt):
        from .qt_backup_status import QTBackupStatus

        super(BzDataTableModel, self).__init__()
        self.qt: QTBackupStatus = qt
        self.remaining_todo = None
        self.data_list: list = []
        self.to_do_cache: list = []
        self.display_cache: list[BackupFile] = []

        self.display_complete_index = 0
        self.display_current_file_index = 0
        self.display_to_do_index = 0

        self.lock: threading.Lock = threading.Lock()

        self.showing_new_file: bool = False
        self.new_file_name: str = str()
        self.new_file_size: int = 0
        self.new_file_start_time: datetime = datetime.now()
        self.new_file_interval: int = 0
        self.interval_timer = None

        self.to_do: ToDoFiles = self.qt.backup_status.to_do
        if self.to_do is None:
            self.qt.signals.to_do_available.connect(self.to_do_loaded)
            self.completed_files_list: Optional[BackupFileList] = None
            self.to_do_files_list: Optional[BackupFileList] = None
        else:
            self.completed_files_list: BackupFileList = self.to_do.completed_file_list
            self.to_do_files_list: BackupFileList = self.to_do.completed_file_list
            self.update_to_do_cache()
            self.layoutChanged.emit()

        if self.qt is not None:
            self.qt.signals.files_updated.connect(self.update_display_cache)

        self.column_names = [
            "Time",
            "File Name",
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
        ]

    @pyqtSlot()
    def to_do_loaded(self):
        self.to_do: ToDoFiles = self.qt.backup_status.to_do
        self.completed_files_list: BackupFileList = self.to_do.completed_file_list
        self.to_do_files_list: BackupFileList = self.to_do.completed_file_list
        self.update_to_do_cache()
        self.layoutChanged.emit()

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
        row_data: BackupFile = self.display_cache[row]

        match role:
            case Qt.ItemDataRole.TextAlignmentRole:
                return self.column_alignment[column]

            case Qt.ItemDataRole.DisplayRole:
                match column:
                    case ColumnNames.TIMESTAMP:
                        if self.row_type(row) == RowType.CURRENT:
                            return self.new_file_start_time.strftime(
                                "%m/%d/%Y %I:%M:%S %p"
                            )
                        return row_data.timestamp.strftime("%m/%d/%Y %I:%M:%S %p")
                    case ColumnNames.FILE_NAME:
                        return str(row_data.file_name)
                    case ColumnNames.FILE_SIZE:
                        return file_size_string(row_data.file_size)
                    case ColumnNames.INTERVAL:
                        if self.row_type(row) == RowType.CURRENT:
                            if self.new_file_interval == 0:
                                return
                            else:
                                return str(self.new_file_interval).split(".")[0]

                        if row_data.end_time == 0:
                            return
                        time_diff = row_data.end_time - row_data.start_time
                        return str(time_diff).split(".")[0]
                    case ColumnNames.RATE:
                        return row_data.rate
                    case _:
                        return

            case Qt.ItemDataRole.ForegroundRole:
                if (
                    self.row_type(row) == RowType.COMPLETED
                    and row_data.completed_run != self.to_do.current_run
                ):
                    return QColor("black")
                return self.RowForegroundColors[self.row_type(row)]

            case Qt.ItemDataRole.TextAlignmentRole:
                return self.column_alignment[column]

            case Qt.ItemDataRole.BackgroundRole:
                if (
                    self.row_type(row) == RowType.COMPLETED
                    and row_data.completed_run != self.to_do.current_run
                ):
                    return QColor("PowderBlue")

                return QColor("black")

            case _:
                return

    def get_normal_data_row(self, role, row, column):
        row_data: BackupResults = self.data_list[row]

        match role:
            case Qt.ItemDataRole.DisplayRole:
                match column:
                    case ColumnNames.TIMESTAMP:
                        return row_data.timestamp.strftime("%m/%d/%Y %I:%M:%S %p")
                    case ColumnNames.FILE_NAME:
                        return row_data.file_name
                    case ColumnNames.FILE_SIZE:
                        return file_size_string(row_data.file_size)
                    case ColumnNames.INTERVAL:
                        if row_data.end_time == 0:
                            return
                        time_diff = row_data.end_time - row_data.start_time
                        return str(time_diff).split(".")[0]
                    case ColumnNames.RATE:
                        return row_data.rate
                    case _:
                        return

            case Qt.ItemDataRole.ForegroundRole:
                match column:
                    case ColumnNames.TIMESTAMP:
                        if row_data.timestamp_color is None:
                            return QColor(row_data.row_color)
                        else:
                            return QColor(row_data.timestamp_color)

                    case ColumnNames.FILE_NAME:
                        if row_data.file_name_color is None:
                            return QColor(row_data.row_color)
                        else:
                            return QColor(row_data.file_name_color)

                    case ColumnNames.FILE_SIZE:
                        if row_data.file_size_color is None:
                            return QColor(row_data.row_color)
                        else:
                            return QColor(row_data.file_size_color)

                    case ColumnNames.INTERVAL:
                        if row_data.start_time_color is None:
                            return QColor(row_data.row_color)
                        else:
                            return QColor(row_data.start_time_color)

                    case ColumnNames.RATE:
                        if row_data.rate_color is None:
                            return QColor(row_data.row_color)
                        else:
                            return QColor(row_data.rate_color)

                    case _:
                        return QColor(row_data.row_color)

    def get_progress_data_row(self, role, row, column):
        match role:
            case Qt.ItemDataRole.DisplayRole:
                match column:
                    case ColumnNames.TIMESTAMP:
                        return self.new_file_start_time.strftime("%m/%d/%Y %I:%M:%S %p")
                    case ColumnNames.FILE_NAME:
                        return self.new_file_name
                    case ColumnNames.FILE_SIZE:
                        return file_size_string(self.new_file_size)
                    case ColumnNames.INTERVAL:
                        if self.new_file_interval == 0:
                            return
                        else:
                            return str(self.new_file_interval).split(".")[0]
            case Qt.ItemDataRole.TextAlignmentRole:
                return self.column_alignment[column]

            case Qt.ItemDataRole.ForegroundRole:
                return QColor("green")

            case Qt.ItemDataRole.BackgroundRole:
                return QColor("black")

            case _:
                return

    def get_to_do_data_row(self, role, row, column):
        match role:
            case Qt.ItemDataRole.DisplayRole:
                match column:
                    case ColumnNames.FILE_NAME:
                        return str(self.to_do_cache[row].file_name)
                    case ColumnNames.FILE_SIZE:
                        return file_size_string(self.to_do_cache[row].file_size)
                    case _:
                        return

    def show_new_file(self, file: str, size: int):
        # self._data_list.append(["", file, "", "0:00", ""])
        self.new_file_name = file
        self.new_file_size = size
        self.showing_new_file = True
        if self.interval_timer is not None:
            if len(self.data_list) > 0 and self.data_list[-1].end_time == 0:
                self.data_list[-1].end_time = datetime.now()
            self.interval_timer.cancel()
        self.new_file_start_time = datetime.now()
        self.interval_timer = threading.Timer(1, self.update_interval)
        self.interval_timer.start()
        self.update_display_cache()
        self.layoutChanged.emit()
        # self.qt.reposition_table()

    def update_interval(self):
        self.new_file_interval = datetime.now() - self.new_file_start_time
        if self.showing_new_file:
            self.interval_timer = threading.Timer(1, self.update_interval)
            self.interval_timer.start()
        self.layoutChanged.emit()

    def add_row(self, row: BackupResults, chunk=False):
        # If there was a previous item processing, set its end time to now,
        # since that is the only way that we know that the previous one was done
        if len(self.data_list) > 0:
            self.data_list[-1].end_time = datetime.now()
        self.data_list.append(row)
        if not chunk:
            if self.interval_timer is not None:
                self.interval_timer.cancel()
            self.showing_new_file = False
            self.new_file_name = str()
            self.new_file_size = 0
            self.new_file_interval = 0
            self.new_file_start_time: datetime = datetime.now()
            self.layoutChanged.emit()
        else:
            self.qt.progress_box.calculate()
            try:
                self.data_list[len(self.data_list) - 2].end_time = datetime.now()
            except IndexError:
                pass

        self.update_to_do_cache()
        self.layoutChanged.emit()

    def update_display_cache(self):
        if self.to_do is None:
            return

        if self.to_do.completed_file_list is not None:
            completed_file_list = self.to_do.completed_file_list
        else:
            completed_file_list = BackupFileList()

        if self.showing_new_file:
            new_file_list = [
                BackupFile(
                    file_name=Path(self.new_file_name), file_size=self.new_file_size
                )
            ]
        else:
            new_file_list = BackupFileList()

        if self.to_do.to_do_file_list is not None:
            to_do_file_list = self.to_do.to_do_file_list[: self.ToDoDisplayCount]
            if self.showing_new_file:
                current_file = self.to_do.to_do_file_list.get(self.new_file_name)
                if current_file is not None:
                    try:
                        index_number = self.to_do.to_do_file_list.file_list.index(
                            current_file
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

    def row_type(self, row: int) -> RowType:
        if self.to_do is None:
            return RowType.UNKNOWN

        if row < len(self.completed_files_list):
            return RowType.COMPLETED

        if self.showing_new_file and row == len(self.completed_files_list):
            return RowType.CURRENT

        return RowType.TO_DO

    def update_to_do_cache(self):
        self.update_display_cache()
        self.to_do: ToDoFiles = self.qt.backup_status.to_do
        if self.to_do is None:
            return

        start_index = self.get_to_do_start_index()
        if start_index is None:
            return

        try:
            to_do_cache = self.to_do.to_do_file_list[
                start_index : start_index + self.ToDoDisplayCount
            ]
        except IndexError:
            to_do_cache = self.to_do.to_do_file_list[start_index:]

        if self.showing_new_file and len(to_do_cache) > 1:
            del to_do_cache[0]

        self.to_do_cache = to_do_cache

    def get_to_do_start_index(self) -> int:
        to_do: "ToDoFiles" = self.qt.backup_status.to_do
        if len(self.data_list) == 0 and not self.showing_new_file:
            return 0
        else:
            if self.showing_new_file:
                filename = self.new_file_name
            elif len(self.data_list) > 0:
                filename = self.data_list[-1].file_name
            else:
                return 0

            to_do_start_data: BackupFile = to_do.get_file(filename)
            if to_do_start_data is None:
                return 0

            return to_do_start_data.list_index
