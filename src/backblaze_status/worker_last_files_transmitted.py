import threading

from PyQt6.QtCore import QObject, pyqtSlot, QThread

from .bz_last_files_transmitted import BzLastFilesTransmitted
from .qt_backup_status import QTBackupStatus


class LastFilesTransmittedWorker(QObject):
    def __init__(self, backup_status: QTBackupStatus):
        super(LastFilesTransmittedWorker, self).__init__()

        self.backup_status = backup_status
        self.signals = self.backup_status.signals
        self.bz_last_files_transmitted = BzLastFilesTransmitted(backup_status)

    @pyqtSlot()
    def run(self):
        threading.current_thread().name = QThread.currentThread().objectName()

        # I want to wait until the to_do thread is initiated, so if it is not already
        # initiated, wait until the initiated signal is sent

        if self.backup_status.to_do is None:
            self.backup_status.signals.to_do_available.connect(
                self.start_bz_last_files_transmitted
            )
        else:
            self.start_bz_last_files_transmitted()

    def start_bz_last_files_transmitted(self):
        self.bz_last_files_transmitted.to_do_files = self.backup_status.to_do
        self.bz_last_files_transmitted.read_file()
