import math
import os
import sys
import time
from datetime import datetime

from icecream import ic

ic.disable()

from PyQt6.QtCore import (
    QObject,
    pyqtSignal,
    pyqtSlot,
    Qt,
    QCoreApplication,
    QThread,
    QThreadPool,
    QTimer,
)
from PyQt6.QtGui import QColor, QShortcut, QIcon, QPixmap, QAction
from PyQt6.QtWidgets import (
    QTableWidgetItem,
    QMainWindow,
    QAbstractItemView,
    QAbstractSlider,
    QHeaderView,
    QDialog, QSizePolicy,
)

from .backup_file import BackupFile
from .backup_results import BackupResults
from .bz_data_table_model import BzDataTableModel
from .main_backup_status import BackupStatus
from .progress import ProgressBox
from .qt_mainwindow import Ui_MainWindow
from .utils import MultiLogger, get_lock, return_lock
from .workers import ProgressBoxWorker, BackupStatusWorker, StatsBoxWorker
from icecream import ic, install
from .to_to_dialog import ToDoDialog

ic.configureOutput(
    includeContext=True, prefix=datetime.now().strftime("%Y-%m-%d %H:%M:S")
)
install()


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
        update_log_line = pyqtSignal(str)
        update_chunk_preparing = pyqtSignal(str)
        update_prepare = pyqtSignal(str, int)
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

        self.large_file_name = None
        self.prepare_file_name = None
        self.display_moved = False
        self.current_last_row: int = 0
        self.in_table: set = set()
        self.chunk_table = self.chunk_box_table

        # **** Set up threads ****

        self.thread_pool = QThreadPool()

        # Clock thread
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.update_clock_display)
        self.clock_timer.start(1000)

        # BackupStatus thread
        self.backup_status: BackupStatus = BackupStatus(self)

        self.backup_status_thread = QThread()
        self.backup_status_worker: BackupStatusWorker = BackupStatusWorker(
            self.backup_status
        )
        self.backup_status_worker.moveToThread(self.backup_status_thread)
        self.backup_status_thread.started.connect(self.backup_status_worker.run)
        self.backup_status_thread.start()

        # Update Stats Box Thread
        self.update_stats_box_thread = QThread()
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

        # Set up key shortcuts

        self.b_key = QShortcut(Qt.Key.Key_B, self.data_model_table)
        self.b_key.activated.connect(self.b_pressed)

        self.t_key = QShortcut(Qt.Key.Key_T, self.data_model_table)
        self.t_key.activated.connect(self.t_pressed)

        self.c_key = QShortcut(Qt.Key.Key_C, self.data_model_table)
        self.c_key.activated.connect(self.c_pressed)

        # Set up Options Menu

        self.show_to_do_button = QAction("&Show To Do List", self)
        self.show_to_do_button.setStatusTip("Show pop up to do list")
        self.show_to_do_button.triggered.connect(self.pop_up_todo)
        self.option_menu.addAction(self.show_to_do_button)

    def define_signals(self):
        # self.signals.update_row.connect(self.update_row)
        # self.signals.insert_row.connect(self.insert_row)
        self.signals.update_log_line.connect(self.update_log_line)
        self.signals.update_chunk_preparing.connect(self.update_chunk_preparing)
        self.signals.update_prepare.connect(self.update_prepare)
        self.signals.start_new_file.connect(self.start_new_file)
        self.data_model_table.verticalScrollBar().actionTriggered.connect(
            self.scroll_bar_moved
        )
        self.progressBar.valueChanged.connect(self.update_progress_bar_percentage)

    def pop_up_todo(self, event):
        print(f"Clicked {event}")
        to_do_dialog = ToDoDialog(self.backup_status.to_do)
        to_do_dialog.exec()

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

    """
    For some reason, keyPressEvent didn't work, so I used shortcuts instead
    
    def keyPressEvent(self, event):
        print(f"Key {event} pressed")
        if event.key() == Qt.Key.Key_B:
            print("B key pressed")
            self.data_model_table.clearSelection()
            self.display_moved = False
            self.data_model_table.scrollToBottom()
        elif event.key() == Qt.Key.Key_T:
            print("T key pressed")
            self.data_model_table.selectRow(0)
            self.data_model_table.scrollToItem(self.data_model_table.item(0, 0))
        elif event.key() == Qt.Key.Key_C:
            selected_items = self.data_model_table.selectedItems()
            if len(selected_items) > 0:
                self.data_model_table.scrollToItem(
                    selected_items[0],
                    hint=QAbstractItemView.ScrollHint.PositionAtCenter,
                )
    """

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

    @pyqtSlot(str)
    def update_chunk_preparing(self, line: str):
        self.file_info.setText(line)

    def update_chunk_table(self, chunk, current_file):
        rows_columns = math.ceil(math.sqrt(current_file.chunks_total))
        chunk_row = math.floor(chunk / rows_columns)
        chunk_column = chunk % rows_columns
        chunk_item = QTableWidgetItem("")
        # self.chunk_table.item(chunk_row, chunk_column)
        if chunk in current_file.chunks_deduped:
            chunk_item.setBackground(QColor("sandybrown"))
        elif chunk in current_file.chunks_transmitted:
            chunk_item.setBackground(QColor("#84fab0"))
        elif chunk in current_file.chunks_prepared:
            chunk_item.setBackground(QColor("#6a11cb"))
        self.chunk_table.setItem(chunk_row, chunk_column, chunk_item)

    @pyqtSlot(str, int)
    def update_prepare(self, filename: str, chunk_num: int):
        ic("In update_prepare")
        current_file: BackupFile = self.backup_status.to_do.file_dict.get(filename)
        if current_file is None:
            return

        self.prepare_chunk_progress_bar.show()
        self.transmit_chunk_progress_bar.hide()
        current_chunk = current_file.chunk_current

        # Figure out how big the table needs to be. Getting the square room gives
        # the number of rows and columns needed to make a square
        rows_columns = math.ceil(math.sqrt(current_file.chunks_total))

        # If there are less than QTBackupStatus.SmallChunkCount chunks, it is too small and
        # goes too fast to bother displaying the chunk table
        if current_file.chunks_total < QTBackupStatus.SmallChunkCount:
            return

        # If there are between QTBackupStatus.SmallChunkCount and QTBackupStatus.LargeChunkCount
        # chunks, then show the chunk table inline
        if current_file.chunks_total < QTBackupStatus.LargeChunkCount:
            self.chunk_table = self.chunk_box_table
            use_dialog = False

        # If there are more than QTBackupStatus.LargeChunkCount chunks, then pop up a dialog for it
        else:
            self.chunk_table = self.chunk_dialog_table
            use_dialog = True

        if self.prepare_file_name != filename:
            self.prepare_file_name = filename

            # For a new file, clear the chunk table, set the column and row count
            # appropriately, and set the size of the table

            self.chunk_table.clear()
            self.chunk_table.setColumnCount(rows_columns)
            self.chunk_table.setRowCount(rows_columns)
            max_size = (rows_columns * QTBackupStatus.PixelSize) + 5
            self.chunk_table.setMaximumSize(max_size, max_size)
            for row in range(rows_columns):
                for column in range(rows_columns):
                    item = QTableWidgetItem("")
                    item.setBackground(QColor("linen"))
                    self.chunk_table.setItem(row, column, item)
                    self.chunk_table.setColumnWidth(column, 5)
                    self.chunk_table.setRowHeight(row, 5)
            self.chunk_table.resizeRowsToContents()
            self.chunk_table.resizeColumnsToContents()
            if use_dialog:
                dialog_width = self.chunk_table.horizontalHeader().length() + 24
                dialog_height = self.chunk_table.verticalHeader().length() + 24
                # self.chunk_table_dialog.setFixedSize(dialog_width, dialog_height)
            else:
                self.chunk_table.setFixedWidth(self.chunk_table.horizontalHeader().length())
                self.chunk_table.setFixedHeight(self.chunk_table.verticalHeader().length())
            self.redraw_chunk_table(current_file)

            self.transmit_chunk_progress_bar.hide()
            self.prepare_chunk_progress_bar.show()
            self.prepare_chunk_progress_bar.setMinimum(0)
            self.prepare_chunk_progress_bar.setMaximum(current_file.chunks_total)
            self.chunk_box.show()
            self.reposition_table()  # Since the bottom moved
            if use_dialog:
                self.chunk_table_dialog.setWindowTitle(str(filename))
                self.chunk_table_dialog.show()
            else:
                self.chunk_table.show()
            self.file_info.hide()

        # Draw the state if the current duplicate block
        ic(self.update_chunk_table(chunk_num, current_file))

        # At intervals, we should redraw all the dots, because sometimes they get out of sync
        if chunk_num % 100 == 0:
            self.redraw_chunk_table(current_file)

        # There is progressbar for large files, so update that
        self.prepare_chunk_progress_bar.setValue(len(current_file.chunks_prepared))

        self.chunk_filename.setText(
            f"Preparing: {filename} ({chunk_num:,} / {current_file.chunks_total:,} chunks)"
        )

    def redraw_chunk_table(self, current_file: BackupFile) -> None:
        """
        Redraw the chunk table with new data
        """

        lock_start = get_lock(
            current_file.lock,
            f"BackupFile ({current_file.file_name})",
            "qt_backup_status:370",
        )
        prepared = current_file.chunks_prepared.copy()
        deduped = current_file.chunks_deduped.copy()
        transmitted = current_file.chunks_transmitted.copy()
        return_lock(
            current_file.lock,
            f"BackupFile ({current_file.file_name})",
            "qt_backup_status:294",
            lock_start,
        )

        self.chunk_table.clearContents()
        for set_chunk in prepared:
            self.update_chunk_table(set_chunk, current_file)
        for set_chunk in deduped:
            self.update_chunk_table(set_chunk, current_file)
        for set_chunk in transmitted:
            self.update_chunk_table(set_chunk, current_file)

    @pyqtSlot(str)
    def update_log_line(self, filename: str):
        current_file: BackupFile = self.backup_status.to_do.file_dict[filename]
        self.backup_status.to_do.current_file = current_file
        default_color = QColor("white")

        if current_file.dedup_current:
            label_color = QColor("orange")
        else:
            label_color = default_color
        label_string = str(current_file.file_name)

        self.prepare_chunk_progress_bar.hide()
        self.transmit_chunk_progress_bar.show()
        self.file_info.setText(f"Processed {label_string}")

        use_dialog = True
        if current_file.large_file:
            current_chunk = current_file.chunk_current
            # Figure out how big the table needs to be. Getting the square room gives
            # the number of rows and columns needed to make a square
            rows_columns = math.ceil(math.sqrt(current_file.chunks_total))

            # If there are less than QTBackupStatus.SmallChunkCount chunks, it is too small and
            # goes too fast to bother displaying the chunk table
            if current_file.chunks_total < QTBackupStatus.SmallChunkCount:
                do_chunk_table = False

            # If there are between QTBackupStatus.SmallChunkCount and QTBackupStatus.LargeChunkCount
            # chunks, then show the chunk table inline
            elif current_file.chunks_total < QTBackupStatus.LargeChunkCount:
                self.chunk_table = self.chunk_box_table
                use_dialog = False
                self.chunk_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                self.chunk_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                do_chunk_table = True

            # If there are more than QTBackupStatus.LargeChunkCount chunks, then pop up a dialog for it
            else:
                self.chunk_table = self.chunk_dialog_table
                do_chunk_table = True
                use_dialog = True
                self.chunk_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                self.chunk_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

            if current_file.chunks_total > 0:
                # If this a new file that is being processed, then mark the previous file completed
                # and add the rows
                if self.large_file_name != filename:
                    self.backup_status.to_do.completed(self.large_file_name)
                    self.large_file_name = filename

                    row_result = BackupResults(
                        timestamp=current_file.timestamp,
                        file_name=label_string,
                        file_size=current_file.file_size,
                        start_time=datetime.now(),
                        rate=current_file.rate,
                        row_color=QColor(label_color),
                    )
                    self.result_data.add_row(row_result, chunk=True)
                    self.reposition_table()

                    # For a new file, clear the chunk table, set the column and row count
                    # appropriately, and set the size of the table

                    if do_chunk_table:
                        self.chunk_table.clear()
                        self.chunk_table.setColumnCount(rows_columns)
                        self.chunk_table.setRowCount(rows_columns)
                        max_size = (rows_columns * QTBackupStatus.PixelSize) + 5
                        self.chunk_table.setMaximumSize(max_size, max_size)
                        for row in range(rows_columns):
                            for column in range(rows_columns):
                                item = QTableWidgetItem("")
                                item.setBackground(QColor("linen"))
                                self.chunk_table.setItem(row, column, item)
                                self.chunk_table.setColumnWidth(column, 5)
                                self.chunk_table.setRowHeight(row, 5)
                        if use_dialog:
                            dialog_width = (
                                self.chunk_table.horizontalHeader().length() + 24
                            )
                            dialog_height = (
                                self.chunk_table.verticalHeader().length() + 24
                            )
                            # self.chunk_table_dialog.setFixedSize(
                            #     dialog_width, dialog_height
                            # )
                        else:
                            self.chunk_table.setFixedWidth(
                                self.chunk_table.horizontalHeader().length()
                            )
                            self.chunk_table.setFixedHeight(
                                self.chunk_table.verticalHeader().length()
                            )
                        self.chunk_table.resizeRowsToContents()
                        self.chunk_table.resizeColumnsToContents()
                        self.redraw_chunk_table(current_file)

                    self.prepare_chunk_progress_bar.hide()
                    self.transmit_chunk_progress_bar.show()
                    self.transmit_chunk_progress_bar.setMinimum(0)
                    self.transmit_chunk_progress_bar.setMaximum(
                        current_file.chunks_total
                    )
                    self.chunk_box.show()
                    self.reposition_table()  # Since the bottom moved
                    if do_chunk_table:
                        if use_dialog:
                            self.chunk_table_dialog.setWindowTitle(str(filename))
                            self.chunk_table_dialog.show()
                        else:
                            self.chunk_table.show()
                    self.file_info.hide()

                # Draw the state if the current duplicate block
                i = current_chunk
                if do_chunk_table:
                    self.update_chunk_table(i, current_file)

                    # At intervals, we should redraw all the dots, because sometimes they get out of sync
                    if i % 100 == 0:
                        self.redraw_chunk_table(current_file)

                # There is progressbar for large files, so update that
                self.transmit_chunk_progress_bar.setValue(
                    len(current_file.chunks_transmitted)
                    + len(current_file.chunks_deduped)
                )

                # self.chunk_progress_bar.setStyleSheet(style_sheet)
                self.chunk_filename.setText(
                    f"Transmitting: {filename} ({i:>4,} / {current_file.chunks_total:,} chunks)"
                )

            else:
                self.chunk_box.hide()
                self.chunk_table_dialog.hide()
                self.file_info.show()
                if current_file.chunks_total == 0:
                    percentage = 0
                else:
                    percentage = (
                        len(current_file.chunks_transmitted) / current_file.chunks_total
                    )

                chunk_label_string = (
                    f"Transmitting: {label_string} - Chunk {current_chunk:,d}"
                    f" of {current_file.chunks_total:,d} ({percentage:2.1%})"
                )
                self.file_info.setText(chunk_label_string)
        else:
            # If it's not a large file, hide the chunk box and treat it normally

            self.chunk_box.hide()
            self.chunk_table_dialog.hide()
            self.file_info.show()
            if self.large_file_name is not None:
                self.backup_status.to_do.completed(self.large_file_name)
                self.large_file_name = None

            self.file_info.setText(f"Processing file: '{filename}")
            self.backup_status.to_do.completed(filename)

            row_result = BackupResults(
                timestamp=current_file.timestamp,
                file_name=label_string,
                file_size=current_file.file_size,
                rate=current_file.rate,
                row_color=QColor(label_color),
            )
            self.result_data.add_row(row_result)
            self.data_model_table.resizeRowsToContents()

    @pyqtSlot(str)
    def start_new_file(self, file_name: str):
        self.chunk_box.hide()
        self.file_info.show()
        self.file_info.setText(f"Preparing new file {file_name}")
        current_file: BackupFile = self.backup_status.to_do.file_dict[file_name]
        if current_file is None:
            file_size = 0
        else:
            file_size = current_file.file_size
        self.result_data.show_new_file(file_name, file_size)
