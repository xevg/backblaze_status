from dataclasses import dataclass, field
from datetime import datetime
from .to_do_files import ToDoFiles, NotFound
import os
from .utils import MultiLogger, file_size_string
from pathlib import Path

check_interval = 10
BZ_DIR = "/Library/Backblaze.bzpkg/bzdata/bzbackup/bzdatacenter/"
BZ_LOG_DIR = "/Library/Backblaze.bzpkg/bzdata/bzlogs/bzreports_lastfilestransmitted/"


class BackupStatus:
    done_file: str = str
    to_do_file: str = str
    # progress_bar: Progress = None
    # progress_columns: dict = dict()
    stats_counter: dict = dict()
    # task: TaskID = None
    # current_interval_worker: Worker | None = None
    # table: DataTable | None = None

    to_do: ToDoFiles = None

    rows: list = list()
    offset_rows: int = 0
    row_number: int = 1
    current_row: int = 0
    previous_todo_row: int = 0
    previous_cursor_row: int = 0
    current_cursor_row: int = 0

    start_size_completed: int = 0
    start_time: datetime = datetime.now()

    """
    def action_reset_cursor(self) -> None:
        self.table = self.query_one("#richtable", DataTable)
        row = len(self.rows) - 1
        if row < 0:
            row = 0
        self.table.move_cursor(row=row, animate=True)
        self.center_scroll()
        self.previous_cursor_row = self.table.cursor_row
    """

    def __init__(self):
        self._multi_log = MultiLogger("securityspy", terminal=True, qt=self)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting BackupStatus")

    async def initialize_monitored_files(self):
        wait_time = check_interval * 60
        while True:
            # Get the list of to_do and done files in the directory
            bz_files = sorted(os.listdir(BZ_DIR))
            for bz_file in bz_files:
                if bz_file[:7] == "bz_todo":
                    self.to_do_file = f"{BZ_DIR}/{bz_file}"
                if bz_file[:7] == "bz_done":
                    self.done_file = f"{BZ_DIR}/{bz_file}"

            # If there is no to_do file, that is because the backup process is not running, so we will sleep and try
            # again.
            if not self.to_do_file:
                self._multi_log.log(
                    f"Backup not running. Waiting for {int(check_interval)} minutes and trying again ..."
                )
                """
                # Put a little progress bar in tracking the time till we check again
                backup_start_progress_bar = ProgressBar(total=wait_time, show_eta=False)
                self.query_one("#progress").update = backup_start_progress_bar
                self.set_interval(1, self.increment_timer, repeat=wait_time)
                await asyncio.sleep(wait_time)
                """
            else:
                break

        self.to_do = ToDoFiles(self.to_do_file)

    def increment_timer(self) -> None:
        pass
        # self.query_one(ProgressBar).advance(1)

    """  
    def create_progress_bar(self) -> None:
        # Set up the progress bar
        self.progress_columns["status_column"] = TextColumn(
            "[yellow]{task.fields[total_size_completed_gb]:,}[/yellow] GB / "
            "[yellow]{task.fields[total_size_gb]:,}[/yellow] GB "
            "(Files: [yellow]{task.fields[total_files_completed]:,}[/yellow] / "
            "[yellow]{task.fields[total_files]:,}[/yellow] "
            "- [purple]{task.fields[files_percentage]:.1%}[/purple])"
        )
        self.progress_columns["self.time_remaining"] = TextColumn(
            "Time Remaining: [green]{task.fields[time_till_complete]}[/green] "
            "Estimated Completion Time: [green]{task.fields[completion_time]}[/green] "
            "Rate: [green]{task.fields[rate]}[/green]"
        )

        self.progress_bar = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            self.progress_columns["status_column"],
            TimeElapsedColumn(),
            self.progress_columns["self.time_remaining"],
        )

    @work()
    async def update_progress_bar(self) -> None:
        while True:
            # Since this is called right at the beginning, sleep the timer_interval
            await asyncio.sleep(timer_interval)

            # Rather than use the total that we completed for the calculation, we look at only what has been completed
            #   during this run. Rather than looking at a moving rate, we just look at the rate as a function of
            #   the progress since the beginning of the run
            total_processed = self.to_do.completed_size - self.start_size_completed
            total_remaining = self.to_do.remaining_size
            total_time_difference = datetime.now() - self.start_time
            seconds_difference = total_time_difference.seconds
            if seconds_difference == 0:
                rate = 0
            else:
                rate = total_processed / seconds_difference
            if rate > 0:
                seconds_remaining = total_remaining / rate
                time_till_complete = timedelta(seconds=seconds_remaining)
                completion_time = "{:%a %m/%d %I:%M %p}".format(
                    datetime.now() + time_till_complete
                )
                time_till_complete_string = str(time_till_complete).split(".")[0]
                rate_string = Text(f"{file_repr(rate)} / second", justify="right")
            else:
                # If there is no progress, just indicate we are calculating
                rate_string = "Calculating ..."
                time_till_complete_string = "Calculating ..."
                completion_time = "Calculating ..."

            # When I want to see how things are moving, I use this for debug. Normally, it is turned off.
            debug = False
            if debug:
                log(
                    f"[red]"
                    f"Total Processed: {file_repr(total_processed)} ({total_processed:,})\n"
                    f"Total Remaining: {file_repr(total_remaining)} ({total_remaining:,})\n"
                    f"   Time Elapsed: {str(total_time_difference).split('.')[0]}\n"
                    f"           Rate: {rate_string}"
                )

            # Update the progress bar with the new values
            self.progress_bar.update(
                self.task,
                time_till_complete=time_till_complete_string,
                completion_time=completion_time,
                rate=rate_string,
            )
            prog_bar = self.query_one("#progress", Static)
            prog_bar.update(self.progress_bar)
    """

    def add_remaining_rows(self, starting_index: int = 0) -> list:
        remaining_rows = list()
        remaining_row_number = 0
        # TODO: Make the number of rows into a configured variable
        for remaining_row in self.to_do.get_remaining(
            starting_index, 500
        ):  # type: BackupFile
            remaining_row_number += 1
            remaining_rows.append(
                [
                    f"R {remaining_row.list_index}",
                    " ",
                    f"{remaining_row.file_name}",
                    f"{file_size_string(remaining_row.file_size)}",
                    " ",
                    " ",
                    "todo",
                    remaining_row.file_name,
                ]
            )
        return remaining_rows

    def generate_table(self) -> None:
        to_do_index = 0

        if self.rows:
            filename = self.rows[-1][7]  # The 8th column of the last row
            try:
                to_do_index = self.to_do.get_index(filename)
                self.previous_todo_row = to_do_index
            except NotFound:
                if self.previous_todo_row:
                    to_do_index = self.previous_todo_row
                else:
                    to_do_index = 0

            self.current_row = len(self.rows)

        remaining = self.add_remaining_rows(to_do_index)
        combined_rows = self.rows + remaining

        self.table.clear()
        for _row in combined_rows:
            row = generate_row(_row)

            self.table.add_row(
                _row[0],
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
            )

        """
        # For now, don't do this, because I'm doing it in update_row

        if self.rows:
            try:
                if self.previous_cursor_row > len(self.rows):
                    self.table.move_cursor(row=self.previous_cursor_row, animate=True)
                else:
                    self.table.move_cursor(
                        row=self.previous_cursor_row + 1, animate=True
                    )
                cursor_row = self.table.cursor_row

                last_row = len(self.rows)
                # Only move the cursor if we're on the right line to start with
                if abs(last_row - cursor_row) < 3:
                    get_row_index = self.table.get_row_index(self.rows[-1][0])
                    self.table.move_cursor(row=get_row_index, animate=True)
                    self.center_scroll()
                    self.center_scroll()

                self.previous_cursor_row = self.table.cursor_row

            except Exception:
                pass
    """

    def generate_stats_string(
        self,
        percentage_duplicate_files,
        percentage_duplicate_size,
        percentage_duplicate_time,
    ) -> str:
        stats_string = (
            f"[aquamarine1]Total Files: {self.stats_counter['files']:>8,d}"
            f" ({file_size_string(self.stats_counter['files_size'])})[/]"
            f"  Regular Files: [magenta]{self.stats_counter['regular_files']:>8,d}"
            f" ({file_size_string(self.stats_counter['regular_files_size'])})"
            f" [{str(self.stats_counter['regular_time']).split('.')[0]}][/]"
            f"  Duplicate Files: [orange3]{self.stats_counter['duplicate_files']:>8,d}"
            f" ({file_size_string(self.stats_counter['duplicate_files_size'])})"
            f" [{str(self.stats_counter['duplicate_time']).split('.')[0]}][/]"
            f"  Percentage Duplicate: [dodger_blue1] {percentage_duplicate_files:.1%}"
            f" ({percentage_duplicate_size:.1%})"
            f"  [{percentage_duplicate_time:.1%}]"
        )

        return stats_string

    async def update_stats_box(self):
        if self.stats_counter["files"] > 0:
            percentage_duplicate_files = (
                self.stats_counter["duplicate_files"] / self.stats_counter["files"]
            )
        else:
            percentage_duplicate_files = 0

        if self.stats_counter["duplicate_files_size"] > 0:
            percentage_duplicate_size = (
                self.stats_counter["duplicate_files_size"]
                / self.stats_counter["files_size"]
            )
        else:
            percentage_duplicate_size = 0

        if self.stats_counter["duplicate_time"] and self.stats_counter["regular_time"]:
            percentage_duplicate_time = self.stats_counter["duplicate_time"] / (
                self.stats_counter["duplicate_time"]
                + self.stats_counter["regular_time"]
            )
        else:
            percentage_duplicate_time = 0

        stats_string = self.generate_stats_string(
            percentage_duplicate_files,
            percentage_duplicate_size,
            percentage_duplicate_time,
        )

        stats_panel = self.query_one("#stats", Static)
        stats_panel.loading = False
        stats_panel.update(stats_string)

    """
    async def next_row_interval_timer(self, row_number):
        # TODO: Make sure that the future files match the current ones. If it gets out of sync, fix it
        now = datetime.now()
        time_difference = now - now
        if not self.table.is_valid_row_index(row_number):
            return

        while True:
            self.table.update_cell_at(
                Coordinate(row_number, 4),
                Text(str(time_difference).split(".")[0], justify="right", style="red"),
                update_width=True,
            )
            value = self.table.get_cell_at(Coordinate(row_number, 2))
            # self.table.update_cell_at((row_number, column), f"[red]{value}")
            update_value = Text(str(value), style="red", justify="left")
            self.table.update_cell_at(Coordinate(row_number, 2), update_value)

            value = self.table.get_cell_at(Coordinate(row_number, 3))
            update_value = Text(str(value), style="red", justify="right")
            # self.table.update_cell_at((row_number, column), f"[red]{value}")
            self.table.update_cell_at(Coordinate(row_number, 3), update_value)

            await asyncio.sleep(1)
            time_difference = timedelta(seconds=time_difference.seconds + 1)

    async def update_row(self, row_number: int, _row: list):
        if self.current_interval_worker is not None:
            self.current_interval_worker.cancel()

        row_index = row_number - 1
        row = generate_row(_row)
        if self.table.is_valid_row_index(row_number):
            self.table.update_cell_at(
                Coordinate(row_index, 0), row_number, update_width=True
            )
            self.table.update_cell_at(
                Coordinate(row_index, 1), row[0], update_width=True
            )
            self.table.update_cell_at(
                Coordinate(row_index, 2), row[1], update_width=True
            )
            self.table.update_cell_at(
                Coordinate(row_index, 3), row[2], update_width=True
            )
            self.table.update_cell_at(
                Coordinate(row_index, 4), row[3], update_width=True
            )
            self.table.update_cell_at(
                Coordinate(row_index, 5), row[4], update_width=True
            )

            self.current_interval_worker = self.next_row_interval_timer(row_number)

        else:
            self.table.add_row(row[1], row[2], row[3], row[4], row[5])

        if self.rows:
            try:
                if self.previous_cursor_row > len(self.rows):
                    self.table.move_cursor(row=self.previous_cursor_row, animate=True)
                else:
                    self.table.move_cursor(
                        row=self.previous_cursor_row + 1, animate=True
                    )
                cursor_row = self.table.cursor_row

                last_row = len(self.rows)
                if last_row > 0:
                    last_row -= 1
                # Only move the cursor if we're on the right line to start with
                if abs(last_row - cursor_row) < 3:
                    self.table.move_cursor(row=last_row, animate=True)
                    self.center_scroll()
                    # self.center_scroll()

                self.previous_cursor_row = self.table.cursor_row

            except Exception:
                pass

    def _check_for_new_transmit_files(self) -> Path:
        last_file = None
        _dir = Path(self.BZ_LOG_DIR)
        for _file in _dir.iterdir():
            if _file.suffix == ".log":
                if not last_file:
                    last_file = _file
                else:
                    if _file.stat().st_mtime > last_file.stat().st_mtime:
                        last_file = _file
        return last_file

   

    def update_progress(self) -> None:
        prog_bar = self.query_one("#progress", Static)
        prog_bar.update(self.progress_bar)
    """

    def read_done_file(self) -> None:
        first_pass = True
        first_row = True
        last_file_time_processed = datetime.now()
        with open(self.done_file, "r") as f:
            while True:
                line = f.readline()
                if line:
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

                        self.stats_counter["files"] += 1
                        self.stats_counter["files_size"] += file_size
                        if (
                            mb_per_second > 20
                        ):  # If it's over 50mb/sec it's probably deduped
                            filename_color = "[orange3]"
                            self.stats_counter["duplicate_files"] += 1
                            self.stats_counter["duplicate_files_size"] += file_size
                            self.stats_counter["duplicate_time"] += time_difference
                        else:
                            filename_color = "[magenta]"
                            self.stats_counter["regular_files"] += 1
                            self.stats_counter["regular_files_size"] += file_size
                            self.stats_counter["regular_time"] += time_difference

                        await self.update_stats_box()

                        new_row = [
                            f"{self.row_number}",
                            f"{datetime.now().strftime('%-I:%M:%S %p')}",
                            f"{filename_color}{file_name}",
                            f"{file_size_string(file_size)}",
                            f"{str(time_difference).split('.')[0]}",
                            f"{mb_per_second:,.2f} MB / second",
                            "completed",
                            file_name,
                        ]
                        self.rows.append(new_row)

                        """
                        if first_row:
                            self.call_from_thread(self.generate_table)
                            first_row = False
                        else:
                            await self.call_from_thread(
                                self.update_row, self.row_number, new_row
                            )

                        # self.call_from_thread(self.generate_table)
                        """

                        self.row_number += 1

                        self._multi_log.log(
                            f"Processed file: "
                            f" {file_name}"
                            f" ({file_size_string(file_size)})"
                            f" Interval:{str(time_difference).split('.')[0]}"
                            f" Rate: {mb_per_second:,.2f} MB / second"
                        )

                        last_file_time_processed = datetime.now()

                    # Sometimes, there are files backed up that are not in the to_do list. I'm not sure why that
                    # happens, but to allow for it, we add the file size information to the to_do file list,
                    # so that the calculations are correct
                    if not self.to_do.exists(file_name):
                        # if not first_pass:
                        #    log_console.log(f"[red]{file_name} not in to do list")
                        self.to_do.add_completed_file(file_size)

                        """
                        # Since we're changing the total size, update the progress bar with those values
                        self.progress_bar.update(
                            self.task,
                            total=self.to_do.total_size,
                            total_size_gb=int(gb(self.to_do.total_size)),
                            total_files=self.to_do.total_files,
                        )
                        self.call_from_thread(self.update_progress)
                        """

                    # Once a file is backed up, mark it as completed, and then update the progress bar
                    self.to_do.completed(file_name)
                    """
                    self.progress_bar.update(
                        self.task,
                        advance=file_size,
                        total_size_completed_gb=int(gb(self.to_do.completed_size)),
                        total_files_completed=self.to_do.completed_files,
                        files_percentage=self.to_do.completed_files
                        / self.to_do.total_files,
                    )
                    self.call_from_thread(self.update_progress)
                    """
                else:
                    # We get to this point when we've read completely through the done file, and preloaded everything
                    # There is some stuff that we need to do as part of the prep for the continued backup
                    if first_pass:
                        # Set these values so that our calculations don't account for all the files that were done
                        #  before the program started
                        self.start_size_completed = self.to_do.completed_size
                        self.start_time = datetime.now()

                        # Change the progress bar from its preload state to backing up
                        self.progress_bar.update(
                            self.task, description="[red]Backing up [/red]"
                        )
                        self.call_from_thread(self.update_progress)

                        # Start the update Thread
                        self.update_progress_bar()
                        self.call_from_thread(self.generate_table)

                    # At this point, we're done with all the first time setup, and we are no longer in the first pass
                    first_pass = False

                    # On every pass through, check to see if the backup program has switched to use new files
                    new_done_file = None
                    new_to_do_file = None

                    bz_files = sorted(os.listdir(BZ_DIR))
                    for file in bz_files:
                        if file[:7] == "bz_todo":
                            new_to_do_file = f"{BZ_DIR}/{file}"
                        if file[:7] == "bz_done":
                            new_done_file = f"{BZ_DIR}/{file}"

                    # If new files exist, the easiest thing to do is just to restart the program, rather than try to
                    #  reset everything. So we do that, after waiting 30 seconds to give the backup time to start
                    if (
                        self.to_do_file != new_to_do_file
                        or self.done_file != new_done_file
                    ):
                        self.progress_bar.update(self.task, finished=True)
                        self.call_from_thread(self.update_progress)

                        log("\n[red]Files have changed, restarting process ...")
                        sleep(30)
                        os.execv(sys.argv[0], sys.argv)

                    # Sleep a half second, then see if there are any more new lines

                    time.sleep(0.5)

    def compose(self) -> ComposeResult:
        self.create_progress_bar()

        data_table = DataTable(
            cursor_type="row",
            id="richtable",
        )
        data_table.loading = True
        yield data_table
        yield BottomContainer(self.progress_bar, id="bot")

    @work(thread=True)
    async def initialize(self) -> None:
        await self.initialize_monitored_files()
        self.call_from_thread(self.generate_table)
        self.task = self.progress_bar.add_task(
            "[red] Preparing ",
            total=self.to_do.total_size,
            total_size_gb=int(gb(self.to_do.total_size)),
            total_size_completed_gb=int(gb(self.to_do.completed_size)),
            total_files=self.to_do.total_files,
            total_files_completed=self.to_do.completed_files,
            files_percentage=self.to_do.completed_files / self.to_do.total_files,
            time_till_complete="Calculating ",
            completion_time="Calculating ",
            rate="Calculating ",
        )
        self.read_done_file()
        self.query_one("#richtable", DataTable).loading = False
        self.start_time = datetime.now()

    async def on_mount(self) -> None:
        # Initialize
        now = datetime.now()
        self.stats_counter = {
            "files": 0,
            "duplicate_files": 0,
            "regular_files": 0,
            "files_size": 0,
            "duplicate_files_size": 0,
            "regular_files_size": 0,
            "duplicate_time": now - now,
            "regular_time": now - now,
        }
        stats_panel = self.query_one("#stats", Static)
        stats_panel.update(self.generate_stats_string(0, 0, 0))
        stats_panel.loading = False

        self.table = self.query_one("#richtable", DataTable)
        self.table.add_column(Text("Row", justify="center"), key="Row")
        self.table.add_column(Text("Time", justify="center"), key="Time")
        self.table.add_column("File Name", key="File Name")
        self.table.add_column(Text("File Size", justify="center"), key="File Size")
        self.table.add_column(Text("Interval", justify="center"), key="Interval")
        self.table.add_column(Text("Rate", justify="center"), key="Rate")

        self.current_cursor_row = self.table.cursor_row
        self.table.loading = True
        self.initialize()

    def center_scroll(self):
        height = self.table.size.height
        scroll_point = int(height / 2)
        if self.table.cursor_row > scroll_point:
            scroll_to_point = self.table.cursor_row - int(height / 2)
            self.table.scroll_to(y=scroll_to_point, duration=0.5)
        else:
            self.table.scroll_to(y=0, duration=0.5)

    def on_data_table_row_selected(self, event: DataTable.RowHighlighted):
        self.center_scroll()
