import sys
from importlib.metadata import version

import rich.traceback
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from .qt_backup_status import QTBackupStatus
from .bz_batch import BzBatch
from .backup_file import BackupFile

# read version from installed package
__version__ = version("backblaze_status")
__extra_version__ = "v0.10.1"

rich.traceback.install(show_locals=False)


def run():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("backblaze_status.png"))
    app.setApplicationName("Backblaze Status")

    QTBackupStatus()
    app.exec()
    sys.exit()
