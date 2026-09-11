from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QFileDialog, QMessageBox, QInputDialog, QComboBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from hub.core.project_manager import ProjectManager
from hub.core.version_manager import VersionManager
from hub.ui import icons
from hub.ui.widgets import ProjectCard


class ProjectTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pm = ProjectManager()
        self.vm = VersionManager()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 16, 24, 16)
        title = QLabel("Projects")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()
        self.btn_new = QPushButton("  New project")
        self.btn_new.setFixedHeight(36)
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.set_icon(self.btn_new, "fa5s.plus")
        self.btn_open = QPushButton("  Open")
        self.btn_open.setFixedHeight(36)
        self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.set_icon(self.btn_open, "fa5s.folder-open")
        header_layout.addWidget(self.btn_new)
        header_layout.addWidget(self.btn_open)
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(24, 16, 24, 16)
        self.scroll_layout.setSpacing(8)
        self.scroll_layout.addStretch()
        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

        self.btn_new.clicked.connect(self._on_new_project)
        self.btn_open.clicked.connect(self._on_open_project)

    def refresh(self):
        while self.scroll_layout.count() > 0:
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        projects = self.pm.get_projects()
        if not projects:
            empty = QLabel("No projects yet.\n\nClick \"New project\" to create your first project.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setFont(QFont("Segoe UI", 12))
            self.scroll_layout.addWidget(empty)
        else:
            for p in projects:
                card = ProjectCard(
                    p.get("name", "Untitled"),
                    p.get("path", ""),
                    p.get("version", ""),
                    p.get("last_opened", ""),
                    p.get("description", ""),
                )
                card.mousePressEvent = lambda e, path=p["path"]: self._on_open_specific(path)
                self.scroll_layout.addWidget(card)
        self.scroll_layout.addStretch()

    def _on_new_project(self):
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        versions = self.vm.get_installed_versions()
        version = ""
        if versions:
            items = list(versions.keys())
            sel, ok2 = QInputDialog.getItem(self, "Select Version", "Editor version:", items, 0, False)
            if ok2 and sel:
                version = sel
        desc, ok3 = QInputDialog.getText(self, "Description", "Description (optional):")
        if not ok3:
            desc = ""
        try:
            path = self.pm.create_project(name, version=version, description=desc)
            self.refresh()
            QMessageBox.information(self, "Created", f"Project '{name}' created successfully.")
        except FileExistsError as e:
            QMessageBox.warning(self, "Error", str(e))

    def _on_open_project(self):
        path = QFileDialog.getExistingDirectory(self, "Open Project")
        if path:
            try:
                self.pm.open_project(path)
                self.refresh()
            except FileNotFoundError as e:
                QMessageBox.warning(self, "Error", str(e))

    def _on_open_specific(self, path):
        versions = self.vm.get_installed_versions()
        if not versions:
            QMessageBox.warning(self, "No Editor",
                                "No editor versions installed.\nInstall one from the Installs tab.")
            return
        version = self.pm.get_project_version(path)
        if version and version in versions:
            self.vm.launch_editor(version)
        else:
            items = list(versions.keys())
            sel, ok = QInputDialog.getItem(self, "Open With",
                                           f"Open project with:", items, 0, False)
            if ok and sel:
                self.vm.launch_editor(sel)
