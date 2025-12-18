# main.py
# Author: Trent Conley
# Date: October 2025
# Description:
#   A PySide6-based desktop application that sorts files into user-defined folders
#   based on allowed file extensions.
#   The interface is designed in Qt Designer (.ui file) and loaded dynamically at runtime.

import sys

from fs_ui.ui_handler import UIHandler
from src.fs_utils.app_utils import Helper
from src.core.file_logic import FileLogic

from PySide6.QtCore import QFile, QIODevice
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QListView, QLabel
from PySide6.QtUiTools import QUiLoader
from PySide6.QtGui import QGuiApplication, QCloseEvent

# Path to the Qt Designer .ui file
MAIN_WINDOW_UI = Helper.resource_path("fs_ui/FileSorterMain.ui")

class FileSorterApp(QMainWindow):
    """
    Main window class for the File Sorter application.
    Loads the UI directly from a .ui file, initializes all widgets,
    and manages user interaction logic (drag/drop, sorting, etc.).
    """
    def __init__(self):
        super().__init__()

        # Load UI
        f = QFile(str(MAIN_WINDOW_UI))
        f.open(QIODevice.ReadOnly)
        self.ui = QUiLoader().load(f, self)
        f.close()

        self.setCentralWidget(self.ui)
        self.setWindowTitle("File Sorter")
        self.resize(400, 300)

        # Menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Help")
        manual_button = file_menu.addAction("Manual")
        file_menu.addAction("Exit", self.close)



        # Widgets
        self.addFolderButton = self.ui.findChild(QPushButton, "addFolderButton")
        self.dragDropButton = self.ui.findChild(QPushButton, "dragDropButton")
        self.folderListView = self.ui.findChild(QListView, "folderListView")
        self.folderLabel = self.ui.findChild(QLabel, "folderLabel")

        self.file_logic = FileLogic(self)
        self.ui_handler = UIHandler(self, self.file_logic)

        manual_button.triggered.connect(self.ui_handler.on_manual_clicked)

    def closeEvent(self, event: QCloseEvent):
        """Save folder rules before the window closes."""
        self.ui_handler.save_folder_rules()
        event.accept()  # explicitly allow close
        super().closeEvent(event)
# =====================================================================
# Application Entrypoint
# =====================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("FileSorterApp")
    window = FileSorterApp()
    window.show()
    sys.exit(app.exec())
