import logging
import os
from utils import MultiLogger, file_size_string
import time
from to_do_files import ToDoFiles
from datetime import datetime
import sys


class BackupStatus:
    BZ_DIR = "/Library/Backblaze.bzpkg/bzdata/bzbackup/bzdatacenter/"
    check_interval = 10

    def __init__(self, qt=None):
        self._multi_log = MultiLogger("BackupStatus", terminal=True, qt=self)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting BackupStatus")

        from qt_backup_status import QTBackupStatus

        self.qt: QTBackupStatus = qt
        self.to_do = None
        self.to_do_file = None
        self.done_file = None

    def run(self):
        self.to_do_file, self.done_file = self.get_file_list()

        self.to_do = ToDoFiles(self.to_do_file)
        self.read_done_file()

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

            # If there is no to_do file, that is because the backup process is not running, so we will sleep and try again.
            if not to_do_file:
                self._multi_log.log(
                    f"Backup not running. Waiting for {int(self.check_interval)} minutes and trying again ..."
                )

                """
                # Put a little progress bar in tracking the time till we check again
                for i in track(
                    range(check_interval * 60),
                    description="[yellow]Waiting for backup to start ...",
                ):
                    time.sleep(1)
                """
                # TODO: Make this a progress bar ...
                time.sleep(1)

            else:
                break

        return (to_do_file, done_file)

    def read_done_file(self):
        last_file_time_processed = datetime.now()
        most_recent_file = None
        first_pass = True
        now = datetime.now()
        stats_counter = {
            "files": 0,
            "duplicate_files": 0,
            "regular_files": 0,
            "files_size": 0,
            "duplicate_files_size": 0,
            "regular_files_size": 0,
            "duplicate_time": now - now,
            "regular_time": now - now,
        }

        offset_rows = 0
        row_number = 1
        rows = list()
        current_row = 0
        control_c = False
        previous_todo_row = None

        with open(self.done_file, "r") as done_file:
            print_counter = 0
            new_row_number = 0
            while True:
                line = done_file.readline()
                if line:
                    if print_counter % 100 == 0:
                        print(f"...{print_counter:,}...", end="", flush=True)
                    print_counter += 1

                    fields = line.strip().split("\t")
                    try:
                        if fields[11] != "-":
                            continue
                    except IndexError:
                        continue

                    file_name = fields[13]
                    file_size = int(fields[12])

                    # If we're not doing the preload of the existing data, then print out every file that is backed up
                    if not first_pass:
                        time_difference = datetime.now() - last_file_time_processed
                        if time_difference.seconds == 0:
                            mb_per_second = 0
                        else:
                            mb_per_second = (
                                file_size / 1024 / 1024
                            ) / time_difference.seconds

                        stats_counter["files"] += 1
                        stats_counter["files_size"] += file_size
                        if (
                            mb_per_second > 20
                        ):  # If it's over 50mb/sec it's probably deduped
                            filename_color = "orange3"
                            stats_counter["duplicate_files"] += 1
                            stats_counter["duplicate_files_size"] += file_size
                            stats_counter["duplicate_time"] += time_difference
                        else:
                            filename_color = "magenta"
                            stats_counter["regular_files"] += 1
                            stats_counter["regular_files_size"] += file_size
                            stats_counter["regular_time"] += time_difference

                        # TODO: Make this a QT thing
                        percentage_duplicate_files = 0
                        percentage_duplicate_size = 0
                        percentage_duplicate_time = 0

                        if stats_counter["files"] > 0:
                            percentage_duplicate_files = (
                                stats_counter["duplicate_files"]
                                / stats_counter["files"]
                            )
                            percentage_duplicate_size = (
                                stats_counter["duplicate_files_size"]
                                / stats_counter["files_size"]
                            )
                            percentage_duplicate_time = stats_counter[
                                "duplicate_time"
                            ] / (
                                stats_counter["duplicate_time"]
                                + stats_counter["regular_time"]
                            )

                        stats_string = (
                            f"Total Files: {stats_counter['files']:>8,d}"
                            f" ({file_size_string(stats_counter['files_size'])})"
                            f"  Regular Files: {stats_counter['regular_files']:>8,d}"
                            f" ({file_size_string(stats_counter['regular_files_size'])})"
                            f" [{str(stats_counter['regular_time']).split('.')[0]}]"
                            f"  Duplicate Files: {stats_counter['duplicate_files']:>8,d}"
                            f" ({file_size_string(stats_counter['duplicate_files_size'])})"
                            f" [{str(stats_counter['duplicate_time']).split('.')[0]}]"
                            f"  Percentage Duplicate: {percentage_duplicate_files:.1%}"
                            f" ({percentage_duplicate_size:.1%})"
                            f"  [{percentage_duplicate_time:.1%}]"
                        )
                        """
                                                stats_string = (
                            f"[aquamarine1]Total Files: {stats_counter['files']:>8,d}"
                            f" ({file_size_string(stats_counter['files_size'])})[/]"
                            f"  Regular Files: [magenta]{stats_counter['regular_files']:>8,d}"
                            f" ({file_size_string(stats_counter['regular_files_size'])})"
                            f" [{str(stats_counter['regular_time']).split('.')[0]}][/]"
                            f"  Duplicate Files: [orange3]{stats_counter['duplicate_files']:>8,d}"
                            f" ({file_size_string(stats_counter['duplicate_files_size'])})"
                            f" [{str(stats_counter['duplicate_time']).split('.')[0]}][/]"
                            f"  Percentage Duplicate: [dodger_blue1] {percentage_duplicate_files:.1%}"
                            f" ({percentage_duplicate_size:.1%})"
                            f"  [{percentage_duplicate_time:.1%}]"
                        )"""
                        stats_list = [
                            {
                                "text": f"Total Files: {stats_counter['files']:>8,d}",
                                "color": "aquamarine",
                            }
                        ]

                        self.qt.signals.update_stats_box.emit(stats_string)

                        rows.append(
                            [
                                f"{row_number}",
                                f"[yellow]{datetime.now().strftime('%H:%M:%S')}",
                                f"{filename_color}{file_name}",
                                f"[green]{(file_size)}",
                                f"[yellow]{str(time_difference).split('.')[0]}[/]",
                                f"[green]{mb_per_second:,.2f} MB[/] / second",
                                "completed",
                                file_name,
                            ]
                        )

                        self.qt.signals.update_row.emit(
                            new_row_number,
                            (
                                str(f"{new_row_number + 1:,}"),
                                str(datetime.now()),
                                file_name,
                                file_size_string(file_size),
                                str(time_difference).split(".")[0],
                                f"{mb_per_second:,.2f} MB / second)",
                            ),
                        )
                        new_row_number += 1
                        row_number += 1

                        # generate_table()
                        self._multi_log.log(
                            f" {file_name}"
                            f" ({file_size_string(file_size)})"
                            f" Interval:{str(time_difference).split('.')[0]}"
                            f" Rate: {mb_per_second:,.2f} MB / second"
                        )
                        # console.log(
                        #     f"{file_name} ({file_repr(file_size)}) {str(time_difference).split('.')[0]} since last file"
                        # )

                        most_recent_file = file_name
                        last_file_time_processed = datetime.now()

                    # Sometimes, there are files backed up that are not in the to_do list. I'm not sure why that happens,
                    #  but to allow for it, we add the file size information to the to_do file list, so that the
                    #  calculations are correct
                    if not self.to_do.exists(file_name):
                        # if not first_pass:
                        #    log_console.log(f"[red]{file_name} not in to do list")
                        self.to_do.add_completed_file(file_size)

                        # Since we're changing the total size, update the progress bar with those values
                        """
                        progress_bar.update(
                            task1,
                            total=todo.total_size,
                            total_size_gb=int(gb(todo.total_size)),
                            total_files=todo.total_files,
                        )
                        """

                    # Once a file is backed up, mark it as completed, and then update the progress bar
                    self.to_do.completed(file_name)
                    """
                    progress_bar.update(
                        task1,
                        advance=file_size,
                        total_size_completed_gb=int(gb(todo.completed_size)),
                        total_files_completed=todo.completed_files,
                        files_percentage=todo.completed_files / todo.total_files,
                    )
                    """
                else:
                    # We get to this point when we've read completely through the done file, and preloaded everything
                    # There is some stuff that we need to do as part of the prep for the continued backup
                    if first_pass:
                        print("... First pass complete")
                        # Set these values so that our calculations don't account for all the files that were done
                        #  before the program started
                        start_size_completed = self.to_do.completed_size
                        start_time = datetime.now()

                        # Change the progress bar from its preload state to backing up
                        # progress_bar.update(task1, description="[red]Backing up ... [/red]")

                        # Start the update Thread
                        """
                        update_thread = threading.Thread(
                            target=update_progress_bar,
                            args=[
                                todo,
                                start_time,
                                start_size_completed,
                                progress_bar,
                                task1,
                            ],
                        )
                        update_thread.daemon = True
                        update_thread.start()
                        """

                    # At this point, we're done with all the first time setup, and we are no longer in the first pass
                    first_pass = False

                    # On every pass through, check to see if the backup program has switched to use new files
                    new_done_file = None
                    new_to_do_file = None

                    new_to_do_file, new_done_file = self.get_file_list()

                    # If new files exist, the easiest thing to do is just to restart the program, rather than try to
                    #  reset everything. So we do that, after waiting 30 seconds to give the backup time to start
                    if (
                        self.to_do_file != new_to_do_file
                        or self.done_file != new_done_file
                    ):
                        # progress_bar.update(task1, finished=True)
                        self._multi_log.log(
                            "Files have changed, restarting process ...",
                            level=logging.WARN,
                        )
                        time.sleep(30)
                        # TODO: I really don't want to restart. Figure this out. I can probably just reset the table?
                        os.execv(sys.argv[0], sys.argv)

        print("File Complete")
