import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import psutil
from flipper import FeatureFlagClient
from rich.console import Console
from xev_utils import MultiLogger

from .configuration import Configuration
from .utils import (
    initialize_features,
)

"""
Initialization of global items
"""

gb_divisor = Configuration.gb_divisor
tb_divisor = Configuration.tb_divisor


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

    def __repr__(self):
        return (
            f"Counters(total_file_exists={self.total_file_exists},"
            f" total_file_exists_size={self.total_file_exists_size},"
            f" total_file_skipped_not_right_type={self.total_file_skipped_not_right_type},"
            f" total_file_symlink={self.total_file_symlink},"
            f" total_file_not_found={self.total_file_not_found},"
            f" total_files={self.total_files})"
        )

    def reset_counters(self):
        """
        Reset all counters to zero
        """
        self.total_file_exists = 0
        self.total_file_exists_size = 0
        self.total_file_skipped_not_right_type = 0
        self.total_file_symlink = 0
        self.total_file_not_found = 0
        self.total_files = 0


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
    sort_index: str = field(init=False)

    def __post_init__(self):
        # In order to sort correctly, set the sort_index field. For the .thm files, remove the first '.'
        if self.file_name.startswith("."):
            self.sort_index = self.file_name.lstrip(".")
        else:
            self.sort_index = self.file_name

    def get_file_size_gb(self) -> float:
        return self.file_size / gb_divisor


@dataclass
class Counters:
    total_files: int = 0
    total_file_skipped_not_right_type: int = 0
    total_file_symlink: int = 0
    total_file_exists: int = 0
    total_file_exists_size: int = 0
    total_file_not_found: int = 0


@dataclass
class Configuration:
    # Add your configuration fields here
    pass


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
    feature_flags: List[str] = field(default_factory=list, init=True)
    configuration: Configuration = field(default_factory=Configuration, init=True)

    files_size: int = field(default=0, init=False)
    cameras: Dict[str, Dict[str, Dict[str, Dict[str, CameraFile]]]] = field(
        default_factory=dict, init=False
    )
    counters: Counters = field(default_factory=Counters, init=False)
    current_date: str = field(default=datetime.now().strftime("%Y-%m-%d"), init=False)
    files: List[CameraFile] = field(default_factory=list, init=False)
    free_disk: int = field(default=0, init=False)
    total_disk_capacity: int = field(default=0, init=False)
    _console: Console = field(default_factory=Console, init=False)
    _features: FeatureFlagClient = None

    def __post_init__(self):
        self._features = initialize_features(self.feature_flags)
        self._multi_log = MultiLogger("securityspy", terminal=True)
        self._module_name = self.__class__.__name__

    @property
    def number_of_files(self):
        return len(self.files)

    def scan(self):
        """
        Scan the disk to generate the list of files
        """
        self._get_disk_usage()
        self._get_cameras()
        self._get_dates_for_cameras()
        self._get_files_for_dates()

    def _get_disk_usage(self):
        """
        Get the disk free space
        """
        disk_usage = psutil.disk_usage(str(self.root_dir))
        self.free_disk = disk_usage.free
        self.total_disk_capacity = disk_usage.total

    def _get_cameras(self):
        """
        Get the list of cameras
        """
        cameras = sorted(list(os.scandir(self.root_dir)), key=lambda e: e.name)
        for this_camera in cameras:
            if this_camera.name[0] == "." or not this_camera.is_dir():
                continue
            self.cameras[this_camera.name] = {"dates": dict()}

    def _get_dates_for_cameras(self):
        """
        Get the dates for each camera
        """
        for camera_name in self.cameras:
            camera_dir = self.root_dir / camera_name
            dates = sorted(
                [
                    date
                    for date in os.listdir(camera_dir)
                    if os.path.isdir(os.path.join(camera_dir, date))
                ]
            )
            for date in dates:
                if date.startswith(".") or date == self.current_date:
                    continue
                self.cameras[camera_name]["dates"][date] = {"files": {}}

    def _get_files_for_dates(self):
        """
        Get the files for each date
        """
        for camera_name, camera_data in self.cameras.items():
            for date, date_data in camera_data["dates"].items():
                date_dir = self.root_dir / camera_name / date
                files = sorted(list(os.scandir(date_dir)), key=lambda e: e.name)
                for file in files:
                    self.counters.total_files += 1
                    file_extension = os.path.splitext(file.name)[1]
                    if file_extension not in [".m4v", ".thm"]:
                        self._multi_log.log(
                            f"Skipping {file.path} (not m4v or thm)",
                            level=logging.DEBUG,
                            module=self._module_name,
                        )
                        self.counters.total_file_skipped_not_right_type += 1
                        continue
                    if file.is_symlink():
                        self._multi_log.log(
                            f"Skipping symlink {file.path}",
                            level=logging.DEBUG,
                            module=self._module_name,
                        )
                        self.counters.total_file_symlink += 1
                        continue
                    try:
                        stat = file.stat()
                        camera_file = CameraFile(
                            file_name=file.name,
                            file_path=Path(camera_name) / date / file.name,
                            file_size=stat.st_size,
                            file_date=stat.st_mtime,
                            is_symlink=file.is_symlink(),
                            file_not_found=False,
                        )
                        self.counters.total_file_exists += 1
                        self.counters.total_file_exists_size += stat.st_size
                        self.files_size += stat.st_size
                        self.files.append(camera_file)
                        self.cameras[camera_name]["dates"][date]["files"][
                            file.name
                        ] = camera_file
                    except FileNotFoundError:
                        self.counters.total_file_not_found += 1

        return
