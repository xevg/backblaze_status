import shutil
import os

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

from dataclasses import dataclass, field
from pathlib import Path

from flipper import FeatureFlagClient

from .configuration import Configuration
from .consolidate_move_file_list import ConsolidatedMoveFilesList
from .diskdata import DiskData

# from .movefiles_app import MoveFilesApp
from .movefilesdata import MoveFilesData
from .qt_movefiles import QTMoveFiles
from .utils import (
    initialize_features,
    MultiLogger,
)

"""
Initialization of global items
"""

gb_divisor = Configuration.gb_divisor
tb_divisor = Configuration.tb_divisor

default_feature_flags = Configuration.default_feature_flags


@dataclass
class MoveFiles:
    """
    This is the main MoveFiles class that does all the work of moving the files

    :param primary_disk: The directory for the primary disk
    :param secondary_disks: A list of secondary disks
    :param feature_flags: Feature flags for turning things on or off
    :param configuration: A Configuration() instance, or create a new one
    :param full_disk_scan: If this is True, then even if we don't need room on additional disks, scan them anyway
    :param move_all_eligible: If this is True, move all the files from one disk to the next,
            not just enough to free yp the appropriate amount of space. Usually just used for the first disk.
    :param projection: If this is true, show a projection of what would happen, but don't actually move anything
    :param move_app: If this is called by the Textual MoveFile class, then this is a pointer to that
    """

    primary_disk: str
    secondary_disks: list
    feature_flags: list = None
    configuration: Configuration = field(default_factory=Configuration)
    full_disk_scan: bool = True
    move_all_eligible: bool = True
    projection: bool = False
    # move_app: MoveFilesApp | None = None
    qt_movefiles: QTMoveFiles | None = None

    def __post_init__(self):
        """
        Set up all the internal variables needed
        :return:
        """
        self.source: DiskData | None = None
        self.destination: DiskData | None = None
        self.files_to_copy: list | None = None

        # self.consolidated_data_list = ConsolidatedMoveFilesList(self, self.move_app)
        self.consolidated_data_list = ConsolidatedMoveFilesList(self, None)

        # This will be printed to the terminal at the end
        self.return_message: list = []

        # Initialize the featureflags
        self._features: FeatureFlagClient = initialize_features(self.feature_flags)

        # Create a new DiskData object for all the disks, and add them all to the self.disks list
        self.disks = [
            DiskData(Path(self.primary_disk), configuration=self.configuration)
        ] + [
            DiskData(Path(disk), configuration=self.configuration)
            for disk in self.secondary_disks
        ]

        # Initialize the logger
        self._multi_log = MultiLogger(
            "securityspy", terminal=True, qt=self.qt_movefiles
        )
        self._module_name = self.__class__.__name__
        self._multi_log.log("Starting MoveFiles", module=self._module_name)

        # Scan all the disks. See scan_disks() for more information
        self.scan_disks()

    def scan_disks(self):
        """
        Scan all the disks that we are using
        :return:
        """

        total_free_space = 0
        total_number_of_files = 0
        total_size_of_files = 0
        total_disk_capacity = 0

        for disk in self.disks:
            disk.scan()

            # If we have debug turned out, output all the metrics of the disk
            log_lines = [
                f"Scanned Disk: {disk.root_dir}",
                f"                  Files to Copy: {disk.counters.total_file_exists:,}",
                f"                  Size of Files: {disk.counters.total_file_exists_size / gb_divisor:,.2f} GB",
                f" Files Skipped - Not Right Type: {disk.counters.total_file_skipped_not_right_type:,}",
                f"  Files Skipped - Symlink Files: {disk.counters.total_file_symlink:,}",
                f"                  Missing Files: {disk.counters.total_file_not_found:,}",
                f"                    Total Files: {disk.counters.total_files:,}",
                f"                       Capacity: {disk.total_disk_capacity / tb_divisor:,.2f} TB",
                f"                     Free Space: {disk.free_disk / gb_divisor:,.2f} GB",
                f"                Percentage Free: {disk.free_disk / disk.total_disk_capacity:.0%}",
                f"                Number of Files: {disk.number_of_files:,}",
                f"                  Size of Files: {disk.files_size / gb_divisor:,.2f} GB",
            ]

            [
                self._multi_log.log(log_line, module=self._module_name)
                for log_line in log_lines
            ]

        # Add the details of that disk to the totals of all disks
        total_free_space += sum(disk.free_disk for disk in self.disks)
        total_number_of_files += sum(disk.number_of_files for disk in self.disks)
        total_size_of_files += sum(disk.files_size for disk in self.disks)
        total_disk_capacity += sum(disk.total_disk_capacity for disk in self.disks)

        # When we have scanned all the disks, then if we are running in debug mode, print out the totals
        log_lines = [
            f"Total:",
            f"          Total Capacity: {total_disk_capacity / tb_divisor:,.2f} TB",
            f"        Total Free Space: {total_free_space / gb_divisor:,.2f} GB",
            f"   Total Percentage Free: {total_free_space / total_disk_capacity:.0%}",
            f"   Total Number of Files: {total_number_of_files:,}",
            f"     Total Size of Files: {total_size_of_files / gb_divisor:,.2f} GB",
        ]

        [
            self._multi_log.log(log_line, module=self._module_name)
            for log_line in log_lines
        ]

    def _get_required_space(
        self, source_disk, destination_disk, additional_size_required=0
    ) -> int:
        """
        A class method to get the required space on the source disk
        :param source_disk:
        :param destination_disk:
        :param additional_size_required:
        :return:
        """

        # If the space required to move is more than the amount on disk plus the required overhead,
        #   we need to free up space

        if additional_size_required == 0:
            additional_size_required = source_disk.files_size

        extra_free_space = (
            self.configuration.free_space_required
            - (destination_disk.free_disk - additional_size_required)
            if destination_disk.free_disk - additional_size_required
            < self.configuration.free_space_required
            else 0
        )

        return extra_free_space

    def prepare_required_files(
        self,
        caches: list[DiskData] = None,
        move_all_eligible_files: bool = False,
        size_moving_to_disk: int = 0,
    ) -> int:
        """
        This method makes a list of the files that are required to move. The way this works is that there are multiple
          volumes that we can move files to. The oldest are taken from the SecuritySpy cache to the first disk. If there
          isn't enough room on the first disk, then the oldest files from the first disk are moved to the second disk.
          If there isn't enough space on the second disk, the oldest files are moved to the third disk. Etc.

        :param caches: The list of directories where SecuritySpy stores its files
        :param move_all_eligible_files: If true, this moves all the files that it can. If false, it only moves enough
            to get to the free space that it needs
        :param size_moving_to_disk: How much free space is needed in bytes
        """

        caches = caches or self.disks

        cache_name = caches[0].root_dir if caches else None

        self._multi_log.log(
            f"Entering <prepare_required_files> Caches: {cache_name}",
            module=self._module_name,
        )

        needs_prune = len(caches) <= 2

        source: DiskData = caches[0]
        destination: DiskData = caches[1]

        # Create a MoveFilesData object for this source/destination combination

        move_files_data = MoveFilesData(
            Path(self.primary_disk),
            source,
            destination,
            size_moving_to_disk,
            self,
            needs_prune,
            self.projection,
            self.configuration,
            move_all_eligible_files=move_all_eligible_files,
        )

        if not needs_prune:
            # We only do this until we hit the last volume
            move_files_data.freed_up_on_destination = self.prepare_required_files(
                caches[1:],
                size_moving_to_disk=move_files_data.size_to_move_to_destination,
                move_all_eligible_files=False,
            )

        # Add the move_files_data to the list
        self.consolidated_data_list.add_files_data(move_files_data)
        move_files_data.output_analysis()
        return move_files_data.size_to_move_to_destination

    def remove_directory(self, directory: Path) -> None:
        """
        Try removing a directory. Because macOS puts in the .FF_Index file, it won't remove the directory, so first
          try and delete the file, then try and delete the directory. In all cases it's ok to fail, so just don't return
          anything
        """

        if os.path.isdir(directory):
            try:
                shutil.rmtree(directory)
                self._multi_log.log(
                    # f"Directory '{directory}' has been removed successfully", color="purple"
                    f"Directory '{directory}' has been removed successfully",
                    module=self._module_name,
                )
            except OSError:
                # I don't care if it fails
                pass

        return


async def run_basic():
    move_app = MoveFiles(
        "/Volumes/CameraCache",
        [
            "/Volumes/CameraHDD/SecuritySpy",
            "/Volumes/CameraHDD2/SecuritySpy",
            "/Volumes/CameraHDD3/SecuritySpy",
            "/Volumes/CameraHDD4/SecuritySpy",
        ],
    )
    move_app.prepare_required_files(move_all_eligible_files=True)
    pass


if __name__ == "__main__":
    # print("Starting movefile main")
    # asyncio.run(run_basic())

    app = MoveFiles(
        "/Volumes/CameraCache",
        [
            "/Volumes/CameraHDD/SecuritySpy",
            "/Volumes/CameraHDD2/SecuritySpy",
            "/Volumes/CameraHDD3/SecuritySpy",
            "/Volumes/CameraHDD4/SecuritySpy",
        ],
        projection=True,
    )
    reply = app.run()
    # a = app
    # a.scan_disks()
    # a.console.print(Rule("Estimating files"))
    # a.prepare_required_files(move_all_eligible=True, projection=True)
    # a.console.print(Rule("Moving files"))
    # a.prepare_required_files(move_all_eligible=True)
    pass
