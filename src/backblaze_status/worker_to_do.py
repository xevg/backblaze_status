import threading
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSlot, QThread

from .to_do_files import ToDoFiles


class ToDoWorker(QObject):
    """
    Worker class for the to_do thread
    """

    def __init__(self, backup_status):
        from .qt_backup_status import QTBackupStatus

        super(ToDoWorker, self).__init__()

        self.backup_status: QTBackupStatus = backup_status
        self.to_do: Optional[ToDoFiles] = None
        self.signals = self.backup_status.signals

    @pyqtSlot()
    def run(self):
        """
        Start the to_do thread
        """
        threading.current_thread().name = QThread.currentThread().objectName()

        self.to_do = ToDoFiles(self.backup_status)

        # Once the initialization of the to_do files are complete, then set the to_do
        # variable in backup_status to this instance, and also send out an alert that
        # it is complete

        self.backup_status.to_do = self.to_do
        self.signals.to_do_available.emit()
