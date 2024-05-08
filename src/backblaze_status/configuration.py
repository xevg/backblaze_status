import configparser
from pathlib import Path


class Configuration:
    """
    Class to manage the configuration
    """

    # Standardize some values
    kb_divisor: int = 1024
    mb_divisor: int = 1024 * kb_divisor  # 1,048,576
    gb_divisor: int = 1024 * mb_divisor  # 1,073,741,824
    tb_divisor: int = 1024 * gb_divisor  # 1,099,511,627,776
    default_chunk_size: int = 10485760  # 10 MB

    def __init__(self, configuration_file: str = None):

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
            fallback="/Volumes/CameraHDD/SecuritySpy,"
            "/Volumes/CameraHDD2/SecuritySpy,"
            "/Volumes/CameraHDD3/SecuritySpy,"
            "/Volumes/CameraHDD4/SecuritySpy",
        )
        self.secondary_disks: list = list()
        for disk in secondary_disks_string.split(","):
            self.secondary_disks.append(Path(disk.strip()))

        self.camera_directory_prefix: str = config.get(
            "camera_directory_prefix", fallback="/Volumes/CameraCache/SecuritySpy"
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

    def initialize_configuration(
        self, new_configuration_file: str = None
    ) -> configparser.ConfigParser:
        """
        Initialize the configuration. If the configuration file does not exist,
        it will be created.
        :param new_configuration_file: The configuration file
        """
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
