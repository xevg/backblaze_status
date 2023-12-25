import time

from backup_status_mainwindow import Ui_MainWindow
from PyQt6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QMainWindow,
    QAbstractItemView,
)
from .backup_status import BackupStatus
from qt_progress_box import ProgressBox

import threading
from PyQt6.QtCore import (
    Qt,
    QTimer,
    QObject,
    pyqtSignal,
    QThread,
    pyqtSlot,
)
from datetime import datetime


class QTBackupStatus(QMainWindow, Ui_MainWindow):
    class Signals(QObject):
        update_row = pyqtSignal(int, list)
        insert_row = pyqtSignal(int)
        update_clock = pyqtSignal(str)
        update_progress_bar = pyqtSignal()
        update_stats_box = pyqtSignal(str)

        interval_timer = pyqtSignal(int)
        stop_interval_timer = pyqtSignal()
        update_data_table_last_row = pyqtSignal(list, name="update_data_table_last_row")
        update_log = pyqtSignal(str)
        update_disk_color = pyqtSignal(int, "PyQt_PyObject")
        add_pre_data_row = pyqtSignal(list)
        update_cell = pyqtSignal(int, int, "PyQt_PyObject", "PyQt_PyObject")
        add_data_row = pyqtSignal(list)
        update_disk_table = pyqtSignal()

    def __init__(
        self,
        test=True,
        gui_test=False,
        *args,
        **kwargs,
    ):
        super(QTBackupStatus, self).__init__(*args, **kwargs)

        self.test = test
        self.gui_test = gui_test

        # Set up the GUI interface
        self.setupUi(self)
        self.show()

        self.signals = self.Signals()
        self.define_signals()

        self.progress_box = ProgressBox(self)

        # **** Set up threads ****

        # Clock thread
        self.clock_thread = threading.Thread(target=self.update_clock, daemon=True)
        self.clock_thread.start()

        # BackupStatus thread
        if not self.gui_test:
            self.backup_status = BackupStatus(self)
            self.backup_status_thread = threading.Thread(
                target=self.backup_status.run, daemon=True
            )
            self.backup_status_thread.start()

        # Test thread
        if self.test:
            self.test_thread = threading.Thread(target=self.test_thread, daemon=True)
            self.test_thread.start()

    def define_signals(self):
        self.signals.update_row.connect(self.update_row)
        self.signals.insert_row.connect(self.insert_row)
        self.signals.update_clock.connect(self.update_clock_display)
        self.signals.update_stats_box.connect(self.update_stats_box)
        self.signals.update_progress_bar.connect(self.update_progress_bar)

    def test_thread(self):
        while True:
            pass
            time.sleep(10)

    def update_clock(self):
        while True:
            date = datetime.now().strftime("%-I:%M:%S %p")
            self.signals.update_clock.emit(date)
            time.sleep(1)

    @pyqtSlot(str)
    def update_clock_display(self, date: str):
        self.clock_display.setText(date)

    @pyqtSlot(str)
    def update_stats_box(self, text: str):
        self.stats_info.setText(text)

    def create_item(self, text: str):
        return QTableWidgetItem(text)

    @pyqtSlot(int)
    def insert_row(self, row: int):
        self.file_display_table.insertRow(row)

    @pyqtSlot(int, list)
    def update_row(self, row: int, row_contents: list):
        # row = (row, time, file_name, file_size, interval, rate)

        if self.file_display_table.rowCount() - 1 < row:
            for i in range(self.file_display_table.rowCount(), row + 1):
                self.insert_row(i)
        for column, contents in enumerate(row_contents):
            item: QTableWidgetItem = self.file_display_table.setItem(
                row, column, self.create_item(contents)
            )
            self.file_display_table.scrollToItem(
                item, hint=QAbstractItemView.ScrollHint.PositionAtCenter
            )
        self.file_display_table.resizeRowsToContents()

    @pyqtSlot()
    def update_progress_bar(self):
        self.progressBar.value(self.)
