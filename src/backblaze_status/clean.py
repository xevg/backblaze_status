import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path

from flipper import FeatureFlagClient
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from .configuration import Configuration
from .utils import initialize_features


@dataclass
class Clean:
    primary_disk: str
    secondary_disks: list
    dry_run: bool = False
    feature_flags: list = field(default_factory=list, init=True)
    configuration: configparser.ConfigParser = field(
        default_factory=Configuration, init=True
    )

    _disks: list = field(default_factory=list, init=False)
    _features: FeatureFlagClient = None
    _console: Console = field(default_factory=Console, init=False)

    def __post_init__(self) -> None:
        self._features = initialize_features(self.feature_flags)
        self.clean()

    class NoValidSymlink(Exception):
        pass

    def check_bad_symlink(self, path: Path) -> Path:
        path_parts = list(path.parts)
        for disk in self.secondary_disks:
            path_parts[2] = disk
            path_parts.insert(3, "SecuritySpy")

            new_sym_path = Path(*path_parts)
            if new_sym_path.is_file():
                return new_sym_path

        raise self.NoValidSymlink

    def clean(self):
        root_volumes = [self.primary_disk] + self.secondary_disks
        # f"{y}/SecuritySpy" for y in self.secondary_disks]

        for root_dir in root_volumes:
            bad_symlinks = 0
            good_symlinks = 0
            wrong_symlinks = 0
            missing_symlinks = 0
            bad_files = 0
            good_files = 0
            empty_directories = 0
            missing_m4v_files = 0

            relink_symlink_list = list()
            bad_symlink_list = list()
            bad_file_list = list()
            empty_directory_list = list()
            missing_m4v_file_list = list()

            for root, dirs, files in os.walk(root_dir):
                # Check for empty directories
                if len(files) == 0 and len(dirs) == 0:
                    if self._features.is_enabled("show_empty_directories"):
                        self._console.print(f"[orange]Empty Directory: {root}")
                    empty_directories += 1
                    empty_directory_list.append(Path(root))
                    continue

                for file in files:
                    filepath = Path(root) / file

                    # Check for missing m4v files on the primary drive
                    if root_dir == f"/Volumes/{self.primary_disk}":
                        if filepath.is_symlink() and filepath.suffix == ".thm":
                            check_filename = filepath.parent
                            file_string = str(filepath.stem)
                            check_filename = check_filename / str(
                                file_string[1:] + ".m4v"
                            )
                            if not check_filename.exists():
                                if self._features.is_enabled("show_missing_m4v"):
                                    self._console.print(
                                        f"Missing m4v file for {filepath}"
                                    )
                                missing_m4v_files += 1
                                missing_m4v_file_list.append(filepath)

                    # Check for symlinks
                    if filepath.is_symlink():
                        if not filepath.is_file():
                            try:
                                new_symlink = self.check_bad_symlink(filepath)
                                if self._features.is_enabled("show_relink_symlinks"):
                                    self._console.print(
                                        f"[green]Relink missing {filepath} to {new_symlink}"
                                    )
                                missing_symlinks += 1
                                relink_symlink_list.append(
                                    {"source": filepath, "destination": new_symlink}
                                )

                            except self.NoValidSymlink:
                                if self._features.is_enabled("show_bad_symlinks"):
                                    self._console.print(
                                        f"[red]Bad symlink for {filepath} ({filepath.readlink()}). Delete"
                                    )
                                bad_symlink_list.append(filepath)
                                bad_symlinks += 1
                        else:
                            linkpath = filepath.readlink().parts
                            if self._features.is_enabled("show_symlinks"):
                                self._console.print(
                                    f"Valid symlink {filepath} ({linkpath[2]})"
                                )
                            good_symlinks += 1

                    # Check for files
                    else:
                        if not filepath.is_file():
                            if self._features.is_enabled("show_bad_files"):
                                self._console.print(f"[red]Bad file {filepath}")
                            bad_file_list.append(filepath)
                            bad_files += 1
                        else:
                            if self._features.is_enabled("show_files"):
                                self._console.print(f"Valid file {filepath}")
                            good_files += 1

                        # Repair symlinks. Don't do it on the primary drive
                        exception_list = [".DS_Store", ".FF_Index"]
                        if root_dir != f"/Volumes/{self.primary_disk}":
                            if (
                                filepath.name not in exception_list
                                and filepath.parts[4] != "Saved"
                            ):
                                parts = list(filepath.parts)
                                parts[2] = self.primary_disk
                                del parts[3]  # Remove the "SecuritySpy" component
                                new_path = Path(*parts)

                                # If there is no file from the primary directory pointing to this file, add it
                                if not new_path.exists():
                                    if self._features.is_enabled(
                                        "show_relink_symlinks"
                                    ):
                                        self._console.print(
                                            f"[green]Relink missing {new_path} to {filepath}"
                                        )
                                    missing_symlinks += 1
                                    relink_symlink_list.append(
                                        {"source": new_path, "destination": filepath}
                                    )

                                # If the file does exist ...
                                else:
                                    # and it is not a symlink, then the file in the secondary directory should be
                                    # removed.
                                    if not new_path.is_symlink():
                                        self._console.print(
                                            f"[orange]File {filepath} should not exist"
                                        )
                                        bad_files += 1
                                        bad_file_list.append(filepath)

                                    # and the file is a symlink, but the symlink doesn't point here, relink it
                                    else:
                                        if new_path.readlink() != filepath:
                                            if self._features.is_enabled(
                                                "show_relink_symlinks"
                                            ):
                                                self._console.print(
                                                    f"[green]Relink wrong {new_path} to {filepath}"
                                                )
                                            wrong_symlinks += 1
                                            relink_symlink_list.append(
                                                {
                                                    "source": new_path,
                                                    "destination": filepath,
                                                }
                                            )

            counter_table = Table(title=f"Cleanup on {root_dir}")

            counter_table.add_column("", justify="left")
            counter_table.add_column("Value", justify="right")

            counter_table.add_row("Empty Directories", f"{empty_directories:,}")
            counter_table.add_row("Good Symlinks", f"{good_symlinks:,}")
            counter_table.add_row("Missing Symlinks", f"{missing_symlinks:,}")
            counter_table.add_row("Wrong Symlinks", f"{wrong_symlinks:,}")
            counter_table.add_row("Bad Symlinks", f"{bad_symlinks:,}")
            counter_table.add_row("Good Files", f"{good_files:,}")
            counter_table.add_row("Bad Files", f"{bad_files:,}")
            counter_table.add_row("Missing m4v Files", f"{missing_m4v_files:,}")
            counter_table.add_row(Rule(), Rule())
            counter_table.add_row(
                "[bold]Total:",
                f"[bold]{good_files + good_symlinks + bad_files + bad_files:,}",
            )

            self._console.print(counter_table)

            # Do the actual deletion unless we are doing a dry run
            if not self.dry_run:
                if len(empty_directory_list) > 0:
                    self._console.print(f"Removing empty directories")
                    for directory in empty_directory_list:
                        try:
                            directory.rmdir()
                            self._console.print(f"Removed directory {directory}")
                        except Exception as exp:
                            self._console.print(
                                f"[red]Failed to remove directory {directory}: {exp}"
                            )

                if len(missing_m4v_file_list) > 0:
                    self._console.print("Removing .thm files with no matching m4v file")
                    for missing_file in missing_m4v_file_list:
                        try:
                            # First unlink the thm that the symlink is pointing to, then the thm file
                            missing_file.readlink().unlink()
                            self._console.print(
                                f"Removed unmatched file {missing_file.readlink()}"
                            )
                            missing_file.unlink()
                            self._console.print(
                                f"Removed unmatched file {missing_file}"
                            )
                        except Exception as exp:
                            self._console.print(
                                f"[red]Failed to remove unmatched file {missing_file}: {exp}"
                            )

                if len(bad_symlink_list) > 0:
                    self._console.print(f"Removing orphaned symlinks")
                    for symlink in bad_symlink_list:  # type: Path
                        try:
                            symlink.unlink()
                            self._console.print(f"Removed orphaned symlink {symlink}")
                        except Exception as exp:
                            self._console.print(
                                f"[red]Failed to remove orphaned symlink {symlink}: {exp}"
                            )

                if len(relink_symlink_list) > 0:
                    self._console.print(f"Relinking broken symlinks")
                    for symlink in relink_symlink_list:  # type: dict
                        source: Path = symlink["source"]
                        destination: Path = symlink["destination"]
                        try:
                            source.unlink(missing_ok=True)
                            source.parent.mkdir(exist_ok=True)
                            source.symlink_to(destination)
                            self._console.print(
                                f"Set symlink {source} to {destination}"
                            )
                        except Exception as exp:
                            self._console.print(
                                f"[red]Failed to change symlink {source} to {destination}: {exp}"
                            )


if __name__ == "__main__":
    default_feature_flags: dict = {
        "show_progress_bar": {
            "usage": "all",
            "default": True,
            "help": "Display progress bars",
        },
        "show_disk_info": {
            "usage": "all",
            "default": True,
            "help": "Show addition information about the disks",
        },
        "show_symlinks": {
            "usage": "clean",
            "default": True,
            "help": "Display information about symlinks",
        },
        "show_missing_m4v": {
            "usage": "clean",
            "default": True,
            "help": "Display missing m4v files",
        },
        "show_files": {
            "usage": "clean",
            "default": True,
            "help": "Display info about the files",
        },
        "show_empty_directories": {
            "usage": "clean",
            "default": True,
            "help": "Display empty directories",
        },
        "show_relink_symlinks": {
            "usage": "clean",
            "default": True,
            "help": "Display symlinks that need to be relinked",
        },
        "show_bad_symlinks": {
            "usage": "clean",
            "default": True,
            "help": "Display bad symlinks",
        },
        "show_bad_files": {
            "usage": "clean",
            "default": True,
            "help": "Display bad files",
        },
    }
    Clean(
        "CameraCache",
        [
            "CameraHDD",
            "CameraHDD2",
            "CameraHDD3",
        ],
        dry_run=True,
    )
