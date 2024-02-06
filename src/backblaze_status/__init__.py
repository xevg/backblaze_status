import sys
from importlib.metadata import version

import rich.traceback
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from .qt_backup_status import QTBackupStatus

# read version from installed package
__version__ = version("backblaze_status")

rich.traceback.install(show_locals=False)


def test_app():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("backblaze_status.png"))
    app.setApplicationName("Backblaze Status")
    #     qdarktheme.setup_theme()

    QTBackupStatus(gui_test=False)
    app.exec()
    sys.exit()


def run():
    test_app()


if __name__ == "__main__":
    run()

# run()
