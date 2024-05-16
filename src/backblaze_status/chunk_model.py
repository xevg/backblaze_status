from datetime import datetime
from enum import IntEnum
from math import floor
from typing import Any

import numpy as np
from PyQt6.QtCore import (
    QAbstractTableModel,
    Qt,
    QModelIndex,
    pyqtSlot,
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

        self.backup_status.signals.update_chunk.connect(self.update_chunk)

        self.table_size = 0
        self.multiplier = 1
        self.chunks_per_row = 0
        self.chunks_per_column = 0
        self.chunk_array = None

    def calculate_chunk(self, row: int, column: int) -> (int, int):
        """
        The table is not a 1:1 of the chunks, because for larger files it would be
        way too big, so this method returns which cell the row and column refer to
        """

        chunk_at_start_of_row = row * self.chunks_per_row
        low_chunk = floor(chunk_at_start_of_row + (column * self.chunks_per_column))
        high_chunk = floor(low_chunk + self.chunks_per_column)

        return low_chunk, high_chunk

    def get_row_col(self, index) -> (int, int):
        row = int(index / self.table_size)
        column = index - (row * self.table_size)
        return row, column

    @pyqtSlot(int)
    def update_chunk(self, chunk_number: int):
        low_index = np.searchsorted(self.chunk_array, [chunk_number], side="left")[0]
        high_index = np.searchsorted(
            self.chunk_array, [chunk_number + 1], side="right"
        )[0]
        for index in [index for index in range(low_index, high_index + 1)]:
            row, column = self.get_row_col(index)
            location_index = self.createIndex(row, column)
            self.dataChanged.emit(location_index, location_index)
            print(f"Updating chunk {chunk_number} ({row}, {column})")

    def reset_table(self):
        """
        Starts a new table with a new file
        """
        to_do: ToDoFiles = self.backup_status.to_do
        # If we haven't read the to_do file yet, or we aren't processing a file, return
        if to_do is None or CurrentState.CurrentFile is None:
            return

        # If there are no chunks, then set the table_size to 0
        try:
            if (
                CurrentState.ToDoList[CurrentState.CurrentFile][ToDoColumns.ChunkCount]
                == 0
            ):
                self.table_size = 0
                return
        except KeyError:
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
            # self.use_dialog = True
            self.table_size = self.TableSize.Large
        else:
            # self.use_dialog = True
            self.table_size = self.TableSize.X_Large

        self.table_size = self.TableSize.Medium
        # TODO: Is this correct, or should I be basing it on each different t-shirt
        #  size?
        pixel_size = int(self.TableSize.X_Large / self.table_size)

        # The multiplier is how many chunks are in each cell

        total_cells = self.table_size * self.table_size
        file_chunks = CurrentState.ToDoList[CurrentState.CurrentFile][
            ToDoColumns.ChunkCount
        ]
        self.multiplier = file_chunks / total_cells
        self.chunks_per_row = self.table_size * self.multiplier
        self.chunks_per_column = self.chunks_per_row / self.table_size
        self.chunk_array = np.array(
            [
                x / 10000
                for x in range(0, chunks * 10000, int(self.chunks_per_column * 10000))
            ]
        )

        # Set the cell width based on the pixel size
        # if self.use_dialog:
        #     dialog_table = self.backup_status.chunk_table_dialog_box.dialog_chunk_table
        #     # max_dimension = (self.table_size * pixel_size) + 5  # 5 for padding
        #     # dialog_table.setMaximumSize(max_dimension, max_dimension)
        #     # dialog_table.resize(self.table_size, self.table_size)
        #
        #     for spot in range(self.table_size):
        #         dialog_table.setColumnWidth(spot, pixel_size)
        #         dialog_table.setRowHeight(spot, pixel_size)
        # else:
        for spot in range(self.table_size):
            self.backup_status.chunk_box_table.setColumnWidth(spot, pixel_size)
            self.backup_status.chunk_box_table.setRowHeight(spot, pixel_size)

        self.layoutChanged.emit()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        row = index.row()
        column = index.column()

        # If we haven't read the to_do file yet, or we aren't processing a file, return
        if CurrentState.CurrentFile is None:
            return

        try:
            file_data = CurrentState.ToDoList[CurrentState.CurrentFile]
        except KeyError:
            return

        # Based on the row and column, figure out what chunk it is
        low_chunk, high_chunk = self.calculate_chunk(row, column)

        counts = {
            ToDoColumns.DedupedChunks: 0,
            ToDoColumns.TransmittedChunks: 0,
            ToDoColumns.PreparedChunks: 0,
            "Unknown": 0,
        }
        for chunk in range(low_chunk, high_chunk + 1):
            if chunk in file_data[ToDoColumns.DedupedChunks]:
                counts[ToDoColumns.DedupedChunks] += 1
            elif chunk in file_data[ToDoColumns.TransmittedChunks]:
                counts[ToDoColumns.TransmittedChunks] += 1
            elif chunk in file_data[ToDoColumns.PreparedChunks]:
                counts[ToDoColumns.PreparedChunks] += 1

        # The order is important. Chunks can be in both transmitted and deduped,
        # and if that happens, they are actually deduped. Also, they will be in
        # prepared, so the order to return is first deduped, then transmitted,
        # then prepared

        match role:
            case Qt.ItemDataRole.BackgroundRole:
                if counts[ToDoColumns.DedupedChunks] > 0:
                    return QColor("#f5a356")

                if counts[ToDoColumns.TransmittedChunks] > 0:
                    return QColor("#84fab0")

                if counts[ToDoColumns.PreparedChunks] > 0:
                    return QColor("#2575fc")

                return QColor("#818a84")  # The default color

            case Qt.ItemDataRole.ToolTipRole:
                return f"{row}, {column}"

            case _:
                return

    def rowCount(self, index: QModelIndex) -> int:
        return int(self.table_size)

    @property
    def row_count(self):
        return self.rowCount(self.createIndex())

    def columnCount(self, index: QModelIndex) -> int:
        if self.table_size == 0:
            # If the table isn't built, then we need to try building it, but it would
            # be too much to do it each time, so just do it if five seconds has
            # passed since the last time
            if (datetime.now() - self.last_reset_table_time).seconds > 5:
                self.reset_table()
                self.last_reset_table_time = datetime.now()

        return int(self.table_size)
