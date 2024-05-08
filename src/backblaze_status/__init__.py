import sys
from importlib.metadata import version

import rich.traceback
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from .qt_backup_status import QTBackupStatus

# read version from installed package
__version__ = version("backblaze_status")
__extra_version__ = "v0.10.1"

# For better error display
rich.traceback.install(show_locals=False)


def run():
    # Start the application and set the icon and application name
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("backblaze_status.png"))
    app.setApplicationName("Backblaze Status")

    QTBackupStatus()
    app.exec()
    sys.exit()
