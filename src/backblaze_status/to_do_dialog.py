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

from .constants import ToDoColumns
from .css_styles import CssStyles
from .current_state import CurrentState
from .to_do_dialog_model import ToDoDialogModel


class ToDoDialog(QDialog):
    """
    This class pops up a dialog box for the entire to do list
    """

    def __init__(self, backup_status, model: ToDoDialogModel):
        super().__init__()

        from .qt_backup_status import QTBackupStatus

        self.backup_status: QTBackupStatus = backup_status
        self.model = model

        self.setStyleSheet(CssStyles.dark_orange)

        # Configuration for the search box
        self.matching_indexes = None
        self.current_matching_index: int = 0

        self.setWindowTitle("To Do Items")
        self.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding
        )

        # Create a group box for the search
        self.search_group_box = QGroupBox()

        # Button to go to current item
        self.current_button = QPushButton("Current Item", parent=self.search_group_box)
        self.current_button.clicked.connect(self.current)

        # Search entry box
        self.query = QLineEdit()
        self.query.setClearButtonEnabled(True)
        self.query.setPlaceholderText("Search...")
        self.query.textChanged.connect(self.search)

        # The results of the search, which is hidden until there are results
        self.query_results = QLabel()
        self.query_results.hide()

        # A button to go to the previous result, which is hidden until there are results
        self.previous_button = QPushButton("Previous", parent=self.search_group_box)
        self.previous_button.setDefault(False)
        self.previous_button.setDisabled(True)
        self.previous_button.clicked.connect(self.previous)
        self.previous_button.hide()

        # A button to go to the next result, which is hidden until there are results
        self.next_button = QPushButton("Next", parent=self.search_group_box)
        self.next_button.setDefault(False)
        self.next_button.setDisabled(True)
        self.next_button.clicked.connect(self.next)
        self.previous_button.hide()

        # Create a horizontal layout and add everything into it
        self.search_layout = QHBoxLayout()

        self.search_layout.addWidget(self.current_button)
        self.search_layout.addWidget(self.query)
        self.search_layout.addWidget(self.query_results)
        self.search_layout.addWidget(self.previous_button)
        self.search_layout.addWidget(self.next_button)
        self.search_group_box.setLayout(self.search_layout)

        # Create a button for closing the window
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(lambda: self.setVisible(False))

        # Create the vertical layout box to hold everything
        self.layout = QVBoxLayout()

        self.table = self.create_data_model_table()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )

        self.setSizeGripEnabled(True)
        self.layout.addWidget(self.search_group_box)
        self.layout.addWidget(self.table)
        self.layout.addWidget(self.button_box)
        self.setLayout(self.layout)

    def current(self):
        """
        Go to the current item
        """
        try:
            index = CurrentState.ToDoList[CurrentState.CurrentFile][
                ToDoColumns.IndexCount
            ]
            model_index = self.model.index(index, 0)
            self.table.scrollTo(
                model_index,
                hint=QAbstractItemView.ScrollHint.PositionAtCenter,
            )
        except KeyError:
            return

    def search(self, search_string: str):
        """
        This method is called whenever the text in the search box is changed
        :param search_string: the contents of the search
        """
        if not search_string:
            # Empty string, don't search.
            self.previous_button.setDisabled(True)
            self.next_button.setDisabled(True)
            self.query_results.hide()
            self.previous_button.hide()
            self.next_button.hide()
            return

        # Get the matching rows, based on the filename column, though cap it
        # at 1,000 items
        self.matching_indexes = self.model.match(
            self.model.index(0, 1),
            Qt.ItemDataRole.DisplayRole,
            search_string,
            hits=1000,
            flags=Qt.MatchFlag.MatchContains,
        )

        if self.matching_indexes:
            # Show the number of matches
            self.query_results.setText(self.get_label_string())
            self.query_results.show()

            # Go to the first item
            index = self.matching_indexes[0]
            self.table.scrollTo(
                index, hint=QAbstractItemView.ScrollHint.PositionAtCenter
            )
            self.table.selectRow(index.row())
            self.previous_button.setDisabled(False)
            self.previous_button.setDefault(False)
            self.next_button.setDisabled(False)
            self.previous_button.show()
            self.next_button.show()
        else:
            self.query_results.setText("No matches")
            self.previous_button.setDisabled(True)
            self.next_button.setDisabled(True)

    def next(self):
        """
        Go to the next matching item. If we go past the last one, wrap.
        """
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
        """
        Go to the previous matching item. If we go past the first one, wrap.
        """
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
        """
        Create the label string, which is the number of matches, and the currently
        matched item.
        """
        return (
            f"{len(self.matching_indexes):,} matches ("
            f"{self.current_matching_index + 1:,})"
        )

    def create_data_model_table(self) -> QTableView:
        """
        Create the table with the file data
        """
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
