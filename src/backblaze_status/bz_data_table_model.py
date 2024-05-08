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
    """
    Enumeration of column names.
    """

    TIMESTAMP = 0
    FILE_NAME = 1
    CHUNKS_PREPARED = 2
    CHUNKS_TRANSMITTED = 3
    CHUNKS_DEDUPED = 4
    FILE_SIZE = 5
    INTERVAL = 6
    RATE = 7


class RowType(Enum):
    """
    Enumeration of row types.
    """

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

    # Map colors to row type
    RowForegroundColors: dict[RowType, QColor] = {
        RowType.COMPLETED: QColor("white"),
        RowType.CURRENT: QColor("green"),
        RowType.TO_DO: QColor("grey"),
        RowType.DUPLICATED: QColor("orange"),
        RowType.PREVIOUS_RUN: QColor("magenta"),
        RowType.SKIPPED: QColor("darkMagenta"),
    }

    def __init__(self, backup_status, batch_size=25, max_rows=200):
        """
        :param backup_status: a link the backup_status class, so that I can access
        the signals
        :param batch_size: how many rows I add (or remove) at a time
        :param max_rows: the maximum number of rows I can have at a time
        """
        # To avoid circular dependencies, import this here
        from .qt_backup_status import QTBackupStatus

        super(BzDataTableModel, self).__init__()
        self.backup_status: QTBackupStatus = backup_status
        self.batch_size: int = batch_size
        self.max_rows: int = max_rows

        # In order to minimize the data in the table, and avoid slowdown of the
        # display, I manage a window of data. start_index and end_index are the
        # boundaries of the window.
        # For end_index, I want the minimum of either length of the list, since I
        # don't want to have more rows than list size, or the batch_size, which is
        # the number of rows to add at a time.
        self.start_index: int = 0
        self.end_index: int = min(CurrentState.ToDoListLength, batch_size)

        # Update the interval time, which I want to do every second
        self.interval_timer = QTimer()
        self.interval_timer.timeout.connect(self.update_interval)
        self.interval_timer.start(1000)

        # Connect to signals
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

        # Map the column names to the ToDoColumns
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

        # Alignment per column
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
        """
        When I get a signal that the To Do file has been loaded, then I have to
        reload the whole table, which means I have to start at the top
        """
        self.start_index = 0
        self.end_index = min(CurrentState.ToDoListLength, self.batch_size)
        self.layoutChanged.emit()

    def rowCount(self, index: QModelIndex) -> int:
        """
        The row count is the end_index - start_index. If they are the same,
        then reset the table
        """
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
                        # For the vertical header, rather than the row number of what
                        # is displayed, I want the row number of the actual to do file.
                        row_num = f"{self.start_index + section + 1:,}"
                        return row_num
            case _:
                return

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        # The row is the requested row plus the start_index, which gives me the
        # actual row from the to do list
        row = index.row() + self.start_index
        column = index.column()

        try:
            # If the row isn't on the list for some reason, return a blank line
            file_name = CurrentState.FileIndex[row]
            row_data = CurrentState.ToDoList[file_name]
        except KeyError:
            return

        match role:
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

    def update_interval(self):
        """
        Updates the interval on the currently processed file every second
        """

        if CurrentState.CurrentFile is None:
            return

        current_row = CurrentState.ToDoList[CurrentState.CurrentFile][
            ToDoColumns.IndexCount
        ]

        start_index = self.index(int(current_row), ColumnNames.CHUNKS_PREPARED)
        end_index = self.index(int(current_row), ColumnNames.INTERVAL)
        self.dataChanged.emit(start_index, end_index, [Qt.ItemDataRole.DisplayRole])

    def canFetchMore(self, index):
        """
        Returns True if more data can be fetched
        """
        if index.isValid():
            return False
        return self.end_index < CurrentState.ToDoListLength

    def fetchLess(self):
        """
        fetchMore is build in and adds more data to the table, but since I want the
        window, then I have to actually remove data at the beginning. This method
        does the work when I scroll up to the beginning, and there is more data to be
        displayed.
        """
        self.layoutAboutToBeChanged.emit()
        old_row = self.start_index
        if self.start_index - self.batch_size > 0:
            self.start_index -= self.batch_size
        else:
            self.start_index = 0
        self.end_index -= self.batch_size
        self.layoutChanged.emit()

        # I want to scroll up to the middle of the new data I've added
        if old_row - self.batch_size < 0:
            scroll_to_row = 0
        else:
            scroll_to_row = old_row - int(self.batch_size / 2)
        self.backup_status.data_model_table.scrollTo(
            self.index(scroll_to_row, 0),
            hint=QAbstractItemView.ScrollHint.PositionAtCenter,
        )

    def fetchMore(self, index):
        """
        If I scroll down to the bottom of the displayed list, add more data.
        """
        if index.isValid():
            return
        current_len = self.end_index - self.start_index
        # If adding more data means that I go over the max_rows, then I need to
        # remove some rows at the beginning
        if current_len >= self.max_rows:
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
        """
        Go to the currently processing file, adjusting the start and end rows so that
        it is in the middle of the viewed rows.
        """
        if CurrentState.CurrentFile is None:
            return
        self.backup_status.data_model_table.resizeRowsToContents()

        self.layoutAboutToBeChanged.emit()
        index = CurrentState.ToDoList[CurrentState.CurrentFile][ToDoColumns.IndexCount]
        self.start_index = int(index - (self.max_rows / 2))
        if self.start_index < 0:
            self.start_index = 0
        self.end_index = int(index + (self.max_rows / 2))
        self.backup_status.data_model_table.scrollTo(
            self.index(index - self.start_index, 0),
            hint=QAbstractItemView.ScrollHint.PositionAtCenter,
        )
        self.layoutChanged.emit()

    def go_to_bottom(self):
        """
        Go the bottom row, adjusting the start and end rows so that it is at the end
        """
        self.layoutAboutToBeChanged.emit()
        index = len(CurrentState.ToDoList)
        self.start_index = int(index - self.max_rows / 2)
        if self.start_index < 0:
            self.start_index = 0
        self.end_index = int(index)
        self.backup_status.data_model_table.scrollTo(
            self.index(index, 0),
            hint=QAbstractItemView.ScrollHint.PositionAtBottom,
        )
        self.layoutChanged.emit()

    def go_to_top(self):
        """
        Go the top row, adjusting the start and end rows so that it is at the end
        """
        self.layoutAboutToBeChanged.emit()
        self.start_index = 0
        self.end_index = min(CurrentState.ToDoListLength, self.batch_size)
        self.backup_status.data_model_table.scrollTo(
            self.index(0, 0),
            hint=QAbstractItemView.ScrollHint.PositionAtTop,
        )
        self.layoutChanged.emit()
