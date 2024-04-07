import os
import threading
import time

from .utils import MultiLogger


class BackupStatus:
    BZ_DIR = "/Library/Backblaze.bzpkg/bzdata/bzbackup/bzdatacenter/"

    def __init__(self, qt=None):
        from .qt_backup_status import QTBackupStatus

        self.qt: QTBackupStatus = qt

        self._multi_log = MultiLogger("BackupStatus", terminal=True, qt=self.qt)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting BackupStatus")

        self.to_do = None
        self.to_do_file = None
        self.done_file = None
        self.bz_last_files_transmitted = None
        self.bz_last_files_transmitted_thread = None
        self.bz_transmit = None
        self.bz_transmit_thread = None
        self.bz_prepare = None
        self.bz_prepare_thread = None

    def run(self):
        from .to_do_files import ToDoFiles

        self.to_do_file, self.done_file = self.get_file_list()
        self.to_do = ToDoFiles(backup_status=self.qt)
        if self.qt:
            self.qt.signals.to_do_available.emit()

        # Setup BzLastFileTransmitted Thread
        from .bz_last_files_transmitted import BzLastFilesTransmitted

        time.sleep(2)  # Let the backup_status thread create the to_do list
        self.bz_last_files_transmitted = BzLastFilesTransmitted(self, qt=self.qt)
        self.bz_last_files_transmitted_thread = threading.Thread(
            target=self.bz_last_files_transmitted.read_file,
            daemon=True,
            name="bz_last_files_transmitted",
        )
        self.bz_last_files_transmitted_thread.start()

        # Setup BzTransmit Thread
        from .bz_transmit import BzTransmit

        self.bz_transmit = BzTransmit(self, backup_status=self.qt)
        self.bz_transmit_thread = threading.Thread(
            target=self.bz_transmit.read_file, daemon=True, name="bz_transmit"
        )
        self.bz_transmit_thread.start()

        # Setup BzPrepare Thread
        from .bz_prepare import BzPrepare

        self.bz_prepare = BzPrepare(self, qt=self.qt)
        self.bz_prepare_thread = threading.Thread(
            target=self.bz_prepare.read_file, daemon=True, name="bz_prepare"
        )
        self.bz_prepare_thread.start()

        while True:
            time.sleep(60)
            pass

    def get_file_list(self):
        while True:
            to_do_file = None
            done_file = None
            # Get the list of to_do and done files in the directory
            bz_files = sorted(os.listdir(self.BZ_DIR))
            for file in bz_files:
                if file[:7] == "bz_todo":
                    to_do_file = f"{self.BZ_DIR}/{file}"
                if file[:7] == "bz_done":
                    done_file = f"{self.BZ_DIR}/{file}"

            # If there is no to_do file, that is because the backup process is not
            # running, so we will sleep and try again.
            if not to_do_file:
                self._multi_log.log(
                    f"Backup not running. Waiting for 1 minute and trying again ..."
                )

                # TODO: Make this a progress bar ...
                time.sleep(60)

            else:
                break
        return to_do_file, done_file
