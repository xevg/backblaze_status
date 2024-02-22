from pathlib import Path
import click
import configparser


class Configuration:
    kb_divisor: int = 1024
    mb_divisor: int = 1024 * kb_divisor
    gb_divisor: int = 1024 * mb_divisor  # 1000000000
    tb_divisor: int = 1024 * gb_divisor  # 1000000000000
    default_chunk_size: int = 10485760

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
            "default": False,
            "help": "Display information about symlinks",
        },
        "show_missing_m4v": {
            "usage": "clean",
            "default": True,
            "help": "Display missing m4v files",
        },
        "show_files": {
            "usage": "clean",
            "default": False,
            "help": "Display info about the files",
        },
        "show_empty_directories": {
            "usage": "clean",
            "default": False,
            "help": "Display empty directories",
        },
        "show_relink_symlinks": {
            "usage": "clean",
            "default": False,
            "help": "Display symlinks that need to be relinked",
        },
        "show_bad_symlinks": {
            "usage": "clean",
            "default": False,
            "help": "Display bad symlinks",
        },
        "show_bad_files": {
            "usage": "clean",
            "default": True,
            "help": "Display bad files",
        },
    }

    def __init__(self, configuration_file: str = None):
        self.gb_divisor = 1000000000
        self.tb_divisor = 1000000000000

        if configuration_file:
            self.configuration_file: str = configuration_file
        else:
            self.configuration_file: str = str(
                Path.home() / ".config" / "securityspy-tools.ini"
            )

        # Read the configuration file and assign the configuration
        self.configuration: configparser.ConfigParser = configparser.ConfigParser()
        config = self.configuration["DEFAULT"]
        self.primary_disk: Path = Path(
            config.get("primary_disk", fallback="/Volumes/CameraCache")
        )

        secondary_disks_string: str = config.get(
            "secondary_disks",
            fallback="/Volumes/CameraHDD/SecuritySpy, /Volumes/CameraHDD2/SecuritySpy, /Volumes/CameraHDD3/SecuritySpy",
        )
        self.secondary_disks: list = list()
        for disk in secondary_disks_string.split(","):
            self.secondary_disks.append(Path(disk.strip()))

        self.camera_directory_prefix: str = config.get(
            "camera_directory_prefix", fallback="/Volumes/Camera"
        )
        self.logfile_dir: Path = Path(
            config.get("logfile_dir", fallback=f"{Path.home()}/logs")
        )

        self.bz_package_dir: Path = Path(
            config.get(
                "bz_package_dir", fallback="/Library/Backblaze.bzpkg/bzdata/bzbackup"
            )
        )
        self.BZ_KNOWN_FILE_LIST: Path = self.bz_package_dir / "bzfileids.dat"
        self.BZ_TODO_DIRECTORY: Path = self.bz_package_dir / "bzdatacenter"

        self.free_space_required: int = config.getint(
            "free_space_required", fallback=500
        )

        self.DEFAULT_CONFIGURATION = f"""[DEFAULT]

primary_disk = {self.primary_disk}
secondary_disks = {secondary_disks_string}

camera_directory_prefix = {self.camera_directory_prefix}

logfile_dir = {self.logfile_dir}

bz_package_dir = {self.bz_package_dir}

# The amount of free space required on each disk

free_space_required = {self.free_space_required}

"""

        self.free_space_required = self.free_space_required * self.gb_divisor

        self.configuration = self.initialize_configuration()

        self.available_features: str = """
\b
"""
        for key in self.default_feature_flags.keys():
            if self.default_feature_flags[key]["usage"] == "all":
                self.available_features += (
                    f"     {click.style(key, fg='bright_red')}:"
                    f" {self.default_feature_flags[key]['help']}\n"
                )
        self.available_features += f"\n\n"

        self.available_clean_features: str = """
\b
"""
        for key in self.default_feature_flags.keys():
            if (
                self.default_feature_flags[key]["usage"] == "all"
                or self.default_feature_flags[key]["usage"] == "clean"
            ):
                self.available_clean_features += (
                    f"     {click.style(key, fg='bright_red')}:"
                    f" {self.default_feature_flags[key]['help']}\n"
                )
        self.available_clean_features += f"\n\n"

    def initialize_configuration(
        self, new_configuration_file: str = None
    ) -> configparser.ConfigParser:
        if not new_configuration_file:
            new_configuration_file = self.configuration_file

        if not Path(new_configuration_file).exists():
            with Path(new_configuration_file).open("w") as f:
                f.write(self.DEFAULT_CONFIGURATION)

        configuration = configparser.ConfigParser()
        configuration.read(new_configuration_file)

        config = configuration["DEFAULT"]

        self.primary_disk: Path = Path(config.get("primary_disk"))

        secondary_disks_string: str = config.get("secondary_disks")
        self.secondary_disks: list = list()
        for disk in secondary_disks_string.split(","):
            self.secondary_disks.append(Path(disk.strip()))

        self.camera_directory_prefix: str = config.get("camera_directory_prefix")
        self.logfile_dir: Path = Path(config.get("logfile_dir"))

        self.bz_package_dir: Path = Path(config.get("bz_package_dir"))
        self.BZ_KNOWN_FILE_LIST: Path = self.bz_package_dir / "bzfileids.dat"
        self.BZ_TODO_DIRECTORY: Path = self.bz_package_dir / "bzdatacenter"

        self.free_space_required: int = (
            config.getint("free_space_required") * self.gb_divisor
        )
        return configuration
