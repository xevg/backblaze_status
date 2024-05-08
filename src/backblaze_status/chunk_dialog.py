from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QTableView,
    QVBoxLayout,
    QHeaderView,
    QAbstractItemView,
    QSizePolicy,
)


class ChunkDialog(QDialog):
    """
    A custom QDialog box for the chunk progress table
    """

    def __init__(self, parent=None):
        super(ChunkDialog, self).__init__(parent)

        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.dialog_chunk_table = self.create_chunk_table()

        self.chunk_table_dialog_layout = QVBoxLayout()
        self.chunk_table_dialog_layout.addWidget(self.dialog_chunk_table)

        self.setLayout(self.chunk_table_dialog_layout)
        self.show()

    def create_chunk_table(self):
        """
        Create the table for the chunk progress
        """
        chunk_table = QTableView(self)
        chunk_table.setObjectName("ChunkTable")

        chunk_table.horizontalHeader().setMaximumSectionSize(2)
        chunk_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Fixed
        )
        chunk_table.horizontalHeader().setVisible(False)
        chunk_table.verticalHeader().setMaximumSectionSize(2)
        chunk_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        chunk_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        chunk_table.verticalHeader().setVisible(False)
        chunk_table.setShowGrid(False)

        return chunk_table
