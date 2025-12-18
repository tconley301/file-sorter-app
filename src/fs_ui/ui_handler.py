import os

import json
from PySide6.QtCore import QUrl, Qt, QStandardPaths
from PySide6.QtGui import QStandardItemModel, QStandardItem, QDesktopServices
from PySide6.QtWidgets import QInputDialog, QFileDialog, QMenu, QListView, QTreeView, QAbstractItemView, \
    QMessageBox
from pathlib import Path

from core.drop_filter import DropFilter
from fs_utils.app_utils import Helper


class UIHandler:
    def __init__(self, window, logic):

        self.window = window
        self.logic = logic

        self._drop_filter = DropFilter(self.window)
        self.window.ui.dragDropButton.setAcceptDrops(True)
        self.window.ui.dragDropButton.installEventFilter(self._drop_filter)
        self._drop_filter.filesDropped.connect(self.on_dropzone_files)
        self.window.ui.dragDropButton.clicked.connect(self.on_dropzone_clicked)

        self.folder_model = QStandardItemModel()
        self.window.ui.folderListView.setModel(self.folder_model)

        self.load_folder_rules()
        self.refresh_folder_list()

        self.window.ui.folderListView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.window.ui.folderListView.customContextMenuRequested.connect(self.on_list_context_menu)
        self.window.ui.folderListView.doubleClicked.connect(self.on_folder_double_clicked)

        self.window.ui.addFolderButton.clicked.connect(self.on_add_folder_clicked)



        self.folder_rules = []
        self.logic.bind_folder_rules(self.folder_rules)

    def on_manual_clicked(self):
        box = QMessageBox(self.window)
        box.setWindowTitle("File Sorter Manual")
        box.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-family: Arial;
                }
                """)
        box.setText("<p>Drag and drop files or folders in <b>Sorting Box</b> or "
                    "click <b>Sorting Box</b> to manually select them instead.</p>"
                    "<p>Double-click an added folder to open in explorer. "
                    "Right-click the folder to bring up the options to "
                    "remove it or edit the allowed extensions.</p>")

        box.setOption(QMessageBox.DontUseNativeDialog, True)  # <-- force Qt dialog
        box.setIcon(QMessageBox.NoIcon)  # <-- avoid Windows "info" beep
        box.setStandardButtons(QMessageBox.Ok)

        box.exec()

    def on_add_folder_clicked(self):
        """Open dialog to add a new destination folder and its allowed extensions."""
        folder_path = QFileDialog.getExistingDirectory(self.window, "Select Folder")
        if not folder_path:
            return

        # Prevent duplicates
        if any(rule["path"] == folder_path for rule in self.folder_rules):
            return

        # Prompt for allowed extensions
        text, ok = QInputDialog.getText(
            self.window,
            "Extensions",
            "Enter allowed extensions (comma-separated):\nExample: jpg, png, pdf"
        )
        exts = Helper.parse_exts(text) if ok else set()

        # Save rule and refresh list
        self.folder_rules.append({
            "path": folder_path,
            "name": os.path.basename(folder_path) or folder_path,
            "exts": exts
        })
        self.refresh_folder_list()
        self.save_folder_rules()

    def on_list_context_menu(self, pos):
        """Show right-click menu to edit or remove folder rules."""
        index = self.window.ui.folderListView.indexAt(pos)
        if not index.isValid():
            return

        menu = QMenu(self.window)
        edit_action = menu.addAction("Edit extensions…")
        remove_action = menu.addAction("Remove")
        chosen = menu.exec(self.window.ui.folderListView.viewport().mapToGlobal(pos))
        if not chosen:
            return

        if chosen == edit_action:
            self.edit_selected_folder_tags(index)
        elif chosen == remove_action:
            self.remove_selected_folder(index)

    def on_folder_double_clicked(self, index):
        item = self.folder_model.itemFromIndex(index)
        rule = item.data(Qt.UserRole)
        folder_path = rule["path"]
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))

    def edit_selected_folder_tags(self, index):
        """Edit allowed extensions for the folder rule tied to this list item."""
        if not index or not index.isValid():
            return

        item = self.folder_model.itemFromIndex(index)
        rule = item.data(Qt.UserRole)  # <-- rule dict stored in UserRole
        if not rule:
            return

        current = ", ".join(sorted(e.lstrip(".") for e in rule.get("exts", set())))

        text, ok = QInputDialog.getText(
            self.window,
            f"Edit extensions for {rule.get('name', '')}",
            "Extensions (comma-separated):",
            text=current
        )
        if ok:
            rule["exts"] = Helper.parse_exts(text)
            self.refresh_folder_list()
            self.save_folder_rules()

    def remove_selected_folder(self, index):
        """Remove the folder rule tied to this list item."""
        if not index or not index.isValid():
            return

        item = self.folder_model.itemFromIndex(index)
        rule = item.data(Qt.UserRole)
        if not rule:
            return

        # prompt user to confirm folder removal
        reply = QMessageBox.question(
            self.window, "Remove folder",
            f"Remove '{rule.get('name', '')}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
             return

        if rule in self.folder_rules:
            self.folder_rules.remove(rule)

        self.refresh_folder_list()
        self.save_folder_rules()

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
            item.setData(rule, Qt.UserRole)

            self.folder_model.appendRow(item)

    # =====================================================================
    # Drag/Drop and Click Handlers
    # =====================================================================
    def on_dropzone_files(self, paths: list):
        """Triggered when files/folders are dropped onto the drop zone."""
        path_objs = [Path(p) for p in paths if p]
        dirs = [p for p in path_objs if p.is_dir()]
        if dirs:
            self.logic.sort_files_from_directory(dirs[0])
            return
        files = [p for p in path_objs if p.is_file()]
        if files:
            self.logic.sort_individual_files(files)

    def on_dropzone_clicked(self):
        """Open a unified file dialog allowing both files and folders to be selected."""
        dlg = QFileDialog(self.window, "Select files and/or folders")
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
            self.logic.sort_individual_files(files)
        for d in dirs:
            self.logic.sort_files_from_directory(d)

    # ============================
    # Folder rules persistence
    # ============================

    def _rules_path(self) -> Path:
        """Return path to the local rules file."""
        base = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
        base.mkdir(parents=True, exist_ok=True)
        return base / "folder_rules.json"

    def save_folder_rules(self) -> None:
        """Save folder_rules to disk as JSON."""
        path = self._rules_path()

        data = []
        for r in self.folder_rules:
            data.append({
                "name": r.get("name", ""),
                "path": r.get("path", ""),
                "exts": sorted(list(r.get("exts", set()))),  # set → list
            })

        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        print("JSON location: ", self._rules_path())

    def load_folder_rules(self) -> None:
        """Load folder_rules from disk if present."""
        path = self._rules_path()
        if not path.exists():
            self.folder_rules = []
            return

        raw = json.loads(path.read_text(encoding="utf-8"))
        self.folder_rules = []

        for r in raw:
            self.folder_rules.append({
                "name": r.get("name", ""),
                "path": r.get("path", ""),
                "exts": set(r.get("exts", [])),  # list → set
            })
