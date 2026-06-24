from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QProgressBar, QFrame,
)
from hub.version import APP_VERSION


class ClickableLabel(QLabel):
    def __init__(self, text="", parent=None, onClick=None):
        super().__init__(text, parent)
        self._onClick = onClick

    def mousePressEvent(self, event):
        if self._onClick:
            self._onClick()
        super().mousePressEvent(event)


class NavButton(QPushButton):
    def __init__(self, text, icon_text="", parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setFixedHeight(48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(QFont("Segoe UI", 11))


class SidebarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(4)
        logo_path = Path(__file__).parent.parent.parent / "zarin_logo.svg"
        logo = QSvgWidget(str(logo_path))
        logo.setFixedHeight(70)
        logo.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)
        self.btn_projects = NavButton("  Projects")
        self.btn_versions = NavButton("  Installs")
        self.btn_settings = NavButton("  Settings")
        layout.addWidget(self.btn_projects)
        layout.addWidget(self.btn_versions)
        layout.addWidget(self.btn_settings)
        layout.addStretch()
        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)


class ProjectCard(QFrame):
    def __init__(self, name, path, version, last_opened, description="", parent=None):
        super().__init__(parent)
        self.project_name = name
        self.project_path = path
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedHeight(90)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        icon = QLabel("📁")
        icon.setFont(QFont("Segoe UI", 24))
        icon.setFixedWidth(40)
        layout.addWidget(icon)
        info = QVBoxLayout()
        info.setSpacing(2)
        name_label = QLabel(name)
        name_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        info.addWidget(name_label)
        meta = ""
        if version:
            meta += f"v{version}  |  "
        if last_opened:
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(last_opened)
                meta += dt.strftime("%d.%m.%Y %H:%M")
            except (ValueError, TypeError):
                meta += last_opened
        if description:
            meta += f"  |  {description[:60]}"
        meta_label = QLabel(meta)
        info.addWidget(meta_label)
        layout.addLayout(info, 1)


class VersionCard(QFrame):
    def __init__(self, tag, is_installed=False, is_latest=False, install_path="",
                 commit_date="", parent=None):
        super().__init__(parent)
        self.tag = tag
        self.is_installed = is_installed
        self.install_path = install_path
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedHeight(80)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        icon = QLabel("✓" if is_installed else "○")
        icon.setFont(QFont("Segoe UI", 18))
        icon.setFixedWidth(32)
        layout.addWidget(icon)
        info = QVBoxLayout()
        info.setSpacing(2)
        name_label = QLabel(f"ZarinEngine {tag}")
        name_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        info.addWidget(name_label)
        status = "Installed" if is_installed else "Not installed"
        if is_latest:
            status += "  (latest)"
        if commit_date:
            from datetime import datetime
            try:
                d = datetime.fromisoformat(commit_date.replace("Z", "+00:00"))
                status += f"  —  {d.strftime('%d.%m.%Y %H:%M')}"
            except (ValueError, TypeError):
                pass
        status_label = QLabel(status)
        info.addWidget(status_label)
        layout.addLayout(info, 1)


class ProgressDialog(QFrame):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(400, 120)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(self.title_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        layout.addWidget(self.progress)
        self.status_label = QLabel("Starting...")
        layout.addWidget(self.status_label)
