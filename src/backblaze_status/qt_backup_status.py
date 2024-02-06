from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from enum import IntEnum

from PyQt6.QtCore import (
    QObject,
    pyqtSignal,
    pyqtSlot,
    Qt,
    QCoreApplication,
    QThread,
    QTimer,
)
from PyQt6.QtGui import QColor, QShortcut, QIcon, QPixmap, QAction
from PyQt6.QtWidgets import (
    QMainWindow,
    QAbstractItemView,
    QAbstractSlider,
    QHeaderView,
)

from .backup_file import BackupFile
from .backup_results import BackupResults
from .bz_data_table_model import BzDataTableModel
from .chunk_model import ChunkModel
from .dev_debug import DevDebug
from .main_backup_status import BackupStatus
from .progress import ProgressBox
from .qt_mainwindow import Ui_MainWindow
from .to_do_dialog import ToDoDialog
from .utils import MultiLogger
from .workers import ProgressBoxWorker, BackupStatusWorker, StatsBoxWorker
from .to_do_files import ToDoFiles


class QTBackupStatus(QMainWindow, Ui_MainWindow):
    PixelSize = 10
    SmallChunkCount = 50
    LargeChunkCount = 400

    class Signals(QObject):
        # update_row = pyqtSignal(int, list, bool)
        # insert_row = pyqtSignal(int)
        update_clock = pyqtSignal(str)
        update_progress_bar = pyqtSignal(dict)
        update_stats_box = pyqtSignal(str)
        # update_log_line = pyqtSignal(str)
        # update_chunk_preparing = pyqtSignal(str)
        # update_prepare = pyqtSignal(str, int)
        start_new_file = pyqtSignal(str)

        interval_timer = pyqtSignal(int)
        stop_interval_timer = pyqtSignal()
        update_data_table_last_row = pyqtSignal(list, name="update_data_table_last_row")
        update_log = pyqtSignal(str)
        update_disk_color = pyqtSignal(int, "PyQt_PyObject")
        add_pre_data_row = pyqtSignal(list)
        update_cell = pyqtSignal(int, int, "PyQt_PyObject", "PyQt_PyObject")
        add_data_row = pyqtSignal(list)
        update_disk_table = pyqtSignal()
        # completed_file = pyqtSignal(str)
        to_do_available = pyqtSignal()

        preparing = pyqtSignal()
        transmitting = pyqtSignal(str)
        # new_large_file = pyqtSignal(str)

    class ProcessingType(IntEnum):
        PREPARING = 0
        TRANSMITTING = 1

    def __init__(
        self,
        test=True,
        gui_test=False,
        *args,
        **kwargs,
    ):
        super(QTBackupStatus, self).__init__(*args, **kwargs)

        self._multi_log = MultiLogger("QTBackupStatus", terminal=True, qt=self)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting QTBackupStatus")

        self.test = test
        self.gui_test = gui_test

        self.debug = DevDebug()
        self.debug.disable("lock")
        self.debug.disable("bz_prepare.show_line")
        self.debug.disable("lastfilestransmitted.show_line")

        icon_path = os.path.join(
            os.path.dirname(sys.modules[__name__].__file__), "backblaze_status.png"
        )
        QCoreApplication.instance().setWindowIcon(QIcon(QPixmap(icon_path)))

        # Set up the GUI interface
        self.setupUi(self)
        self.show()
        self.data_model_table.resizeRowsToContents()

        self.signals = self.Signals()
        self.define_signals()

        self.previous_file_name = None
        self.current_file_name = None
        self.large_file_name = None
        self.prepare_file_name = None
        self.display_moved = False
        self.current_last_row: int = 0
        self.in_table: set = set()

        self.selected_row: int = -1

        self.large_file_update_timer: QTimer | None = None

        self.processing_type: QTBackupStatus.ProcessingType = (
            QTBackupStatus.ProcessingType.PREPARING
        )

        self.to_do_loaded = False

        self.to_do_dialog: ToDoDialog | None = None

        self.setWindowTitle("Backblaze Status")
        # **** Set up threads ****

        # Clock thread
        self.clock_timer = QTimer()
        self.clock_timer.setObjectName("Clock Update")
        self.clock_timer.timeout.connect(self.update_clock_display)
        self.clock_timer.start(1000)

        # BackupStatus thread
        self.backup_status: BackupStatus = BackupStatus(self)

        self.backup_status_thread = QThread()
        self.backup_status_thread.setObjectName("BackupStatusThread")
        self.backup_status_worker: BackupStatusWorker = BackupStatusWorker(
            self.backup_status
        )
        self.backup_status_worker.moveToThread(self.backup_status_thread)
        self.backup_status_thread.started.connect(self.backup_status_worker.run)
        self.backup_status_thread.start()

        QThread.sleep(2)  # Just give it a chance to start

        # Update Stats Box Thread
        self.update_stats_box_thread = QThread()
        self.update_stats_box_thread.setObjectName("UpdateStatsBox")
        self.update_stats_box_worker: StatsBoxWorker = StatsBoxWorker(
            self.backup_status
        )
        self.update_stats_box_worker.moveToThread(self.update_stats_box_thread)
        self.update_stats_box_worker.update_stats_box.connect(self.update_stats_box)
        self.update_stats_box_thread.started.connect(self.update_stats_box_worker.run)
        self.update_stats_box_thread.start()

        time.sleep(1)  # Let things get settled

        # Update Progress Bar Thread
        self.progress_box = ProgressBox(self.backup_status)

        self.progress_box_thread = QThread()
        self.progress_box_thread.setObjectName("ProgressBox")
        self.progress_box_worker: ProgressBoxWorker = ProgressBoxWorker(
            self.progress_box
        )
        self.progress_box_worker.moveToThread(self.progress_box_thread)
        self.progress_box_worker.update_progress_box.connect(self.update_progress_box)
        self.progress_box_thread.started.connect(self.progress_box_worker.run)
        self.progress_box_thread.start()

        self.result_data = BzDataTableModel(self)
        self.data_model_table.setModel(self.result_data)
        self.data_model_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )

        # Update Chunk Box
        self.chunk_box_timer = QTimer()
        self.chunk_box_timer.setObjectName("ChunkBoxUpdate")
        self.chunk_box_timer.timeout.connect(self.update_chunk_progress)
        self.chunk_box_timer.start(100)

        self.chunk_model = ChunkModel(self)
        self.chunk_box_table.setModel(self.chunk_model)
        self.chunk_dialog_table.setModel(self.chunk_model)

        # Set up key shortcuts

        self.b_key = QShortcut(Qt.Key.Key_B, self.data_model_table)
        self.b_key.activated.connect(self.b_pressed)

        self.t_key = QShortcut(Qt.Key.Key_T, self.data_model_table)
        self.t_key.activated.connect(self.t_pressed)

        self.c_key = QShortcut(Qt.Key.Key_C, self.data_model_table)
        self.c_key.activated.connect(self.c_pressed)

        self.data_model_table.clicked.connect(self.toggle_selection)

        # Set up Options Menu

        self.show_to_do_button = QAction("&Show To Do List", self)
        self.show_to_do_button.setStatusTip("Show pop up to do list")
        self.show_to_do_button.triggered.connect(self.pop_up_todo)
        self.option_menu.addAction(self.show_to_do_button)
        self.show_to_do_button.setDisabled(True)

    def define_signals(self):
        # self.signals.update_row.connect(self.update_row)
        # self.signals.insert_row.connect(self.insert_row)
        # self.signals.update_log_line.connect(self.update_log_line)
        # self.signals.update_chunk_preparing.connect(self.update_chunk_preparing)
        # self.signals.update_prepare.connect(self.update_prepare)
        self.signals.start_new_file.connect(self.start_new_file)
        self.signals.preparing.connect(self.set_preparing)
        self.signals.transmitting.connect(self.set_transmitting)
        # self.signals.new_large_file.connect(self.new_large_file)
        # self.signals.completed_file.connect(self.complete_file)
        self.chunk_show_dialog_button.clicked.connect(self.show_chunk_dialog)

        self.data_model_table.verticalScrollBar().actionTriggered.connect(
            self.scroll_bar_moved
        )
        self.progressBar.valueChanged.connect(self.update_progress_bar_percentage)

    @pyqtSlot()
    def show_chunk_dialog(self):
        print("Show chunk button clicked")
        self.chunk_show_dialog_button.activateWindow()
        self.chunk_show_dialog_button.raise_()

    def pop_up_todo(self, event):
        print(f"Clicked {event}")
        if self.to_do_dialog is None:
            self.to_do_dialog = ToDoDialog(self.result_data)
            self.to_do_dialog.exec()
        else:
            self.to_do_dialog.reset_list()
            self.to_do_dialog.setVisible(True)

    @pyqtSlot()
    def b_pressed(self):
        """
        Go to the bottom of the table, and clear the selection
        """

        self.data_model_table.clearSelection()
        self.display_moved = False
        self.data_model_table.scrollToBottom()

    @pyqtSlot()
    def t_pressed(self):
        """
        Go to the top of the table
        """
        self.data_model_table.selectRow(0)
        self.data_model_table.scrollTo(self.result_data.index(0, 0))

    @pyqtSlot()
    def c_pressed(self):
        """
        Center the selected row. Don't do anything if there is no row selected
        """
        selected_items = self.data_model_table.selectedIndexes()
        if len(selected_items) > 0:
            self.data_model_table.scrollTo(
                selected_items[0], hint=QAbstractItemView.ScrollHint.PositionAtCenter
            )
        else:
            self.reposition_table()

    def reposition_table(self):
        """
        Reposition the table to the bottom, if there isn't already a row selected
        """
        self.data_model_table.resizeRowsToContents()
        selected_items = self.data_model_table.selectedIndexes()
        if len(selected_items) > 0:
            return  # If we are not at the bottom, don't scroll there

        self.data_model_table.scrollTo(
            self.result_data.index(len(self.result_data.data_list) - 1, 0),
            hint=QAbstractItemView.ScrollHint.PositionAtCenter,
        )

    def toggle_selection(self, e):
        if e.row() == self.selected_row:
            self.data_model_table.clearSelection()
            self.selected_row = -1
        else:
            self.selected_row = e.row()

    def scroll_bar_moved(self, event):
        """
        If they scroll to the bottom, clear the selection and stay there
        """
        if event == QAbstractSlider.SliderAction.SliderToMaximum:
            self.data_model_table.clearSelection()
            self.reposition_table()
            self.display_moved = False
        else:
            self.display_moved = True

    def update_clock_display(self):
        self.clock_display.setText(datetime.now().strftime("%-I:%M:%S %p"))

    @pyqtSlot(str)
    def update_stats_box(self, text: str):
        self.stats_info.setText(text)
        self.to_do_loaded = True
        self.show_to_do_button.setDisabled(False)

    @pyqtSlot(dict)
    def update_progress_box(self, values: dict):
        self.progressBar.setValue(values["completed_size"])
        self.progressBar.setMaximum(values["total_size"])
        self.elapsed_time.setText(values["elapsed_time"])
        self.progress.setText(values["progress_string"])
        self.time_remaining.setText(values["remaining"])
        self.completion_time.setText(values["completion_time"])
        self.rate.setText(values["rate"])

    @pyqtSlot(int)
    def update_progress_bar_percentage(self, value: int):
        if self.progressBar.maximum() == 0:
            return
        percentage = (value - self.progressBar.minimum()) / (
            self.progressBar.maximum() - self.progressBar.minimum()
        )
        self.progressBar.setFormat(f"{percentage:.2%}")

    @pyqtSlot()
    def set_preparing(self):
        to_do = self.backup_status.to_do  # type: ToDoFiles
        current_file: BackupFile = to_do.get_file(self.large_file_name)
        if current_file is None:
            return

        self.processing_type = QTBackupStatus.ProcessingType.PREPARING
        self.backup_status.to_do.current_file = current_file

        self.prepare_chunk_progress_bar.setMinimum(0)
        self.prepare_chunk_progress_bar.setMaximum(current_file.chunks_total)
        self.initialize_chunk_table()
        self.chunk_box.show()
        self.reposition_table()  # Since the bottom moved
        self.file_info.hide()

    @pyqtSlot(str)
    def set_transmitting(self, filename: str):
        to_do: ToDoFiles = self.backup_status.to_do
        current_file: BackupFile = to_do.get_file(filename)
        if current_file is None:
            return

        to_do.current_file = current_file
        self.processing_type = QTBackupStatus.ProcessingType.TRANSMITTING
        self.result_data.show_new_file(filename, current_file.file_size)

        if current_file.large_file:
            self.large_file_name = filename
            self.chunk_model.filename = filename
            self.transmit_chunk_progress_bar.setMinimum(0)
            self.transmit_chunk_progress_bar.setMaximum(current_file.chunks_total)
            self.initialize_chunk_table()
            self.chunk_box.show()
            self.reposition_table()  # Since the bottom moved
        else:
            self.chunk_box.hide()
            self.chunk_table_dialog.hide()
            self.file_info.show()

    @pyqtSlot()
    def initialize_chunk_table(self):
        to_do: ToDoFiles = self.backup_status.to_do
        current_file: BackupFile = to_do.get_file(self.chunk_model.filename)
        if current_file is None or self.chunk_model.table_size == 0:
            self.chunk_show_dialog_button.setText("Table not ready yet")
            self.chunk_show_dialog_button.setDisabled(True)
            self.chunk_show_dialog_button.show()
            self.chunk_model.reset_table()
            timer = QTimer()
            timer.setSingleShot(True)
            timer.start(10000)  # 10 seconds
            timer.timeout.connect(self.initialize_chunk_table)
            return

        if self.chunk_model.use_dialog:
            self.chunk_dialog_table.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            self.chunk_dialog_table.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )

            self.chunk_table_dialog.setWindowTitle(self.chunk_model.filename)
            self.chunk_table_dialog.show()
            self.chunk_dialog_table.show()
            self.chunk_box_table.hide()
            self.chunk_show_dialog_button.show()
            self.chunk_show_dialog_button.setEnabled(True)

            self.chunk_dialog_table.resizeRowsToContents()
            self.chunk_dialog_table.resizeColumnsToContents()

            self.chunk_dialog_table.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.chunk_dialog_table.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )

            self.chunk_dialog_table.setFixedWidth(
                self.chunk_box_table.horizontalHeader().length()
            )
            self.chunk_dialog_table.setFixedHeight(
                self.chunk_box_table.verticalHeader().length()
            )
        else:
            self.chunk_box_table.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.chunk_box_table.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )

            self.chunk_box_table.setFixedWidth(
                self.chunk_box_table.horizontalHeader().length()
            )
            self.chunk_box_table.setFixedHeight(
                self.chunk_box_table.verticalHeader().length()
            )
            # @@@ self.chunk_box_table.show()
            self.chunk_table_dialog.hide()
            self.chunk_show_dialog_button.hide()

            self.chunk_box_table.resizeRowsToContents()
            self.chunk_box_table.resizeColumnsToContents()

    def update_chunk_progress(self):
        to_do: ToDoFiles = self.backup_status.to_do
        if to_do is None or to_do.current_file is None:
            return

        current_file: BackupFile = to_do.current_file
        if current_file is None:
            return

        if self.processing_type == QTBackupStatus.ProcessingType.TRANSMITTING:
            # There is progressbar for large files, so update that
            max_transmitted = current_file.max_transmitted
            max_deduped = current_file.max_deduped

            self.transmit_chunk_progress_bar.setValue(
                max([max_deduped, max_transmitted])
            )

            # self.chunk_progress_bar.setStyleSheet(style_sheet)
            self.chunk_filename.setText(
                f"Transmitting: {str(current_file.file_name)}"
                f" ({current_file.current_chunk:>4,} /"
                f" {current_file.chunks_total:,} chunks)"
            )

        if self.processing_type == QTBackupStatus.ProcessingType.PREPARING:
            # There is progressbar for large files, so update that
            self.prepare_chunk_progress_bar.setValue(current_file.max_prepared)

            # self.chunk_progress_bar.setStyleSheet(style_sheet)
            self.chunk_filename.setText(
                f"Preparing: {str(current_file.file_name)}"
                f" ({current_file.current_chunk:>4,} /"
                f" {current_file.chunks_total:,} chunks)"
            )

    @pyqtSlot(str)
    def start_new_file(self, file_name: str):
        self.chunk_box.hide()
        self.file_info.show()

        self.file_info.setText(f"Preparing new file {file_name}")
        if self.previous_file_name is None:
            self.previous_file_name = file_name
        elif self.previous_file_name != file_name:
            to_do: ToDoFiles = self.backup_status.to_do
            previous_file: BackupFile = to_do.get_file(self.previous_file_name)
            if previous_file is not None:
                to_do.completed(self.previous_file_name)
            default_color = QColor("white")
            if previous_file is None or previous_file.is_deduped:
                label_color = QColor("orange")
            else:
                label_color = default_color

            row_result = BackupResults(
                timestamp=previous_file.timestamp,
                file_name=self.previous_file_name,
                file_size=previous_file.file_size,
                rate=previous_file.rate,
                row_color=QColor(label_color),
                start_time=datetime.now(),
            )
            self.result_data.add_row(row_result, chunk=previous_file.large_file)
            self.reposition_table()
            self.previous_file_name = file_name

        to_do: ToDoFiles = self.backup_status.to_do
        current_file: BackupFile = to_do.get_file(file_name)
        self.transmit_chunk_progress_bar.setValue(0)
        self.transmit_chunk_progress_bar.setMaximum(100)
        self.prepare_chunk_progress_bar.setValue(0)
        self.prepare_chunk_progress_bar.setMaximum(100)

        if current_file.large_file:
            self.large_file_name = file_name
            self.chunk_model.filename = file_name
            self.initialize_chunk_table()
            self.set_preparing()
        else:
            self.large_file_name = None

        file_size = current_file.file_size
        self.result_data.show_new_file(file_name, file_size)
