"""Central qtawesome icon helpers for ZarinHub.

All UI icons go through :func:`icon` / :func:`pixmap` so the app keeps
working (with plain text buttons) even if ``qtawesome`` is not installed.

Colors are theme-aware: ZarinHub follows the OS color scheme (Qt propagates
Windows dark mode into the Fusion palette), so the default foreground color
is picked from the live application palette — light icons on dark theme,
dark icons on light theme. Pass an explicit *color* only for fixed
backgrounds (e.g. the blue update banner) or semantic accents.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPalette, QPixmap
from PyQt6.QtWidgets import QApplication

try:
    import qtawesome as qta
except ImportError:  # graceful fallback: text-only UI
    qta = None

#: Foreground for dark application themes (Hub default, ``theme: dark``).
DARK_THEME_FG = "#d4d4d4"
#: Foreground for light application themes.
LIGHT_THEME_FG = "#3b4048"
#: Backwards-compatible default; prefer ``color=None`` (auto) in new code.
DEFAULT_COLOR = DARK_THEME_FG
ACCENT_BLUE = "#61afef"
SUCCESS_GREEN = "#98c379"
WARNING_RED = "#e74c3c"
MUTED_GRAY = "#6b7280"
WHITE = "#ffffff"


def is_dark_theme() -> bool:
    """True when the running app uses a dark theme (OS-driven)."""
    app = QApplication.instance()
    if app is None:
        return True  # Hub default config theme is "dark"
    try:
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except Exception:
        pass
    try:
        bg = app.palette().color(QPalette.ColorRole.Window)
        return bg.lightness() < 128
    except Exception:
        return True


def auto_color() -> str:
    """Foreground icon color matching the current application theme."""
    return DARK_THEME_FG if is_dark_theme() else LIGHT_THEME_FG


def _resolve(color: str | None) -> str:
    return auto_color() if color is None else color


def available() -> bool:
    """True when qtawesome is installed and usable."""
    return qta is not None


def icon(name: str, color: str | None = None) -> QIcon:
    """Return a QIcon for a FontAwesome name (e.g. ``'fa5s.folder'``).

    ``color=None`` (default) follows the current application theme.
    """
    if qta is None:
        return QIcon()
    try:
        return qta.icon(name, color=_resolve(color))
    except Exception:
        return QIcon()


def pixmap(name: str, size: int = 24, color: str | None = None) -> QPixmap:
    """Return a QPixmap for use in QLabel-based status icons."""
    if qta is None:
        return QPixmap()
    try:
        return qta.icon(name, color=_resolve(color)).pixmap(QSize(size, size))
    except Exception:
        return QPixmap()


def set_icon(widget, name: str, color: str | None = None) -> None:
    """Set a qtawesome icon on a QAbstractButton (no-op without qtawesome)."""
    if qta is None:
        return
    try:
        widget.setIcon(qta.icon(name, color=_resolve(color)))
    except Exception:
        pass


def set_label_icon(label, name: str, size: int = 24, color: str | None = None) -> bool:
    """Put a qtawesome glyph into a QLabel. Returns True when applied."""
    pm = pixmap(name, size, color)
    if pm.isNull():
        return False
    label.setPixmap(pm)
    return True
