from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QDialogButtonBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTableWidgetItem,
)
from PyQt6.QtCore import Qt
from .to_do_files import ToDoFiles
from .backup_file import BackupFile
from .utils import file_size_string


class ToDoDialog(QDialog):
    def __init__(self, to_do_files: ToDoFiles):
        super().__init__()

        self.to_do_files = to_do_files

        self.setWindowTitle("Remaining To Do Items")

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        # self.button_box.accepted.connect(self.accept)
        # self.button_box.rejected.connect(self.reject)

        self.layout = QVBoxLayout()

        self.table = QTableWidget(self)
        column_names = [
            "File Name",
            "File Size",
        ]
        self.table.setColumnCount(len(column_names))
        self.table.setRowCount(0)
        for index, column_name in enumerate(column_names):
            item = QTableWidgetItem(column_name)
            if index > 1:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            else:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
            self.table.setHorizontalHeaderItem(index, item)

            self.table.horizontalHeader().setStretchLastSection(False)
            self.table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.ResizeToContents
            )
            self.table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.ResizeMode.Stretch
            )
            self.table.verticalHeader().setVisible(True)

        if self.to_do_files is None:
            self.table.insertRow(0)
            self.table.setItem(0, 0, QTableWidgetItem("To Do is not ready yet"))
            return

        for file in self.to_do_files.todo_files:  # type: BackupFile
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(file.file_name)))
            self.table.setItem(
                row, 1, QTableWidgetItem(file_size_string(file.file_size))
            )

        self.layout.addWidget(self.table)
        self.layout.addWidget(self.button_box)
        self.setLayout(self.layout)
