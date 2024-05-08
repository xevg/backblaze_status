from PyQt6.QtCore import (
    QObject,
    pyqtSignal,
)


class Signals(QObject):
    """
    A class that contains all the signals needed for the application
    """

    update_stats_box = pyqtSignal()
    go_to_current_row = pyqtSignal()
    update_chunk_progress = pyqtSignal()

    # Data triggers

    to_do_available = pyqtSignal()
    start_new_file = pyqtSignal(str)

    # To Do read messages

    get_messages = pyqtSignal(dict)

    # Backup Running
    backup_running = pyqtSignal(bool)
