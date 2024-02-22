import math
from threading import Lock
from typing import Any
from datetime import datetime
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, pyqtSlot, QTimer
from PyQt6.QtGui import QColor
from enum import IntEnum

from .backup_file import BackupFile
from .to_do_files import ToDoFiles
from rich.pretty import pprint
from icecream import ic


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
        from .to_do_files import ToDoFiles

        super(ChunkModel, self).__init__()
        self.qt: QTBackupStatus = qt

        self._file_name: str | None = None
        self.current_file: BackupFile | None = None

        self.use_dialog: bool = False
        self.last_reset_table_time: datetime = datetime.now()

        self.update_timer: QTimer = QTimer()
        self.update_timer.timeout.connect(self.layoutChanged.emit)
        self.update_timer.start(500)

        self.table_size = 0

        self.lock: Lock = Lock()

        # self.qt.signals.new_large_file.connect(self.set_filename)

    @property
    def filename(self) -> str:
        return self._file_name

    @filename.setter
    def filename(self, value: str):
        # ic(f"set chunk filename to {value}")
        self._file_name = value
        self.reset_table()
        self.layoutChanged.emit()

    @pyqtSlot(str)
    def set_filename(self, filename: str):
        self.filename = filename

    def calculate_chunk(self, row: int, column: int) -> int:
        cell_size = self.table_size * self.table_size
        multiplier = self.current_file.total_chunk_count / cell_size
        chunk = row * self.table_size + column
        chunk *= multiplier
        return int(chunk)

    def reset_table(self):
        try:
            self.lock.acquire()
            self._reset_table()
        finally:
            self.lock.release()

    def _reset_table(self):
        to_do: ToDoFiles = self.qt.backup_status.to_do
        if to_do is None:
            return

        self.current_file: BackupFile = to_do.get_file(str(self.filename))
        # ic(f"reset_table for {self.filename} ({self.current_file}")

        if self.current_file is None or self.current_file.total_chunk_count == 0:
            self.table_size = 0
            return

        chunks = self.current_file.total_chunk_count

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

        # Hard coding it

        self.use_dialog = False
        self.table_size = self.TableSize.Medium

        pixel_size = int(self.TableSize.X_Large / self.table_size)
        max_dimension = (self.table_size * pixel_size) + 5  # 5 for padding

        # max_size = (self.rows_columns * self.qt.PixelSize) + 5
        if self.use_dialog:
            # self.qt.chunk_dialog_table.setMaximumSize(max_dimension, max_dimension)
            for spot in range(self.table_size):
                self.qt.chunk_dialog_table.setColumnWidth(spot, pixel_size)
                self.qt.chunk_dialog_table.setRowHeight(spot, pixel_size)
        else:
            # self.qt.chunk_box_table.setMaximumSize(max_dimension, max_dimension)
            for spot in range(self.table_size):
                self.qt.chunk_box_table.setColumnWidth(spot, pixel_size)
                self.qt.chunk_box_table.setRowHeight(spot, pixel_size)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        row = index.row()
        column = index.column()

        to_do: ToDoFiles = self.qt.backup_status.to_do
        if to_do is None:
            return

        self.current_file: BackupFile = to_do.get_file(self.filename)
        if self.current_file is None:
            return

        chunk = self.calculate_chunk(row, column)  # row * self.rows_columns + column

        # The order is important. Chunks can be in both transmitted and deduped,
        # and if that happens, they are actually deduped. Also, they will be in
        # prepared, so the order to return is first deduped, then transmitted,
        # then prepared

        if role == Qt.ItemDataRole.BackgroundRole:
            if chunk in self.current_file.deduped_chunks:
                return QColor("#f5a356")

            if chunk in self.current_file.transmitted_chunks:
                return QColor("#84fab0")

            if chunk in self.current_file.prepared_chunks:
                return QColor("#2575fc")

            return QColor("#818a84")  # The default color

    def rowCount(self, index: QModelIndex) -> int:
        # Subtract two so that no matter what the way things are, we don't go over
        return self.table_size

    def columnCount(self, index: QModelIndex) -> int:
        # Subtract two so that no matter what the way things are, we don't go over
        if self.table_size == 0:
            if (datetime.now() - self.last_reset_table_time).seconds > 5:
                self.reset_table()
                self.last_reset_table_time = datetime.now()

        return self.table_size
