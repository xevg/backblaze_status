from dataclasses import dataclass, field
from datetime import datetime
from PyQt6.QtGui import QColor


@dataclass
class BackupResults:
    timestamp: datetime
    file_name: str
    file_size: int
    start_time: datetime = field(default=datetime.now())
    end_time: datetime = field(default=0)
    rate: str = field(default_factory=str)
    row_color: QColor = field(default=None)
    timestamp_color: QColor = field(default=None)
    file_name_color: QColor = field(default=None)
    file_size_color: QColor = field(default=None)
    start_time_color: QColor = field(default=None)
    rate_color: QColor = field(default=None)

    def __post_init__(self):
        if self.row_color is None:
            self.row_color = QColor("white")
