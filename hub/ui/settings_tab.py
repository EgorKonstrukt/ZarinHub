from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QFileDialog, QMessageBox,
    QGroupBox, QFormLayout, QComboBox, QProgressBar,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont

from hub.utils.config import Config
from hub.utils.platform import is_python_installed
from hub.ui import icons
from hub.version import APP_NAME, APP_VERSION
from hub.core.updater import check_latest_version, is_update_available, apply_update


class UpdateCheckWorker(QThread):
    finished = pyqtSignal(object, str)

    def run(self):
        try:
            latest, err = check_latest_version()
            self.finished.emit(latest, err)
        except Exception as e:
            self.finished.emit(None, str(e))


class UpdateApplyWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, latest):
        super().__init__()
        self.latest = latest

    def run(self):
        try:
            apply_update(self.latest, self._on_progress)
            self.finished.emit(True, "ZarinHub will now restart to apply the update.")
        except Exception as e:
            self.finished.emit(False, str(e))

    def _on_progress(self, pct, msg):
        self.progress.emit(pct, msg)


class SettingsTab(QWidget):
    settingsChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = Config()
        self._update_worker = None
        self._apply_worker = None
        self._latest_update = None
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 16, 24, 16)
        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addWidget(header)

        scroll = QWidget()
        form = QVBoxLayout(scroll)
        form.setContentsMargins(32, 24, 32, 24)
        form.setSpacing(16)

        gb_general = QGroupBox("General")
        gf_general = QFormLayout(gb_general)
        gf_general.setSpacing(12)

        self.edit_hub_path = QLineEdit()
        btn_hub = QPushButton("Browse...")
        icons.set_icon(btn_hub, "fa5s.folder-open")
        btn_hub.clicked.connect(lambda: self._browse(self.edit_hub_path))
        hb_hub = QHBoxLayout()
        hb_hub.addWidget(self.edit_hub_path, 1)
        hb_hub.addWidget(btn_hub)
        gf_general.addRow("Hub path:", hb_hub)

        self.edit_editor_path = QLineEdit()
        btn_editor = QPushButton("Browse...")
        icons.set_icon(btn_editor, "fa5s.folder-open")
        btn_editor.clicked.connect(lambda: self._browse(self.edit_editor_path))
        hb_editor = QHBoxLayout()
        hb_editor.addWidget(self.edit_editor_path, 1)
        hb_editor.addWidget(btn_editor)
        gf_general.addRow("Editor installs:", hb_editor)

        self.edit_projects_path = QLineEdit()
        btn_projects = QPushButton("Browse...")
        icons.set_icon(btn_projects, "fa5s.folder-open")
        btn_projects.clicked.connect(lambda: self._browse(self.edit_projects_path))
        hb_projects = QHBoxLayout()
        hb_projects.addWidget(self.edit_projects_path, 1)
        hb_projects.addWidget(btn_projects)
        gf_general.addRow("Projects folder:", hb_projects)

        form.addWidget(gb_general)

        gb_editor = QGroupBox("Editor")
        gf_editor = QFormLayout(gb_editor)
        gf_editor.setSpacing(12)

        self.cb_auto_update = QCheckBox("Automatically download editor updates")
        gf_editor.addRow("", self.cb_auto_update)

        self.edit_github = QLineEdit()
        gf_editor.addRow("GitHub repository:", self.edit_github)

        self.combo_source = QComboBox()
        self.combo_source.addItem("Release (tagged versions)", "release")
        self.combo_source.addItem("Latest (master branch)", "branch")
        gf_editor.addRow("Download source:", self.combo_source)

        form.addWidget(gb_editor)

        gb_system = QGroupBox("System")
        gf_system = QFormLayout(gb_system)
        gf_system.setSpacing(12)

        self.cb_auto_python = QCheckBox("Auto-install Python if missing")
        gf_system.addRow("", self.cb_auto_python)

        self.python_status = QLabel()
        gf_system.addRow("Python:", self.python_status)

        self.edit_python_path = QLineEdit()
        btn_python = QPushButton("Browse...")
        icons.set_icon(btn_python, "fa5s.folder-open")
        btn_python.clicked.connect(lambda: self._browse(self.edit_python_path))
        hb_python = QHBoxLayout()
        hb_python.addWidget(self.edit_python_path, 1)
        hb_python.addWidget(btn_python)
        gf_system.addRow("Python install path:", hb_python)

        self.btn_install_python = QPushButton("Install Python 3.13")
        self.btn_install_python.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.set_icon(self.btn_install_python, "fa5b.python", icons.ACCENT_BLUE)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_install_python)
        btn_row.addStretch()
        gf_system.addRow("", btn_row)

        form.addWidget(gb_system)

        gb_update = QGroupBox(f"Update {APP_NAME}")
        vu_layout = QVBoxLayout(gb_update)
        vu_layout.setSpacing(12)
        self.lbl_version = QLabel(f"Current version: <b>{APP_VERSION}</b>")
        self.lbl_version.setFont(QFont("Segoe UI", 11))
        vu_layout.addWidget(self.lbl_version)
        self.lbl_update_status = QLabel("")
        self.lbl_update_status.setFont(QFont("Segoe UI", 10))
        vu_layout.addWidget(self.lbl_update_status)
        self.update_progress = QProgressBar()
        self.update_progress.setVisible(False)
        vu_layout.addWidget(self.update_progress)
        btn_row = QHBoxLayout()
        self.btn_check_update = QPushButton("Check for Updates")
        self.btn_check_update.setFixedHeight(36)
        self.btn_check_update.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.set_icon(self.btn_check_update, "fa5s.sync-alt")
        self.btn_check_update.clicked.connect(self._check_update)
        btn_row.addWidget(self.btn_check_update)
        self.btn_apply_update = QPushButton("Update Now")
        self.btn_apply_update.setFixedHeight(36)
        self.btn_apply_update.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.set_icon(self.btn_apply_update, "fa5s.download", icons.SUCCESS_GREEN)
        self.btn_apply_update.setVisible(False)
        self.btn_apply_update.clicked.connect(self._apply_update)
        btn_row.addWidget(self.btn_apply_update)
        btn_row.addStretch()
        vu_layout.addLayout(btn_row)
        form.addWidget(gb_update)

        btn_save = QPushButton("Save Settings")
        btn_save.setFixedHeight(40)
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.set_icon(btn_save, "fa5s.save", icons.SUCCESS_GREEN)
        btn_save.clicked.connect(self._save_settings)
        form.addWidget(btn_save, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(scroll)

    def _load_settings(self):
        self.edit_hub_path.setText(self.cfg.get("hub_path"))
        self.edit_editor_path.setText(self.cfg.get("editor_install_path"))
        self.edit_projects_path.setText(self.cfg.get("projects_path"))
        self.cb_auto_update.setChecked(self.cfg.get("auto_update_editor"))
        self.edit_github.setText(self.cfg.get("github_repo"))
        idx = self.combo_source.findData(self.cfg.get("source_type"))
        if idx >= 0:
            self.combo_source.setCurrentIndex(idx)
        self.cb_auto_python.setChecked(self.cfg.get("auto_install_python"))
        self.edit_python_path.setText(self.cfg.get("python_install_path"))
        if is_python_installed():
            self.python_status.setText("Python 3.13 detected")
            self.btn_install_python.setVisible(False)
        else:
            self.python_status.setText("Python 3.13 not found")
            self.btn_install_python.setVisible(True)

    def _save_settings(self):
        self.cfg.set("hub_path", self.edit_hub_path.text())
        self.cfg.set("editor_install_path", self.edit_editor_path.text())
        self.cfg.set("projects_path", self.edit_projects_path.text())
        self.cfg.set("auto_update_editor", self.cb_auto_update.isChecked())
        self.cfg.set("github_repo", self.edit_github.text())
        self.cfg.set("source_type", self.combo_source.currentData())
        self.cfg.set("auto_install_python", self.cb_auto_python.isChecked())
        self.cfg.set("python_install_path", self.edit_python_path.text())
        self.settingsChanged.emit()
        QMessageBox.information(self, "Saved", "Settings saved successfully.")

    def _check_update(self):
        self.btn_check_update.setEnabled(False)
        self.lbl_update_status.setText("Checking for updates...")
        self._update_worker = UpdateCheckWorker()
        self._update_worker.finished.connect(self._on_update_check)
        self._update_worker.start()

    def _on_update_check(self, latest, err):
        self._update_worker = None
        self.btn_check_update.setEnabled(True)
        if latest is None:
            if err:
                self.lbl_update_status.setText(f"Update check failed: {err[:60]}")
            else:
                self.lbl_update_status.setText("Could not check for updates.")
            return
        self._latest_update = latest
        if is_update_available(latest):
            ver = latest["version"]
            self.lbl_update_status.setText(f"Update <b>{ver}</b> available!")
            self.btn_apply_update.setVisible(True)
        else:
            self.lbl_update_status.setText("You have the latest version.")

    def _apply_update(self):
        if not self._latest_update:
            return
        reply = QMessageBox.question(
            self, "Update ZarinHub",
            f"Update to version {self._latest_update['version']}?\n\n"
            "ZarinHub will restart after the update.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.btn_apply_update.setVisible(False)
        self.btn_check_update.setEnabled(False)
        self.lbl_update_status.setText("Downloading update...")
        self.update_progress.setVisible(True)
        self.update_progress.setValue(0)
        self._apply_worker = UpdateApplyWorker(self._latest_update)
        self._apply_worker.progress.connect(self._on_update_progress)
        self._apply_worker.finished.connect(self._on_update_finished)
        self._apply_worker.start()

    def _on_update_progress(self, pct, msg):
        self.update_progress.setValue(pct)
        self.lbl_update_status.setText(msg)

    def _on_update_finished(self, success, msg):
        self._apply_worker = None
        self.update_progress.setVisible(False)
        self.btn_check_update.setEnabled(True)
        if success:
            QMessageBox.information(self, "Update", msg)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self.window().close)
            QTimer.singleShot(1000, __import__("sys").exit, [0])
        else:
            QMessageBox.warning(self, "Update Failed", msg)
            self.lbl_update_status.setText("Update failed.")

    def _browse(self, line_edit):
        path = QFileDialog.getExistingDirectory(self, "Select folder")
        if path:
            line_edit.setText(path)
