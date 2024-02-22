import threading

from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot

from .progress_box import ProgressBox


class ProgressBoxWorker(QObject):
    update_progress_box = pyqtSignal(dict)

    def __init__(self, progress_box: ProgressBox) -> None:
        super(ProgressBoxWorker, self).__init__()

        self.progress_box = progress_box
        # self.signals = StatsBoxWorker.Signals()

    @pyqtSlot()
    def run(self):
        threading.current_thread().name = QThread.currentThread().objectName()

        while True:
            values = dict()
            total_size = self.progress_box.total_size
            completed_size = self.progress_box.total_size_completed
            while total_size > 2147483646:
                total_size /= 1024
                completed_size /= 1024
            values["total_size"] = int(total_size)
            values["completed_size"] = int(completed_size)
            values["elapsed_time"] = self.progress_box.elapsed_time
            values["progress_string"] = self.progress_box.progress_string
            values["remaining"] = self.progress_box.time_remaining
            values["completion_time"] = self.progress_box.completion_time
            values["rate"] = self.progress_box.rate

            self.update_progress_box.emit(values)
            QThread.sleep(1)
