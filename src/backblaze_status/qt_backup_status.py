from __future__ import annotations

import os
import sys
from datetime import datetime
from enum import IntEnum
from typing import Optional
import threading

from PyQt6.QtCore import (
    pyqtSlot,
    Qt,
    QCoreApplication,
    QThread,
    QTimer,
)
from PyQt6.QtGui import QShortcut, QIcon, QPixmap, QAction
from PyQt6.QtWidgets import (
    QMainWindow,
    QAbstractItemView,
    QAbstractSlider,
    QHeaderView,
)
from icecream import ic, install

from .backup_file import BackupFile
from .bz_data_table_model import BzDataTableModel
from .chunk_model import ChunkModel
from .dev_debug import DevDebug
from .exceptions import CurrentFileNotSet
from .progress_box import ProgressBox
from .qt_mainwindow import Ui_MainWindow
from .signals import Signals
from .to_do_dialog import ToDoDialog
from .to_do_dialog_model import ToDoDialogModel
from .to_do_files import ToDoFiles
from .utils import MultiLogger
from .worker_to_do import ToDoWorker


def debug_print(message: str):
    thread_name = threading.current_thread().name
    date = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} <{thread_name}>'

    print(f"{date} {message}")


# Set up icecream debugging
def get_ic_prefix():
    thread_name = threading.current_thread().name
    return f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} <{thread_name}>'


ic.configureOutput(includeContext=True, prefix=get_ic_prefix)
install()


class QTBackupStatus(QMainWindow, Ui_MainWindow):
    # How large is each chunk in the chunk table, by pixel
    PixelSize = 10

    # A file with less than LargeChunkCount is medium sized. A LargeChunkCount or
    # larger and I create a separate window for it
    SmallChunkCount = 50
    LargeChunkCount = 400

    class ProcessingType(IntEnum):
        """
        Enum class to indicate the type of processing we are currently doing
        """

        PREPARING = 0
        TRANSMITTING = 1

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super(QTBackupStatus, self).__init__(*args, **kwargs)

        # Set up logging

        self._multi_log = MultiLogger("QTBackupStatus", terminal=True, qt=self)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting QTBackupStatus")

        # Set up dev debugging

        self.debug = DevDebug()
        self.debug.disable("lock")
        self.debug.disable("bz_prepare.show_line")
        self.debug.disable("lastfilestransmitted.show_line")

        # Set up the system icon, for the task bar

        icon_path = os.path.join(
            os.path.dirname(sys.modules[__name__].__file__), "backblaze_status.png"
        )
        QCoreApplication.instance().setWindowIcon(QIcon(QPixmap(icon_path)))

        # Set up the GUI interface

        self.setupUi(self)
        self.show()
        self.data_model_table.resizeRowsToContents()

        # Set up signals

        self.signals = Signals()
        self.define_signals()

        # Set up data elements

        self.previous_file_name = None
        self.large_file_name = None

        # Flag to note if the display viewport has moved
        self.display_moved = False

        # Currently selected row
        self.selected_row: int = -1

        # Flag if I am preparing or transmitting
        self.processing_type: QTBackupStatus.ProcessingType = (
            QTBackupStatus.ProcessingType.PREPARING
        )

        # Placeholder for the ToDoDialog
        self.to_do_dialog: ToDoDialog | None = None

        # **** Set up threads ****

        # Setup to_do thread
        self.to_do_thread = QThread()
        self.to_do_thread.setObjectName("ToDoThread")
        self.to_do: ToDoFiles = ToDoFiles(self)
        self.to_do.moveToThread(self.to_do_thread)
        self.to_do_thread.started.connect(self.to_do.run)
        self.to_do_thread.start()

        # Setup BzLastFileTransmitted Thread
        from .worker_last_files_transmitted import LastFilesTransmittedWorker

        self.bz_last_files_transmitted_thread = QThread()
        self.bz_last_files_transmitted_thread.setObjectName("LastFileTransmittedThread")
        self.bz_last_files_transmitted_thread_worker: LastFilesTransmittedWorker = (
            LastFilesTransmittedWorker(self)
        )
        self.bz_last_files_transmitted_thread_worker.moveToThread(
            self.bz_last_files_transmitted_thread
        )
        self.bz_last_files_transmitted_thread.started.connect(
            self.bz_last_files_transmitted_thread_worker.run
        )
        self.bz_last_files_transmitted_thread.start()

        # Setup BzTransmit Thread
        from .worker_bz_transmit import BZTransmitWorker

        self.bz_transmit_thread = QThread()
        self.bz_transmit_thread.setObjectName("BzTransmitThread")
        self.bz_transmit_thread_worker: BZTransmitWorker = BZTransmitWorker(self)
        self.bz_transmit_thread_worker.moveToThread(self.bz_transmit_thread)
        self.bz_transmit_thread.started.connect(self.bz_transmit_thread_worker.run)
        self.bz_transmit_thread.start()

        # Setup BzPrepare Thread
        from .worker_bz_prepare import BzPrepareWorker

        self.bz_prepare_thread = QThread()
        self.bz_prepare_thread.setObjectName("BzTransmitThread")
        self.bz_prepare_thread_worker: BzPrepareWorker = BzPrepareWorker(self)
        self.bz_prepare_thread_worker.moveToThread(self.bz_prepare_thread)
        self.bz_prepare_thread.started.connect(self.bz_prepare_thread_worker.run)
        self.bz_prepare_thread.start()

        # Clock thread
        self.clock_timer = QTimer()
        self.clock_timer.setObjectName("Clock Update")
        self.clock_timer.timeout.connect(self.update_clock_display)
        self.clock_timer.start(1000)

        # Update Stats Box Thread
        from .worker_stats_box import StatsBoxWorker

        self.update_stats_box_thread = QThread()
        self.update_stats_box_thread.setObjectName("UpdateStatsBox")
        self.update_stats_box_worker: StatsBoxWorker = StatsBoxWorker(self)
        self.update_stats_box_worker.moveToThread(self.update_stats_box_thread)
        self.update_stats_box_worker.update_stats_box.connect(self.update_stats_box)
        self.update_stats_box_thread.started.connect(self.update_stats_box_worker.run)
        self.update_stats_box_thread.start()

        # Update Progress Bar Thread
        from .worker_progress_box import ProgressBoxWorker

        self.progress_box = ProgressBox(self)

        self.progress_box_thread = QThread()
        self.progress_box_thread.setObjectName("ProgressBox")
        self.progress_box_worker: ProgressBoxWorker = ProgressBoxWorker(self)
        self.progress_box_worker.moveToThread(self.progress_box_thread)
        self.progress_box_worker.update_progress_box.connect(self.update_progress_box)
        self.progress_box_thread.started.connect(self.progress_box_worker.run)
        self.progress_box_thread.start()

        # Update Chunk Box

        self.chunk_model = ChunkModel(self)
        self.chunk_box_table.setModel(self.chunk_model)
        self.chunk_dialog_table.setModel(self.chunk_model)

        self.chunk_box_timer = QTimer()
        self.chunk_box_timer.setObjectName("ChunkBoxUpdate")
        self.chunk_box_timer.timeout.connect(self.update_chunk_progress)
        self.chunk_box_timer.start(100)

        # Update the windows title
        self.signals.backup_running.emit(False)
        self.signals.backup_running.emit(False)

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

        # Connect the data table with the model
        self.result_data: Optional[BzDataTableModel] = None
        self.result_data = BzDataTableModel(self)
        self.data_model_table.setModel(self.result_data)
        self.data_model_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )

    def define_signals(self):
        self.signals.backup_running.connect(self.set_window_title)

        self.signals.start_new_file.connect(self.start_new_file)
        self.signals.preparing.connect(self.set_preparing)
        self.signals.transmitting.connect(self.set_transmitting)

        self.chunk_show_dialog_button.clicked.connect(self.show_chunk_dialog)

        self.data_model_table.verticalScrollBar().actionTriggered.connect(
            self.scroll_bar_moved
        )
        self.progressBar.valueChanged.connect(self.update_progress_bar_percentage)

        self.signals.to_do_available.connect(self.to_do_available)

    @pyqtSlot()
    def to_do_available(self):
        pass

    @pyqtSlot(bool)
    def set_window_title(self, running: bool) -> None:
        if running:
            self.setWindowTitle("Backblaze Status")
        else:
            self.setWindowTitle("Backblaze Status  *** Backups not running ***")

    @pyqtSlot()
    def show_chunk_dialog(self):
        print("Show chunk button clicked")
        self.chunk_show_dialog_button.activateWindow()
        self.chunk_show_dialog_button.raise_()

    def pop_up_todo(self, event):
        if self.to_do_dialog is None:
            self.to_do_dialog = ToDoDialog(self, ToDoDialogModel(self))
            self.to_do_dialog.exec()
        else:
            self.to_do_dialog.update_display_cache()
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

        if self.result_data is not None:
            self.data_model_table.scrollTo(
                self.result_data.index(len(self.to_do.completed_files) - 1, 0),
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
        """
        A timer is called once a second to update the clock box
        """
        self.clock_display.setText(datetime.now().strftime("%-I:%M:%S %p"))

    @pyqtSlot(str)
    def update_stats_box(self, text: str):
        """
        Called by the update_stats_box_worker to update the stats box on the GUI
        """
        self.stats_info.setText(text)
        self.show_to_do_button.setDisabled(False)

    @pyqtSlot(dict)
    def update_progress_box(self, values: dict):
        """
        Called by the update_progress_box_worker to update the GUI.
        The progress box contains the following objects:
        - A progress bar
        - The elapsed time
        - The progress - X/Y GB (A/B files [total file percentage])
        - The time remaining till completion
        - The estimated time of completion
        - The rate of backup
        """
        if values.get("completed_size") is None:
            return
        max_value = 2147483647
        if values["completed_size"] > max_value or values["total_size"] > max_value:
            values["completed_size"] = int(values["completed_size"] / 1024)
            values["total_size"] = int(values["total_size"] / 1024)

        self.progressBar.setValue(values["completed_size"])
        self.progressBar.setMaximum(values["total_size"])
        self.elapsed_time.setText(values["elapsed_time"])
        self.progress.setText(values["progress_string"])
        self.time_remaining.setText(values["remaining"])
        self.completion_time.setText(values["completion_time"])
        self.rate.setText(values["rate"])

    @pyqtSlot(int)
    def update_progress_bar_percentage(self, value: int):
        """
        Called when the value of the progress bar is updated, to set the format of
        the progress bar
        """
        if self.progressBar.maximum() == 0:
            return
        percentage = (value - self.progressBar.minimum()) / (
            self.progressBar.maximum() - self.progressBar.minimum()
        )
        self.progressBar.setFormat(f"{percentage:.2%}")

    @pyqtSlot()
    def set_preparing(self):
        """
        Called when a new large file is being prepared
        """

        # Grab the BackupFile object for the current file. If there isn't one,
        # that is an issue, and probably shouldn't happen, since it was created before.

        preparing_file: BackupFile = self.to_do.current_file
        # ic(f"set_preparing({str(preparing_file.file_name)})")

        if preparing_file is None:
            raise CurrentFileNotSet

        # Since preparing is the first step for a new file, set the
        # ToDoFiles.current_file to this file
        self.processing_type = QTBackupStatus.ProcessingType.PREPARING

        # Initialize the chunk_progress_bar
        self.prepare_chunk_progress_bar.setMinimum(0)
        self.prepare_chunk_progress_bar.setMaximum(preparing_file.total_chunk_count)

        # Initialize the chunk_progress table
        self.chunk_model.filename = str(preparing_file.file_name)
        self.initialize_chunk_table()

        # Show the chunk_box anx hide the file_info box
        self.chunk_box.show()
        self.reposition_table()  # Since the bottom moved
        self.file_info.hide()
        self.signals.files_updated.emit()

    @pyqtSlot(str)
    def set_transmitting(self, filename: str):
        """
        Called from the bz_lasttransmitting thread when a file starts transmitting,
        completing the prepared phase
        """

        # Grab the BackupFile object for the current file. If there isn't one,
        # that is an issue, and probably shouldn't happen, since it was created before.

        # ic(f"set_transmitting({filename})")

        if self.to_do.current_file is None:
            self.to_do.current_file = self.to_do.get_file(filename)

        transmitting_file: BackupFile = self.to_do.current_file
        if transmitting_file is None:
            return

        self.processing_type = QTBackupStatus.ProcessingType.TRANSMITTING
        self.result_data.show_new_file(transmitting_file)

        if transmitting_file.is_large_file:
            # Initialize the chunk_progress table
            self.chunk_model.filename = str(transmitting_file.file_name)
            self.initialize_chunk_table()

            # Initialize the chunk_progress_bar
            self.transmit_chunk_progress_bar.setMinimum(0)
            self.transmit_chunk_progress_bar.setMaximum(
                transmitting_file.total_chunk_count
            )

            # Initialize the chunk_progress table
            self.chunk_model.filename = str(transmitting_file.file_name)
            self.initialize_chunk_table()

            # Show the chunk_box anx hide the file_info box
            self.chunk_box.show()
            self.reposition_table()  # Since the bottom moved
            self.file_info.hide()
        else:
            # If this isn't a large file, just use the file_info box
            self.chunk_box.hide()
            self.chunk_table_dialog.hide()
            self.file_info.show()
        self.signals.files_updated.emit()

    @pyqtSlot()
    def initialize_chunk_table(self):
        """
        Set up the table that shows the chunk progress
        """

        current_file: BackupFile = self.to_do.get_file(str(self.chunk_model.filename))

        # ic(f"initialize_chunk_table current_file={self.chunk_model.filename}")

        if current_file is None or self.chunk_model.table_size == 0:
            # self.chunk_show_dialog_button.setText("Table not ready yet")
            # self.chunk_show_dialog_button.setDisabled(True)
            # self.chunk_show_dialog_button.show()
            self.chunk_model.reset_table()

            # If it doesn't exist, try again in 10 seconds
            timer = QTimer()
            timer.setSingleShot(True)
            timer.start(10000)  # 10 seconds
            timer.timeout.connect(self.initialize_chunk_table)
            return

        if self.chunk_model.use_dialog:
            # If the file is really large, I need to use a popup to show the progress
            self.chunk_dialog_table.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            self.chunk_dialog_table.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )

            self.chunk_table_dialog.setWindowTitle(str(self.chunk_model.filename))
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
        if self.to_do is None or self.to_do.current_file is None:
            return

        current_file: BackupFile = self.to_do.current_file
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
                f" {current_file.total_chunk_count:,} chunks)"
            )

        if self.processing_type == QTBackupStatus.ProcessingType.PREPARING:
            # There is progressbar for large files, so update that
            self.prepare_chunk_progress_bar.setValue(current_file.max_prepared)

            # self.chunk_progress_bar.setStyleSheet(style_sheet)
            self.chunk_filename.setText(
                f"Preparing: {str(current_file.file_name)}"
                f" ({current_file.current_chunk:>4,} /"
                f" {current_file.total_chunk_count:,} chunks)"
            )

    @pyqtSlot(str)
    def start_new_file(self, file_name: str):
        """
        Called by the BzTransmit thread when it detects a new file
        """

        # ic(f"start_new_file({file_name})")

        # Hide the chunk box if it was visible and replace it with the file_info box
        self.chunk_box.hide()
        self.file_info.show()

        self.file_info.setText(f"Preparing new file {file_name}")

        # Check if we are already processing this file
        if self.previous_file_name is None:
            self.previous_file_name = file_name
        elif self.previous_file_name != file_name:
            # If I have moved to a new file from the previous file, then I need to
            # close out the processing on the previous file
            previous_file: BackupFile = self.to_do.get_file(self.previous_file_name)
            if previous_file is not None:
                # Mark it complete on the ToDoList
                self.to_do.mark_completed(self.previous_file_name)
                self.result_data.layoutChanged.emit()
                self.previous_file_name = file_name

        new_file: BackupFile = self.to_do.get_file(file_name)
        if new_file is None:
            return

        new_file.start_time = datetime.now()

        # Set this file to the current file I am working on
        self.to_do.current_file = new_file

        # Reset the chunk progress bars
        self.transmit_chunk_progress_bar.setValue(0)
        self.transmit_chunk_progress_bar.setMaximum(100)
        self.prepare_chunk_progress_bar.setValue(0)
        self.prepare_chunk_progress_bar.setMaximum(100)

        # If the new file is a large file, set it to prepare mode
        if new_file.is_large_file:
            self.set_preparing()

        self.result_data.show_new_file(new_file)
