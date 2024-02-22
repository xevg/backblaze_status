from .main_backup_status import BackupStatus
from PyQt6.QtCore import QObject, pyqtSlot, QThread
import threading


class BackupStatusWorker(QObject):
    def __init__(self, backup_status: BackupStatus):
        super(BackupStatusWorker, self).__init__()

        self.backup_status = backup_status

    @pyqtSlot()
    def run(self):
        threading.current_thread().name = QThread.currentThread().objectName()
        self.backup_status.run()
