from __future__ import annotations

import os
import sys
import threading
from datetime import datetime, timedelta
from typing import Optional

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
    QTableWidgetItem,
    QLabel,
)
from icecream import ic, install

from .bz_data_table_model import BzDataTableModel
from .chunk_model import ChunkModel
from .constants import ToDoColumns, States
from .current_state import CurrentState
from .qt_mainwindow import UiMainWindow
from .signals import Signals
from .to_do_dialog import ToDoDialog
from .to_do_dialog_model import ToDoDialogModel
from .to_do_files import ToDoFiles
from .utils import MultiLogger, file_size_string
from .configuration import Configuration


# Set up icecream debugging
def get_ic_prefix():
    thread_name = threading.current_thread().name
    return f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} <{thread_name}>'


# ic.configureOutput(includeContext=True, prefix=get_ic_prefix)
install()
ic.disable()


class QTBackupStatus(QMainWindow, UiMainWindow):
    # How large is each chunk in the chunk table, by pixel
    PixelSize = 10

    # A file with less than LargeChunkCount is medium-sized. A LargeChunkCount or
    # larger and I create a separate window for it
    SmallChunkCount = 50
    LargeChunkCount = 400

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

        # Set up the system icon, for the task bar

        icon_path = os.path.join(
            os.path.dirname(sys.modules[__name__].__file__), "backblaze_status.png"
        )
        QCoreApplication.instance().setWindowIcon(QIcon(QPixmap(icon_path)))

        # Set the name of the application
        if sys.platform.startswith("darwin"):
            # Set app name, if PyObjC is installed
            # Python 2 has PyObjC preinstalled
            # Python 3: pip3 install pyobjc-framework-Cocoa
            try:
                from Foundation import NSBundle

                bundle = NSBundle.mainBundle()
                if bundle:
                    app_name = vars(sys.modules[__name__])["__package__"]
                    # os.path.splitext(os.path.basename(sys.argv[0]))[0]
                    app_info = (
                        bundle.localizedInfoDictionary() or bundle.infoDictionary()
                    )
                    if app_info:
                        app_info["CFBundleName"] = app_name
                    self._multi_log.log(f"Set application name to '{app_name}'")
            except ImportError:
                pass

        # Set up the GUI interface

        self.setup_ui(self)
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

        # # Setup BzTransmit Thread
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
        #
        # Clock thread
        self.clock_timer = QTimer()
        self.clock_timer.setObjectName("Clock Update")
        self.clock_timer.timeout.connect(self.update_clock_display)
        self.clock_timer.start(1000)

        # Progress Timer
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self.update_progress_box)
        self.progress_timer.start(1000)

        #
        # # Update Stats Box Thread
        # from .worker_stats_box import StatsBoxWorker
        #
        # self.update_stats_box_thread = QThread()
        # self.update_stats_box_thread.setObjectName("UpdateStatsBox")
        # self.update_stats_box_worker: StatsBoxWorker = StatsBoxWorker(self)
        # self.update_stats_box_worker.moveToThread(self.update_stats_box_thread)
        # self.update_stats_box_worker.update_stats_box.connect(self.update_stats_box)
        # self.update_stats_box_thread.started.connect(self.update_stats_box_worker.run)
        # self.update_stats_box_thread.start()

        # Update Chunk Box

        self.chunk_model = ChunkModel(self)
        self.chunk_box_table.setModel(self.chunk_model)
        self.chunk_table_dialog_box.dialog_chunk_table.setModel(self.chunk_model)

        # Update the windows title
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

        self.data_model_table.verticalScrollBar().valueChanged.connect(self.scrolled)
        self.data_model_table.verticalScrollBar().actionTriggered.connect(
            self.scroll_bar_moved
        )

    def define_signals(self):
        self.signals.backup_running.connect(self.set_window_title)
        self.progressBar.valueChanged.connect(self.update_progress_bar_percentage)
        self.signals.update_chunk_progress.connect(self.update_chunk_progress)
        self.signals.to_do_available.connect(self.to_do_available)
        self.signals.update_stats_box.connect(self.update_stats_box)

        self.signals.start_new_file.connect(self.start_new_file)

        self.chunk_show_dialog_button.clicked.connect(self.show_chunk_dialog)

        self.data_model_table.verticalScrollBar().actionTriggered.connect(
            self.scroll_bar_moved
        )

    @pyqtSlot(bool)
    def set_window_title(self, running: bool) -> None:
        if running:
            self.setWindowTitle("Backblaze Status (Pandas)")
        else:
            self.setWindowTitle(
                "Backblaze Status (Pandas)  *** Backups not running ***"
            )

    @pyqtSlot()
    def to_do_available(self):
        self.show_to_do_button.setDisabled(False)

    @pyqtSlot()
    def show_chunk_dialog(self):
        print("Show chunk button clicked")
        self.chunk_show_dialog_button.show()
        self.chunk_show_dialog_button.activateWindow()
        self.chunk_show_dialog_button.raise_()

    def pop_up_todo(self, _):
        if self.to_do_dialog is None:
            self.to_do_dialog = ToDoDialog(self, ToDoDialogModel(self))
            self.to_do_dialog.exec()
        else:
            # self.to_do_dialog.update_display_cache()
            self.to_do_dialog.setVisible(True)

    @pyqtSlot()
    def b_pressed(self):
        """
        Go to the bottom of the table, and clear the selection
        """

        self.data_model_table.clearSelection()
        self.display_moved = False
        self.result_data.go_to_bottom()
        self.data_model_table.resizeRowsToContents()

    @pyqtSlot()
    def t_pressed(self):
        """
        Go to the top of the table
        """
        self.data_model_table.selectRow(0)
        self.data_model_table.scrollTo(self.result_data.index(0, 0))
        self.data_model_table.resizeRowsToContents()

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
            self.signals.go_to_current_row.emit()
        self.data_model_table.resizeRowsToContents()

    def reposition_table(self):
        """
        Reposition the table to the bottom, if there isn't already a row selected
        """
        self.data_model_table.resizeRowsToContents()
        selected_items = self.data_model_table.selectedIndexes()
        if len(selected_items) > 0:
            return  # If we are not at the bottom, don't scroll there

        self.signals.go_to_current_row.emit()

    def scrolled(self, _):
        # print(f"scrolled {value}")
        actual_value = self.data_model_table.verticalScrollBar().value()
        if actual_value == self.data_model_table.verticalScrollBar().minimum():
            if self.result_data.start_index > 0:
                self.result_data.fetchLess()

        pass

    def scroll_bar_moved(self, event):
        # TODO: Do I need this? If I delete it, remember to delete the signal as well
        if event == QAbstractSlider.SliderAction.SliderToMaximum:
            self.data_model_table.clearSelection()
        elif event == QAbstractSlider.SliderAction.SliderToMinimum:
            if self.result_data.start_index > 0:
                self.result_data.fetchLess()

    def toggle_selection(self, e):
        if e.row() == self.selected_row:
            self.data_model_table.clearSelection()
            self.selected_row = -1
        else:
            self.selected_row = e.row()

    def update_clock_display(self):
        """
        A timer is called once a second to update the clock box
        """
        self.clock_display.setText(datetime.now().strftime("%-I:%M:%S %p"))

    @pyqtSlot()
    def update_stats_box(self):
        """
        Called by the update_stats_box_worker to update the stats box on the GUI
        """
        total_files_string = (
            f'<td style="text-align: right; padding-right: 8;">'
            f"Total Files:</td>"
            f'<td style="text-align: right; padding-right: 8;"><b>'
            f"{self.total_files:12,} / "
            f"{file_size_string(self.total_bytes):10}"
            f"</b></td>"
        )

        total_chunks_string = (
            f"<td style='text-align: right; padding-right: 8;'>"
            f"Total Chunks:</td>"
            f"<td style='text-align: right; padding-right: 8;'><b>"
            f"{self.total_chunks:12,} / "
            f"{file_size_string(self.total_chunk_bytes):10}"
            f"</b></td>"
        )

        completed_files_string = (
            f"<td style='text-align: right; padding-right: 8;'>"
            f"Completed Files:</td>"
            f"<td style='text-align: right; padding-right: 8;'><b>"
            f"{self.completed_files:12,} / "
            f"{file_size_string(self.completed_bytes):10}"
            f"</b></td>"
        )

        completed_chunks_string = (
            f"<td style='text-align: right; padding-right: 8;'>"
            f"Completed Chunks:</td>"
            f"<td style='text-align: right; padding-right: 8;'><b>"
            f"{self.completed_chunks:12,} / "
            f"{file_size_string(self.completed_chunk_bytes):10}"
            f"</b></td>"
        )

        skipped_files_string = (
            f"<td style='text-align: right; padding-right: 8;'>"
            f"Skipped Files:</td>"
            f"<td style='text-align: right; padding-right: 8;'><b>"
            f"{self.skipped_files:12,} / "
            f"{file_size_string(self.skipped_bytes):10}"
            f"</b></td>"
        )

        skipped_chunks_string = (
            f"<td style='text-align: right; padding-right: 8;'>"
            f"Skipped Chunks:</td>"
            f"<td style='text-align: right; padding-right: 8;'><b>"
            f"{self.skipped_chunks:12,} / "
            f"{file_size_string(self.skipped_chunk_bytes):10}"
            f"</b></td>"
        )

        remaining_files_string = (
            f"<td style='text-align: right; padding-right: 8;'>"
            f"Remaining Files:</td>"
            f"<td style='text-align: right; padding-right: 8;'><b>"
            f"{self.remaining_files:12,} / "
            f"{file_size_string(self.remaining_bytes):10}"
            f"</b></td>"
        )

        remaining_chunks_string = (
            f"<td style='text-align: right; padding-right: 8;'>"
            f"Remaining Chunks:</td>"
            f"<td style='text-align: right; padding-right: 8;'><b>"
            f"{self.remaining_chunks:12,} / "
            f"{file_size_string(self.remaining_chunk_bytes):10}"
            f"</b></td>"
        )

        transmitted_files_string = (
            f"<td style='text-align: right; padding-right: 8;'>"
            f"Transmitted Files:</td>"
            f"<td style='text-align: right; padding-right: 8;'><b>"
            f"{self.transmitted_files:12,} / "
            f"{file_size_string(self.transmitted_bytes):10}"
            f"</b></td>"
        )

        transmitted_chunks_string = (
            f"<td style='text-align: right; padding-right: 8;'>"
            f"Transmitted Chunks:</td>"
            f"<td style='text-align: right; padding-right: 8;'><b>"
            f"{int(self.transmitted_chunks):12,} / "
            f"{file_size_string(self.transmitted_chunk_bytes):10}"
            f"</b></td>"
        )

        duplicate_files_string = (
            f"<td style='text-align: right; padding-right: 8;'>"
            f"Duplicate Files:</td>"
            f"<td style='text-align: right; padding-right: 8;'><b>"
            f"{self.duplicate_files:12,} / "
            f"{file_size_string(self.duplicate_bytes):10}"
            f"</b></td>"
        )

        duplicate_chunks_string = (
            f"<td style='text-align: right; padding-right: 8;'>"
            f"Duplicate Chunks:</td>"
            f"<td style='text-align: right; padding-right: 8;'><b>"
            f"{int(self.duplicate_chunks):12,} / "
            f"{file_size_string(self.duplicate_chunk_bytes):10}"
            f"</b></td>"
        )

        if self.duplicate_files + self.transmitted_files == 0:
            percentage_file_duplicate = 0
        else:
            percentage_file_duplicate = self.duplicate_files / (
                self.duplicate_files + self.transmitted_files
            )
            if percentage_file_duplicate > 1:
                percentage_file_duplicate = 1

        if self.duplicate_bytes + self.transmitted_bytes == 0:
            percentage_size_duplicate = 0
        else:
            percentage_size_duplicate = self.duplicate_bytes / (
                self.duplicate_bytes + self.transmitted_bytes
            )
            if percentage_size_duplicate > 1:
                percentage_size_duplicate = 1

        if self.duplicate_chunks + self.transmitted_chunks == 0:
            percentage_chunk_duplicate = 0
        else:
            percentage_chunk_duplicate = self.duplicate_chunks / (
                self.duplicate_chunks + self.transmitted_chunks
            )
            if percentage_chunk_duplicate > 1:
                percentage_chunk_duplicate = 1

        if self.duplicate_chunk_bytes + self.transmitted_chunk_bytes == 0:
            percentage_chunk_size_duplicate = 0
        else:
            percentage_chunk_size_duplicate = self.duplicate_chunk_bytes / (
                self.duplicate_chunk_bytes + self.transmitted_chunk_bytes
            )
            if percentage_chunk_size_duplicate > 1:
                percentage_chunk_size_duplicate = 1

        percentage_duplicate_files_string = (
            f"<td style='text-align: right; padding-right: 8;'>"
            f"Percentage Duplicate Files:</td>"
            f"<td style='text-align: right; padding-right: 8;'><b>"
            f"{percentage_file_duplicate:.2%}"
            f"</b></td>"
        )

        percentage_duplicate_chunks_string = (
            f"<td style='text-align: right; padding-right: 8;'>"
            f"Percentage Duplicate Chunks:</td>"
            f"<td style='text-align: right; padding-right: 8;'><b>"
            f"{percentage_chunk_duplicate:.2%}"
            f"</b></td>"
        )

        CurrentState.StatsString = (
            f"<center><table>"
            f"<tr>"
            f"{total_files_string}"
            f"{completed_files_string}"
            f"{skipped_files_string}"
            f"{transmitted_files_string}"
            f"{duplicate_files_string}"
            f"{percentage_duplicate_files_string}"
            f"{remaining_files_string}"
            f"</tr><tr>"
            f"{total_chunks_string}"
            f"{completed_chunks_string}"
            f"{skipped_chunks_string}"
            f"{transmitted_chunks_string}"
            f"{duplicate_chunks_string}     "
            f"{percentage_duplicate_chunks_string}"
            f"{remaining_chunks_string}"
            f"</tr></table></center>"
        )
        self.stats_info.setText(CurrentState.StatsString)

        # self.show_to_do_button.setDisabled(False)

    @pyqtSlot()
    def update_progress_box(self):
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
        if self.completed_bytes == 0:
            return

        completed_bytes = self.completed_bytes
        total_bytes = self.total_bytes

        # The progress bar is an int, so if the value is larger than what an int can
        # hold, then I just keep dividing numerator and denominator until they both fit
        while (
            completed_bytes >= CurrentState.MaxProgressValue
            or total_bytes >= CurrentState.MaxProgressValue
        ):
            completed_bytes = completed_bytes / 1024
            total_bytes = total_bytes / 1024

        self.progressBar.setValue(int(completed_bytes))
        self.progressBar.setMaximum(int(total_bytes))
        self.elapsed_time.setText(
            str(datetime.now() - CurrentState.StartTime).split(".")[0]
        )
        time_remaining = str(timedelta(seconds=CurrentState.TimeRemaining)).split(".")[
            0
        ]
        self.time_remaining.setText(
            f'Time Remaining: <span style="color: cyan">' f"{time_remaining} </span>"
        )

        if CurrentState.EstimatedCompletionTime is None:
            completion_time = "Calculating ..."
        else:
            completion_time = CurrentState.EstimatedCompletionTime.strftime(
                "%a %m/%d %-I:%M %p"
            )
        self.completion_time.setText(
            f"Estimated Completion Time: "
            f'<span style="color: cyan"> {completion_time}'
            f"</span>"
        )
        self.rate.setText(
            f'Rate: <span style="color: cyan">'
            f"{file_size_string(CurrentState.Rate)} / sec"
            f"</span>"
        )

        completed_bytes_string = file_size_string(self.completed_bytes)
        completed_file_string = self.completed_files
        completed_chunks_string = self.completed_chunks
        progress_string = (
            f'<span style="color: yellow">{completed_bytes_string} '
            f"</span> /"
            f' <span style="color: yellow">{file_size_string(self.total_bytes)} '
            f"</span> "
            f' (Files: <span style="color: yellow">{completed_file_string:,} </span> /'
            f' <span style="color: yellow">{self.total_files:,}</span>'
            f' [<span style="color: magenta">'
            f"{CurrentState.CompletedFilesPercentage:.1%}</span>],"
            f' Chunks: <span style="color: yellow">'
            f" {completed_chunks_string:,}</span> /"
            f' <span style="color: yellow">{self.total_chunks:,} </span>'
            f' [<span style="color: magenta">'
            f"{CurrentState.CompletedChunksPercentage:.1%}</span>])"
        )
        self.progress.setText(progress_string)

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

    def update_chunk_progress(self):
        if self.to_do is None or CurrentState.CurrentFile is None:
            return

        total_chunks = CurrentState.ToDoList[CurrentState.CurrentFile][
            ToDoColumns.ChunkCount
        ]
        if CurrentState.CurrentFileState == States.Transmitting:

            # There is progressbar for large files, so update that
            total_transmitted_chunks = len(
                CurrentState.ToDoList[CurrentState.CurrentFile][
                    ToDoColumns.TransmittedChunks
                ]
            )
            max_transmitted = (
                0
                if total_transmitted_chunks == 0
                else max(
                    CurrentState.ToDoList[CurrentState.CurrentFile][
                        ToDoColumns.TransmittedChunks
                    ]
                )
            )
            total_deduped_chunks = len(
                CurrentState.ToDoList[CurrentState.CurrentFile][
                    ToDoColumns.DedupedChunks
                ]
            )
            max_deduped = (
                0
                if total_deduped_chunks == 0
                else max(
                    CurrentState.ToDoList[CurrentState.CurrentFile][
                        ToDoColumns.DedupedChunks
                    ]
                )
            )
            max_chunk = max([max_deduped, max_transmitted])

            self.transmit_chunk_progress_bar.setValue(max_chunk)

            self.chunk_filename.setText(
                f"Transmitting: {CurrentState.CurrentFile}"
                f" ({total_transmitted_chunks + total_deduped_chunks:>4,} /"
                f" {total_chunks:,} chunks)"
            )

        elif CurrentState.CurrentFileState == States.Preparing:

            max_prepared = (
                0
                if len(
                    CurrentState.ToDoList[CurrentState.CurrentFile][
                        ToDoColumns.PreparedChunks
                    ]
                )
                == 0
                else max(
                    CurrentState.ToDoList[CurrentState.CurrentFile][
                        ToDoColumns.PreparedChunks
                    ]
                )
            )
            # There is progressbar for large files, so update that
            self.prepare_chunk_progress_bar.setValue(max_prepared)

            self.chunk_filename.setText(
                f"Preparing: {CurrentState.CurrentFile}"
                f" ({max_prepared:>4,} /"
                f" {total_chunks:,} chunks)"
            )

    @pyqtSlot(str)
    def start_new_file(self, file_name: str):
        """
        Called by the BzTransmit thread when it detects a new file
        """
        # ic(f"start_new_file({file_name})")

        # Hide the chunk box if it was visible and replace it with the file_info box
        if CurrentState.ToDoList[file_name][ToDoColumns.IsLargeFile]:

            self.file_info.hide()
            self.chunk_box.show()

            chunks = CurrentState.ToDoList[file_name][ToDoColumns.ChunkCount]
            # Reset the chunk progress bars
            self.transmit_chunk_progress_bar.setValue(0)
            self.transmit_chunk_progress_bar.setMaximum(chunks)
            self.prepare_chunk_progress_bar.setValue(0)
            self.prepare_chunk_progress_bar.setMaximum(chunks)

            self.chunk_model.reset_table()
            if self.chunk_model.use_dialog:
                self.use_chunk_dialog()
            else:
                self.use_chunk_box()

        else:
            self.chunk_box.hide()
            self.file_info.show()
            self.file_info.setText(f"Sending file {file_name}")

    def use_chunk_dialog(self):
        # If the file is really large, I need to use a popup to show the progress
        self.dialog_chunk_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.dialog_chunk_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.chunk_table_dialog_box.setWindowTitle(CurrentState.CurrentFile)
        self.chunk_table_dialog_box.show()
        self.dialog_chunk_table.show()
        self.chunk_box_table.hide()
        self.chunk_show_dialog_button.show()
        self.chunk_show_dialog_button.setEnabled(True)

        self.dialog_chunk_table.resizeRowsToContents()
        self.dialog_chunk_table.resizeColumnsToContents()

        self.dialog_chunk_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.dialog_chunk_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.dialog_chunk_table.setFixedWidth(
            self.chunk_box_table.horizontalHeader().length()
        )
        self.dialog_chunk_table.setFixedHeight(
            self.chunk_box_table.verticalHeader().length()
        )

    def use_chunk_box(self):
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
        self.chunk_table_dialog_box.hide()
        self.chunk_show_dialog_button.hide()
        self.chunk_box_table.show()

        self.chunk_box_table.resizeRowsToContents()
        self.chunk_box_table.resizeColumnsToContents()

    @property
    def total_files(self) -> int:
        return CurrentState.TotalFiles

    @property
    def total_bytes(self) -> float:
        return CurrentState.TotalBytes

    @property
    def total_chunks(self) -> int:
        return CurrentState.TotalChunks

    @property
    def total_chunk_bytes(self) -> float:
        return self.total_chunks * Configuration.default_chunk_size

    @property
    def completed_files(self) -> int:
        return (
            CurrentState.CompletedFiles
            + CurrentState.TotalFilesPreCompleted
            + CurrentState.SkippedFiles
        )

    @property
    def completed_bytes(self) -> float:
        return (
            CurrentState.CompletedBytes
            + CurrentState.TotalBytesPreCompleted
            + CurrentState.SkippedBytes
        )

    @property
    def completed_chunks(self) -> int:
        return (
            CurrentState.CompletedChunks
            + CurrentState.TotalChunksPreCompleted
            + CurrentState.SkippedChunks
        )

    @property
    def completed_chunk_bytes(self) -> float:
        return self.completed_chunks * Configuration.default_chunk_size

    @property
    def skipped_files(self) -> int:
        return CurrentState.SkippedFiles

    @property
    def skipped_bytes(self) -> float:
        return CurrentState.SkippedBytes

    @property
    def skipped_chunks(self) -> int:
        return CurrentState.SkippedChunks

    @property
    def skipped_chunk_bytes(self) -> float:
        return self.skipped_chunks * Configuration.default_chunk_size

    @property
    def remaining_files(self) -> int:
        return CurrentState.RemainingFiles

    @property
    def remaining_bytes(self) -> float:
        return CurrentState.RemainingBytes

    @property
    def remaining_chunks(self) -> int:
        return CurrentState.RemainingChunks

    @property
    def remaining_chunk_bytes(self) -> float:
        return self.remaining_chunks * Configuration.default_chunk_size

    @property
    def transmitted_files(self) -> int:
        return CurrentState.TransmittedFiles

    @property
    def transmitted_bytes(self) -> float:
        return CurrentState.TransmittedBytes

    @property
    def transmitted_chunks(self) -> int:
        return CurrentState.TransmittedChunks + CurrentState.CurrentTransmittedChunks

    @property
    def transmitted_chunk_bytes(self) -> float:
        return self.transmitted_chunks * Configuration.default_chunk_size

    @property
    def duplicate_files(self) -> int:
        return CurrentState.DuplicateFiles

    @property
    def duplicate_bytes(self) -> float:
        return CurrentState.DuplicateBytes

    @property
    def duplicate_chunks(self) -> int:
        return CurrentState.DuplicateChunks + CurrentState.CurrentDedupedChunks

    @property
    def duplicate_chunk_bytes(self) -> float:
        return self.duplicate_chunks * Configuration.default_chunk_size
