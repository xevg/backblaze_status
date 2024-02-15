from PyQt6.QtCore import (
    QObject,
    pyqtSignal,
)


class Signals(QObject):
    # GUI Regular Updated

    update_clock = pyqtSignal(str)
    update_progress_bar = pyqtSignal(dict)
    update_stats_box = pyqtSignal(str)

    # Manage interval timer

    interval_timer = pyqtSignal(int)
    stop_interval_timer = pyqtSignal()

    # Data triggers

    to_do_available = pyqtSignal()
    start_new_file = pyqtSignal(str)

    # Modes

    preparing = pyqtSignal()
    transmitting = pyqtSignal(str)

    # update_data_table_last_row = pyqtSignal(list, name="update_data_table_last_row")
    # update_log = pyqtSignal(str)
    # update_disk_color = pyqtSignal(int, "PyQt_PyObject")
    # add_pre_data_row = pyqtSignal(list)
    # update_cell = pyqtSignal(int, int, "PyQt_PyObject", "PyQt_PyObject")
    # add_data_row = pyqtSignal(list)
    # update_disk_table = pyqtSignal()
    # completed_file = pyqtSignal(str)
    # new_large_file = pyqtSignal(str)
