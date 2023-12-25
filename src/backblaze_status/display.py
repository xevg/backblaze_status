from abc import ABC, abstractmethod


class Display(ABC):
    pass

    @abstractmethod
    def update_disk_cell(self, disk_name: str, column_index: int, table: str, item):
        pass

    @abstractmethod
    def update_disk_color(self, disk_name: str, color: str):
        pass

    @abstractmethod
    def add_pre_data_row(self, row_data):
        pass

    @abstractmethod
    def stop_interval_timer(self):
        pass

    @abstractmethod
    def update_data_table_last_row(self, row_data):
        pass

    @abstractmethod
    def add_table_item(self, text: str, alignment: str = None, color: str = None):
        pass
