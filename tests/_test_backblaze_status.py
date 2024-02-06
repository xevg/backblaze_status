import sys
from backblaze_status import ToDoFiles, BzLastFilesTransmitted, QTBackupStatus
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon, QPixmap
from asyncslot import AsyncSlotRunner
app = QApplication(sys.argv)
app.setApplicationName("Backblaze Status")

# qdarktheme.setup_theme()

QTBackupStatus(gui_test=False)
with AsyncSlotRunner():
    app.exec()
# bz = BzLastFilesTransmitted(ToDoFiles("/tmp/todo_file"))
# bz.read_transmit_file()
