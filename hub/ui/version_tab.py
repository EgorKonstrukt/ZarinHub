from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QMessageBox, QProgressBar, QFileDialog,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from hub.core.version_manager import VersionManager
from hub.core.github_api import GitHubAPI
from hub.ui.widgets import VersionCard
from hub.ui.install_dialog import InstallOutputDialog


class InstallWorker(QThread):
    output_line = pyqtSignal(str, bool)
    progress_val = pyqtSignal(int, str)
    install_finished = pyqtSignal(bool, str)

    def __init__(self, tag, dialog):
        super().__init__()
        self.tag = tag
        self.vm = VersionManager()

        self.output_line.connect(dialog.append_line, Qt.ConnectionType.QueuedConnection)
        self.progress_val.connect(dialog.set_progress, Qt.ConnectionType.QueuedConnection)

    def run(self):
        try:
            self.vm.download_and_install(
                self.tag,
                progress_callback=self._on_progress,
                output_callback=self._on_output
            )
            self.install_finished.emit(True, f"Version {self.tag} installed successfully.")
        except Exception as e:
            self.install_finished.emit(False, str(e))

    def _on_progress(self, p, msg):
        self.progress_val.emit(int(p * 100), msg)

    def _on_output(self, text, is_error):
        self.output_line.emit(text, is_error)


class VersionTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.vm = VersionManager()
        self._setup_ui()
        self._worker = None

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 16, 24, 16)
        title = QLabel("Installs")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        header_layout.addWidget(title)

        self.install_path_label = QLabel()
        header_layout.addWidget(self.install_path_label)

        self.btn_change_path = QPushButton("Change folder")
        self.btn_change_path.setFixedHeight(28)
        self.btn_change_path.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_change_path.clicked.connect(self._on_change_install_path)
        header_layout.addWidget(self.btn_change_path)

        header_layout.addStretch()
        self.btn_add_existing = QPushButton("  Add existing")
        self.btn_add_existing.setFixedHeight(36)
        self.btn_add_existing.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self.btn_add_existing)
        self.btn_refresh = QPushButton("  Check for updates")
        self.btn_refresh.setFixedHeight(36)
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self.btn_refresh)
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

        self.btn_add_existing.clicked.connect(self._on_add_existing)
        self.btn_refresh.clicked.connect(self.refresh)

    def _on_change_install_path(self):
        from PyQt6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self, "Select install folder")
        if path:
            self.vm.cfg.set("editor_install_path", path)
            self.refresh()

    def _update_path_label(self):
        p = self.vm.install_path
        self.install_path_label.setText(str(p))

    def refresh(self):
        self._update_path_label()
        while self.scroll_layout.count() > 0:
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        installed = self.vm.get_installed_versions()
        available = self.vm.get_available_versions()

        if not available:
            offline = QLabel("Could not fetch releases.\nCheck your internet connection.")
            offline.setAlignment(Qt.AlignmentFlag.AlignCenter)
            offline.setFont(QFont("Segoe UI", 12))
            self.scroll_layout.addWidget(offline)
            self.scroll_layout.addStretch()
            return

        latest_tag = available[0].tag_name if available else ""

        for release in available:
            tag = release.tag_name
            is_installed = tag in installed
            is_latest = tag == latest_tag
            info = installed.get(tag, {})
            card = VersionCard(tag, is_installed, is_latest,
                               info.get("path", ""),
                               commit_date=info.get("commit_date", ""))
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(0, 0, 16, 0)
            btn_layout.setSpacing(8)
            if is_installed:
                btn_launch = QPushButton("Launch")
                btn_launch.setFixedHeight(32)
                btn_launch.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_remove = QPushButton("Remove")
                btn_remove.setFixedHeight(32)
                btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_launch.clicked.connect(lambda checked, t=tag: self._launch(t))
                btn_remove.clicked.connect(lambda checked, t=tag: self._remove(t))
                btn_layout.addWidget(btn_launch)
                btn_layout.addWidget(btn_remove)
            else:
                btn_install = QPushButton("Download" if not is_latest else "Download Latest")
                btn_install.setFixedHeight(32)
                btn_install.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_install.clicked.connect(lambda checked, t=tag: self._install(t))
                btn_layout.addWidget(btn_install)
            card.layout().addLayout(btn_layout)
            self.scroll_layout.addWidget(card)

        self.scroll_layout.addStretch()

    def _install(self, tag):
        reply = QMessageBox.question(
            self, "Install Version",
            f"Download and install ZarinEngine {tag}?\n\nThis may take a few minutes.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        dialog = InstallOutputDialog(f"Installing ZarinEngine {tag}", self)
        self._worker = InstallWorker(tag, dialog)
        self._worker.install_finished.connect(lambda success, msg: self._on_install_finished(dialog, success, msg))
        self._worker.start()
        dialog.exec()

    def _on_install_finished(self, dialog, success, msg):
        dialog.set_finished(success, msg)
        self.refresh()

    def _on_add_existing(self):
        path = QFileDialog.getExistingDirectory(self, "Select ZarinEngine installation directory")
        if not path:
            return
        try:
            tag = self.vm.add_existing_version(path)
            self.refresh()
            QMessageBox.information(self, "Added", f"Version '{tag}' registered from\n{path}")
        except (ValueError, FileNotFoundError) as e:
            QMessageBox.warning(self, "Error", str(e))

    def _launch(self, tag):
        self.vm.launch_editor(tag)

    def _remove(self, tag):
        reply = QMessageBox.question(
            self, "Remove Version",
            f"Remove ZarinEngine {tag}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.vm.remove_version(tag)
            self.refresh()
