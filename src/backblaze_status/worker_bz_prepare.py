import threading

from PyQt6.QtCore import QObject, pyqtSlot, QThread

from .bz_prepare import BzPrepare
from .qt_backup_status import QTBackupStatus


class BzPrepareWorker(QObject):
    def __init__(self, backup_status: QTBackupStatus):
        super(BzPrepareWorker, self).__init__()

        self.backup_status = backup_status
        self.signals = self.backup_status.signals
        self.bz_prepare = BzPrepare(backup_status)

    @pyqtSlot()
    def run(self):
        threading.current_thread().name = QThread.currentThread().objectName()

        # I want to wait until the to_do thread is initiated, so if it is not already
        # initiated, wait until the initiated signal is sent

        if self.backup_status.to_do is None:
            self.backup_status.signals.to_do_available.connect(self.start_bz_prepare)
        else:
            self.start_bz_prepare()

    @pyqtSlot()
    def start_bz_prepare(self):
        self.bz_prepare.to_do_files = self.backup_status.to_do
        self.bz_prepare.read_file()
