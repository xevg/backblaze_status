from PyQt6 import QtCore
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase, QFont
from PyQt6.QtWidgets import (
    QLabel,
    QWidget,
    QGroupBox,
    QHBoxLayout,
    QProgressBar,
    QSizePolicy,
    QMenuBar,
    QStatusBar,
    QHeaderView,
    QVBoxLayout,
    QAbstractItemView,
    QTableView,
    QPushButton,
)

from .chunk_dialog import ChunkDialog
from .css_styles import CssStyles


class UiMainWindow(object):
    """
    This class defines the UI main window.
    """

    def setup_ui(self, MainWindow):

        # Set the name of the window and the default size
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(2100, 1000)

        # Define the font to use when I need a fixed font
        self.messlo_font = QFontDatabase.font("MessloLGS NF", "", 12)
        self.fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.fixed_font.setStyleHint(QFont.StyleHint.Monospace)
        self.fixed_font.setPointSize(12)

        # QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)

        # The main widget
        self.central_widget = QWidget(parent=MainWindow)
        self.central_widget.setObjectName("centralWidget")
        size_policy = QSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )
        self.central_widget.setSizePolicy(size_policy)
        # I'm using a stylesheet
        self.central_widget.setStyleSheet(CssStyles.dark_orange)

        """
        The chunk box is shown if it is a large file, otherwise the file info box is 
        shown.
        
                          **** Layout ****
                          
        +---------------------------------------------------+
        |                                                   |
        |                                                   |
        |                  data_model_table                 |
        |                                                   |
        +---------------------------------------------------+
        |                  chunk_box (visible)              |
        +---------------------------------------------------+
        |                  file_info_box (hidden)           |
        +---------------------------------------------------+
        |          stat_box                     |    Clock  |
        +---------------------------------------------------+
        |                  progress_box                     |
        +---------------------------------------------------+
        """

        # The main container that holds everything
        self.main_vertical_container = QVBoxLayout(self.central_widget)
        self.main_vertical_container.setObjectName("verticalLayout")

        # Set up the data model table, and add it to the main container
        self.data_model_table = self.create_data_model_table()
        self.data_model_table.setWordWrap(True)
        self.data_model_table.horizontalHeader().sectionResized.connect(
            self.data_model_table.resizeRowsToContents
        )
        self.main_vertical_container.addWidget(self.data_model_table)

        # Set up the chunk box and add it to main container
        self.chunk_box = self.large_file_box()
        self.main_vertical_container.addWidget(self.chunk_box)

        # Set up the file info box. It is hidden until needed
        self.file_info = self.create_label_box(
            "FileInfo", placeholder="Waiting to start processing ..."
        )
        self.file_info.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.file_info.hide()
        self.main_vertical_container.addWidget(self.file_info)

        # Set up the groupbox that holds the stats as well as a clock. The clock is
        # mainly there for me to see that the GUI is processing, but it's also good
        # when I am looking at the timestamps.

        self.stat_groupbox = QGroupBox(parent=self.central_widget)
        self.stat_groupbox.setObjectName("StatGroupbox")

        # Create a horizontal layout that the stats box and the clock go into
        self.stats_horizontal_Layout = QHBoxLayout(self.stat_groupbox)
        self.stats_horizontal_Layout.setObjectName("StatsHorizontalLayout")
        self.stats_horizontal_Layout.setContentsMargins(0, 0, 0, 0)

        self.stats_info = self.create_label_box(
            "StatsInfo",
            parent=self.stat_groupbox,
            placeholder="Waiting for data ...",
        )
        size_policy = QSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )
        # This sets the size so that the stats box to clock box ratio is 7:1
        size_policy.setHorizontalStretch(7)
        size_policy.setVerticalStretch(0)
        size_policy.setHeightForWidth(self.stats_info.sizePolicy().hasHeightForWidth())
        self.stats_info.setSizePolicy(size_policy)

        self.stats_horizontal_Layout.addWidget(self.stats_info)

        self.clock_display = self.create_label_box(
            "Clock",
            parent=self.stat_groupbox,
            placeholder="Clock",
        )
        size_policy = QSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )
        size_policy.setHorizontalStretch(1)
        size_policy.setVerticalStretch(0)
        size_policy.setHeightForWidth(
            self.clock_display.sizePolicy().hasHeightForWidth()
        )
        self.clock_display.setSizePolicy(size_policy)
        self.stats_horizontal_Layout.addWidget(self.clock_display)

        # Add the group box to the main container
        self.main_vertical_container.addWidget(self.stat_groupbox)

        # Set up the total progress bar. The progress bar consists of:
        #  A "Total:" label
        #  A QProgressBar
        #  A label box with elapsed time
        #  A label box for the progress
        #  A label box for time remaining
        #  A label box for projected completion time
        #  A label box for rate
        #
        # Those all go into a group box

        self.progress_groupbox = QGroupBox(parent=self.central_widget)
        self.progress_groupbox.setObjectName("ProgressGroupbox")

        self.progress_horizontal_layout = QHBoxLayout(self.progress_groupbox)
        self.progress_horizontal_layout.setObjectName("horizontalLayout")

        self.progress_bar_header = QLabel(parent=self.progress_groupbox)
        self.progress_bar_header.setObjectName("header")
        self.progress_horizontal_layout.addWidget(self.progress_bar_header)
        self.progress_bar_header.setText("Total:")
        self.progress_bar_header.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.progress_bar_header.setFont(self.fixed_font)

        self.progressBar = QProgressBar(parent=self.progress_groupbox)
        self.progressBar.setObjectName("OrangeProgressBar")
        self.progress_horizontal_layout.addWidget(self.progressBar)
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(100)
        self.progressBar.setValue(0)

        self.elapsed_time = QLabel(parent=self.progress_groupbox)
        self.elapsed_time.setObjectName("ElapsedTime")
        self.progress_horizontal_layout.addWidget(self.elapsed_time)
        self.elapsed_time.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.elapsed_time.setFont(self.fixed_font)
        self.elapsed_time.setText("Elapsed Time: Calculating ...")

        self.progress = QLabel(parent=self.progress_groupbox)
        self.progress.setObjectName("Progress")
        self.progress_horizontal_layout.addWidget(self.progress)
        self.progress.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.progress.setFont(self.fixed_font)
        self.progress.setText("Progress: Calculating ...")

        self.time_remaining = QLabel(parent=self.progress_groupbox)
        self.time_remaining.setObjectName("TimeRemaining")
        self.progress_horizontal_layout.addWidget(self.time_remaining)
        self.time_remaining.setFont(self.fixed_font)
        self.time_remaining.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.time_remaining.setText("Time Remaining: Calculating ...")

        self.completion_time = QLabel(parent=self.progress_groupbox)
        self.completion_time.setObjectName("CompletionTime")
        self.progress_horizontal_layout.addWidget(self.completion_time)
        self.completion_time.setFont(self.fixed_font)
        self.completion_time.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.completion_time.setText("Completion Time: Calculating ...")

        self.rate = QLabel(parent=self.progress_groupbox)
        self.rate.setObjectName("Rate")
        self.progress_horizontal_layout.addWidget(self.rate)
        self.rate.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.rate.setFont(self.fixed_font)
        self.rate.setText("Rate: Calculating ...")

        # Add the progress group to the main container
        self.main_vertical_container.addWidget(self.progress_groupbox)

        # Set the main window widget
        MainWindow.setCentralWidget(self.central_widget)

        # There is also a menubar that I set up. I will add to the status bar in the
        # QtBackupStatus class

        self.menubar = QMenuBar(parent=MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 24))
        self.menubar.setObjectName("menubar")
        self.setMenuBar(self.menubar)
        self.option_menu = self.menubar.addMenu("Options")

        self.statusbar = QStatusBar(parent=MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        # Connect all the slots
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def large_file_box(self):
        """
        Create the box that is shown if there is a large file. This box has:
          A group box to hold everything
          A horizontal container
            Another group box to hold the progress bars
                A vertical container
                    A prepare progress bar
                    A transmit progress bar
            A label box for the file name
            A chunk table
            A button to show the dialog box

        The button to show the dialog box is only visible if there is a file large
        enough to require one
        """
        chunk_group_box = QGroupBox(self.central_widget)
        chunk_group_box.setObjectName("ChunkGroupBox")
        chunk_group_box.setMaximumHeight(150)
        horizontal = QHBoxLayout(chunk_group_box)
        horizontal.setObjectName("ChunkBoxHorizontal")

        chunk_progress_group_box = QGroupBox(chunk_group_box)
        chunk_progress_group_box.setObjectName("ChunkProgressGroupBox")
        chunk_progress_layout = QVBoxLayout(chunk_progress_group_box)
        chunk_progress_group_box.setLayout(chunk_progress_layout)

        horizontal.addWidget(chunk_progress_group_box)

        self.transmit_chunk_progress_bar = QProgressBar(chunk_group_box)
        self.transmit_chunk_progress_bar.setObjectName("TransmitProgressBar")
        # self.transmit_chunk_progress_bar.hide()

        self.prepare_chunk_progress_bar = QProgressBar(chunk_group_box)
        self.prepare_chunk_progress_bar.setObjectName("PrepareProgressBar")
        # self.prepare_chunk_progress_bar.hide()

        chunk_progress_layout.addWidget(self.prepare_chunk_progress_bar)
        chunk_progress_layout.addWidget(self.transmit_chunk_progress_bar)

        self.chunk_filename = QLabel(chunk_group_box)
        self.chunk_filename.setObjectName("ChunkFilename")
        horizontal.addWidget(self.chunk_filename)
        self.chunk_filename.setText("Waiting to start processing ...")
        self.chunk_filename.setFont(self.fixed_font)

        self.chunk_box_table = self.create_chunk_table()
        horizontal.addWidget(self.chunk_box_table)

        self.chunk_show_dialog_button = QPushButton(
            "Push to Show Table", parent=self.central_widget
        )
        horizontal.addWidget(self.chunk_show_dialog_button)
        self.chunk_show_dialog_button.hide()

        self.chunk_table_dialog_box = ChunkDialog(self.central_widget)

        return chunk_group_box

    def create_chunk_table(self, widget=None):
        """
        Create the table that is shown if there is a chunk table
        """
        if widget is None:
            widget = self.central_widget

        chunk_table = QTableView(widget)
        chunk_table.setObjectName("ChunkTable")

        chunk_table.horizontalHeader().setMaximumSectionSize(2)
        chunk_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        chunk_table.horizontalHeader().setVisible(False)
        chunk_table.verticalHeader().setMaximumSectionSize(2)
        chunk_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        chunk_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        chunk_table.verticalHeader().setVisible(False)
        chunk_table.setShowGrid(False)

        return chunk_table

    def create_data_model_table(self) -> QTableView:
        """
        Create the table that displays all the file data
        """
        data_model_table = QTableView(self.central_widget)
        data_model_table.setObjectName("DataModelTable")
        data_model_table.setShowGrid(False)
        size_policy = QSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        size_policy.setHeightForWidth(False)
        data_model_table.setSizePolicy(size_policy)

        # The table will fit the screen horizontally
        data_model_table.horizontalHeader().setStretchLastSection(False)
        data_model_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

        data_model_table.verticalHeader().setVisible(True)

        # Specify how the selection is done, which it to select the whole row
        data_model_table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        data_model_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        data_model_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        return data_model_table

    def create_label_box(
        self, name: str, parent=None, placeholder: str = "Waiting ..."
    ):
        """
        A generic wrapper function to create a label box
        :param name: Name of the label box
        :param parent: Parent of the label box
        :param placeholder: Placeholder text of the label box
        """
        parent = parent or self.central_widget

        label = QLabel(parent=parent)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setObjectName(name)
        if placeholder:
            label.setText(placeholder)

        return label
