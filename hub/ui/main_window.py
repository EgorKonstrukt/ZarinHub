from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QLabel, QPushButton,
)

from hub.version import APP_NAME
from hub.ui.widgets import SidebarWidget
from hub.ui import icons
from hub.ui.project_tab import ProjectTab
from hub.ui.version_tab import VersionTab
from hub.ui.settings_tab import SettingsTab
from hub.utils.config import Config
from hub.core.updater import check_latest_version, is_update_available


class UpdateCheckThread(QThread):
    finished = pyqtSignal(object)

    def run(self):
        try:
            latest, _ = check_latest_version()
            self.finished.emit(latest)
        except Exception:
            self.finished.emit(None)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = Config()
        self._latest_update = None
        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._check_update_async()

    def _setup_window(self):
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)
        icon_path = str(Path(__file__).parent.parent.parent / "zarin_icon.svg")
        self.setWindowIcon(QIcon(icon_path))

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.banner = QWidget()
        self.banner.setVisible(False)
        self.banner.setStyleSheet("background-color: #2d5a9e;")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(16, 8, 16, 8)
        self.banner_label = QLabel()
        self.banner_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.banner_label.setStyleSheet("color: white;")
        banner_layout.addWidget(self.banner_label, 1)
        self.banner_btn = QPushButton("Update Now")
        self.banner_btn.setFixedHeight(32)
        self.banner_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.set_icon(self.banner_btn, "fa5s.download", icons.WHITE)
        self.banner_btn.setStyleSheet(
            "background-color: #4caf50; color: white; font-weight: bold; "
            "border: none; border-radius: 4px; padding: 4px 16px;"
        )
        self.banner_btn.clicked.connect(self._on_banner_update)
        banner_layout.addWidget(self.banner_btn)
        self.banner_close = QPushButton()
        self.banner_close.setFixedSize(28, 28)
        self.banner_close.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.set_icon(self.banner_close, "fa5s.times", icons.WHITE)
        if self.banner_close.icon().isNull():
            self.banner_close.setText("✕")
        self.banner_close.setStyleSheet(
            "background-color: transparent; color: white; border: none; font-size: 16px;"
        )
        self.banner_close.clicked.connect(lambda: self.banner.setVisible(False))
        banner_layout.addWidget(self.banner_close)
        root_layout.addWidget(self.banner)

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = SidebarWidget()
        body_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.project_tab = ProjectTab()
        self.version_tab = VersionTab()
        self.settings_tab = SettingsTab()
        self.stack.addWidget(self.project_tab)
        self.stack.addWidget(self.version_tab)
        self.stack.addWidget(self.settings_tab)
        body_layout.addWidget(self.stack, 1)

        root_layout.addLayout(body_layout)

    def _connect_signals(self):
        self.sidebar.btn_projects.clicked.connect(lambda: self._switch_tab(0))
        self.sidebar.btn_versions.clicked.connect(lambda: self._switch_tab(1))
        self.sidebar.btn_settings.clicked.connect(lambda: self._switch_tab(2))
        self.settings_tab.settingsChanged.connect(lambda: (
            self.version_tab.refresh(),
            self.project_tab.refresh(),
        ))
        self.sidebar.btn_projects.setChecked(True)

    def _switch_tab(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate([
            self.sidebar.btn_projects,
            self.sidebar.btn_versions,
            self.sidebar.btn_settings,
        ]):
            btn.setChecked(i == index)
        if index == 0:
            self.project_tab.refresh()
        elif index == 1:
            self.version_tab.refresh()

    def _check_update_async(self):
        self._thread = UpdateCheckThread()
        self._thread.finished.connect(self._on_auto_check)
        self._thread.start()

    def _on_auto_check(self, latest):
        self._thread = None
        if latest is None:
            return
        if not is_update_available(latest):
            return
        self._latest_update = latest
        self.banner_label.setText(
            f"Update ZarinHub v{latest['version']} available"
        )
        self.banner.setVisible(True)

    def _on_banner_update(self):
        self.banner.setVisible(False)
        self._switch_tab(2)
        self.settings_tab._latest_update = self._latest_update
        self.settings_tab.lbl_update_status.setText(
            f"Update <b>{self._latest_update['version']}</b> available!"
        )
        self.settings_tab.btn_apply_update.setVisible(True)

    def showEvent(self, event):
        super().showEvent(event)
        self.project_tab.refresh()
        self.version_tab.refresh()
