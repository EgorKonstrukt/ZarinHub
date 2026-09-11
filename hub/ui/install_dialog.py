import re
import sys
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QProgressBar, QLabel, QWidget,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QTextCursor

from hub.ui import icons


def ansi_to_html(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    COLORS = {
        "0": None, "1": ("span", "font-weight:bold"),
        "30": ("span", "color:#3b4048"), "31": ("span", "color:#e06c75"),
        "32": ("span", "color:#98c379"), "33": ("span", "color:#d19a66"),
        "34": ("span", "color:#61afef"), "35": ("span", "color:#c678dd"),
        "36": ("span", "color:#56b6c2"), "37": ("span", "color:#abb2bf"),
        "90": ("span", "color:#5c6370"), "91": ("span", "color:#be5046"),
        "92": ("span", "color:#98c379"), "93": ("span", "color:#e5c07b"),
        "94": ("span", "color:#61afef"), "95": ("span", "color:#c678dd"),
        "96": ("span", "color:#56b6c2"), "97": ("span", "color:#dfdfdf"),
    }
    tag_stack = []
    def _close_all():
        nonlocal tag_stack
        out = "".join(f"</{t}>" for t in reversed(tag_stack))
        tag_stack = []
        return out
    result = []
    pos = 0
    for m in re.finditer(r'\x1b\[([\d;]*)m', text):
        result.append(text[pos:m.start()])
        codes = m.group(1).split(";") if m.group(1) else ["0"]
        for code in codes:
            if code == "0":
                result.append(_close_all())
            elif code in COLORS:
                tag, style = COLORS[code]
                tag_stack.append(tag)
                result.append(f"<{tag} style='{style}'>")
        pos = m.end()
    result.append(text[pos:])
    result.append(_close_all())
    return "".join(result).replace("\n", "<br>")


class InstallOutputDialog(QDialog):
    def __init__(self, title="Installation", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(800, 500)
        self.resize(900, 600)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint
        )
        self._cancelled = False
        self._last_lines: list[str] = []
        self._busy_timer = QTimer(self)
        self._busy_timer.setInterval(500)
        self._busy_timer.timeout.connect(self._tick_busy)
        self._busy_dots = 0
        self._busy_base = ""
        self._stall_timer = QTimer(self)
        self._stall_timer.setSingleShot(True)
        self._stall_timer.setInterval(3000)
        self._stall_timer.timeout.connect(self._on_stalled)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 10))
        layout.addWidget(self.output, 1)
        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(4)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        bl.addWidget(self.progress)
        hl = QHBoxLayout()
        hl.setContentsMargins(0, 0, 0, 0)
        self.status_label = QLabel("Starting...")
        hl.addWidget(self.status_label, 1)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedSize(80, 28)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.set_icon(self.btn_cancel, "fa5s.times")
        self.btn_cancel.clicked.connect(self._on_cancel)
        hl.addWidget(self.btn_cancel)
        bl.addLayout(hl)
        layout.addWidget(bottom)

    def _on_cancel(self):
        self._cancelled = True
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("Cancelling...")
        self.append_line("Cancelling...", is_error=True)

    def is_cancelled(self) -> bool:
        return self._cancelled

    def append_line(self, text: str, is_error: bool = False):
        self._stall_timer.start()
        raw = text.rstrip("\r\n")
        if not raw:
            return
        replace_last = raw.startswith("\r")
        if replace_last:
            raw = raw.lstrip("\r")
        if not raw:
            return
        prefix = "<span style='color:#e06c75'>" if is_error else ""
        suffix = "</span>" if is_error else ""
        html_line = prefix + ansi_to_html(raw) + suffix
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if replace_last and self._last_lines:
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            cursor.insertHtml(html_line + "<br>")
            self._last_lines[-1] = raw
        else:
            cursor.insertHtml(html_line + "<br>")
            self._last_lines.append(raw)
            if len(self._last_lines) > 200:
                self._last_lines = self._last_lines[-100:]
        scrollbar = self.output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def set_progress(self, value: int, status: str = ""):
        self.progress.setValue(value)
        if status:
            self._busy_base = status
            self.status_label.setText(status)
            self._busy_timer.stop()
        self._stall_timer.start()

    def _on_stalled(self):
        if not self._busy_base:
            return
        self._busy_dots = 0
        self._busy_timer.start()

    def _tick_busy(self):
        self._busy_dots = (self._busy_dots + 1) % 4
        dots = "." * self._busy_dots
        self.status_label.setText(self._busy_base + "  " + dots)

    def set_finished(self, success: bool, message: str = ""):
        self._busy_timer.stop()
        self._stall_timer.stop()
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("Close")
        icons.set_icon(self.btn_cancel, "fa5s.check", icons.SUCCESS_GREEN)
        self.btn_cancel.clicked.disconnect()
        self.btn_cancel.clicked.connect(self.accept)
        if success:
            self.append_line("")
            self.append_line("✓ Installation completed successfully.", is_error=False)
            self.progress.setValue(100)
            self.status_label.setText("Done")
        else:
            self.append_line("")
            self.append_line(f"✗ {message}", is_error=True)
            self.status_label.setText("Failed")
