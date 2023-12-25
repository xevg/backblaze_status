import qdarktheme
import sys
from backup_status_mainwindow import Ui_MainWindow
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QMainWindow, QApplication
from qt_backup_status import QTBackupStatus


class TestQT(QMainWindow, Ui_MainWindow):
    pass


app = QApplication(sys.argv)
qdarktheme.setup_theme()
t = QTBackupStatus(gui_test=True)
t.signals.insert_row.emit(0)
t.signals.update_row.emit(0, ("a", "b", "c"))
# t = TestQT()
# t.setupUi(t)
# t.show()
app.exec()
