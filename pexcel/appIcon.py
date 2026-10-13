"""Draws the Pexcel icon in code, so no image files are needed at runtime."""

from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap


def drawIconPixmap(size):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    margin = size * 0.06
    tileRect = QRectF(margin, margin, size - margin * 2, size - margin * 2)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#1e7b4f"))
    painter.drawRoundedRect(tileRect, size * 0.2, size * 0.2)

    # Light sheet with a grid in the lower right.
    sheetRect = QRectF(size * 0.40, size * 0.30, size * 0.46, size * 0.52)
    painter.setBrush(QColor("#e9f6ef"))
    painter.drawRoundedRect(sheetRect, size * 0.05, size * 0.05)
    gridPen = QPen(QColor("#1e7b4f"))
    gridPen.setWidthF(max(1.0, size * 0.025))
    painter.setPen(gridPen)
    for step in range(1, 3):
        x = sheetRect.left() + sheetRect.width() * step / 3
        painter.drawLine(QLineF(x, sheetRect.top() + size * 0.04, x, sheetRect.bottom() - size * 0.04))
    for step in range(1, 4):
        y = sheetRect.top() + sheetRect.height() * step / 4
        painter.drawLine(QLineF(sheetRect.left() + size * 0.04, y, sheetRect.right() - size * 0.04, y))

    # Big "P" on the left.
    font = QFont("Segoe UI", 10)
    font.setBold(True)
    font.setPixelSize(int(size * 0.56))
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(QRectF(size * 0.10, size * 0.12, size * 0.5, size * 0.76), Qt.AlignCenter, "P")

    painter.end()
    return pixmap


def createAppIcon():
    icon = QIcon()
    for size in [16, 24, 32, 48, 64, 128, 256]:
        icon.addPixmap(drawIconPixmap(size))
    return icon
