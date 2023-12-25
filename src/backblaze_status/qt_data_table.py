from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView

from PyQt6 import QtCore, QtGui


class MoveDataTable(QTableWidget):
    HEADER_BACKGROUND_COLOR = QtGui.QColor(166, 166, 166)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setShowGrid(False)
        self.setAutoFillBackground(True)
        self._initialize_table()

    def _initialize_table(self):
        column_names = ["Time", "File Name", "File Size", "Interval", "Rate"]
        self.setColumnCount(len(column_names))
        self.setRowCount(0)

        for index, column_name in enumerate(column_names):
            item = QTableWidgetItem(column_name)
            item.setBackground(self.HEADER_BACKGROUND_COLOR)
            self.setHorizontalHeaderItem(index, item)

        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
