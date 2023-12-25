import logging
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import NewType
from icecream import ic

from rich.text import Text
from xev_utils import file_size_string

from .configuration import Configuration
from .diskdata import CameraFile
from .display import Display
from .movefilesdata import MoveFilesData
from .prune import Prune
from .qt_display import QtDisplay
from .no_display import NoDisplay
from .utils import MultiLogger

gb_divisor = Configuration.gb_divisor
tb_divisor = Configuration.tb_divisor

MoveFiles = NewType("MoveFiles", None)
MoveFilesApp = NewType("MoveFilesApp", None)


@dataclass
class ConsolidatedMoveFilesList:
    movefiles: MoveFiles
    move_app: MoveFilesApp
    configuration: Configuration = field(default_factory=Configuration)

    move_file_list: list[MoveFilesData] = field(default_factory=list)

    total_file_count: int = field(default=0, init=False)
    current_total_file_count: int = field(default=0, init=False)

    total_file_size: int = field(default=0, init=False)
    current_total_file_size: int = field(default=0, init=False)

    start_time: datetime | None = field(default=None, init=False)
    current_start_time: datetime | None = field(default=None, init=False)

    completed_files: int = field(default=0, init=False)
    current_completed_files: int = field(default=0, init=False)

    completed_size: int = field(default=0, init=False)
    current_completed_size: int = field(default=0, init=False)

    current_title: str = field(default="MoveFiles", init=False)

    current_source_name: str = field(default=None, init=False)
    current_destination_name: str = field(default=None, init=False)

    return_message: list[str] = field(default_factory=list, init=False)

    def __post_init__(self):
        self.qt = self.movefiles.qt_movefiles
        if self.qt:
            self.display: Display = QtDisplay(self.qt)
        else:
            self.display = NoDisplay()

        self._multi_log = MultiLogger("securityspy", terminal=True, qt=self.qt)
        self._module_name = self.__class__.__name__
        ic.configureOutput(includeContext=True)

    def add_files_data(self, data: MoveFilesData) -> None:
        self.move_file_list.append(data)
        self.total_file_count += data.number_of_files
        self.total_file_size += data.size_to_move_to_destination

    def log_(self, line, level=logging.INFO):
        self._multi_log.log(line, module="ConsolidateMoveFileList", level=level)

    def combined_move(self) -> None:
        for row_index, data in enumerate(self.move_file_list):  # Type: MoveFileData
            if data.needs_prune:
                prune_obj = Prune(
                    data.destination.root_dir,
                    Path(data.primary_disk),
                    data.free_up_on_destination,
                    move_app=self.move_app,
                )
                data.freed_up_on_destination = prune_obj.scan_and_prune()

            self.current_source_name = str(data.source.root_dir.parts[2])
            self.current_destination_name = str(data.destination.root_dir.parts[2])

            item = self.display.add_table_item(
                f"{data.free_space_on_source_after_move_gb:,.2f} GB",
                alignment="right",
            )
            self.display.update_disk_cell(self.current_source_name, 2, "diskinfo", item)

            item = self.display.add_table_item(
                f"{data.free_space_on_destination_after_move_gb:,.2f} GB",
                alignment="right",
            )
            self.display.update_disk_cell(
                self.current_destination_name, 2, "diskinfo", item
            )

            for volume_index, disk in enumerate(self.movefiles.disks):
                disk_name = str(disk.root_dir.parts[2])
                if disk_name == self.current_source_name:
                    color = "cyan"
                elif disk_name == self.current_destination_name:
                    color = "magenta"
                else:
                    color = "white"

                self.display.update_disk_color(disk_name, color)

            self.return_message.append(data.summary)
            self.log_(data.summary)

            self.log_(
                f"Getting ready to move from {str(data.source.root_dir.parts[2])}"
                f" to {str(data.destination.root_dir.parts[2])}"
                f" ({data.number_of_files} files / {data.size_to_move_to_destination_gb:,.2f} GB)",
            )
            self.current_title = (
                f'Moving from <span style="color: cyan"> {str(data.source.root_dir.parts[2])} </span>'
                f' to <span style="color: magenta">{str(data.destination.root_dir.parts[2])} </span>'
                f" ({data.number_of_files} files / {data.size_to_move_to_destination_gb:,.2f} GB)"
            )

            self.move_files(data)

    def move_files(self, data: MoveFilesData):
        self.current_start_time = datetime.now()
        if not self.start_time:
            self.start_time = datetime.now()

        self.current_total_file_size = data.size_to_move_to_destination
        self.current_total_file_count = data.number_of_files
        self.current_completed_files = 0
        self.current_completed_size = 0

        # Sort the files by date
        for file in sorted(
            data.files_for_copy, key=lambda e: e.sort_index
        ):  # type: CameraFile
            # await asyncio.sleep(0.001)  # Just here to allow the GUI to update
            origin_file = data.source.root_dir / file.file_path
            destination_file = data.destination.root_dir / file.file_path

            pre_row = [
                self.display.add_table_item(
                    f"{datetime.now().strftime('%-I:%M:%S %p')}",
                    alignment="right",
                    color="yellow",
                ),
                self.display.add_table_item(
                    file.file_name,
                    alignment="center",
                    color="green",
                ),
                self.display.add_table_item(
                    f"{file_size_string(file.file_size)}",
                    alignment="right",
                    color="green",
                ),
                self.display.add_table_item(""),
                self.display.add_table_item(""),
            ]
            self.display.add_pre_data_row(pre_row)

            # Try creating the directory at the destination if it doesn't exist
            try:
                destination_file.parent.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                # We don't care if it exists
                pass
            except Exception as exp:
                self.log_(
                    Text(
                        f"Failed to create parent directory '{destination_file.parent}':  {exp}",
                        style="red",
                    )
                )
            else:
                self.log_(f"Created directory {destination_file.parent}")

            pre_move_time = time.perf_counter()

            # Try and delete the file if there is already a version at the destination. This might be because
            #   it tried copying the file but could not.

            try:
                destination_file.unlink(missing_ok=True)
            except Exception as exp:
                self.log_(
                    Text(
                        f"Failed to unlink file '{destination_file}':  {exp}",
                        style="red",
                    )
                )

            try:
                # Move the file
                shutil.move(str(origin_file), str(destination_file))
            except Exception as exp:
                self.log_(
                    Text(
                        f"Failed to move file '{origin_file}' -> '{destination_file}':  {exp}",
                        style="red",
                    )
                )

            try:
                # After we remove the file, try to remove the parent directory, ignoring if it is not empty
                self.remove_directory(origin_file.parent)
            except Exception as exp:
                self._multi_log.log(
                    Text(
                        f"Failed to remove directory '{origin_file.parent}':  {exp}",
                        style="red",
                    ),
                    level=logging.DEBUG,
                )

            # Remove the linked file from the primary cache, and link the new one
            link_file = Path(data.primary_disk) / file.file_path
            try:
                # Create the parent directory if it doesn't exist
                link_file.parent.mkdir(parents=True, exist_ok=True)

                # Delete the file
                link_file.unlink(missing_ok=True)

                # Create a new symlink to the destination
                link_file.symlink_to(destination_file)
            except Exception as exp:
                self._multi_log.log(
                    Text(f"Failed to do symlink '{link_file}':  {exp}", style="red")
                )

            post_move_time = time.perf_counter()
            move_time_diff = post_move_time - pre_move_time
            elapsed_move_time = timedelta(seconds=move_time_diff)

            # Since these files should all take less than a minute, just turn it red if it's more

            file_size_gb = file.file_size / gb_divisor
            file_size_mb = file_size_gb * 1024
            if elapsed_move_time.seconds == 0:
                mb_per_second = file_size_mb
            else:
                mb_per_second = file_size_mb / elapsed_move_time.seconds

            if elapsed_move_time.seconds > 60:
                color = "red"
            else:
                color = "yellow"

            # Since the .thm files are so much smaller, this helps me visually distinguish between them
            if origin_file.suffix == ".thm":
                file_color = "blue"
            else:
                file_color = "magenta"

            # Update the row with the final data
            update_row = (
                self.display.add_table_item(
                    f"{datetime.now().strftime('%-I:%M:%S %p')}",
                    alignment="right",
                    color="yellow",
                ),
                self.display.add_table_item(
                    f" {origin_file} -> {destination_file}",
                    alignment="left",
                    color=file_color,
                ),
                self.display.add_table_item(
                    f"{file_size_string(file.file_size)}",
                    alignment="right",
                    color="green",
                ),
                self.display.add_table_item(
                    f"{str(elapsed_move_time).split('.')[0]}",
                    alignment="right",
                    color=color,
                ),
                self.display.add_table_item(
                    f"{mb_per_second:,.2f} MB / second",
                    alignment="right",
                    color=color,
                ),
            )
            self.display.update_data_table_last_row(update_row)

            # Now that the file is copied, update the disk info panel
            # self.move_app.update_disk_info()  # We already have a timer to do this

            self.log_(
                f"Moved {origin_file.name} from {str(origin_file.parts[2])} to {str(destination_file.parts[2])}"
                f" ({file_size_string(file.file_size)})"
                f" in {str(elapsed_move_time).split('.')[0]}"
                f" ({mb_per_second:.2f} MB / second)"
            )

            # Update the stats
            self.completed_files += 1
            self.current_completed_files += 1
            self.completed_size += file.file_size
            self.current_completed_size += file.file_size
            now = datetime.now()
            seconds_difference = (now - self.start_time).seconds
            current_seconds_difference = (now - self.current_start_time).seconds

            # Calculate the total rate
            if seconds_difference == 0:
                rate = 0
            else:
                rate = self.completed_size / seconds_difference

            # Calculate the current rate
            if current_seconds_difference == 0:
                current_rate = 0
            else:
                current_rate = self.current_completed_size / current_seconds_difference

            total_size_gb = int(self.total_file_size / gb_divisor)
            current_total_size_gb = int(self.current_total_file_size / gb_divisor)

            completed_size_gb = self.completed_size / gb_divisor
            current_completed_size_gb = self.current_completed_size / gb_divisor

            total_files_completed = self.completed_files
            current_total_files_completed = self.current_completed_files

            total_files = self.total_file_count
            current_total_files = self.current_total_file_count

            files_percentage = self.completed_files / self.total_file_count
            current_files_percentage = (
                self.current_completed_files / self.current_total_file_count
            )

    def remove_directory(self, directory: Path) -> None:
        """
        Try removing a directory. Because macOS puts in the .FF_Index file, it won't remove the directory, so first
          try and delete the file, then try and delete the directory. In all cases it's ok to fail, so just don't return
          anything
        """
        # I turned off spotlight, so it shouldn't create the .FF_Index files, but just in case it does, delete them
        ff_index = directory / ".FF_Index"
        ff_index.unlink(missing_ok=True)

        try:
            directory.rmdir()
            self._multi_log.log(
                Text(
                    f"Directory '{directory}' has been removed successfully",
                    style="purple",
                )
            )

        except OSError:
            # I don't care if it fails
            pass

        return
