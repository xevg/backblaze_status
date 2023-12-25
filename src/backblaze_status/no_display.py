from .display import Display


class NoDisplay(Display):
    pass

    def update_disk_cell(self, disk_name: str, column_index: int, table: str, item):
        pass

    def update_disk_color(self, disk_name: str, color: str):
        pass

    def add_pre_data_row(self, row_data):
        pass

    def stop_interval_timer(self):
        pass

    def update_data_table_last_row(self, row_data):
        pass

    def add_table_item(self, text: str, alignment: str = None, color: str = None):
        pass
