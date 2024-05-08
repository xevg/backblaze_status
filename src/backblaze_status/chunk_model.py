from datetime import datetime
from enum import IntEnum
from typing import Any

from PyQt6.QtCore import (
    QAbstractTableModel,
    Qt,
    QModelIndex,
    QTimer,
)
from PyQt6.QtGui import QColor

from .constants import ToDoColumns
from .current_state import CurrentState
from .to_do_files import ToDoFiles


class ChunkModel(QAbstractTableModel):
    """
    The data model for the chunk progress table
    """

    class ModelSize(IntEnum):
        """
        The t-shirt sizes of the chunk progress table, to determine how big of a box
        to make it
        """

        Small = 50
        Medium = 400
        Large = 10000
        X_Large = 50000
        Default = 400

    class TableSize(IntEnum):
        """
        The size of the table for each t-shirt size
        """

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

        # Update the table every half a second
        self.update_timer: QTimer = QTimer()
        self.update_timer.timeout.connect(self.layoutChanged.emit)
        self.update_timer.start(500)

        self.table_size = 0

    def calculate_chunk(self, row: int, column: int) -> int:
        """
        The table is not a 1:1 of the chunks, because for larger files it would be
        way too big, so this method returns which cell the row and column refer to
        """

        # The tables are square
        cell_size = self.table_size * self.table_size

        # The multiplier is how many chunks are in each cell
        multiplier = (
            CurrentState.ToDoList[CurrentState.CurrentFile][ToDoColumns.ChunkCount]
            / cell_size
        )

        chunk = row * self.table_size + column
        chunk *= multiplier
        return int(chunk)

    def reset_table(self):
        """
        Starts a new table with a new file
        """
        to_do: ToDoFiles = self.backup_status.to_do
        # If we haven't read the to_do file yet, or we aren't processing a file, return
        if to_do is None or CurrentState.CurrentFile is None:
            return

        # If there are no chunks, then set the table_size to 0
        if CurrentState.ToDoList[CurrentState.CurrentFile][ToDoColumns.ChunkCount] == 0:
            self.table_size = 0
            return

        chunks = CurrentState.ToDoList[CurrentState.CurrentFile][ToDoColumns.ChunkCount]

        # By default, we don't use the dialog
        self.use_dialog = False

        # Set the t-shirt table size based on the number of chunks.
        # For Large and Extra Large, use the dialog box.

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

        # TODO: Is this correct, or should I be basing it on each different t-shirt
        #  size?
        pixel_size = int(self.TableSize.X_Large / self.table_size)

        max_dimension = (self.table_size * pixel_size) + 5  # 5 for padding

        # Set the cell width based on the pixel size
        if self.use_dialog:
            dialog_table = self.backup_status.chunk_table_dialog_box.dialog_chunk_table
            dialog_table.setMaximumSize(max_dimension, max_dimension)
            for spot in range(self.table_size):
                dialog_table.setColumnWidth(spot, pixel_size)
                dialog_table.setRowHeight(spot, pixel_size)
        else:
            for spot in range(self.table_size):
                self.backup_status.chunk_box_table.setColumnWidth(spot, pixel_size)
                self.backup_status.chunk_box_table.setRowHeight(spot, pixel_size)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        row = index.row()
        column = index.column()

        to_do: ToDoFiles = CurrentState.ToDoList[CurrentState.CurrentFile]

        # If we haven't read the to_do file yet, or we aren't processing a file, return
        if to_do is None or CurrentState.CurrentFile is None:
            return

        # Based on the row and column, figure out what chunk it is
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
        return int(self.table_size)

    def columnCount(self, index: QModelIndex) -> int:
        if self.table_size == 0:
            # If the table isn't built, then we need to try building it, but it would
            # be too much to do it each time, so just do it if five seconds has
            # passed since the last time
            if (datetime.now() - self.last_reset_table_time).seconds > 5:
                self.reset_table()
                self.last_reset_table_time = datetime.now()

        return int(self.table_size)
