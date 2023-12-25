import asyncio
import inspect
import logging
import threading
from datetime import datetime, timedelta

import psutil
from rich import box
from rich.panel import Panel
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.progress import (
    TimeRemainingColumn,
)
from rich.text import Text
from textual import work
from textual.worker import WorkerState
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.coordinate import Coordinate
from textual.message import Message
from textual.reactive import Reactive
from textual.widgets import (
    Static,
    DataTable,
    RichLog,
    Button,
)
from textual.widgets.data_table import RowDoesNotExist
from textual.worker import Worker

from .configuration import Configuration
from xev_utils import MultiLogger, file_size_string

"""
Initialization of global items
"""

gb_divisor = Configuration.gb_divisor
tb_divisor = Configuration.tb_divisor

default_feature_flags = Configuration.default_feature_flags

# Define column names as constants
TIME_COLUMN = "Time"
FILE_NAME_COLUMN = "File Name"
FILE_SIZE_COLUMN = "File Size"
INTERVAL_COLUMN = "Interval"
RATE_COLUMN = "Rate"


class BottomContainer(Container):
    """
    Creates a container with three boxes:
      Top Left - A scrolling display for log messages
      Top Right - A datatable for disk information
      Bottom - The progress bar

    """

    def __init__(self, progress_bar: Progress, *args, **kwargs):
        """

        :param progress_bar: The progress bar instance
        :param args:
        :param kwargs:
        """
        self.progress_bar = progress_bar
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal():
                yield RichLog(id="rich_log", wrap=True)
                yield DataTable(id="disk_info")
            yield Static(
                Panel(
                    self.progress_bar,
                    box=box.SIMPLE,
                ),
                id="progress",
            )


class MoveFilesApp(App):
    """
    This is MoveFile class for use with textual
    """

    CSS_PATH = "securityspy_tools.tcss"

    def __init__(
        self,
        primary_disk: str,
        secondary_disks: list,
        feature_flags: list = None,
        configuration: Configuration = Configuration(),
        move_all_eligible: bool = True,
        projection: bool = False,
        *args,
        **kwargs,
    ):
        """
        :param primary_disk: The directory for the primary disk
        :param secondary_disks: A list of secondary disks
        :param feature_flags: Feature flags for turning things on or off
        :param configuration: A Configuration() instance, or create a new one
        :param move_all_eligible: If this is True, move all the files from one disk to the next,
                not just enough to free yp the appropriate amount of space. Usually just used for the first disk.
        :param projection: If this is true, show a projection of what would happen, but don't actually move anything
        :param args:
        :param kwargs:
        """
        super().__init__(*args, **kwargs)

        # Save all the information
        self.primary_disk = primary_disk
        self.secondary_disks = secondary_disks
        self.feature_flags = feature_flags
        self.configuration = configuration
        self.move_all_eligible_files = move_all_eligible
        self.projection = projection

        self.init_complete = False

        # Initialize the logger
        self._multi_log = MultiLogger("securityspy", terminal=True)
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting MoveFilesApp")

        from .movefiles_textual import MoveFiles

        # Since this is just the wrapper for textual, create a regular MoveFiles instance
        self.movefiles = MoveFiles(
            primary_disk,
            secondary_disks,
            feature_flags,
            configuration,
            move_all_eligible,
            projection,
            move_app=self,
        )

        self.row_number = 1  # The current row number

        self.rows: list = list()  # The rows for the DataTable

        # We need these locks to not have threads stop all over each other
        self._lock: threading.Lock = threading.Lock()
        self.move_lock: threading.Lock = threading.Lock()
        self.diskinfo_lock: threading.Lock = threading.Lock()

        # This is used to help center the rows
        self.previous_cursor_row = 0

        # Places to store the widget instances
        self.progress_widget: Static | None = None
        self.datatable_widget: DataTable | None = None
        self.log_widget: RichLog | None = None
        self.disk_info_widget: DataTable | None = None
        self.header_widget: Static | None = None

        self.current_interval_worker: Worker | None = None

        # These are used for tracking the disk usage widget
        now = datetime.now()
        self.disk_info_color_update: dict = {"free": now, "used": now}
        self.start_disk_size: dict = dict()

        self.progress_task = None
        self.current_progress_task = None
        self.progress_bar: Progress | None = None
        self.create_progress_bar()

        self.exit_button_created = False

    class MoveFilesMessage(Message):
        """
        This class is used to send messages between widgets. It calls back to on_move_files_app_move_files_message
        """

        def __init__(self, message_type: str, message_data) -> None:
            """

            :param message_type: The type of message
            :param message_data: Data about the message
            """
            super().__init__()
            self.message_type = message_type
            self.message_data = message_data

    def compose(self) -> ComposeResult:
        """
        compose creates the layout

        :return:
        """

        # If we are just doing a projection, we don't want any textual screen
        if self.projection:
            return

        # Create the DataTable that displays the moved files
        data_table = DataTable(cursor_type="row", id="richtable")

        # This is the header box, the DataTable, and the BottomContainer, which has the log, disk information
        #   and progress bar

        with Vertical():
            yield Static(Text("MoveApp", style="bold", justify="center"), id="header")
            yield data_table
            yield BottomContainer(self.progress_bar, id="bottom_box")

    async def on_mount(self) -> None:
        """
        on_mount is called once the layout is complete, so that I can fill in all the information
        :return:
        """

        # Now that the widgets have been created, get links to them
        self.progress_widget = self.query_one("#progress")
        self.log_widget = self.query_one("#rich_log", RichLog)
        self.disk_info_widget = self.query_one("#disk_info", DataTable)
        self.datatable_widget = self.query_one("#richtable", DataTable)
        self.header_widget = self.query_one("#header", Static)

        self._multi_log.rich_log = self.log_widget

        self.init_complete = True

        # Create the columns for the DataTable containing the moved files
        self.datatable_widget.add_column(
            Text(TIME_COLUMN, justify="center"), key="Time"
        )
        self.datatable_widget.add_column(FILE_NAME_COLUMN, key="File Name")
        self.datatable_widget.add_column(
            Text(FILE_SIZE_COLUMN, justify="center"), key="File Size"
        )
        self.datatable_widget.add_column(
            Text(INTERVAL_COLUMN, justify="center"), key="Interval"
        )
        self.datatable_widget.add_column(
            Text(RATE_COLUMN, justify="center"), key="Rate"
        )

        # Create the columns for the DataTable containing the disk information
        self.disk_info_widget.add_column(Text("Disk", justify="center"), key="Disk")
        self.disk_info_widget.add_column(
            Text("Capacity", justify="center"), key="Capacity"
        )
        self.disk_info_widget.add_column(
            Text("Available", justify="center"), key="Available"
        )
        self.disk_info_widget.add_column(Text("Used", justify="center"), key="Used")
        self.disk_info_widget.add_column(
            Text("Difference", justify="center"), key="Diff"
        )
        self.disk_info_widget.add_column(Text("Target", justify="center"), key="Target")

        # We are not going to scroll through the disk info table, so no cursor
        self.disk_info_widget.show_cursor = False

        # Prepare the rows for the disk info table
        for disk in self.movefiles.disks:
            disk_name = disk.root_dir.parts[2]  # Get the name of the volume
            disk_usage = self.get_disk_usage(disk.root_dir)
            free_disk = disk_usage.free
            used_disk = disk_usage.used
            total_disk_capacity = disk_usage.total

            # Save the beginning disk size, so that we can use it for comparison
            self.start_disk_size[disk_name] = free_disk

            # Add a row for each disk
            self.disk_info_widget.add_row(
                Text(disk_name, justify="left"),
                Text(f"{file_size_string(total_disk_capacity)}", justify="right"),
                Text(f"{free_disk / gb_divisor:,.2f} GB", justify="right"),
                Text(f"{used_disk / gb_divisor:,.2f} GB", justify="right"),
                "",  # This column is only populated if there is a difference in the size of the disk
                Text(
                    "Unknown", justify="right"
                ),  # This should be filled in by the goal size
                key=disk_name,
            )

        # Log that we are starting the main application. It has to be done here because before this point,
        #   write_log doesn't exist
        self._multi_log.log(
            Text("Starting Main Textual Application"), module=self._module_name
        )

        # Set a timer to update the progress bar every second
        self.set_interval(1, self.update_progress_bar, repeat=0)

        # Set a timer to start the actual program. If I don't do this, then this function never ends.
        #   This timer does no repeat
        self.set_interval(1, self.move_files_timer, repeat=1)

        # start the diskinfo timer
        self.set_interval(10, self.update_disk_info, repeat=0)

    def get_disk_usage(self, root_dir: str):
        try:
            return psutil.disk_usage(root_dir)
        except Exception as e:
            self._multi_log.log(
                Text(f"Error getting disk usage for {root_dir}: {e}"),
                module=self._module_name,
            )

    async def move_files_timer(self) -> None:
        """
        This function calls the MoveFiles.prepare_required_files function. It waits till the funtion returns, and then
          rather than exiting, it pops up a button to click to exit. This is that I can see what has happened before
          it disappears
        """

        await self.movefiles.prepare_required_files(
            move_all_eligible_files=self.move_all_eligible_files
        )
        self.move_files()

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Called when the worker state changes."""

        if (
            event.worker.name == "move_files"
            and (
                event.state == WorkerState.ERROR
                or event.state == WorkerState.CANCELLED
                or event.state == WorkerState.SUCCESS
            )
            and not self.exit_button_created
        ):
            exit_button = Button("Click to exit", id="button_exit")
            self.progress_widget.mount(
                exit_button
            )  # Put the button over the progress bar
            self.exit_button_created = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """
        When the button is pressed, exit, passing back the return_message
        :param event:
        :return:
        """
        self.exit(message="\n".join(self.movefiles.return_message))

    async def on_move_files_app_move_files_message(
        self, message: MoveFilesMessage
    ) -> None:
        """
        This function is called in response to a message being sent.
        :param message:
        :return:
        """
        match message.message_type:
            # If a "clear" is sent, clear the table
            case "clear":
                self.clear_table()

            # If an "update_table" is sent, update the table with the data passed in
            case "update_table":
                self.update_table(message.message_data)

            # If "update_headers" is called, I update the header bar with the data passed in
            case "update_header":
                self.update_screen_header(message.message_data)

            case "interval_timer":
                self.current_interval_worker = self.next_row_interval_timer(
                    message.message_data
                )

            case "interval_timer_cancel":
                if self.current_interval_worker:
                    self.current_interval_worker.cancel()

    def action_reset_cursor(self) -> None:
        """
        This method is called to the cursor to the most recent row of moved files
        :return:
        """

        row = len(self.rows) - 1
        if row < 0:
            row = 0
        self.datatable_widget.move_cursor(row=row, animate=True)
        self.center_scroll()  # Scroll the selected cursor to the center
        self.previous_cursor_row = self.datatable_widget.cursor_row

    def center_scroll(self):
        """
        This method scrolls the selected row of the table to the center of the screen
        :return:
        """
        height = self.datatable_widget.size.height
        scroll_point = int(height / 2)
        if self.datatable_widget.cursor_row > scroll_point:
            scroll_to_point = self.datatable_widget.cursor_row - int(height / 2)
            self.datatable_widget.scroll_to(y=scroll_to_point, duration=1.0)
        else:
            self.datatable_widget.scroll_to(y=0, duration=1.0)

    def on_data_table_row_selected(self, event: DataTable.RowHighlighted):
        """
        When a row is selected, center the row on the screen
        :param event:
        :return:
        """
        self.center_scroll()

    def create_progress_bar(self) -> None:
        # Set up the progress bar
        status_column = TextColumn(
            "[yellow]{task.fields[completed_size_gb]:,.2f}[/] GB / "
            "[yellow]{task.fields[total_size_gb]:,}[/] GB "
            "(Files: [yellow]{task.fields[total_files_completed]:,}[/] / "
            "[yellow]{task.fields[total_files]:,}[/] "
            "- [purple]{task.fields[files_percentage]:.1%}[/purple])"
        )
        time_remaining = TextColumn(
            "Estimated Completion Time: [green]{task.fields[completion_time]}[/green]"
            " Rate: [green]{task.fields[rate]}[/green]"
        )
        self.progress_bar = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(pulse_style="bar.pulse"),
            TaskProgressColumn(),
            status_column,
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            time_remaining,
        )

        self.current_progress_task = self.progress_bar.add_task(
            f"Current ...",
            total=0,
            total_size_gb=0,
            completed_size=0,
            completed_size_gb=0,
            total_files=0,
            total_files_completed=0,
            files_completed=0,
            files_percentage=0,
            time_till_complete="Calculating ...",
            completion_time="Calculating ...",
            rate="Calculating ...",
        )

        self.progress_task = self.progress_bar.add_task(
            f"Total:",
            total=0,
            total_size_gb=0,
            completed_size=0,
            completed_size_gb=0,
            total_files=0,
            total_files_completed=0,
            files_completed=0,
            files_percentage=0,
            time_till_complete="Calculating ...",
            completion_time="Calculating ...",
            rate="Calculating ...",
        )

    def update_disk_info(self):
        """
        This method updates the disk information panel
        :return:
        """

        self.diskinfo_lock.acquire()  # Lock because multiple things may be accessing it
        for disk in self.movefiles.disks:
            # Get the disk usage information, and also create Text() objects with that data
            disk_usage = psutil.disk_usage(str(disk.root_dir))
            free_disk = disk_usage.free
            free_disk_text = Text(f"{free_disk / gb_divisor:,.2f} GB", justify="right")
            used_disk = disk_usage.used
            used_disk_text = Text(f"{used_disk / gb_divisor:,.2f} GB", justify="right")

            disk_name = disk.root_dir.parts[2]

            disk_row_index = self.disk_info_widget.get_row_index(disk_name)

            # Get the free size of the disk when we started
            start_free = self.start_disk_size[disk_name]

            # Get the difference of the free space between now and when we started
            free_diff = free_disk - start_free

            # If there is a difference in the free space between the start and now
            if free_diff != 0:
                # Set the color, red if we've reduced the free space, blue if the free space has increased
                if free_diff < 0:
                    color = "bright_magenta"
                else:
                    color = "bright_cyan"

                free_diff_text = Text(
                    file_size_string(
                        free_diff, sign=True
                    ),  # Use file_repr so that we show it even if its KB or MB
                    justify="right",
                    style=color,
                )

                # Update the difference column
                self.disk_info_widget.update_cell_at(
                    Coordinate(disk_row_index, 4),
                    free_diff_text,
                    update_width=True,
                )

                # Update the free space and used space columns, if they've changed
                self.disk_info_widget.update_cell_at(
                    Coordinate(disk_row_index, 2), free_disk_text, update_width=True
                )
                self.disk_info_widget.update_cell_at(
                    Coordinate(disk_row_index, 3), used_disk_text, update_width=True
                )
        self.diskinfo_lock.release()

    def update_screen_header(self, title: Reactive[str]) -> None:
        """
        Update the header to the new title
        :param title: What the header should be updated to
        :return:
        """
        self.title = title
        self.header_widget.update(Text(str(title), style="bold", justify="center"))

    def update_progress_bar(self) -> None:
        """
        Just update the progress widget with the latest progress information
        :return:
        """
        self.progress_widget.update(self.progress_bar)

    def update_table(self, row: list) -> None:
        """
        A row is passed in, and we update that row with the new data
        :param row: [key_name, time, file_name, file_size, interval, rate]
        :return:
        """

        # Try to get the row, and then update it. If it doesn't exist, then I add the row at the end
        try:
            self.datatable_widget.get_row(row[0])
            self.datatable_widget.update_cell(
                row[0], TIME_COLUMN, row[1], update_width=True
            )
            self.datatable_widget.update_cell(
                row[0], FILE_NAME_COLUMN, row[2], update_width=True
            )
            self.datatable_widget.update_cell(
                row[0], FILE_SIZE_COLUMN, row[3], update_width=True
            )
            self.datatable_widget.update_cell(
                row[0], INTERVAL_COLUMN, row[4], update_width=True
            )
            self.datatable_widget.update_cell(
                row[0], RATE_COLUMN, row[5], update_width=True
            )

        except RowDoesNotExist:
            self.datatable_widget.add_row(
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
                key=row[0],
                label=row[0],
            )

            # If we've added a new row, then move the cursor to the new row
            cursor_row = self.datatable_widget.cursor_row
            max_row = self.datatable_widget.row_count
            if cursor_row == max_row - 2:
                self.datatable_widget.move_cursor(row=max_row)

    @work()
    async def next_row_interval_timer(self, row_number):
        row_number -= 1
        now = datetime.now()
        time_difference = now - now
        while not self.datatable_widget.is_valid_row_index(row_number):
            await asyncio.sleep(1)  # need to wait for the row to be valid

        while True:
            self.datatable_widget.update_cell_at(
                Coordinate(row_number, 3),
                Text(str(time_difference).split(".")[0], justify="right", style="red"),
                update_width=True,
            )
            await asyncio.sleep(1)
            time_difference = timedelta(seconds=time_difference.seconds + 1)

    def clear_table(self) -> None:
        """
        Just tell the datatable widget to clear the contents
        :return:
        """
        self.datatable_widget.clear()

    @work(thread=True, name="move_files")
    async def move_files(self) -> None:
        """
        This method moves the files, by calling the MoveFiles.move_files. This runs as separate worker thread, so it
           doesn't interfere with updating the screen
        :return:
        """
        # Try to acquire the lock. Don't do any work until it is acquired. This is because there may be different
        #   disks moving files at the same time, which we do not want

        self._multi_log.log(
            Text("Trying to acquire lock (MoveFileApps.move_file)"),
            module="MoveFileApps.move_file",
            level=logging.DEBUG,
        )
        self.move_lock.acquire()
        self._multi_log.log(
            Text("Acquired lock and running move_files (MoveFileApps.move_file)"),
            module="MoveFileApps.move_file",
            level=logging.DEBUG,
        )
        # Once we have the lock, move the files
        await self.movefiles.consolidated_data_list.combined_move()

        # And then release the lock
        self._multi_log.log(
            Text("Releasing lock (MoveFileApps.move_file)"),
            module="MoveFileApps.move_file",
            level=logging.DEBUG,
        )
        self.move_lock.release()
