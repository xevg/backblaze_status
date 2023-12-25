import configparser
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psutil
from backblaze_tools import KnownFiles
from rich.console import Console

from .configuration import Configuration
from .utils import remove_directory, initialize_features, MultiLogger

gb_divisor = Configuration.gb_divisor
tb_divisor = Configuration.tb_divisor

# MoveFilesApp = typing.NewType("MoveFilesApp", None)


class Prune:
    """
    Class to prune files from disk, from oldest to youngest. If files aren't backed up, they are not pruned.
    """

    @dataclass
    class Filedata:
        """
        Class to store date about the files
        """

        camera: str
        date: str
        filename: str
        path: Path
        file_size: int
        file_date: datetime
        backed_up: bool

    def __init__(
        self,
        root_dir: Path,
        main_directory: Path,
        free_size_required: int,
        feature_flags: list | None = None,
        move_app=None,
        configuration: configparser.ConfigParser = Configuration(),
    ) -> None:
        """
        Init for Prune

        param root_dir: The root that we are pruning
        param main_directory: The initial cache directory, so we can remove the symlinks
        param free_size: The amount of space we need to free up
        :rtype: object
        """

        self.root_dir = str(root_dir)
        self.main_directory = str(main_directory)
        self.free_size_required = free_size_required
        self.feature_flags = feature_flags
        self.thm_data_list = dict()
        self.file_data_list = list()
        self.to_be_deleted = list()
        self.skipped_not_backed_up = 0
        self.skipped_not_right_type = 0
        self.skipped_symlink = 0
        self.space_freed = 0
        self._console = Console()
        self._features = initialize_features(self.feature_flags)
        self.configuration = configuration
        self.known_files = None
        self.move_app = move_app

        # How much free space is on the disk
        self.disk_usage = psutil.disk_usage(self.root_dir)
        self.free = self.disk_usage.free
        self.free_gb = int(self.disk_usage.free / gb_divisor)

        # How much space needs to be freed up
        self.required_free = self.free_size_required - self.free
        self.required_free_gb = int(self.required_free / gb_divisor)

        # Initialize the logger
        self._multi_log = MultiLogger(
            "securityspy",
            terminal=True,
        )  # , qt_log=self.move_files.move_qt)
        self._module_name = self.__class__.__name__

        self._multi_log.log(
            f"Beginning Prune of {self.root_dir}", module=self._module_name
        )
        self._multi_log.log(
            f"{self.root_dir} currently has {self.free_gb:,} GB free"
            f" ({self.disk_usage.percent}%). {self.free_size_required / gb_divisor:,.2f} free space required.",
            module=self._module_name,
        )

        if self.required_free > 0:
            self._multi_log.log(
                f"Need to free up {self.required_free_gb:,} GB to reach"
                f" {configuration.free_space_required / gb_divisor:,.2f} GB free",
                module=self._module_name,
            )

    def log_(self, line, log_level=logging.INFO):
        self._multi_log.log(line, module=self._module_name, level=log_level)

    def scan_and_prune(self) -> float:
        if self.free > self.required_free:
            self.log_("There is more free space than required. Not pruning")
            return 0.0

        self.log_("Scanning backup information")

        self.initialize_known_files()

        # Get the information about backups. We need this because if the files aren't backed up, we won't prune them

        self.log_("Scanning files")

        self.scan_disk()

        self.log_("Pruning files")

        return self.prune()

    # TODO: Make this a thread
    def initialize_known_files(self):
        self.known_files = KnownFiles()

    def scan_disk(self):
        """
        Scan the disk and put together the list of files that are candidates for pruning
        """

        # Get the cameras
        cameras = sorted(list(os.scandir(self.root_dir)), key=lambda e: e.name)
        for this_camera in cameras:  # type: os.DirEntry
            # We don't care about hidden directories, and we also don't want to prune any saved files
            if this_camera.name[0] == "." or this_camera.name == "Saved":
                continue

            # Skip unless it's a directory
            if not this_camera.is_dir():
                continue

            # Get the dates for the camera. They need to be a directory.

            dates = sorted(list(os.scandir(this_camera.path)), key=lambda e: e.name)
            for date in dates:  # type: os.DirEntry
                if date.name[0] == ".":
                    continue

                # Skip unless it's a directory
                if not date.is_dir():
                    continue

                scanned_files = sorted(os.scandir(date.path), key=lambda e: e.name)
                for file in scanned_files:  # type: os.DirEntry
                    # Get the information about the file
                    stat = file.stat()

                    # Add to the prune list only if it is a m4v or thm file, and if it's not a symlink
                    if file.is_file():
                        self.skipped_symlink += 1
                        continue
                    if file.name[-3:] == "m4v" or file.name[-3:] == "thm":
                        # Check to see if the file has been backed up
                        backed_up = self.is_backed_up(file.path)
                        file_data = self.Filedata(
                            this_camera.name,
                            date.name,
                            file.name,
                            Path(file.path),
                            stat.st_size,
                            datetime.fromtimestamp(stat.st_mtime),
                            backed_up,
                        )
                        # Add them to two separate lists. We want to delete the thm file if we are pruning the
                        #   m4v file, so we need to save those separately.
                        if file.name[-3:] == "thm":
                            self.thm_data_list[file.path] = file_data
                        else:
                            self.file_data_list.append(file_data)

        # Sort the list by file date, so that the oldest are first
        self.file_data_list.sort(key=lambda x: x.file_date)

    def prune(self) -> float:
        """
        This function does the actual pruning
        """

        # For reporting, we want the earliest and latest date
        earliest_date = datetime.now()
        latest_date = datetime.fromtimestamp(0)

        self.log_("Collecting oldest files")

        for file in self.file_data_list:  # type: Prune.Filedata
            # Only prune files that are already backed up
            if not file.backed_up:
                self.skipped_not_backed_up += 1
                continue

            self.space_freed += file.file_size
            self.log_(
                f"{file.filename:45} {file.file_date} {file.file_size / gb_divisor:.2f} GB "
                + f" (Total to be deleted: {self.space_freed / gb_divisor:.2f} GB)"
            )

            # If the file is later than the latest date, or earlier than the earliest date, update the appropriate item
            if file.file_date > latest_date:
                latest_date = file.file_date
            if file.file_date < earliest_date:
                earliest_date = file.file_date

            # Add the file to the to_be_deleted list
            self.to_be_deleted.append(file)

            # If we are deleting the video file, also delete the thm file.
            thm_file = f"{str(file.path.parent)}/.{file.filename[:-3]}thm"
            if thm_file in self.thm_data_list:
                if self.thm_data_list[thm_file].backed_up:
                    self.to_be_deleted.append(self.thm_data_list[thm_file])

            # Check to see if we have freed enough space yet
            if self.space_freed > self.required_free:
                break

        # Now do the actual deletion
        total_deleted = 0.0
        for file in self.to_be_deleted:  # type: Prune.Filedata
            # Because we've moved the files from the cache directory and replaced it with symbolic links,
            # we want to delete the symbolic as well
            cache_file_path = str(file.path).replace(self.root_dir, self.main_directory)

            # Delete the file
            try:
                file.path.unlink()
                total_deleted += file.file_size
                self.log_(f"Deleted {str(file.path)}")

            except Exception as exp:
                self.log_(
                    f"Failed to delete file {str(file.path)}: {exp}",
                    log_level=logging.ERROR,
                )

            # Also delete the link in the cache directory that points to the file
            try:
                os.remove(cache_file_path)
                self.log_(f"Deleted symlink {cache_file_path}")

            except Exception as exp:
                # Since there may not be the symlink, I don't care if it's not deleted
                self.log_(
                    f"{cache_file_path} not removed: {exp}", log_level=logging.DEBUG
                )

            # try and remove the directory if it is empty. But before we do that, we need to remove the .FF_Index file
            for dir_name in [
                file.path.parent,
                Path(cache_file_path).parent,
            ]:
                remove_directory(dir_name, self._console)
                # remove_directory(dir_name, self._console, self._multi_log.logger)

        new_disk_usage = psutil.disk_usage(self.root_dir)
        new_free_gb = int(new_disk_usage.free / gb_divisor)
        earliest_date = str(earliest_date).split(".")[0]
        latest_date = str(latest_date).split(".")[0]

        self.log_(
            f"Deleted {len(self.to_be_deleted):,} file, from {earliest_date} to"
            f" {latest_date}"
        )
        self.log_(
            f"{self.root_dir} currently has {new_free_gb:,} GB free ({new_disk_usage.percent}%)"
        )
        self.log_(
            f"Deleted {len(self.to_be_deleted):,} file, from {earliest_date} to {latest_date}"
        )
        self.log_(
            f"Skipped {self.skipped_not_backed_up:,} files that haven't been backed up yet"
        )
        self._console.print(
            f"{self.root_dir} currently has {new_free_gb:,} GB free ({new_disk_usage.percent}%)"
        )

        return total_deleted

    def is_backed_up(self, filename):
        """
        Check if the file is backed up. It is only considered backed up if it is the known file list, and it
          is not in the to_do list to be backed up again.
        """
        if (
            filename in self.known_files.known_files
            and filename not in self.known_files.to_do_filenames
        ):
            return True
        return False


if __name__ == "__main__":
    Prune(Path("/Volumes/CameraCache"), Path("/Volumes/CameraHDD3/SecuritySpy"), 0)
    pass
