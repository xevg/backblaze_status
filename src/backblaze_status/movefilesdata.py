from dataclasses import dataclass, field
from pathlib import Path
from typing import NewType

from .configuration import Configuration
from .diskdata import DiskData, CameraFile
from .utils import MultiLogger

"""
Initialization of global items
"""

gb_divisor = Configuration.gb_divisor
tb_divisor = Configuration.tb_divisor

MoveFiles = NewType("MoveFiles", None)
MoveFilesApp = NewType("MoveFilesApp", None)


@dataclass
class MoveFilesData:
    """
    Store the data for the files that need to be moved for each source/destination pair
    """

    primary_disk: Path
    source: DiskData
    destination: DiskData
    size_moving_to_disk: int
    move_files: MoveFiles
    needs_prune: bool
    projection: bool
    configuration: Configuration
    move_all_eligible_files: bool = False

    _files_for_copy: list = field(default_factory=list, init=False)
    size_to_move_to_destination: int = field(default=0, init=False)
    freed_up_on_destination: int = field(default=0, init=False)

    def __post_init__(self):
        self.min_free_space_required = self.configuration.free_space_required
        # Initialize the logger
        self._multi_log = MultiLogger(
            "securityspy", terminal=True, qt=self.move_files.qt_movefiles
        )
        self._module_name = self.__class__.__name__

        # Set up files_for_copy
        # Do we need to move all the files? If so, we just do that and not worry about the sizes.
        # If we don't want to move all the files, move just enough to free up space for the files coming in,
        #   with the extra buffer

        if (
            self.required_space_to_free_up_on_source == 0
            and not self.move_all_eligible_files
        ):
            return 0

        total_size = 0
        for file in sorted(
            self.source.files, key=lambda e: e.sort_index
        ):  # type: CameraFile
            self._files_for_copy.append(file)
            total_size += file.file_size

            # End when we hit the required size
            if (
                not self.move_all_eligible_files
                and total_size > self.required_space_to_free_up_on_source
            ):
                break

        self.size_to_move_to_destination = total_size

    @property
    def summary(self) -> str:
        source_name = str(self.source.root_dir.parts[2])
        destination_name = str(self.destination.root_dir.parts[2])
        title = (
            f"Need to move {self.number_of_files:,} files"
            f" ({self.size_to_move_to_destination_gb:,.2f} GB)"
            f" from {source_name} to {destination_name}"
            f" ({self.free_space_on_destination_after_move_gb:,.2f}"
            f" GB available on {destination_name} after move,"
            f" {self.free_space_on_source_after_move_gb:,.2f}"
            f" GB available on {source_name} after all moves, "
            f"{self.free_space_on_source_after_interim_move_gb:,.2f}"
            f" GB available on {source_name} after this move)"
        )
        return title

    def output_analysis(self):
        source_name = str(self.source.root_dir.parts[2])
        destination_name = str(self.destination.root_dir.parts[2])
        title = (
            f"Need to move {self.number_of_files:,} files"
            f" ({self.size_to_move_to_destination_gb:,.2f} GB)"
            f" from {source_name} to {destination_name}"
            f" ({self.free_space_on_destination_after_move_gb:,.2f}"
            f" GB available on {destination_name} after move,"
            f" {self.free_space_on_source_after_move_gb:,.2f}"
            f" GB available on {source_name} after all moves, "
            f"{self.free_space_on_source_after_interim_move_gb:,.2f}"
            f" GB available on {source_name} after this move)"
        )
        self._multi_log.log(title, module=self._module_name)

    @property
    def free_space_on_source_before_move(self) -> int:
        """
        The free space on the source after we move all the files over to it, but before we move all the files off

        :return:
        """
        return self.source.free_disk - self.size_moving_to_disk

    @property
    def free_space_on_source_before_move_gb(self) -> float:
        """
        free_space_on_source_before_move in GB

        :return:
        """
        return self.free_space_on_source_before_move / gb_divisor

    @property
    def size_to_move_to_destination_gb(self) -> float:
        """
        size_to_move_to_destination in GB

        :return:
        """
        return self.size_to_move_to_destination / gb_divisor

    @property
    def required_space_to_free_up_on_source(self) -> int:
        """
        How much space I need to free up on the source disk for the incoming files

        :return:
        """

        # If the size moving to this disk plus the minimum free space is less than the space available,
        #   then we don't need to free up any space
        if (
            self.size_moving_to_disk + self.min_free_space_required
            < self.source.free_disk
        ):
            required_space = 0
        else:
            # If we need to free up space, we need to free up what we are moving + the minimum space required,
            #   and subtract the current free space. So if:
            #     free space: 10
            #     minimum free: 5
            #     size to move: 25
            #   25 + 5 - 10 = 20, we need to free up 20, so when we add 25 we have 5 still free

            required_space = (
                self.size_moving_to_disk
                + self.min_free_space_required
                - self.source.free_disk
            )

        return required_space

    @property
    def required_space_to_free_up_on_source_gb(self) -> float:
        """
        required_space_to_free_up_on_source in GB

        :return:
        """
        return self.required_space_to_free_up_on_source / gb_divisor

    @property
    def available_space_for_files_on_destination(self) -> int:
        """
        How much space is available for the files on the destination disk, taking into account the free space required

        :return:
        """
        return self.destination.free_disk - self.min_free_space_required

    @property
    def available_space_for_files_on_destination_gb(self) -> float:
        """
        available_space_for_files_on_destination in GB

        :return:
        """
        return self.available_space_for_files_on_destination / gb_divisor

    @property
    def free_up_on_destination(self) -> int:
        """
        free_up_on_destination is the size of the files minus the available free space. That tells us
           how much space we need to free up to allow the files to be moved

        :return:
        """
        free = (
            self.size_to_move_to_destination
            - self.available_space_for_files_on_destination
        )
        if free < 0:
            return 0
        else:
            return free

    @property
    def free_up_on_destination_gb(self) -> float:
        """
        free_up_on_destination in GB

        :return:
        """
        return self.free_up_on_destination / gb_divisor

    @property
    def free_space_on_destination_after_move(self) -> int:
        """
        How much space is left on the destination after we move the files there
        :return:
        """

        if self.freed_up_on_destination > 0:
            free_number = self.freed_up_on_destination
        else:
            free_number = self.free_up_on_destination
        return (
            self.destination.free_disk + free_number - self.size_to_move_to_destination
        )

    @property
    def free_space_on_destination_after_move_gb(self) -> float:
        """
        free_space_on_destination_after_move as GB
        :return:
        """
        return self.free_space_on_destination_after_move / gb_divisor

    @property
    def free_space_on_source_after_move(self) -> int:
        """
        How much space is left on the source after moving files out and moving files in

        :return:
        """
        return (
            self.source.free_disk
            + self.size_to_move_to_destination
            - self.size_moving_to_disk
        )

    @property
    def free_space_on_source_after_move_gb(self) -> float:
        """
        free_space_on_source_after_move as GB
        :return:
        """
        return self.free_space_on_source_after_move / gb_divisor

    @property
    def free_space_on_source_after_interim_move(self) -> int:
        """
        How much space is there after the files move off, but before we move the files on
        :return:
        """
        return self.source.free_disk + self.size_to_move_to_destination

    @property
    def free_space_on_source_after_interim_move_gb(self) -> float:
        return self.free_space_on_source_after_interim_move / gb_divisor

    @property
    def number_of_files(self) -> int:
        return len(self.files_for_copy)

    @property
    def files_for_copy(self) -> list[CameraFile]:
        return self._files_for_copy
