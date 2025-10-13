# main.py
# Author: Trent Conley
# Date: October 2025
# Description:
#   A PySide6-based desktop application that sorts files into user-defined folders
#   based on allowed file extensions.
#   The interface is designed in Qt Designer (.ui file) and loaded dynamically at runtime.

import sys
import os
import shutil
from pathlib import Path
from typing import List

from PySide6.QtCore import QObject, QEvent, Qt, Signal, QFile, QIODevice, QUrl
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QInputDialog, QMenu, QMessageBox,
    QPushButton, QListView, QLabel, QTreeView, QAbstractItemView
)
from PySide6.QtUiTools import QUiLoader

# Path to the Qt Designer .ui file
UI_PATH = Path(__file__).parent / "FileSorterApp.ui"


# =====================================================================
# Drag-and-Drop Filter
# =====================================================================
class DropFilter(QObject):
    """
    A reusable event filter class that enables drag-and-drop functionality.
    It listens for QEvent.DragEnter and QEvent.Drop events and emits a
    signal containing the dropped file paths.
    """
    filesDropped = Signal(list)  # Signal that emits a list[str] of dropped file paths

    def eventFilter(self, obj, event):
        """Intercepts drag/drop events and extracts local file paths."""
        if event.type() == QEvent.DragEnter:
            mime = event.mimeData()
            if mime and mime.hasUrls():
                event.acceptProposedAction()
                return True

        elif event.type() == QEvent.Drop:
            mime = event.mimeData()
            if mime and mime.hasUrls():
                paths = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
                if paths:
                    self.filesDropped.emit(paths)
                    event.acceptProposedAction()
                    return True
        return False


# =====================================================================
# Main Application Window
# =====================================================================
class FileSorterApp(QMainWindow):
    """
    Main window class for the File Sorter application.
    Loads the UI directly from a .ui file, initializes all widgets,
    and manages user interaction logic (drag/drop, sorting, etc.).
    """


    def __init__(self):
        super().__init__()

        # -----------------------------------------------------------------
        # Load and initialize UI
        # -----------------------------------------------------------------
        f = QFile(str(UI_PATH))
        if not f.open(QIODevice.ReadOnly):
            raise RuntimeError(f"Couldn't open {UI_PATH}: {f.errorString()}")

        loader = QUiLoader()
        loaded = loader.load(f, None)  # The .ui file defines a QMainWindow
        f.close()
        if loaded is None:
            raise RuntimeError("QUiLoader.load() returned None — check your .ui path or design.")

        # Adopt UI components into this QMainWindow
        self.setWindowTitle("File Sorter")
        self.setCentralWidget(loaded.centralWidget())
        if loaded.menuBar():
            self.setMenuBar(loaded.menuBar())
        if loaded.statusBar():
            self.setStatusBar(loaded.statusBar())
        self.setGeometry(loaded.geometry())

        # Center the window on the active screen
        screen = QApplication.primaryScreen()
        geo = self.frameGeometry()
        geo.moveCenter(screen.availableGeometry().center())
        self.move(geo.topLeft())

        # -----------------------------------------------------------------
        # Locate widgets from UI (ensure objectNames match Designer)
        # -----------------------------------------------------------------
        self.addFolderButton: QPushButton = self.findChild(QPushButton, "addFolderButton")
        self.dragDropButton: QPushButton = self.findChild(QPushButton, "dragDropButton")
        self.folderListView: QListView = self.findChild(QListView, "folderListView")
        self.folderLabel: QLabel = self.findChild(QLabel, "folderLabel")

        if not all([self.addFolderButton, self.dragDropButton, self.folderListView]):
            raise RuntimeError("One or more widgets not found by objectName — check your .ui file.")

        # -----------------------------------------------------------------
        # Connect signals (buttons, context menus, drag/drop)
        # -----------------------------------------------------------------
        self.addFolderButton.clicked.connect(self.on_add_folder_clicked)

        # Optional sort button (if exists in UI)
        sort_btn = self.findChild(QPushButton, "sortButton")
        if sort_btn:
            sort_btn.clicked.connect(self.sort_files)

        # Enable drag-and-drop behavior on the drop zone button
        self._drop_filter = DropFilter(self)
        self.dragDropButton.setAcceptDrops(True)
        self.dragDropButton.installEventFilter(self._drop_filter)
        self._drop_filter.filesDropped.connect(self.on_dropzone_files)

        # Also allow clicking to manually select files/folders
        self.dragDropButton.clicked.connect(self.on_dropzone_clicked)
        self.dragDropButton.setToolTip("Drop files/folders here, or click to select manually")

        # -----------------------------------------------------------------
        # Data model setup (stores user folder rules)
        # -----------------------------------------------------------------
        # Each rule: {"path": str, "name": str, "exts": set[str]}
        self.folder_rules: List[dict] = []

        # Model for the QListView (displays folder rules)
        self.folder_model = QStandardItemModel()
        self.folderListView.setModel(self.folder_model)

        # Enable right-click context menu on folder list
        self.folderListView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.folderListView.customContextMenuRequested.connect(self.on_list_context_menu)

    # =====================================================================
    # Helper Methods
    # =====================================================================
    def parse_exts(self, text: str) -> set:
        """
        Convert user input like 'jpg, PNG , .pdf' into a normalized set:
        {'.jpg', '.png', '.pdf'}
        """
        exts = set()
        for part in text.split(','):
            s = part.strip().lower()
            if not s:
                continue
            if not s.startswith('.'):
                s = '.' + s
            exts.add(s)
        return exts

    def refresh_folder_list(self):
        """Rebuild the ListView based on current folder_rules."""
        self.folder_model.clear()
        for rule in self.folder_rules:
            label = rule["name"]
            if rule["exts"]:
                label += "  [ " + ", ".join(sorted(rule["exts"])) + " ]"
            item = QStandardItem(label)
            item.setEditable(False)
            item.setToolTip(rule["path"])
            self.folder_model.appendRow(item)

    # =====================================================================
    # UI Actions — Adding, Editing, Removing Folders
    # =====================================================================
    def on_add_folder_clicked(self):
        """Open dialog to add a new destination folder and its allowed extensions."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder_path:
            return

        # Prevent duplicates
        if any(rule["path"] == folder_path for rule in self.folder_rules):
            return

        # Prompt for allowed extensions
        text, ok = QInputDialog.getText(
            self,
            "Extensions",
            "Enter allowed extensions (comma-separated):\nExample: jpg, png, pdf"
        )
        exts = self.parse_exts(text) if ok else set()

        # Save rule and refresh list
        self.folder_rules.append({
            "path": folder_path,
            "name": os.path.basename(folder_path) or folder_path,
            "exts": exts
        })
        self.refresh_folder_list()

    def on_list_context_menu(self, pos):
        """Show right-click menu to edit or remove folder rules."""
        index = self.folderListView.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()

        menu = QMenu(self)
        edit_action = menu.addAction("Edit extensions…")
        remove_action = menu.addAction("Remove")
        chosen = menu.exec(self.folderListView.viewport().mapToGlobal(pos))

        if chosen == edit_action:
            self.edit_selected_folder_tags(row)
        elif chosen == remove_action:
            self.remove_selected_folder(row)

    def edit_selected_folder_tags(self, row: int):
        """Edit allowed extensions for an existing folder rule."""
        rule = self.folder_rules[row]
        current = ', '.join(sorted(e.lstrip('.') for e in rule['exts']))
        text, ok = QInputDialog.getText(
            self,
            f"Edit extensions for {rule['name']}",
            "Extensions (comma-separated):",
            text=current
        )
        if ok:
            rule['exts'] = self.parse_exts(text)
            self.refresh_folder_list()

    def remove_selected_folder(self, row: int):
        """Remove a folder rule from the list."""
        del self.folder_rules[row]
        self.refresh_folder_list()

    # =====================================================================
    # Drag/Drop and Click Handlers
    # =====================================================================
    def on_dropzone_files(self, paths: list):
        """Triggered when files/folders are dropped onto the drop zone."""
        path_objs = [Path(p) for p in paths if p]
        dirs = [p for p in path_objs if p.is_dir()]
        if dirs:
            self.sort_files_from_directory(dirs[0])
            return
        files = [p for p in path_objs if p.is_file()]
        if files:
            self.sort_individual_files(files)

    def on_dropzone_clicked(self):
        """Open a unified file dialog allowing both files and folders to be selected."""
        dlg = QFileDialog(self, "Select files and/or folders")
        dlg.setDirectory(str(Path.home()))
        dlg.setOption(QFileDialog.DontUseNativeDialog, True)  # Enables folder selection
        dlg.setFileMode(QFileDialog.ExistingFiles)            # Multi-select mode
        dlg.setNameFilter("All Files (*.*)")
        dlg.setAcceptMode(QFileDialog.AcceptOpen)

        # Allow multi-selection inside dialog’s list/tree views
        views = dlg.findChildren(QListView) + dlg.findChildren(QTreeView)
        for view in views:
            view.setSelectionMode(QAbstractItemView.ExtendedSelection)

        if not dlg.exec():
            return

        # Retrieve local file paths (supports both files and directories)
        urls = dlg.selectedUrls()  # type: list[QUrl]
        paths = [Path(u.toLocalFile()) for u in urls if u.isLocalFile()]
        if not paths:
            return

        # Separate files and folders, process each appropriately
        files = [p for p in paths if p.is_file()]
        dirs = [p for p in paths if p.is_dir()]

        if files:
            self.sort_individual_files(files)
        for d in dirs:
            self.sort_files_from_directory(d)

    # =====================================================================
    # File Sorting Core Logic
    # =====================================================================
    def resolve_name_collision(self, dest_dir: Path, filename: str) -> Path:
        """
        Ensure unique filenames when moving files.
        Example: 'file.txt' -> 'file (1).txt' if the name already exists.
        """
        candidate = dest_dir / filename
        if not candidate.exists():
            return candidate

        stem = Path(filename).stem
        suffix = Path(filename).suffix
        i = 1
        while True:
            candidate = dest_dir / f"{stem} ({i}){suffix}"
            if not candidate.exists():
                return candidate
            i += 1

    def find_target_for_extension(self, ext: str):
        """Find the first folder rule that matches a given file extension."""
        ext = (ext or "").lower()
        if not ext.startswith('.'):
            ext = '.' + ext if ext else ''
        for rule in self.folder_rules:
            if ext in rule['exts']:
                return rule
        return None

    def _move_one_file(self, entry: Path) -> str:
        """Move a single file to its destination folder based on extension rules."""
        try:
            rule = self.find_target_for_extension(entry.suffix)
            if not rule:
                return "skipped"
            dest_dir = Path(rule['path'])
            dest_dir.mkdir(parents=True, exist_ok=True)
            target = self.resolve_name_collision(dest_dir, entry.name)
            shutil.move(str(entry), str(target))
            return "moved"
        except Exception as e:
            print(f"Error moving {entry}: {e}")
            return "error"

    def sort_files(self):
        """Prompt user to select a folder and sort its contents."""
        source_dir = QFileDialog.getExistingDirectory(self, "Select Source Folder to Sort")
        if not source_dir:
            return
        self.sort_files_from_directory(Path(source_dir))

    def sort_files_from_directory(self, source: Path):
        """Sort all files within a selected directory based on folder rules."""
        if not self.folder_rules:
            QMessageBox.information(self, "No Rules", "Add at least one folder with allowed extensions first.")
            return
        moved = skipped = errors = 0
        for entry in source.iterdir():
            if not entry.is_file():
                continue
            result = self._move_one_file(entry)
            if result == "moved":
                moved += 1
            elif result == "skipped":
                skipped += 1
            else:
                errors += 1
        QMessageBox.information(self, "Sorting Complete",
                                f"Moved: {moved}\nSkipped: {skipped}\nErrors: {errors}")

    def sort_individual_files(self, files: List[Path]):
        """Sort a list of individual files dropped or manually selected by the user."""
        if not self.folder_rules:
            QMessageBox.information(self, "No Rules", "Add at least one folder with allowed extensions first.")
            return
        moved = skipped = errors = 0
        for f in files:
            if not f.exists() or not f.is_file():
                continue
            result = self._move_one_file(f)
            if result == "moved":
                moved += 1
            elif result == "skipped":
                skipped += 1
            else:
                errors += 1
        QMessageBox.information(self, "Sorting Complete",
                                f"Moved: {moved}\nSkipped: {skipped}\nErrors: {errors}")


# =====================================================================
# Application Entrypoint
# =====================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FileSorterApp()
    window.show()
    sys.exit(app.exec())
