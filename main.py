import sys
from pathlib import Path

# Ensure the hub package is importable
sys.path.insert(0, str(Path(__file__).parent))


def main():
    from PyQt6.QtWidgets import QApplication
    from hub.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setOrganizationName("Zarrakun")
    app.setApplicationName("ZarinHub")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
