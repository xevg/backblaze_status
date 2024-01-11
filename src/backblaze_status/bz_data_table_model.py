import threading
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PyQt6.QtGui import QColor

from .backup_file import BackupFile
from .backup_results import BackupResults
from .to_do_files import ToDoFiles
from .utils import file_size_string


class ColumnNames(IntEnum):
    TIMESTAMP = 0
    FILE_NAME = 1
    FILE_SIZE = 2
    INTERVAL = 3
    RATE = 4


class BzDataTableModel(QAbstractTableModel):
    ToDoDisplayCount: int = 52

    def __init__(self, qt):
        from .qt_backup_status import QTBackupStatus

        super(BzDataTableModel, self).__init__()
        self.qt: QTBackupStatus = qt
        self.remaining_todo = None
        self.data_list: list = list()
        self.to_do_cache: list = list()

        self.lock: threading.Lock = threading.Lock()

        self.showing_new_file: bool = False
        self.new_file_name: str = str()
        self.new_file_size: int = 0
        self.new_file_start_time: datetime = datetime.now()
        self.new_file_interval: str = str()
        self.interval_timer = None

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

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        row = index.row()
        column = index.column()
        to_do_row = row - len(self.data_list)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return self.column_alignment[column]

        # First handle all the rows before the last row of the data list
        if row < len(self.data_list) - 1:
            row_data: BackupResults = self.data_list[row]

            return self.get_normal_data_row(role, row, column)

        # Now decide what to do with the last row
        # 1) If we are not showing the new file, show the last row
        # 2) If we are showing the new file, and it is the same as the last row, show the progress row
        # 3) If we are showing the new file, and it is *not* the same as the last row, show the last row

        if row == len(self.data_list) - 1:
            if not self.showing_new_file:
                return self.get_normal_data_row(role, row, column)

            if self.showing_new_file:
                if self.new_file_name == self.data_list[row].file_name:
                    return self.get_progress_data_row(role, row, column)
                else:
                    return self.get_normal_data_row(role, row, column)

        # Now decide what to do with the row after the last row
        # 1) If it is showing, and different than the last row, show the progress row
        # 2) If the progress row has already been shown, show the first row of to_do

        if row == len(self.data_list):
            if (
                self.showing_new_file
                and self.new_file_name != self.data_list[row - 1].file_name
            ):
                # There is an extra row, so we need to subtract one
                to_do_row -= 1
                return self.get_progress_data_row(role, row, column)

            return self.get_to_do_data_row(role, 0, column)

        # At this point, we are showing the to do list

        return self.get_to_do_data_row(role, to_do_row, column)

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

    def rowCount(self, index: QModelIndex) -> int:
        # Subtract two so that no matter what the way things are, we don't go over
        return len(self.data_list) + len(self.to_do_cache) - 2

    def columnCount(self, index: QModelIndex) -> int:
        return len(self.column_names)

    def show_new_file(self, file: str, size: int):
        # self._data_list.append(["", file, "", "0:00", ""])
        self.new_file_name = file
        self.qt.backup_status.to_do.preparing_file = file
        self.new_file_size = size
        self.showing_new_file = True
        if self.interval_timer is not None:
            if len(self.data_list) > 0 and self.data_list[-1].end_time == 0:
                self.data_list[-1].end_time = datetime.now()
            self.interval_timer.cancel()
        self.new_file_start_time = datetime.now()
        self.interval_timer = threading.Timer(1, self.update_interval)
        self.interval_timer.start()
        self.layoutChanged.emit()
        # self.qt.reposition_table()

    def update_interval(self):
        self.new_file_interval = datetime.now() - self.new_file_start_time
        if self.showing_new_file:
            self.interval_timer = threading.Timer(1, self.update_interval)
            self.interval_timer.start()
        self.layoutChanged.emit()

    def add_row(self, row: BackupResults, chunk=False):
        # self.beginInsertRows(QModelIndex(), len(self._data_list), 1)
        # self.lock.acquire()
        current_item = self.qt.backup_status.to_do.file_dict.get(row.file_name)
        if current_item is not None:
            self.qt.backup_status.to_do.current_file = current_item
        self.data_list.append(row)
        # self.get_remaining_to_do(retrieve=True)
        if not chunk:
            if self.interval_timer is not None:
                self.interval_timer.cancel()
            self.showing_new_file = False
            self.new_file_name = str()
            self.new_file_size = 0
            self.new_file_interval = 0
            self.new_file_start_time = 0
            self.layoutChanged.emit()
        else:
            self.qt.progress_box.calculate()
            try:
                self.data_list[len(self.data_list) - 2].end_time = datetime.now()
            except IndexError:
                pass

        self.update_to_do_cache()
        self.layoutChanged.emit()

    def update_to_do_cache(self):
        to_do: ToDoFiles = self.qt.backup_status.to_do
        if not to_do:
            return

        if len(self.data_list) == 0:
            start_index = 0
        else:
            if self.showing_new_file:
                filename = self.new_file_name
            else:
                filename = self.data_list[-1].file_name

            to_do_start_data: BackupFile = to_do.file_dict.get(filename)
            if to_do_start_data is None:
                return 0

            start_index = to_do_start_data.list_index

        try:
            to_do_cache = self.qt.backup_status.to_do.file_list[
                start_index : start_index + self.ToDoDisplayCount
            ]
        except IndexError:
            to_do_cache = self.qt.backup_status.to_do.file_list[start_index:]

        if self.showing_new_file and len(to_do_cache) > 1:
            del to_do_cache[0]

        self.to_do_cache = to_do_cache
