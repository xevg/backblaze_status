import asyncio
import sys
from importlib.metadata import version
from pathlib import Path

import click
import rich.traceback
from rich.console import Console
from PyQt6.QtWidgets import QApplication


import qdarktheme
from qt_backup_status import QTBackupStatus

# read version from installed package
# __version__ = version("securityspy_tools")

# rich.traceback.install(show_locals=False)


app = QApplication(sys.argv)
qdarktheme.setup_theme()
# from .movefiles_qt import MainWindow

# window = MainWindow()
# window.show()
# app.exec()

QTBackupStatus()
app.exec()
