from PyQt6.QtWidgets import QTableView

class ChunkTable(QTableView):
    def __init__(self):
        super().__init__()

        self.filename = None

