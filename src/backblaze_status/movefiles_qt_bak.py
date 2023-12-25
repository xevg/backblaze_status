import sys
import time

from .backup_status_mainwindow import Ui_MainWindow
from .configuration import Configuration
from xev_utils import file_size_string
import threading
from datetime import datetime
import psutil
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QMainWindow, QApplication
from PyQt6.QtCore import (
    Qt,
    QTimer,
    QThreadPool,
    QRunnable,
    pyqtSlot,
    pyqtSignal,
    QThread,
    QObject,
)
from PyQt6.QtGui import QBrush
from .utils import MultiLogger


gb_divisor = Configuration.gb_divisor
tb_divisor = Configuration.tb_divisor


class Signals(QObject):
    update_table_data = pyqtSignal(list, name="update_table_data")
    update_log_data = pyqtSignal(str, name="update_log_data")


class MoveFilesWorker(QRunnable):
    def __init__(self, qt_movefiles):
        super(MoveFilesWorker, self).__init__()
        self.qt_movefiles = qt_movefiles
        self.signals = Signals()
        self.signals.update_log_data.connect(self.handle_trigger)

        # self.signals.update_data.connect(self.handle_trigger)
        # self.signals.update_data.emit(["test"])

    # @pyqtSlot()
    def run(self):
        print("Started Thread")
        self.qt_movefiles.movefiles.prepare_required_files(
            move_all_eligible_files=self.qt_movefiles.move_all_eligible_files
        )

        self.qt_movefiles.movefiles.consolidated_data_list.combined_move()
        print("Tread is done")

    def handle_trigger(self, data):
        print(f"Got a trigger: {data}")


def add_row(widget: QTableWidget, row: list):
    widget.insertRow(widget.rowCount())
    row_index = widget.rowCount() - 1
    for column in range(len(row)):
        widget.setItem(row_index, column, row[column])
    widget.resizeRowsToContents()


def _add_table_item(
    text: str, alignment=Qt.AlignmentFlag.AlignLeft
) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(alignment)
    return item


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, qt_movefiles, *args, obj=None, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.qt_movefiles = qt_movefiles
        self.signals = Signals()

        self._multi_log = MultiLogger("securityspy", terminal=True)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting MoveFilesApp")

        self.disk_usage_timer = QTimer()
        self.disk_usage_timer.timeout.connect(self._update_disk_table)
        self.disk_usage_timer.start(10 * 1000)  # 10 seconds

        self.move_thread = threading.Thread(target=self.move_file_worker, daemon=True)
        self.move_thread.start()

    def _update_disk_table(self):
        for row_index, disk in enumerate(self.qt_movefiles.movefiles.disks):
            # Get the disk usage information, and also create Text() objects with that data
            disk_usage = psutil.disk_usage(str(disk.root_dir))
            free_disk = disk_usage.free
            free_disk_item = _add_table_item(
                f"{free_disk / gb_divisor:,.2f} GB", Qt.AlignmentFlag.AlignRight
            )
            used_disk = disk_usage.used
            used_disk_item = _add_table_item(
                f"{used_disk / gb_divisor:,.2f} GB", Qt.AlignmentFlag.AlignRight
            )

            disk_name = disk.root_dir.parts[2]

            # Get the free size of the disk when we started
            start_free = self.qt_movefiles.start_disk_size[disk_name]

            # Get the difference of the free space between now and when we started
            free_diff = free_disk - start_free

            # If there is a difference in the free space between the start and now
            if free_diff != 0:
                free_diff_item = _add_table_item(
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

    def _get_disk_usage(self, root_dir: str):
        try:
            return psutil.disk_usage(root_dir)
        except Exception as e:
            self._multi_log.log(
                f"Error getting disk usage for {root_dir}: {e}",
                module=self._module_name,
            )

    def move_file_worker(self):
        print("Started Thread")
        time.sleep(2)  # Let other things finish up
        self.qt_movefiles.movefiles.prepare_required_files(
            move_all_eligible_files=self.qt_movefiles.move_all_eligible_files
        )

        self.qt_movefiles.movefiles.consolidated_data_list.combined_move()
        print("Tread is done")


class QTMoveFiles:
    """
    This is MoveFile class for use with PtQt6
    """

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
        """
        :param primary_disk: The directory for the primary disk
        :param secondary_disks: A list of secondary disks
        :param feature_flags: Feature flags for turning things on or off
        :param configuration: A Configuration() instance, or create a new one
        :param move_all_eligible: If this is True, move all the files from one disk to the next,
                not just enough to free yp the appropriate amount of space. Usually just used for the first disk.
        :param projection: If this is true, show a projection of what would happen, but don't actually move anything
        :param args:
        :param kwargs:
        """

        # Save all the information
        self.primary_disk = primary_disk
        self.secondary_disks = secondary_disks
        self.feature_flags = feature_flags
        self.configuration = configuration
        self.move_all_eligible_files = move_all_eligible
        self.projection = projection

        self.init_complete = False

        # Initialize the logger
        self._multi_log = MultiLogger("securityspy", terminal=True, qt_log=self)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting MoveFilesApp")

        # This needs to be here so we don't have a partial import
        from .movefiles_main import MoveFiles

        # Since this is just the wrapper for textual, create a regular MoveFiles instance
        self.movefiles = MoveFiles(
            primary_disk,
            secondary_disks,
            feature_flags,
            configuration,
            move_all_eligible,
            projection,
            qt_movefiles=self,
        )

        self.row_number = 1  # The current row number

        self.rows: list = list()  # The rows for the DataTable

        # We need these locks to not have threads stop all over each other
        self._lock: threading.Lock = threading.Lock()
        self.move_lock: threading.Lock = threading.Lock()
        self.diskinfo_lock: threading.Lock = threading.Lock()

        # This is used to help center the rows
        self.previous_cursor_row = 0

        # These are used for tracking the disk usage widget
        now = datetime.now()
        self.disk_info_color_update: dict = {"free": now, "used": now}
        self.start_disk_size: dict = dict()

        self._create_disk_table()

    def update_log(self, line: str):
        if hasattr(self, "main_window"):
            self.main_window.richlog.append(line)
            self.main_window.richlog.ensureCursorVisible()

    def get_disk_usage(self, root_dir: str):
        try:
            return psutil.disk_usage(root_dir)
        except Exception as e:
            self._multi_log.log(
                f"Error getting disk usage for {root_dir}: {e}",
                module=self._module_name,
            )

    def update_title(self, title: str):
        if hasattr(self, "main_window"):
            self.main_window.setWindowTitle(title)

    def _create_disk_table(self):
        for disk in self.movefiles.disks:
            disk_name = disk.root_dir.parts[2]  # Get the name of the volume
            disk_usage = self.get_disk_usage(disk.root_dir)
            free_disk = disk_usage.free
            used_disk = disk_usage.used
            total_disk_capacity = disk_usage.total

            # Save the beginning disk size, so that we can use it for comparison
            self.start_disk_size[disk_name] = free_disk

            # Add a row for each disk
            add_row(
                self.main_window.diskinfo,
                [
                    _add_table_item(disk_name),
                    _add_table_item(
                        f"{file_size_string(total_disk_capacity)}",
                        alignment=Qt.AlignmentFlag.AlignRight,
                    ),
                    _add_table_item(
                        f"{free_disk / gb_divisor:,.2f} GB",
                        alignment=Qt.AlignmentFlag.AlignRight,
                    ),
                    _add_table_item(
                        f"{used_disk / gb_divisor:,.2f} GB",
                        alignment=Qt.AlignmentFlag.AlignRight,
                    ),
                    _add_table_item(
                        ""
                    ),  # This column is only populated if there is a difference in the size of the disk
                    _add_table_item("Unknown", alignment=Qt.AlignmentFlag.AlignRight),
                ],  # This should be filled in by the goal size
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    qt = QTMoveFiles()
    window = MainWindow()
    window.show()
    app.exec()
