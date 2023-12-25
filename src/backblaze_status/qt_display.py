from PyQt6.QtCore import Qt
from .display import Display
from icecream import ic
from .qt_movefiles import QTMoveFiles


# QT_QPA_PLATFORM_PLUGIN_PATH=/Users/xev/opt/anaconda3/envs/backblaze_tools/lib/python3.11/site-packages/PyQt6/Qt6/plugins/platforms;
class QtDisplay(Display):
    def __init__(self, display):
        ic.configureOutput(includeContext=True)
        self.qt: QTMoveFiles = display
        self.signals = self.qt.signals
        self.color_map = {
            "magenta": Qt.GlobalColor.magenta,
            "cyan": Qt.GlobalColor.cyan,
            "white": Qt.GlobalColor.white,
            "yellow": Qt.GlobalColor.yellow,
            "green": Qt.GlobalColor.green,
            "red": Qt.GlobalColor.red,
            "blue": Qt.GlobalColor.blue,
        }
        self.tablemap = {
            "diskinfo": self.qt.diskinfo,
        }

        self.alignment_map = {
            "right": Qt.AlignmentFlag.AlignRight,
            "center": Qt.AlignmentFlag.AlignHCenter,
            "left": Qt.AlignmentFlag.AlignLeft,
        }

    def update_disk_cell(self, disk_name: str, column_index: int, table: str, item):
        # ic(f"update_disk_cell({disk_name}, {column_index}, {table}, {item})")
        self.signals.update_cell.emit(
            self.qt.volume_info[disk_name]["row_index"],
            column_index,
            self.tablemap[table],
            item,
        )

    def update_disk_color(self, disk_name: str, color: str):
        # ic(f"update_disk_color({disk_name}, {color})")
        # ic(
        #     f'self.signals.update_disk_color.emit({self.qt.volume_info[disk_name]["row_index"]},'
        #     f" {self.color_map[color]})"
        # )
        self.signals.update_disk_color.emit(
            self.qt.volume_info[disk_name]["row_index"], self.color_map[color]
        )

    def add_pre_data_row(self, row_data):
        # ic(f"add_pre_data_row({row_data}")
        self.signals.add_pre_data_row.emit(row_data)

    def stop_interval_timer(self):
        # ic("stop_interval_timer")
        self.signals.stop_interval_timer.emit()

    def update_data_table_last_row(self, row_data):
        # ic(f"update_data_table_last_row({row_data}")
        self.signals.update_data_table_last_row.emit(row_data)

    def add_table_item(self, text: str, alignment: str = "left", color: str = "white"):
        # ic(f"add_table_item({text}, {alignment}, {color})")
        return self.qt.add_table_item(
            text,
            alignment=self.alignment_map[alignment],
            color=self.color_map[color],
        )
