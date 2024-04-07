from PyQt6.QtCore import (
    QObject,
    pyqtSignal,
)


class Signals(QObject):
    # GUI Regular Updated

    update_clock = pyqtSignal(str)
    update_progress_bar = pyqtSignal(dict)
    update_stats_box = pyqtSignal(str)

    calculate_progress = pyqtSignal()

    # Manage interval timer

    interval_timer = pyqtSignal(int)
    stop_interval_timer = pyqtSignal()

    # Data triggers

    to_do_available = pyqtSignal()
    start_new_file = pyqtSignal(str)
    files_updated = pyqtSignal()

    # To Do Triggers

    add_file = pyqtSignal(str, bool)
    mark_completed = pyqtSignal(str)

    # Modes

    preparing = pyqtSignal()
    transmitting = pyqtSignal(str)

    # Backup Running
    backup_running = pyqtSignal(bool)
