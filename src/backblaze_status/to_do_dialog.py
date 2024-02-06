from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QDialogButtonBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTableWidgetItem,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QGroupBox,
    QSizePolicy,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, QSize
from .backup_file import BackupFile
from .utils import file_size_string
from .bz_data_table_model import BzDataTableModel


class ToDoDialog(QDialog):
    def __init__(self, model: BzDataTableModel):
        super().__init__()

        self.model = model

        self.matching_items = None
        self.current_matching_item = 0

        self.setWindowTitle("Remaining To Do Items")
        self.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding
        )

        self.search_group_box = QGroupBox("Search")
        self.query = QLineEdit()
        self.query.setClearButtonEnabled(True)
        self.query.setPlaceholderText("Search...")
        self.query.textChanged.connect(self.search)

        self.query_results = QLabel()
        self.query_results.hide()
        self.previous_button = QPushButton("Previous", parent=self.search_group_box)
        self.previous_button.setDefault(False)
        self.previous_button.setDisabled(True)
        self.next_button = QPushButton("Next", parent=self.search_group_box)
        self.next_button.setDefault(False)
        self.next_button.setDisabled(True)
        self.previous_button.clicked.connect(self.previous)
        self.next_button.clicked.connect(self.next)

        self.search_layout = QHBoxLayout()

        self.search_layout.addWidget(self.query)
        self.search_layout.addWidget(self.query_results)
        self.search_layout.addWidget(self.previous_button)
        self.search_layout.addWidget(self.next_button)
        self.search_group_box.setLayout(self.search_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        # self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(lambda: self.setVisible(False))

        self.layout = QVBoxLayout()

        self.table = QTableWidget(self)

        column_names = ["File Size", "File Name", "Backup Total"]
        self.table.setColumnCount(len(column_names))
        self.table.setRowCount(0)
        for index, column_name in enumerate(column_names):
            item = QTableWidgetItem(column_name)
            if index == 1:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
            else:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            self.table.setHorizontalHeaderItem(index, item)

        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        size_policy = QSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.table.setSizePolicy(size_policy)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.verticalHeader().setVisible(True)

        self.reset_list()
        self.setSizeGripEnabled(True)
        self.layout.addWidget(self.search_group_box)
        self.layout.addWidget(self.table)
        self.layout.addWidget(self.button_box)
        self.setLayout(self.layout)

    def reset_list(self):
        from .to_do_files import ToDoFiles

        self.table.clearContents()
        self.table.setRowCount(0)
        to_do: ToDoFiles = self.model.qt.backup_status.to_do
        if not to_do:
            return

        start_index = self.model.get_to_do_start_index()

        to_do_cache = to_do.file_list[start_index:]
        total_to_back_up = 0
        for file in to_do_cache:  # type: BackupFile
            total_to_back_up += file.file_size
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 1, QTableWidgetItem(str(file.file_name)))
            self.table.setItem(
                row, 0, QTableWidgetItem(file_size_string(file.file_size))
            )
            self.table.setItem(
                row, 2, QTableWidgetItem(file_size_string(total_to_back_up))
            )

        self.table.resizeColumnsToContents()

    def search(self, s):
        self.table.setCurrentItem(None)
        if not s:
            # Empty string, don't search.
            self.previous_button.setDisabled(True)
            self.next_button.setDisabled(True)
            self.query_results.hide()
            return

        self.matching_items = self.table.findItems(s, Qt.MatchFlag.MatchContains)
        if self.matching_items:
            self.query_results.setText(self.get_label_string())

            self.query_results.show()
            # we have found something
            item = self.matching_items[0]  # take the first
            self.table.setCurrentItem(item)
            self.previous_button.setDisabled(False)
            self.previous_button.setDefault(False)
            self.next_button.setDisabled(False)
        else:
            self.previous_button.setDisabled(True)
            self.next_button.setDisabled(True)

    def next(self):
        next_item = self.current_matching_item + 1
        if len(self.matching_items) < next_item:
            next_item = 0
        self.current_matching_item = next_item
        self.table.setCurrentItem(self.matching_items[next_item])
        self.query_results.setText(self.get_label_string())

    def previous(self):
        previous_item = self.current_matching_item - 1
        if previous_item < 0:
            previous_item = len(self.matching_items) - 1
        self.current_matching_item = previous_item
        self.table.setCurrentItem(self.matching_items[previous_item])
        self.query_results.setText(self.get_label_string())

    def get_label_string(self):
        return (
            f"{len(self.matching_items):,} matches ({self.current_matching_item + 1:,})"
        )

    def sizeHint(self):
        return QSize(2000, 500)
