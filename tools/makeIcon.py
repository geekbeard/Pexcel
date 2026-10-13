"""Writes assets/pexcel.ico for the exe build."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import QApplication

from pexcel.appIcon import drawIconPixmap


def main():
    app = QApplication(sys.argv)
    outputPath = os.path.join(os.path.dirname(__file__), "..", "assets", "pexcel.ico")
    drawIconPixmap(256).save(os.path.abspath(outputPath), "ICO")
    print("Wrote " + os.path.abspath(outputPath))


if __name__ == "__main__":
    main()
