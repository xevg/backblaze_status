from datetime import datetime
from enum import IntEnum
from typing import Any

from PyQt6.QtCore import (
    QAbstractTableModel,
    Qt,
    QModelIndex,
    QTimer,
    QReadWriteLock,
)
from PyQt6.QtGui import QColor

from .constants import ToDoColumns
from .current_state import CurrentState
from .to_do_files import ToDoFiles


class ChunkModel(QAbstractTableModel):
    class ModelSize(IntEnum):
        Small = 50
        Medium = 400
        Large = 10000
        X_Large = 50000
        Default = 400

    class TableSize(IntEnum):
        Small = 20
        Medium = 50
        Large = 75
        X_Large = 100

    def __init__(self, qt):
        from .qt_backup_status import QTBackupStatus

        super(ChunkModel, self).__init__()
        self.backup_status: QTBackupStatus = qt

        self.use_dialog: bool = False
        self.last_reset_table_time: datetime = datetime.now()

        self.update_timer: QTimer = QTimer()
        self.update_timer.timeout.connect(self.layoutChanged.emit)
        self.update_timer.start(500)

        self.table_size = 0

        self.lock: QReadWriteLock = QReadWriteLock(
            recursionMode=QReadWriteLock.RecursionMode.Recursive
        )

    def calculate_chunk(self, row: int, column: int) -> int:
        cell_size = self.table_size * self.table_size
        multiplier = (
            CurrentState.ToDoList[CurrentState.CurrentFile][ToDoColumns.ChunkCount]
            / cell_size
        )
        chunk = row * self.table_size + column
        chunk *= multiplier
        return int(chunk)

    def reset_table(self):
        to_do: ToDoFiles = self.backup_status.to_do
        if to_do is None or CurrentState.CurrentFile is None:
            return

        if (
            CurrentState.CurrentFile is None
            or CurrentState.ToDoList[CurrentState.CurrentFile][ToDoColumns.ChunkCount]
            == 0
        ):
            self.table_size = 0
            return

        chunks = CurrentState.ToDoList[CurrentState.CurrentFile][ToDoColumns.ChunkCount]

        self.use_dialog = False

        if chunks <= self.ModelSize.Small:
            self.table_size = self.TableSize.Small
        elif chunks <= self.ModelSize.Medium:
            self.table_size = self.TableSize.Medium
        elif chunks <= self.ModelSize.Large:
            self.use_dialog = True
            self.table_size = self.TableSize.Large
        else:
            self.use_dialog = True
            self.table_size = self.TableSize.X_Large

        pixel_size = int(self.TableSize.X_Large / self.table_size)

        max_dimension = (self.table_size * pixel_size) + 5  # 5 for padding
        # max_size = (self.rows_columns * self.qt.PixelSize) + 5

        if self.use_dialog:
            self.backup_status.chunk_table_dialog_box.dialog_chunk_table.setMaximumSize(
                max_dimension, max_dimension
            )
            for spot in range(self.table_size):
                self.backup_status.chunk_table_dialog_box.dialog_chunk_table.setColumnWidth(
                    spot, pixel_size
                )
                self.backup_status.chunk_table_dialog_box.dialog_chunk_table.setRowHeight(
                    spot, pixel_size
                )
        else:
            # self.qt.chunk_box_table.setMaximumSize(max_dimension, max_dimension)
            for spot in range(self.table_size):
                self.backup_status.chunk_box_table.setColumnWidth(spot, pixel_size)
                self.backup_status.chunk_box_table.setRowHeight(spot, pixel_size)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        row = index.row()
        column = index.column()

        to_do = CurrentState.ToDoList[CurrentState.CurrentFile]
        if to_do is None or CurrentState.CurrentFile is None:
            return

        chunk = self.calculate_chunk(row, column)  # row * self.rows_columns + column

        # The order is important. Chunks can be in both transmitted and deduped,
        # and if that happens, they are actually deduped. Also, they will be in
        # prepared, so the order to return is first deduped, then transmitted,
        # then prepared

        if role == Qt.ItemDataRole.BackgroundRole:
            if chunk in to_do[ToDoColumns.DedupedChunks]:
                return QColor("#f5a356")

            if chunk in to_do[ToDoColumns.TransmittedChunks]:
                return QColor("#84fab0")

            if chunk in to_do[ToDoColumns.PreparedChunks]:
                return QColor("#2575fc")

            return QColor("#818a84")  # The default color

    def rowCount(self, index: QModelIndex) -> int:
        # Subtract two so that no matter what the way things are, we don't go over
        return int(self.table_size)

    def columnCount(self, index: QModelIndex) -> int:
        # Subtract two so that no matter what the way things are, we don't go over
        if self.table_size == 0:
            if (datetime.now() - self.last_reset_table_time).seconds > 5:
                self.reset_table()
                self.last_reset_table_time = datetime.now()

        return int(self.table_size)
