from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QFileDialog, QMessageBox,
    QGroupBox, QFormLayout, QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from hub.utils.config import Config
from hub.utils.platform import is_python_installed


class SettingsTab(QWidget):
    settingsChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = Config()
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
        btn_hub.clicked.connect(lambda: self._browse(self.edit_hub_path))
        hb_hub = QHBoxLayout()
        hb_hub.addWidget(self.edit_hub_path, 1)
        hb_hub.addWidget(btn_hub)
        gf_general.addRow("Hub path:", hb_hub)

        self.edit_editor_path = QLineEdit()
        btn_editor = QPushButton("Browse...")
        btn_editor.clicked.connect(lambda: self._browse(self.edit_editor_path))
        hb_editor = QHBoxLayout()
        hb_editor.addWidget(self.edit_editor_path, 1)
        hb_editor.addWidget(btn_editor)
        gf_general.addRow("Editor installs:", hb_editor)

        self.edit_projects_path = QLineEdit()
        btn_projects = QPushButton("Browse...")
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
        btn_python.clicked.connect(lambda: self._browse(self.edit_python_path))
        hb_python = QHBoxLayout()
        hb_python.addWidget(self.edit_python_path, 1)
        hb_python.addWidget(btn_python)
        gf_system.addRow("Python install path:", hb_python)

        self.btn_install_python = QPushButton("Install Python 3.13")
        self.btn_install_python.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_install_python)
        btn_row.addStretch()
        gf_system.addRow("", btn_row)

        form.addWidget(gb_system)

        btn_save = QPushButton("Save Settings")
        btn_save.setFixedHeight(40)
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
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

    def _browse(self, line_edit):
        path = QFileDialog.getExistingDirectory(self, "Select folder")
        if path:
            line_edit.setText(path)
