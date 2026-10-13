"""Pexcel entry point. Usage: Pexcel.exe [file]"""

import ctypes
import sys

from PySide6.QtWidgets import QApplication

from pexcel.appIcon import createAppIcon
from pexcel.mainWindow import MainWindow


def main():
    # Gives the exe its own taskbar icon instead of the generic Python one.
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Pexcel.Viewer")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Pexcel")
    app.setOrganizationName("Pexcel")
    app.setStyle("Fusion")
    app.setWindowIcon(createAppIcon())

    window = MainWindow(app)
    window.show()

    # Opening a file from Explorer ("Open with") passes its path as the first argument.
    if len(sys.argv) > 1:
        window.openPath(sys.argv[1])

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
