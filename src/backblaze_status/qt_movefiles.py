import sys
import threading
import time
from icecream import ic

import psutil
from PyQt6.QtCore import (
    Qt,
    QTimer,
    QObject,
    pyqtSignal,
    QThread,
    pyqtSlot,
)
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QMainWindow, QApplication
from xev_utils import file_size_string

from .configuration import Configuration
from .backup_status_mainwindow import Ui_MainWindow
from .utils import MultiLogger
from datetime import datetime, timedelta

gb_divisor = Configuration.gb_divisor
tb_divisor = Configuration.tb_divisor


class IntervalTimer(threading.Timer):
    def run(self):
        # ic(f"IntervalTimer starting with row {self.args}")
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


class Signals(QObject):
    interval_timer = pyqtSignal(int)
    stop_interval_timer = pyqtSignal()
    update_data_table_last_row = pyqtSignal(list, name="update_data_table_last_row")
    update_log = pyqtSignal(str)
    update_disk_color = pyqtSignal(int, "PyQt_PyObject")
    add_pre_data_row = pyqtSignal(list)
    update_cell = pyqtSignal(int, int, "PyQt_PyObject", "PyQt_PyObject")
    add_data_row = pyqtSignal(list)
    update_progress_bar = pyqtSignal()
    update_disk_table = pyqtSignal()


class ThreadWorker(QThread):
    thread_worker_finished = pyqtSignal()

    def __init__(self, qt_move, parent=None):
        super(ThreadWorker, self).__init__(parent)

        print("Init of worker thread")
        self.qt_move = qt_move

    def run(self):
        print("Starting Worker thread")
        self.qt_move.move_file_worker()
        # self.qt_move.test_emissions()
        self.thread_worker_finished.emit()
        return

        counter = 0
        while True:
            counter += 1
            print(f"Worker count is {counter}")
            time.sleep(1)
            self.interval_timer.emit(counter)
            if counter == 20:
                break


class QTMoveFiles(QMainWindow, Ui_MainWindow):
    def __init__(
        self,
        primary_disk: str,
        secondary_disks: list,
        feature_flags: list = None,
        configuration: Configuration = Configuration(),
        move_all_eligible: bool = True,
        projection: bool = False,
        *args,
        **kwargs,
    ):
        super(QTMoveFiles, self).__init__(*args, **kwargs)

        # Save all the information
        self.primary_disk = primary_disk
        self.secondary_disks = secondary_disks
        self.feature_flags = feature_flags
        self.configuration = configuration
        self.move_all_eligible = move_all_eligible
        self.projection = projection

        self.movefiles = None

        ic.configureOutput(includeContext=True)

        # Set up the GUI interface
        self.setupUi(self)
        self.show()

        # self.signal_items[""]
        # self.signal_mapper = QSignalMapper(self)

        self.interval_timer_value: int = 0
        self.interval_timer_row: int = 0
        self.interval_active_timer: IntervalTimer | None = None

        self.volume_info: dict = dict()
        self.previous_files_completed = 0
        self.current_previous_files_completed = 0

        self.moveinfo_populated = False

        # self.move_thread = threading.Thread(target=self.move_file_worker, daemon=True)
        # self.move_thread.start()

        # self.thread = QThread()
        self.worker = ThreadWorker(self)
        self.signals = Signals()

        self.move_thread = threading.Thread(target=self.worker.run, daemon=True)
        self.move_thread.start()

        # Create connections

        self.signals.update_disk_color.connect(self.update_disk_color)
        self.signals.update_cell.connect(self.update_cell)
        self.signals.add_data_row.connect(self.add_data_row)
        self.signals.add_pre_data_row.connect(self.add_pre_data_row)
        self.signals.stop_interval_timer.connect(self.stop_interval_timer)
        self.signals.update_data_table_last_row.connect(self.update_data_table_last_row)
        self.signals.update_log.connect(self.update_log)
        self.signals.update_progress_bar.connect(self.update_progress_bar)
        self.signals.update_disk_table.connect(self.update_disk_table)

        # self.worker.moveToThread(self.thread)
        # self.worker.thread_worker_finished.connect(self.handle_thread_finished)
        # self.thread.started.connect(self.handle_thread_started)
        # self.thread.finished.connect(self.handle_thread_finished)
        # self.thread.start()

        # Create a timer to update the disk table

        self.disk_usage_timer = IntervalTimer(10, self.update_disk_table_wrapper)
        self.disk_usage_timer.start()

        self.create_progress_bar()

        self.progress_bar_timer = IntervalTimer(
            1,
            self.update_progress_bar_wrapper,
        )
        self.progress_bar_timer.start()

        # progress_bar_timer = QTimer()
        # progress_bar_timer.timeout.connect(self.update_progress_bar)
        # progress_bar_timer.start(1000)

        self._multi_log = MultiLogger("securityspy", terminal=True, qt=self)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting QTMoveFiles")

    @staticmethod
    def add_row(widget: QTableWidget, row: list, reverse: bool = False) -> int:
        # # ic(f"add_row({widget}, {row})")
        if reverse:
            widget.insertRow(0)
            row_index = 0
        else:
            widget.insertRow(widget.rowCount())
            row_index = widget.rowCount() - 1

        for column in range(len(row)):
            widget.setItem(row_index, column, row[column])
        widget.resizeRowsToContents()
        widget.scrollToBottom()
        # widget.verticalScrollBar().setSliderPosition(
        #     widget.verticalScrollBar().maximum()
        # )
        return row_index

    @pyqtSlot(int, int, "PyQt_PyObject", "PyQt_PyObject")
    def update_cell(
        self, row: int, column: int, widget: QTableWidget, cell_data: QTableWidgetItem
    ):
        # ic(f"update_cell({row}, {column}, {widget}, {cell_data})")
        widget.setItem(row, column, cell_data)
        widget.resizeRowsToContents()

    @pyqtSlot(int, "PyQt_PyObject")
    def update_disk_color(self, row: int, color: QColor):
        # ic(f"update_disk_color({row}, {color}")
        item = self.diskinfo.item(row, 0)
        item.setForeground(QBrush(color))

    @pyqtSlot(list)
    def add_data_row(self, row: list):
        # ic(f"add_data_row({row})")
        self.add_row(self.file_display_table, row)

    @pyqtSlot(list)
    def add_pre_data_row(self, row: list):
        # ic(f"add_pre_data_row({row})")
        added_row = self.add_row(self.file_display_table, row)
        self.start_interval_timer(added_row)

    @pyqtSlot(list)
    def update_data_table_last_row(self, row: list):
        # ic(f"update_data_table_last_row({row})")
        # ic("Stopping interval timer")
        self.stop_interval_timer()
        last_row = self.file_display_table.rowCount() - 1
        for column, item in enumerate(row):
            self.file_display_table.setItem(last_row, column, item)

    @staticmethod
    def add_table_item(
        text: str, alignment=Qt.AlignmentFlag.AlignLeft, color=Qt.GlobalColor.white
    ) -> QTableWidgetItem:
        # ic(f"add_table_item({text}, {alignment}, {color})")
        item = QTableWidgetItem(text)
        item.setTextAlignment(alignment)
        item.setForeground(QBrush(color))
        return item

    def _create_disk_table(self):
        # ic("_create_disk_table()")
        for index, disk in enumerate(self.movefiles.disks):
            disk_name = disk.root_dir.parts[2]  # Get the name of the volume
            disk_usage = self._get_disk_usage(disk.root_dir)
            free_disk = disk_usage.free
            used_disk = disk_usage.used
            total_disk_capacity = disk_usage.total

            # Save the beginning disk size, so that we can use it for comparison

            row_to_add = [
                self.add_table_item(disk_name),
                self.add_table_item(
                    f"{file_size_string(total_disk_capacity)}",
                    alignment=Qt.AlignmentFlag.AlignRight,
                ),
                self.add_table_item(
                    f"{free_disk / gb_divisor:,.2f} GB",
                    alignment=Qt.AlignmentFlag.AlignRight,
                ),
                self.add_table_item(
                    f"{used_disk / gb_divisor:,.2f} GB",
                    alignment=Qt.AlignmentFlag.AlignRight,
                ),
                self.add_table_item(
                    ""
                ),  # This column is only populated if there is a difference in the size of the disk
                self.add_table_item("Unknown", alignment=Qt.AlignmentFlag.AlignRight),
            ]

            row_index = self.add_row(self.diskinfo, row_to_add)
            self.volume_info[disk_name] = {
                "start_available_size": free_disk,
                "row_index": row_index,
            }

    def update_disk_table_wrapper(self):
        self.signals.update_disk_table.emit()

    @pyqtSlot()
    def update_disk_table(self):
        # ic("_update_disk_table()")
        if not hasattr(self.movefiles, "disks"):
            return
        populated = self.moveinfo_populated
        for row_index, disk in enumerate(self.movefiles.disks):
            # Get the disk usage information, and also create Text() objects with that data
            disk_usage = self._get_disk_usage(disk.root_dir)
            free_disk = disk_usage.free
            free_disk_item = self.add_table_item(
                f"{free_disk / gb_divisor:,.2f} GB", Qt.AlignmentFlag.AlignRight
            )
            used_disk = disk_usage.used
            used_disk_item = self.add_table_item(
                f"{used_disk / gb_divisor:,.2f} GB", Qt.AlignmentFlag.AlignRight
            )

            disk_name = disk.root_dir.parts[2]

            # Get the free size of the disk when we started
            start_free = self.volume_info[disk_name]["start_available_size"]

            # Get the difference of the free space between now and when we started
            free_diff = free_disk - start_free

            # If there is a difference in the free space between the start and now
            if free_diff != 0:
                free_diff_item = self.add_table_item(
                    file_size_string(
                        free_diff, sign=True
                    ),  # Use file_repr so that we show it even if its KB or MB
                    Qt.AlignmentFlag.AlignRight,
                )

                # Set the color, red if we've reduced the free space, blue if the free space has increased
                if free_diff < 0:
                    free_diff_item.setForeground(QBrush(Qt.GlobalColor.magenta))
                else:
                    free_diff_item.setForeground(QBrush(Qt.GlobalColor.cyan))

                # Update the difference column
                self.diskinfo.setItem(row_index, 4, free_diff_item)

                # Update the free space and used space columns, if they've changed
                self.diskinfo.setItem(row_index, 2, free_disk_item)
                self.diskinfo.setItem(row_index, 3, used_disk_item)

            move_file_list = self.movefiles.consolidated_data_list.move_file_list
            move_file_list_len = len(move_file_list)
            if move_file_list_len > 0:
                if row_index == move_file_list_len:
                    target = move_file_list[
                        row_index - 1
                    ].free_space_on_destination_after_move
                else:
                    move_data = move_file_list[row_index]
                    if not populated:
                        moveinfo_row = [
                            self.add_table_item(
                                str(move_data.source.root_dir.parts[2])
                            ),
                            self.add_table_item(
                                str(move_data.destination.root_dir.parts[2])
                            ),
                            self.add_table_item(
                                f"{move_data.size_to_move_to_destination_gb:,.2f} GB",
                                Qt.AlignmentFlag.AlignRight,
                            ),
                            self.add_table_item(
                                f"{move_data.number_of_files:,}",
                                Qt.AlignmentFlag.AlignRight,
                            ),
                        ]
                        self.add_row(self.moveinfo, moveinfo_row, reverse=True)
                        self.moveinfo_populated = True

                    target = move_data.free_space_on_source_after_move

                target_item = self.add_table_item(
                    f"{target / gb_divisor:,.2f} GB", Qt.AlignmentFlag.AlignRight
                )
                self.diskinfo.setItem(row_index, 5, target_item)

    def _get_disk_usage(self, root_dir: str):
        try:
            return psutil.disk_usage(root_dir)
        except Exception as e:
            self._multi_log.log(
                f"Error getting disk usage for {root_dir}: {e}",
                module=self._module_name,
            )

    @pyqtSlot()
    def start_interval_timer(self, row: int = 1000):
        # ic(f"start_interval_timer({row})")
        self.interval_timer_row = row
        self.interval_timer_value = 0
        self.interval_active_timer = IntervalTimer(
            1,
            self.handle_interval_timer,
        )
        self.interval_active_timer.start()

        """
        if self.interval_active_timer and self.interval_active_timer.isActive():
            self.interval_active_timer.stop()

        # ic()
        self.interval_active_timer = QTimer()
        # ic()
        self.interval_active_timer.timeout.connect(self.handle_interval_timer)
        # ic()
        self.interval_active_timer.start(2000)  # 1 seconds
        # ic()
        """

    @pyqtSlot()
    def stop_interval_timer(self):
        # ic("stop_interval_timer()")
        if self.interval_active_timer:
            self.interval_active_timer.cancel()
            # self.interval_active_timer.stop()

    @pyqtSlot()
    def handle_interval_timer(self):
        self.interval_timer_value += 1
        # ic(
        #   f"handle_interval_timer() - interval_timer_value is {self.interval_timer_value}"
        # )
        time_difference = timedelta(seconds=self.interval_timer_value)
        item = self.add_table_item(
            str(time_difference).split(".")[0],
            alignment=Qt.AlignmentFlag.AlignRight,
            color=Qt.GlobalColor.red,
        )
        self.file_display_table.setItem(self.interval_timer_row, 3, item)

    @pyqtSlot(str)
    def update_log(self, line: str):
        # ic(f"update_log({line})")
        self.richlog.append(line)
        self.richlog.ensureCursorVisible()

    def create_progress_bar(self):
        progress_string = (
            f'<span style="color: yellow">0 </span> GB /'
            f' <span style="color: yellow">0 </span> GB'
            f' (Files: <span style="color: yellow"> 0 </span> /'
            f' <span style="color: yellow"> 0 </span>'
            f' [<span style="color: magenta"> 0% </span>])'
        )
        self.progress.setText(progress_string)
        self.current_progress.setText(progress_string)

        self.elapsed_time.setText("0:00")
        self.current_elapsed_time.setText("0:00")

        self.time_remaining.setText("Time Remaining: Calculating ...")
        self.current_time_remaining.setText("Time Remaining: Calculating ...")

        self.completion_time.setText("Estimated Completion Time: Calculating ...")
        self.current_completion_time.setText(
            "Estimated Completion Time: Calculating ..."
        )

        self.rate.setText("Rate: Calculating ...")
        self.current_rate.setText("Rate: Calculating ...")

    def update_progress_bar_wrapper(self):
        self.signals.update_progress_bar.emit()

    @pyqtSlot()
    def update_progress_bar(self):  # , progress_string: str):
        # ic("update_progress_bar()")
        if not self.movefiles:
            return

        data = self.movefiles.consolidated_data_list

        start_time = data.start_time
        current_start_time = data.current_start_time

        total_size_gb = int(data.total_file_size / gb_divisor)
        current_total_size_gb = int(data.current_total_file_size / gb_divisor)

        completed_size_gb = data.completed_size / gb_divisor
        current_completed_size_gb = data.current_completed_size / gb_divisor

        total_files_completed = data.completed_files
        current_total_files_completed = data.current_completed_files

        total_files = data.total_file_count
        current_total_files = data.current_total_file_count

        if data.total_file_count == 0:
            files_percentage = 0
        else:
            files_percentage = data.completed_files / data.total_file_count

        if data.current_total_file_count == 0:
            current_files_percentage = 0
        else:
            current_files_percentage = (
                data.current_completed_files / data.current_total_file_count
            )

        if data.total_file_size == 0:
            size_percentage = 0
        else:
            size_percentage = data.completed_size / data.total_file_size

        if data.current_total_file_size == 0:
            current_size_percentage = 0
        else:
            current_size_percentage = (
                data.current_completed_size / data.current_total_file_size
            )

        title = data.current_title
        self.move_title.setText(title)

        self.current_bar_header.setText(
            f'<span style="color: cyan">{data.current_source_name}</span> '
            f' -> <span style="color: magenta"> {data.current_destination_name}</span>'
        )

        progress_string = (
            f'<span style="color: yellow">{completed_size_gb:,.2f} </span> GB /'
            f' <span style="color: yellow">{total_size_gb:,.2f} </span> GB'
            f' (Files: <span style="color: yellow">{total_files_completed:,} </span> /'
            f' <span style="color: yellow">{total_files:,}</span>'
            f' [<span style="color: magenta">{files_percentage:.1%}</span>])'
        )
        self.progress.setText(progress_string)

        current_progress_string = (
            f'<span style="color: yellow">{current_completed_size_gb:,.2f} </span> GB /'
            f' <span style="color: yellow">{current_total_size_gb:,.2f} </span> GB'
            f' (Files: <span style="color: yellow">{current_total_files_completed:,} </span> /'
            f' <span style="color: yellow">{current_total_files:,}</span>'
            f' [<span style="color: magenta">{current_files_percentage:.1%}</span>])'
        )
        self.current_progress.setText(current_progress_string)

        self.progressBar.setValue(int(size_percentage * 100))
        self.current_progressBar.setValue(int(current_size_percentage * 100))

        if start_time:
            now = datetime.now()
            elapsed_time = now - data.start_time
            current_elapsed_time = now - data.current_start_time

            seconds_difference = elapsed_time.seconds
            current_seconds_difference = current_elapsed_time.seconds

            # Calculate the total rate
            if seconds_difference == 0:
                rate = 0
            else:
                rate = data.completed_size / seconds_difference

            if current_seconds_difference == 0:
                current_rate = 0
            else:
                current_rate = data.current_completed_size / current_seconds_difference

            # Calculate time remaining

            if rate == 0:
                time_remaining_string = "Time Remaining: Calculating ..."
                rate_string = "Rate: Calculating ..."
                estimated_completion_time = "Calculating ..."
            else:
                rate_string = f'Rate:  <span style="color:green"> {file_size_string(rate)}</span> / second'
                remaining_size = data.total_file_size - data.completed_size
                seconds_remaining = remaining_size / rate
                time_remaining_string = f'Time Remaining: <span style="color:cyan"> {str(timedelta(seconds=seconds_remaining))}</span>'
                estimated_completion_time = (
                    now + timedelta(seconds=seconds_remaining)
                ).strftime("%a %m/%d %-I:%M %p")

            if current_rate == 0:
                current_time_remaining_string = "Time Remaining: Calculating ..."
                current_rate_string = "Rate: Calculating ..."
                current_estimated_completion_time = "Calculating ..."
            else:
                current_rate_string = f'Rate:  <span style="color:green"> {file_size_string(current_rate)}</span> / second'
                current_remaining_size = (
                    data.current_total_file_size - data.current_completed_size
                )
                current_seconds_remaining = current_remaining_size / current_rate
                current_time_remaining_string = f'Time Remaining: <span style="color:cyan"> {str(timedelta(seconds=current_seconds_remaining))}</span>'
                current_estimated_completion_time = (
                    now + timedelta(seconds=current_seconds_remaining)
                ).strftime("%a %m/%d %-I:%M %p")

            self.elapsed_time.setText(str(elapsed_time).split(".")[0])
            self.current_elapsed_time.setText(str(current_elapsed_time).split(".")[0])

            if self.previous_files_completed != data.completed_files:
                self.previous_files_completed = data.completed_files
                self.time_remaining.setText(time_remaining_string.split(".")[0])
                self.rate.setText(rate_string)

                self.completion_time.setText(
                    f'Estimated Completion Time:  <span style="color:cyan"> {estimated_completion_time} </span>'
                )

            if self.current_previous_files_completed != data.current_completed_files:
                self.current_previous_files_completed = data.current_completed_files
                self.current_time_remaining.setText(
                    current_time_remaining_string.split(".")[0]
                )
                self.current_rate.setText(current_rate_string)

                self.current_completion_time.setText(
                    f'Estimated Completion Time:  <span style="color:cyan"> {current_estimated_completion_time} </span>'
                )

    def move_file_worker(self):
        # This needs to be here, so we don't have a partial import
        from .movefiles_main import MoveFiles

        # Since this is just the wrapper for textual, create a regular MoveFiles instance
        self.movefiles = MoveFiles(
            self.primary_disk,
            self.secondary_disks,
            self.feature_flags,
            self.configuration,
            self.move_all_eligible,
            self.projection,
            qt_movefiles=self,
        )

        self._create_disk_table()

        self.movefiles.prepare_required_files(
            move_all_eligible_files=self.move_all_eligible
        )

        self.movefiles.consolidated_data_list.combined_move()
        print("Thread is done")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    qt = QTMoveFiles()
    app.exec()
