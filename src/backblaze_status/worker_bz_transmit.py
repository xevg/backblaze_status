import threading

from PyQt6.QtCore import QObject, pyqtSlot, QThread

from .bz_transmit import BzTransmit
from .qt_backup_status import QTBackupStatus


class BZTransmitWorker(QObject):
    """
    The wrapper class to run BzTransmit as a separate thread
    """
    def __init__(self, backup_status: QTBackupStatus):
        super(BZTransmitWorker, self).__init__()

        self.backup_status = backup_status
        self.signals = self.backup_status.signals
        self.bz_transmit = BzTransmit(backup_status)

    @pyqtSlot()
    def run(self):
        threading.current_thread().name = QThread.currentThread().objectName()

        # I want to wait until the to_do thread is initiated, so if it is not already
        # initiated, wait until the initiated signal is sent

        if self.backup_status.to_do is None:
            self.backup_status.signals.to_do_available.connect(self.start_bz_transmit)
        else:
            self.start_bz_transmit()

    @pyqtSlot()
    def start_bz_transmit(self):
        self.bz_transmit.to_do = self.backup_status.to_do
        self.bz_transmit.read_file()
