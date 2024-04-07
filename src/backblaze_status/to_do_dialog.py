from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QDialogButtonBox,
    QTableView,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QGroupBox,
    QSizePolicy,
    QAbstractItemView,
)

from .css_styles import CssStyles
from .to_do_dialog_model import ToDoDialogModel
from .to_do_files import ToDoFiles


class ToDoDialog(QDialog):
    def __init__(self, backup_status, model: ToDoDialogModel):
        super().__init__()

        self.backup_status: "QTBackupStatus" = backup_status
        self.model = model

        self.setStyleSheet(CssStyles.dark_orange)
        self.matching_indexes = None
        self.current_matching_index: int = 0

        self.setWindowTitle("To Do Items")
        self.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding
        )

        self.search_group_box = QGroupBox("Search")

        self.current_button = QPushButton("Current Item", parent=self.search_group_box)
        self.current_button.clicked.connect(self.current)

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

        self.search_layout.addWidget(self.current_button)
        self.search_layout.addWidget(self.query)
        self.search_layout.addWidget(self.query_results)
        self.search_layout.addWidget(self.previous_button)
        self.search_layout.addWidget(self.next_button)
        self.search_group_box.setLayout(self.search_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        # self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(lambda: self.setVisible(False))

        self.layout = QVBoxLayout()

        self.table = self._create_data_model_table()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )

        if self.backup_status is not None:
            self.backup_status.signals.files_updated.connect(
                self.model.update_display_cache
            )

        self.setSizeGripEnabled(True)
        self.layout.addWidget(self.search_group_box)
        self.layout.addWidget(self.table)
        self.layout.addWidget(self.button_box)
        self.setLayout(self.layout)

        if self.backup_status is not None:
            self.backup_status.signals.files_updated.connect(self.update_display_cache)

        self.update_display_cache()

    def update_display_cache(self):
        if self.isVisible():
            self.model.update_display_cache()

    def current(self):
        to_do: ToDoFiles = self.backup_status.to_do
        if to_do is not None and to_do.current_file is not None:
            index = to_do.to_do_file_list.file_list.index(to_do.current_file)
            model_index = self.model.index(index, 0)
            self.table.scrollTo(
                model_index,
                hint=QAbstractItemView.ScrollHint.PositionAtCenter,
            )

    def search(self, search_string: str):
        # self.table.setCurrentItem(None)
        if not search_string:
            # Empty string, don't search.
            self.previous_button.setDisabled(True)
            self.next_button.setDisabled(True)
            self.query_results.hide()
            return

        self.matching_indexes = self.model.match(
            self.model.index(0, 1),
            Qt.ItemDataRole.DisplayRole,
            search_string,
            hits=1000,
            flags=Qt.MatchFlag.MatchContains,
        )
        key_list = (
            self.backup_status.backup_status.to_do.to_do_file_list.file_dict.keys()
        )
        if self.matching_indexes:
            self.query_results.setText(self.get_label_string())

            self.query_results.show()
            # we have found something
            index = self.matching_indexes[0]  # take the first
            self.table.scrollTo(
                index, hint=QAbstractItemView.ScrollHint.PositionAtCenter
            )
            self.table.selectRow(index.row())
            self.previous_button.setDisabled(False)
            self.previous_button.setDefault(False)
            self.next_button.setDisabled(False)
        else:
            self.query_results.setText("No matches")
            self.previous_button.setDisabled(True)
            self.next_button.setDisabled(True)

    def next(self):
        next_item = self.current_matching_index + 1
        if len(self.matching_indexes) <= next_item:
            next_item = 0
        self.current_matching_index = next_item
        self.table.scrollTo(
            self.matching_indexes[next_item],
            hint=QAbstractItemView.ScrollHint.PositionAtCenter,
        )
        self.table.selectRow(self.matching_indexes[next_item].row())
        self.query_results.setText(self.get_label_string())

    def previous(self):
        previous_item = self.current_matching_index - 1
        if previous_item < 0:
            previous_item = len(self.matching_indexes) - 1
        self.current_matching_index = previous_item
        self.table.scrollTo(
            self.matching_indexes[previous_item],
            hint=QAbstractItemView.ScrollHint.PositionAtCenter,
        )
        self.table.selectRow(self.matching_indexes[previous_item].row())
        self.query_results.setText(self.get_label_string())

    def get_label_string(self):
        return (
            f"{len(self.matching_indexes):,} matches ("
            f"{self.current_matching_index + 1:,})"
        )

    def _create_data_model_table(self) -> QTableView:
        data_model_table = QTableView(self)
        data_model_table.setObjectName("DialogModelTable")
        data_model_table.setShowGrid(False)
        size_policy = QSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        size_policy.setHeightForWidth(False)
        data_model_table.setSizePolicy(size_policy)
        # Table will fit the screen horizontally
        data_model_table.horizontalHeader().setStretchLastSection(False)
        data_model_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        data_model_table.verticalHeader().setVisible(True)
        data_model_table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        data_model_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        data_model_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        return data_model_table

    def sizeHint(self):
        return QSize(2300, 500)
