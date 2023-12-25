#!/Users/xev/opt/anaconda3/bin/python3

"""
How this should work:
1) Read configuration to get disk list
2) figure out how much we are moving from the main disk
3) for each secondary disk, figure out how much needs to move
4) If we need to move more than there is room for, move the files to the next disk
5) If it is the last disk, and we are out of space, then prune the disk to allow space for it (plus the overhead)
5) Move the files
"""
import logging
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import psutil
from flipper import FeatureFlagClient
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.rule import Rule
from rich.table import Table

from .configuration import Configuration
from .prune import Prune
from .utils import remove_directory, file_repr, initialize_logger, initialize_features

"""
Initialization of global items
"""

gb_divisor = Configuration.gb_divisor
tb_divisor = Configuration.tb_divisor

default_feature_flags = Configuration.default_feature_flags


@dataclass
class Counters:
    """
    A class to hold counter information
    """

    total_file_exists: int = 0
    total_file_exists_size: int = 0
    total_file_skipped_not_right_type: int = 0
    total_file_symlink: int = 0
    total_file_not_found: int = 0
    total_files: int = 0


@dataclass(order=True)
class CameraFile:
    """
    This contains the details of one data file
    """

    file_name: str
    file_path: Path
    file_size: int
    file_date: float
    is_symlink: bool
    file_not_found: bool
    file_size_gb: float = field(init=False)
    sort_index: str = field(init=False)

    def __post_init__(self):
        self.file_size_gb = self.file_size / gb_divisor

        # In order to sort correctly, set the sort_index field. For the .thm files, remove the first '.'
        if self.file_name[0] == ".":
            self.sort_index = self.file_name[1:]
        else:
            self.sort_index = self.file_name


@dataclass
class DiskData:
    """
    A class to hold data about a disk. The only required parameter is root_dir

    Args:
        root_dir (Path): The root directory of the SecuritySpy files

    Attributes:
        files_size (int): The total number of bytes of the files on the disk
        cameras (dict): The cameras that we have
        number_of_files (int): The number of files
        counters (Counters): Counts of various statistics
        current_date (str): The current date in the format that the cameras use. This is used to keep from moving
               today's files.
        files (list): The list of files
        free_disk (int): The number of bytes that are free on the disk

    """

    root_dir: Path
    feature_flags: list = field(default_factory=list, init=True)
    configuration: Configuration = field(default_factory=Configuration, init=True)

    files_size: int = field(default=0, init=False)
    cameras: dict = field(default_factory=dict, init=False)
    counters: Counters = field(default_factory=Counters, init=False)
    current_date: str = field(default=datetime.now().strftime("%Y-%m-%d"), init=False)
    files: list = field(default_factory=list, init=False)
    free_disk: int = field(default=0, init=False)
    total_disk_capacity: int = field(default=0, init=False)
    _console: Console = field(default_factory=Console, init=False)
    _features: FeatureFlagClient = None

    def __post_init__(self):
        self._features = initialize_features(self.feature_flags)

        initialize_logger(__name__, self.configuration)
        self._logger = logging.getLogger("MoveFiles")

    @property
    def number_of_files(self):
        return len(self.files)

    def scan(self):
        """
        Scan the disk to generate the list of files
        """

        # Get the disk free space
        disk_usage = psutil.disk_usage(str(self.root_dir))
        self.free_disk = disk_usage.free
        self.total_disk_capacity = disk_usage.total

        # Get the list of cameras
        cameras = sorted(list(os.scandir(self.root_dir)), key=lambda e: e.name)

        # Iterate through the cameras
        for this_camera in cameras:
            # Ignore any hidden files
            if this_camera.name[0] == "." or not this_camera.is_dir():
                continue

            self.cameras[this_camera.name] = {"dates": dict()}
            date_list = self.cameras[this_camera.name]["dates"]

            # Get the dates for the camera
            dates = sorted(list(os.scandir(this_camera.path)), key=lambda e: e.name)

            # Iterate through the dates
            for date in dates:
                # Files from today are not eligible, and ignore hidden files as well
                if date.name[0] == "." or date.name == self.current_date:
                    continue

                date_list[date.name] = {"files": {}}
                file_list = date_list[date.name]["files"]

                # Only look at directories
                if date.is_dir():
                    # Get the files for that date
                    scanned_files = sorted(os.scandir(date.path), key=lambda e: e.name)

                    # Iterate through the files
                    for file in scanned_files:
                        self.counters.total_files += 1

                        # We only care about m4v and thm files
                        if file.name[-3:] != "m4v" and file.name[-3:] != "thm":
                            self._logger.log_debug(
                                f"Skipping {file.path} (not m4v or thm)"
                            )
                            self.counters.total_file_skipped_not_right_type += 1
                            continue

                        # We don't process any files that are symlinks
                        if file.is_symlink():
                            self._logger.log_debug(f"Skipping symlink {file.path}")
                            self.counters.total_file_symlink += 1
                            continue

                        try:
                            # Get the information about the file, and create the CameraFile instance for the file
                            stat = file.stat()
                            file_list[file.name] = CameraFile(
                                file_name=file.name,
                                file_path=Path(this_camera.name)
                                / date.name
                                / file.name,
                                file_size=stat.st_size,
                                file_date=stat.st_mtime,
                                is_symlink=file.is_symlink(),
                                file_not_found=False,
                            )

                            # If we get here, then it is eligible to be copied. Update the various
                            #   data fields and add it to the list
                            self.counters.total_file_exists += 1
                            self.counters.total_file_exists_size += stat.st_size
                            self.files_size += stat.st_size
                            self.files.append(file_list[file.name])

                        except FileNotFoundError:
                            self.counters.total_file_not_found += 1

        # Output the stats
        counter_table = Table(title=f"File Information for {self.root_dir}")

        counter_table.add_column("Type", justify="left")
        counter_table.add_column("Value", justify="right")

        counter_table.add_row(
            "Size of Files to Copy",
            f"{int(self.counters.total_file_exists_size / gb_divisor):,} GB",
        )
        counter_table.add_row("Files to Copy", f"{self.counters.total_file_exists:,}")

        counter_table.add_row(
            "Files Skipped - Not Right Type",
            f"{self.counters.total_file_skipped_not_right_type:,}",
        )
        counter_table.add_row(
            "Files Skipped - Symlink Files", f"{self.counters.total_file_symlink:,}"
        )
        counter_table.add_row(
            "Missing Files", f"{self.counters.total_file_not_found:,}"
        )
        counter_table.add_row(Rule(), Rule())
        counter_table.add_row(
            "[bold]Total Files", f"[bold]{self.counters.total_files:,}"
        )
        if self._features.is_enabled("show_disk_info"):
            self._console.print(counter_table)

        return


@dataclass
class MoveFiles:
    primary_disk: str
    secondary_disks: list
    feature_flags: list = field(default_factory=list)
    configuration: Configuration = field(default_factory=Configuration)

    _disks: list = field(default_factory=list, init=False)
    _features: FeatureFlagClient = None
    _console: Console = field(default_factory=Console, init=False)

    def __post_init__(self) -> None:
        self._features = initialize_features(self.feature_flags)
        self._disks.append(
            DiskData(Path(self.primary_disk), configuration=self.configuration)
        )
        for disk in self.secondary_disks:
            self._disks.append(DiskData(Path(disk), configuration=self.configuration))

        initialize_logger(__name__, self.configuration)
        self._logger = logging.getLogger("MoveFiles")
        self._logger.info("Starting MoveFiles")

    @property
    def console(self) -> Console:
        return self._console

    def scan_disks(self):
        total_free_space = 0
        total_number_of_files = 0
        total_size_of_files = 0
        total_disk_capacity = 0

        # Output the information
        table = Table(title="Disk Information")
        table.add_column("Disk", justify="right")
        table.add_column("Total Capacity", justify="right")
        table.add_column("Free Space", justify="right")
        table.add_column("Percentage Free", justify="right")
        table.add_column("Number of Files Available", justify="right")
        table.add_column("Size of Files", justify="right")

        for disk in self._disks:  # type: DiskData
            disk.scan()

            table.add_row(
                str(disk.root_dir),
                f"{disk.total_disk_capacity / tb_divisor:,.2f} TB",
                f"{disk.free_disk / gb_divisor:,.2f} GB",
                f"{disk.free_disk / disk.total_disk_capacity:.0%}",
                f"{disk.number_of_files:,}",
                f"{disk.files_size / gb_divisor:,.2f} GB",
            )

            total_free_space += disk.free_disk
            total_number_of_files += disk.number_of_files
            total_size_of_files += disk.files_size
            total_disk_capacity += disk.total_disk_capacity

        table.add_row(None, Rule(), Rule(), Rule(), Rule(), Rule())
        table.add_row(
            "[bold]Total:",
            f"[bold]{total_disk_capacity / tb_divisor:,.2f} TB",
            f"[bold]{total_free_space / gb_divisor:,.2f} GB",
            f"[bold]{total_free_space / total_disk_capacity:.0%}",
            f"[bold]{total_number_of_files:,}",
            f"[bold]{total_size_of_files / gb_divisor:,.2f} GB",
        )
        if self._features.is_enabled("show_disk_info"):
            self._console.print(table)

    def move_required_files(
        self,
        caches: list = None,
        move_all_eligible: bool = False,
        additional_size_required: int = 0,
        projection: bool = False,
    ):
        """
        This function makes a list of the files that are required to move. The way this works is that there are multiple
          volumes that we can move files to. The oldest are taken from the SecuritySpy cache to the first disk. If there
          isn't enough room on the first disk, then the oldest files from the first disk are moved to the second disk.
          If there isn't enough space on the second disk, the oldest files are moved to the third disk. Etc.

        param main_directory (Path): The directory where SecuritySpy stores its files
        param caches (list): The list of the volumes that we use to move the files
        param move_all_eligible (bool): If true, this moves all the files that it can. If false, it only moves enough
            to get to the free space that it needs
        param additional_size_required (int): How much free space is needed in bytes
        """

        free_space_required = self.configuration.free_space_required

        if not caches:
            caches = self._disks
        # If this destination cache is the last one, we'll need to prune if required
        if len(caches) > 2:
            needs_prune = False
        else:
            needs_prune = True

        source_cache: DiskData = caches[0]
        destination_cache: DiskData = caches[1]

        required_space = self._get_required_space(
            source_cache, destination_cache, additional_size_required
        )

        # If we need to free up space, then do it
        if required_space > (destination_cache.free_disk - free_space_required):
            # If this is the last disk, then rather than move it somewhere else, we need to prune the required space
            #  from this disk, otherwise, make room on the destination disk for the files to be moved to.

            if needs_prune:
                if projection:
                    self._console.print(
                        f"Need to prune {required_space / gb_divisor:,.2f} GB "
                        f"from {destination_cache.root_dir}"
                    )
                else:
                    Prune(
                        destination_cache.root_dir,
                        Path(self.primary_disk),
                        required_space,
                    )
            else:
                self.move_required_files(
                    caches[1:],
                    False,
                    additional_size_required=required_space,
                    projection=projection,
                )

        # move_all_eligible is used to specify that not just enough to free up space should be moved, but all possible
        #  files.
        if move_all_eligible:
            self._console.print(
                f"Need to move {source_cache.number_of_files:,} files"
                f" ({source_cache.files_size / gb_divisor:,.2f} GB)"
                f" from {source_cache.root_dir} to {destination_cache.root_dir}"
                f" ({(destination_cache.free_disk + source_cache.files_size - free_space_required) / gb_divisor:,.2f}"
                f" GB available after move)"
            )
            self._logger.info(
                f"Need to move {source_cache.number_of_files:,} files"
                f" ({source_cache.files_size / gb_divisor:,.2f} GB)"
                f" from {source_cache.root_dir} to {destination_cache.root_dir}"
                f" ({(destination_cache.free_disk + source_cache.files_size - free_space_required) / gb_divisor:,.2f}"
                f" GB available after move)"
            )
            if not projection:
                self.move_files(source_cache, destination_cache, source_cache.files)
        else:
            # Get only the files that are needed to free up the appropriate amount of space
            files_for_copy, size_for_copy = get_required_file_list(
                additional_size_required, source_cache.files
            )
            self._console.print(
                f"Need to move {len(files_for_copy):,} files"
                f" ({size_for_copy / gb_divisor:,.2f} GB)"
                f" from {source_cache.root_dir} to {destination_cache.root_dir}"
                f" ({(destination_cache.free_disk - size_for_copy + required_space) / gb_divisor:,.2f}"
                f" GB available after move)"
            )
            self._logger.info(
                f"Need to move {len(files_for_copy):,} files"
                f" ({size_for_copy / gb_divisor:,.2f} GB)"
                f" from {source_cache.root_dir} to {destination_cache.root_dir}"
                f" ({(destination_cache.free_disk - size_for_copy + required_space) / gb_divisor:,.2f}"
                f" GB available after move)"
            )
            if not projection:
                self.move_files(
                    source_cache,
                    destination_cache,
                    files_for_copy,
                )

    def _get_required_space(
        self, source_disk, destination_disk, additional_size_required=0
    ) -> int:
        # If the space required to move is more than the amount on disk plus the required overhead,
        #   we need to free up space

        free_space_required = self.configuration.free_space_required

        if additional_size_required == 0:
            additional_size_required = source_disk.files_size

        extra_free_space = 0
        # If the amount of free disk that we have and the size of the files we need to move are more than the required
        #  reserved space, then we need to move some files off of this disk. extra_free_space is how much space we
        #  need to free up on the disk
        if destination_disk.free_disk - additional_size_required < free_space_required:
            extra_free_space = free_space_required - (
                destination_disk.free_disk - additional_size_required
            )
        return extra_free_space

    def move_files(
        self,
        source: DiskData,
        destination: DiskData,
        file_list: list,
    ):
        """
        Move the files

        param main_directory (Path): The directory where SecuritySpy stores its files
        param origin_directory (Path): The path of where we are copying files from
        param destination_directory (Path): The path where we are copying files to
        param file_list (list): The files we are going to copy
        """

        self._console.rule(
            f"[bold purple] Moving files from {source.root_dir} to"
            f" {destination.root_dir}"
        )
        # Get the total size, so that we can set the progress bar appropriately
        total_size = 0
        for file in file_list:  # type: CameraFile
            total_size += file.file_size

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
            " Dest Free Disk: [green]{task.fields[dest_free_disk]:,.2f} GB[/green]"
        )
        progress_bar = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            status_column,
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            time_remaining,
        )
        completed_size = 0
        completed_files = 0
        total_files = len(file_list)
        disk_usage = psutil.disk_usage(str(destination.root_dir))
        destination_free_disk = disk_usage.free

        task1 = progress_bar.add_task(
            f"Moving ...",
            total=total_size,
            total_size_gb=int(total_size / gb_divisor),
            completed_size=0,
            completed_size_gb=0,
            total_files=total_files,
            total_files_completed=0,
            files_completed=0,
            files_percentage=0,
            time_till_complete="Calculating ...",
            completion_time="Calculating ...",
            rate="Calculating ...",
            dest_free_disk=destination_free_disk / gb_divisor,
        )

        log_title = (
            f"Moving {len(file_list):,} files"
            f" ({total_size / gb_divisor:,.2f} GB)"
            f" from {source.root_dir} to {destination.root_dir}"
            f" ({(destination.free_disk - source.files_size)/gb_divisor:,.2f}"
            f" GB available after move)"
        )

        layout = Layout()
        layout.split_column(Layout(name="log_message"), Layout(name="progress", size=3))

        move_table = Table(expand=True)
        move_table.add_column(justify="center")
        move_table.add_column("Time", footer="Time", max_width=10, justify="center")
        move_table.add_column("File Name", footer="File Name")
        move_table.add_column("File Size", footer="File Size", justify="right")
        move_table.add_column("Interval", footer="Interval", justify="right")
        move_table.add_column("Rate", footer="Rate", justify="right")

        layout["progress"].update(
            Panel(progress_bar, title="Progress", border_style="green")
        )
        layout["log_message"].update(Panel(move_table, title=log_title))
        row_number = 1
        rows = list()

        with Live(layout, refresh_per_second=10, screen=True):
            start_time = datetime.now()
            # Sort the files by date
            for file in sorted(
                file_list, key=lambda e: e.sort_index
            ):  # type: CameraFile
                origin_file = source.root_dir / file.file_path
                destination_file = destination.root_dir / file.file_path

                try:
                    # Try creating the directory at the destination if it doesn't exist
                    destination_file.parent.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass

                pre_move_time = time.perf_counter()
                """
                if features.is_enabled("log_debug"):
                    progress.console.print(
                        f"Moving [green]{origin_file}[/]"
                        f" -> [green] {destination_file}[/]"
                    )
                """

                # Try and delete the file if there is already a version at the destination. This might be because
                #   it tried copying the file but could not.

                try:
                    destination_file.unlink(missing_ok=True)
                except Exception as exp:
                    self._logger.error(
                        f"Failed to unlink file '{destination_file}':  {exp}"
                    )
                    progress_bar.console.print_exception()

                try:
                    # Move the file
                    shutil.move(str(origin_file), str(destination_file))
                except Exception as exp:
                    self._logger.error(
                        f"Failed to move file '{origin_file}' -> '{destination_file}':  {exp}"
                    )
                    progress_bar.console.print_exception()

                try:
                    # After we remove the file, try to remove the parent directory, ignoring if it is not empty
                    remove_directory(origin_file.parent, self._console, self._logger)
                except Exception as exp:
                    self._logger.error(
                        f"Failed to remove directory '{origin_file.parent}':  {exp}"
                    )
                    progress_bar.console.print_exception()

                try:
                    # Remove the linked file, and link the new one
                    link_file = Path(self.primary_disk) / file.file_path

                    # Create the parent directory if it doesn't exist
                    link_file.parent.mkdir(parents=True, exist_ok=True)

                    # Delete the file
                    link_file.unlink(missing_ok=True)

                    # Create a new symlink to the destination
                    link_file.symlink_to(destination_file)
                except Exception as exp:
                    self._logger.error(f"Failed to do symlink '{link_file}':  {exp}")
                    progress_bar.console.print_exception()

                post_move_time = time.perf_counter()
                move_time_diff = post_move_time - pre_move_time
                elapsed_move_time = timedelta(seconds=move_time_diff)

                if elapsed_move_time.seconds > 60:
                    color = "[red]"
                else:
                    color = "[yellow]"
                file_size_gb = file.file_size / gb_divisor
                file_size_mb = file_size_gb * 1024
                if elapsed_move_time.seconds == 0:
                    mb_per_second = file_size_mb
                else:
                    mb_per_second = file_size_mb / elapsed_move_time.seconds

                if origin_file.suffix == ".thm":
                    file_color = "light_slate_blue"
                else:
                    file_color = "magenta"

                rows.append(
                    [
                        f"{row_number}",
                        f"[yellow]{datetime.now().strftime('%H:%M:%S')}[/]",
                        f" [{file_color}]{origin_file}[/] -> [{file_color}]{destination_file}[/]",
                        f"[green]{file_repr(file.file_size)}",
                        f"{color}{str(elapsed_move_time).split('.')[0]}[/]",
                        f"[green]{mb_per_second:,.2f} MB[/] / second",
                    ]
                )
                row_number += 1

                if self._console.is_terminal:
                    width, os_height = os.get_terminal_size()
                    height = (
                        os_height - 9
                    )  # leave space for the borders and progress bar
                else:
                    os_height = 0
                    height = 20

                move_table = Table(expand=True)
                move_table.add_column(justify="center")
                move_table.add_column(
                    "Time", footer="Time", max_width=10, justify="center"
                )
                move_table.add_column("File Name", footer="File Name")
                move_table.add_column("File Size", footer="File Size", justify="right")
                move_table.add_column("Interval", footer="Interval", justify="center")
                move_table.add_column("Rate", footer="Rate", justify="right")

                if len(rows) > height:
                    display_rows = rows[
                        -height:
                    ]  # Get rid of the beginning rows that don't fit
                else:
                    display_rows = rows

                for row in display_rows:
                    move_table.add_row(row[0], row[1], row[2], row[3], row[4], row[5])
                layout["log_message"].update(
                    Panel(
                        move_table,
                        title=log_title,
                    )
                )

                """
                self._console.log_message(
                    f"Moved {color}{origin_file}{end_color} -> {color}{destination_file}{end_color} "
                    f"({color}[yellow]{file_repr(file.file_size)}[/yellow]{end_color}) "
                    f"in {color}{str(elapsed_move_time).split('.')[0]} "
                    f"({mb_per_second:.2f} MB / second){end_color}",
                    highlight=False,
                )
                """
                self._logger.info(
                    f"Moved {origin_file} -> {destination_file}"
                    f" ({file_repr(file.file_size)})"
                    f" in {str(elapsed_move_time).split('.')[0]}"
                    f"({mb_per_second:.2f} MB / second)"
                )

                # Update the stats
                completed_files += 1
                completed_size += file.file_size
                seconds_difference = (datetime.now() - start_time).seconds

                # Calculate the rate
                if seconds_difference == 0:
                    rate = 0
                else:
                    rate = completed_size / seconds_difference

                # Calculate the remaining time
                if rate == 0:
                    time_till_complete = 0
                    completion_time = "Calculating ..."
                else:
                    seconds_remaining = (total_size - completed_size) / rate
                    time_till_complete = timedelta(seconds=seconds_remaining)
                    completion_time = "{:%a %m/%d %I:%M %p}".format(
                        datetime.now() + time_till_complete
                    )

                # Update the progress bar
                time_till_complete_string = str(time_till_complete).split(".")[0]
                rate_string = f"{file_repr(rate)} / second"
                disk_usage = psutil.disk_usage(str(destination_file))
                destination_free_disk = disk_usage.free

                progress_bar.update(
                    task1,
                    advance=file.file_size,
                    completed_size_gb=completed_size / gb_divisor,
                    total_files_completed=completed_files,
                    files_percentage=completed_files / total_files,
                    time_till_complete=time_till_complete_string,
                    completion_time=completion_time,
                    rate=rate_string,
                    dest_free_disk=destination_free_disk / gb_divisor,
                )


def get_required_file_list(size_required: int, file_list: list) -> (list, int):
    """
    The is passed in the size that we need to free up, and the list of all files, and returns a list of the files
      that need to be moved to free up the appropriate amount of space

    param size_required (int): The number of bytes we need to free up
    param file_list (list): The list of files

    """
    required_files = list()
    total_file_size = 0

    # Sort the files by filename. This works as a good date sort, because the file name is in the format
    #  YYYY-MM-DD Camera_Name HH etc., so sorting by name sorts by date
    for file in sorted(file_list, key=lambda e: e.sort_index):  # type: CameraFile
        required_files.append(file)
        total_file_size += file.file_size

        # End when we hit the required size
        if total_file_size > size_required:
            break

    return required_files, total_file_size


if __name__ == "__main__":
    a = MoveFiles(
        "/Volumes/CameraCache",
        [
            "/Volumes/CameraHDD/SecuritySpy",
            "/Volumes/CameraHDD2/SecuritySpy",
            "/Volumes/CameraHDD3/SecuritySpy",
        ],
    )
    a.scan_disks()
    a.console.print(Rule("Estimating files"))
    a.move_required_files(move_all_eligible=True, projection=True)
    a.console.print(Rule("Moving files"))
    a.move_required_files(move_all_eligible=True)
    pass
