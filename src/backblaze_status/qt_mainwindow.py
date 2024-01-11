# Form implementation generated from reading ui file 'pyqy_test.ui'
#
# Created by: PyQt6 UI code generator 6.4.2
#
# WARNING: Any manual changes made to this file will be lost when pyuic6 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt6 import QtCore
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase, QAction
from PyQt6.QtWidgets import (
    QLabel,
    QFrame,
    QWidget,
    QGroupBox,
    QHBoxLayout,
    QProgressBar,
    QSizePolicy,
    QMenuBar,
    QMenu,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QVBoxLayout,
    QAbstractItemView,
    QDialog,
    QTableView,
)

from .css_styles import CssStyles

# import qdarktheme


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(2100, 1000)

        # Define the font to use when I need a fixed font
        self.fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.fixed_font.setPointSize(12)

        # The main widget
        self.centralwidget = QWidget(parent=MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.centralwidget.setStyleSheet(CssStyles.dark_orange)

        """
                          **** Layout ****
                          
        +---------------------------------------------------+
        |                                                   |
        |                                                   |
        |                  file_display_table               |
        |                                                   |
        +---------------------------------------------------+
        |                  chunk_box (hidden)               |
        +---------------------------------------------------+
        |                  message_box (hidden)             |
        +---------------------------------------------------+
        |                  file_info_box (hidden)           |
        +---------------------------------------------------+
        |          stat_box                     |    Clock  |
        +---------------------------------------------------+
        |                  progress_box                     |
        +---------------------------------------------------+
        """

        self.main_vertical_container = QVBoxLayout(self.centralwidget)
        self.main_vertical_container.setObjectName("verticalLayout")

        # self._create_data_model_table()
        # test_table = QTableView(self.centralwidget)
        # test_table.setObjectName("TestTable")
        # test_table.setModel(BzDataTableModel(self))
        # test_table.resizeRowsToContents()
        # self.main_vertical_container.addWidget(test_table)

        # Set up the data table
        self.file_display_table = self._create_data_table()
        self.main_vertical_container.addWidget(self.file_display_table)
        self.file_display_table.hide()

        self.data_model_table = self._create_data_model_table()
        self.data_model_table.setWordWrap(True)
        self.data_model_table.horizontalHeader().sectionResized.connect(
            self.data_model_table.resizeRowsToContents
        )
        self.main_vertical_container.addWidget(self.data_model_table)

        self.chunk_box = self._create_chunk_box()
        self.main_vertical_container.addWidget(self.chunk_box)
        self.chunk_box.hide()

        # Set up the message box. It is hidden until needed
        self.message_box = self._create_label_box(
            "MessageBox",
            placeholder="Message Box Placeholder",
            style={
                "background-color": "lightpink",
                "color": "black",
                "padding": "5px",
                "border-color": "red",
                "border-width": "3px",
            },
        )
        self.message_box.hide()
        self.main_vertical_container.addWidget(self.message_box)

        # Set up the file info box. It is hidden until needed

        self.file_info = self._create_label_box(
            "FileInfo", placeholder="Waiting to start processing ..."
        )
        self.file_info.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # self.file_info.hide()
        self.main_vertical_container.addWidget(self.file_info)

        # Set up the stats boxes
        self.stat_groupbox = QGroupBox(parent=self.centralwidget)
        # self.groupBox.setGeometry(QtCore.QRect(150, 70, 611, 80))
        self.stat_groupbox.setObjectName("StatGroupbox")

        self.stats_horizontal_Layout = QHBoxLayout(self.stat_groupbox)
        self.stats_horizontal_Layout.setObjectName("StatsHorizontalLayout")
        self.stats_horizontal_Layout.setContentsMargins(0, 0, 0, 0)

        self.stats_info = self._create_label_box(
            "StatsInfo",
            parent=self.stat_groupbox,
            placeholder="Waiting for data ...",
        )
        sizePolicy = QSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )
        sizePolicy.setHorizontalStretch(7)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.stats_info.sizePolicy().hasHeightForWidth())
        self.stats_info.setSizePolicy(sizePolicy)

        self.stats_horizontal_Layout.addWidget(self.stats_info)

        self.clock_display = self._create_label_box(
            "Clock",
            parent=self.stat_groupbox,
            placeholder="Clock",
        )
        sizePolicy = QSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.clock_display.sizePolicy().hasHeightForWidth()
        )
        self.clock_display.setSizePolicy(sizePolicy)

        self.stats_horizontal_Layout.addWidget(self.clock_display)

        self.main_vertical_container.addWidget(self.stat_groupbox)

        # Set up the total progress bar

        self.progress_groupbox = QGroupBox(parent=self.centralwidget)
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

        self.main_vertical_container.addWidget(self.progress_groupbox)

        MainWindow.setCentralWidget(self.centralwidget)

        self.menubar = QMenuBar(parent=MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 24))
        self.menubar.setObjectName("menubar")
        self.setMenuBar(self.menubar)
        self.option_menu = self.menubar.addMenu("Options")

        # self.option_menu = QMenu("&Options", self)
        # self.menubar.addMenu(options)

        self.statusbar = QStatusBar(parent=MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        # self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def _create_data_table(self) -> QTableWidget:
        """
        Create the data table
        :return:  the data table
        """
        data_table = QTableWidget(parent=self.centralwidget)
        data_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        data_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        data_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # data_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        data_table.setShowGrid(False)
        sizePolicy = QSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        sizePolicy.setHorizontalStretch(2)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(data_table.sizePolicy().hasHeightForWidth())
        data_table.setSizePolicy(sizePolicy)
        data_table.setObjectName("DisplayTable")
        column_names = [
            "Time",
            "File Name",
            "File Size",
            "Interval",
            "Rate - marker",
        ]
        data_table.setColumnCount(len(column_names))
        data_table.setRowCount(0)
        for index, column_name in enumerate(column_names):
            item = QTableWidgetItem(column_name)
            if index > 1:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            else:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
            data_table.setHorizontalHeaderItem(index, item)

        # Table will fit the screen horizontally
        data_table.horizontalHeader().setStretchLastSection(False)
        data_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        data_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        data_table.verticalHeader().setVisible(True)
        return data_table

    def _create_progress_table(self):
        data_table = QTableWidget(parent=self.centralwidget)
        data_table.setShowGrid(False)
        sizePolicy = QSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        sizePolicy.setHeightForWidth(False)
        data_table.setSizePolicy(sizePolicy)
        data_table.setObjectName("ProgressTable")
        data_table.setColumnCount(20)
        data_table.setRowCount(20)

        # Table will fit the screen horizontally
        data_table.horizontalHeader().setStretchLastSection(False)
        data_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        data_table.verticalHeader().setVisible(False)
        data_table.horizontalHeader().setVisible(False)

        return data_table

    def _create_chunk_box(self):
        chunk_groupBox = QGroupBox(self.centralwidget)
        chunk_groupBox.setObjectName("ChunkGroupBox")
        chunk_groupBox.setMaximumHeight(150)
        horizontal = QHBoxLayout(chunk_groupBox)
        horizontal.setObjectName("ChunkBoxHorizontal")

        self.transmit_chunk_progress_bar = QProgressBar(chunk_groupBox)
        self.transmit_chunk_progress_bar.setObjectName("TransmitProgressBar")
        self.transmit_chunk_progress_bar.hide()

        horizontal.addWidget(self.transmit_chunk_progress_bar)

        self.prepare_chunk_progress_bar = QProgressBar(chunk_groupBox)
        self.prepare_chunk_progress_bar.setObjectName("PrepareProgressBar")
        self.prepare_chunk_progress_bar.hide()

        horizontal.addWidget(self.prepare_chunk_progress_bar)

        self.chunk_filename = QLabel(chunk_groupBox)
        self.chunk_filename.setObjectName("ChunkFilename")
        horizontal.addWidget(self.chunk_filename)
        self.chunk_filename.setText("Label goes here")
        self.chunk_filename.setFont(self.fixed_font)

        self.chunk_box_table = self._create_chunk_table()
        horizontal.addWidget(self.chunk_box_table)
        self.chunk_box_table.hide()

        self.chunk_table_dialog = QDialog()
        self.chunk_table_dialog.setWindowModality(Qt.WindowModality.NonModal)
        self.chunk_table_dialog.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.chunk_dialog_table = self._create_chunk_table()

        self.chunk_table_dialog_layout = QVBoxLayout()
        self.chunk_table_dialog_layout.addWidget(self.chunk_dialog_table)

        self.chunk_table_dialog.setLayout(self.chunk_table_dialog_layout)

        return chunk_groupBox

    def _create_chunk_table(self):
        chunk_table = QTableWidget(self.centralwidget)
        chunk_table.setObjectName("ChunkTable")

        chunk_table.horizontalHeader().setMaximumSectionSize(6)
        chunk_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Fixed
        )
        chunk_table.horizontalHeader().setVisible(False)

        chunk_table.verticalHeader().setMaximumSectionSize(6)
        chunk_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        chunk_table.verticalHeader().setVisible(False)
        chunk_table.setShowGrid(False)

        return chunk_table

    def _create_data_model_table(self) -> QTableView:
        data_model_table = QTableView(self.centralwidget)
        data_model_table.setObjectName("DataModelTable")
        data_model_table.setShowGrid(False)
        sizePolicy = QSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        sizePolicy.setHeightForWidth(False)
        data_model_table.setSizePolicy(sizePolicy)
        # Table will fit the screen horizontally
        data_model_table.horizontalHeader().setStretchLastSection(False)
        data_model_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        # test_table.horizontalHeader().setSectionResizeMode(
        #     1, QHeaderView.ResizeMode.Stretch
        # )
        data_model_table.verticalHeader().setVisible(True)
        data_model_table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        data_model_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        data_model_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        return data_model_table

    def _create_label_box(
        self, name: str, parent=None, placeholder: str = "Placeholder", style=None
    ):
        parent = parent or self.centralwidget
        style = style or dict()

        label = QLabel(parent=parent)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setObjectName(name)
        if placeholder:
            label.setText(placeholder)
        if style:
            styles = " ".join([f"{k}: {v};" for (k, v) in style.items()])
            style_string = f"QLabel#{name} {{ {styles} }} "
            label.setStyleSheet(style_string)

        return label

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.progress_bar_header.setText(_translate("MainWindow", "TextLabel"))
        self.progress.setText(_translate("MainWindow", "TextLabel"))
        self.elapsed_time.setText(_translate("MainWindow", "TextLabel"))
        self.time_remaining.setText(_translate("MainWindow", "TextLabel"))
        self.completion_time.setText(_translate("MainWindow", "TextLabel"))
        self.rate.setText(_translate("MainWindow", "TextLabel"))
