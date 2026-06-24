from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget

from hub.version import APP_NAME
from hub.ui.widgets import SidebarWidget
from hub.ui.project_tab import ProjectTab
from hub.ui.version_tab import VersionTab
from hub.ui.settings_tab import SettingsTab
from hub.utils.config import Config


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = Config()
        self._setup_window()
        self._setup_ui()
        self._connect_signals()

    def _setup_window(self):
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)
        icon_path = str(Path(__file__).parent.parent.parent / "zarin_icon.svg")
        self.setWindowIcon(QIcon(icon_path))

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = SidebarWidget()
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.project_tab = ProjectTab()
        self.version_tab = VersionTab()
        self.settings_tab = SettingsTab()
        self.stack.addWidget(self.project_tab)
        self.stack.addWidget(self.version_tab)
        self.stack.addWidget(self.settings_tab)
        layout.addWidget(self.stack, 1)

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

    def showEvent(self, event):
        super().showEvent(event)
        self.project_tab.refresh()
        self.version_tab.refresh()
