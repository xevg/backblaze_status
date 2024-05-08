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
    CHUNKS_PREPARED = 2
    CHUNKS_TRANSMITTED = 3
    CHUNKS_DEDUPED = 4
    FILE_SIZE = 5
    INTERVAL = 6
    RATE = 7


class RowType(Enum):
    COMPLETED = auto()
    CURRENT = auto()
    TO_DO = auto()
    DUPLICATED = auto()
    PREVIOUS_RUN = auto()
    UNKNOWN = auto()
    SKIPPED = auto()


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
        RowType.PREVIOUS_RUN: QColor("magenta"),
        RowType.SKIPPED: QColor("darkMagenta"),
    }

    def __init__(self, backup_status, batch_size=25, max_nodes=200):
        from .qt_backup_status import QTBackupStatus

        super(BzDataTableModel, self).__init__()
        self.backup_status: QTBackupStatus = backup_status
        self.batch_size: int = batch_size
        self.max_nodes: int = max_nodes

        self.start_index: int = 0
        self.end_index: int = min(CurrentState.ToDoListLength, batch_size)

        self.interval_timer = QTimer()
        self.interval_timer.timeout.connect(self.update_interval)
        self.interval_timer.start(1000)

        self.batch_size: int = batch_size
        self.max_nodes: int = max_nodes

        self.backup_status.signals.to_do_available.connect(self.to_do_loaded)
        self.backup_status.signals.go_to_current_row.connect(self.go_to_current_row)

        self.column_names = [
            "Time",
            "File Name",
            "Chunks Prepared",
            "Chunks Transmitted",
            "Chunks Deduped",
            "File Size",
            "Interval",
            "Rate",
        ]

        self.source_column_names = [
            ToDoColumns.StartTime,
            ToDoColumns.FileName,
            ToDoColumns.PreparedChunksCount,
            ToDoColumns.TransmittedChunksCount,
            ToDoColumns.DedupedChunksCount,
            ToDoColumns.FileSize,
            ToDoColumns.Interval,
            ToDoColumns.Rate,
        ]

        self.column_alignment = [
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        ]

    @pyqtSlot()
    def to_do_loaded(self):
        self.start_index = 0
        self.end_index = min(CurrentState.ToDoListLength, self.batch_size)
        self.layoutChanged.emit()

    def rowCount(self, index: QModelIndex) -> int:
        row_count = self.end_index - self.start_index
        if row_count == 0:
            self.start_index = 0
            self.end_index = min(CurrentState.ToDoListLength, self.batch_size)
        return self.end_index - self.start_index

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
                        row_num = f"{self.start_index + section + 1:,}"
                        return row_num
            case _:
                return

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        row = index.row() + self.start_index
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
                match self.source_column_names[column]:
                    case ToDoColumns.StartTime:
                        start_time: datetime = row_data[ToDoColumns.StartTime]
                        if start_time is None:
                            return

                        result = start_time.strftime("%m/%d/%Y %I:%M:%S %p")
                        return result

                    case ToDoColumns.FileName:
                        return file_name

                    case ToDoColumns.PreparedChunksCount:
                        result = len(row_data[ToDoColumns.PreparedChunks])
                        if result == 0:
                            return
                        return result

                    case ToDoColumns.TransmittedChunksCount:
                        result = len(row_data[ToDoColumns.TransmittedChunks])
                        if result == 0:
                            return
                        return result

                    case ToDoColumns.DedupedChunksCount:
                        result = len(row_data[ToDoColumns.DedupedChunks])
                        if result == 0:
                            return
                        return result

                    case ToDoColumns.FileSize:
                        return file_size_string(row_data[ToDoColumns.FileSize])

                    case ToDoColumns.Interval:
                        start_time = row_data[ToDoColumns.StartTime]
                        end_time = row_data[ToDoColumns.EndTime]
                        if start_time is None:
                            return

                        if end_time is None:
                            end_time = datetime.now()

                        if (
                            start_time.tzinfo is None
                            or start_time.tzinfo.utcoffset(start_time) is None
                        ):
                            start_time = start_time.astimezone()
                        if (
                            end_time.tzinfo is None
                            or end_time.tzinfo.utcoffset(end_time) is None
                        ):
                            end_time = end_time.astimezone()

                        return str(end_time - start_time).split(".")[0]

                    case ToDoColumns.Rate:
                        start_time = row_data[ToDoColumns.StartTime]
                        end_time = row_data[ToDoColumns.EndTime]
                        if start_time is None or end_time is None:
                            return

                        if (
                            start_time.tzinfo is None
                            or start_time.tzinfo.utcoffset(start_time) is None
                        ):
                            start_time = start_time.astimezone()
                        if (
                            end_time.tzinfo is None
                            or end_time.tzinfo.utcoffset(end_time) is None
                        ):
                            end_time = end_time.astimezone()

                        time_difference = (end_time - start_time).total_seconds()
                        if time_difference == 0:
                            return "0.0 / sec" ""
                        result = row_data[ToDoColumns.FileSize] / time_difference
                        return f"{file_size_string(result)} / sec"

                    # case ToDoColumns.IsDeduped:
                    #     deduped = row_data[ToDoColumns.IsDeduped]
                    #     if deduped.isna():
                    #         return False
                    #     else:
                    #         return deduped
                    # case _:
                    #     return str(row_data[self.source_column_names[column]])

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
                # if (
                #     self.row_type(row) == RowType.COMPLETED
                #     or self.row_type(row) == RowType.DUPLICATED
                # ) and row_data.completed_run != self.to_do.current_run:
                #     return QColor("PowderBlue")

                if file_name == CurrentState.CurrentFile:
                    return QColor("papayawhip")

                return QColor("black")

            case _:
                return

    def update_interval(self):
        # Refresh the interval column on the currently progressing item
        # print(f"Update Data Interval: {str(datetime.now()).split('.')[0]}")
        if CurrentState.CurrentFile is None:
            return

        current_row = CurrentState.ToDoList[CurrentState.CurrentFile][
            ToDoColumns.IndexCount
        ]

        start_index = self.index(int(current_row), ColumnNames.CHUNKS_PREPARED)
        end_index = self.index(int(current_row), ColumnNames.INTERVAL)
        self.dataChanged.emit(start_index, end_index, [Qt.ItemDataRole.DisplayRole])

    def canFetchMore(self, index):
        if index.isValid():
            return False
        return self.end_index < CurrentState.ToDoListLength

    def fetchLess(self):
        self.layoutAboutToBeChanged.emit()
        old_row = self.start_index
        if self.start_index - self.batch_size > 0:
            self.start_index -= self.batch_size
        else:
            self.start_index = 0
        self.end_index -= self.batch_size
        self.layoutChanged.emit()
        self.backup_status.data_model_table.scrollTo(
            self.index(old_row, 0),
            hint=QAbstractItemView.ScrollHint.PositionAtCenter,
        )

    def fetchMore(self, index):
        if index.isValid():
            return
        current_len = self.end_index - self.start_index
        if current_len >= self.max_nodes:
            self.layoutAboutToBeChanged.emit()
            if self.start_index + self.batch_size < CurrentState.ToDoListLength:
                self.start_index += self.batch_size

            self.end_index += self.batch_size
            self.layoutChanged.emit()
        else:
            target_len = min(current_len + self.batch_size, CurrentState.ToDoListLength)
            self.beginInsertRows(index, current_len, target_len - 1)
            self.end_index = target_len
            self.endInsertRows()

    def go_to_current_row(self):
        if CurrentState.CurrentFile is None:
            return
        self.backup_status.data_model_table.resizeRowsToContents()

        self.layoutAboutToBeChanged.emit()
        index = CurrentState.ToDoList[CurrentState.CurrentFile][ToDoColumns.IndexCount]
        self.start_index = int(index - (self.max_nodes / 2))
        if self.start_index < 0:
            self.start_index = 0
        self.end_index = int(index + (self.max_nodes / 2))
        self.backup_status.data_model_table.scrollTo(
            self.index(index - self.start_index, 0),
            hint=QAbstractItemView.ScrollHint.PositionAtCenter,
        )
        self.layoutChanged.emit()

    def go_to_bottom(self):
        self.layoutAboutToBeChanged.emit()
        index = len(CurrentState.ToDoList)
        self.start_index = int(index - self.max_nodes / 2)
        if self.start_index < 0:
            self.start_index = 0
        self.end_index = int(index)
        self.backup_status.data_model_table.scrollTo(
            self.index(index - self.start_index, 0),
            hint=QAbstractItemView.ScrollHint.PositionAtCenter,
        )
        self.layoutChanged.emit()
