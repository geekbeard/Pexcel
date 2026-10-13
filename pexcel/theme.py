"""Light and dark looks for the app, built on the Fusion style."""

import os
import tempfile

from PySide6.QtCore import QLineF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPalette, QPen

THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"

LIGHT_COLORS = {
    "window": "#f3f5f4",
    "base": "#ffffff",
    "alternateBase": "#f7f9f8",
    "text": "#1b1f23",
    "mutedText": "#6a737d",
    "border": "#d5dbd8",
    "grid": "#e3e7e5",
    "header": "#eef2f0",
    "headerText": "#3a4046",
    "accent": "#1e7b4f",
    "accentText": "#ffffff",
    "selection": "#cfe8da",
    "selectionText": "#10291c",
    "hover": "#e4ece8",
    "checkBorder": "#8a958f",
}

DARK_COLORS = {
    "window": "#1e2124",
    "base": "#25292d",
    "alternateBase": "#2a2f33",
    "text": "#e6e8ea",
    "mutedText": "#9aa3ab",
    "border": "#3a4046",
    "grid": "#33393e",
    "header": "#2d3236",
    "headerText": "#c9cfd4",
    "accent": "#3fb27f",
    "accentText": "#0e1a14",
    "selection": "#2f5a45",
    "selectionText": "#f0f5f2",
    "hover": "#343a3f",
    "checkBorder": "#6b747c",
}


def isSystemDark(app):
    try:
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:
        return False


def resolveColors(app, themeName):
    if themeName == THEME_DARK:
        return DARK_COLORS
    if themeName == THEME_LIGHT:
        return LIGHT_COLORS
    if isSystemDark(app):
        return DARK_COLORS
    return LIGHT_COLORS


def buildPalette(colors):
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(colors["window"]))
    palette.setColor(QPalette.WindowText, QColor(colors["text"]))
    palette.setColor(QPalette.Base, QColor(colors["base"]))
    palette.setColor(QPalette.AlternateBase, QColor(colors["alternateBase"]))
    palette.setColor(QPalette.Text, QColor(colors["text"]))
    palette.setColor(QPalette.Button, QColor(colors["header"]))
    palette.setColor(QPalette.ButtonText, QColor(colors["text"]))
    palette.setColor(QPalette.ToolTipBase, QColor(colors["base"]))
    palette.setColor(QPalette.ToolTipText, QColor(colors["text"]))
    palette.setColor(QPalette.PlaceholderText, QColor(colors["mutedText"]))
    palette.setColor(QPalette.Highlight, QColor(colors["selection"]))
    palette.setColor(QPalette.HighlightedText, QColor(colors["selectionText"]))
    palette.setColor(QPalette.Link, QColor(colors["accent"]))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(colors["mutedText"]))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(colors["mutedText"]))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(colors["mutedText"]))
    return palette


def buildStyleSheet(colors):
    return """
    QMainWindow, QWidget#centralArea {{ background: {window}; }}
    QToolBar {{
        background: {window}; border: none; border-bottom: 1px solid {border};
        padding: 4px 6px; spacing: 4px;
    }}
    QToolButton {{
        border: 1px solid transparent; border-radius: 6px; padding: 5px 9px; color: {text};
    }}
    QToolButton:hover {{ background: {hover}; border-color: {border}; }}
    QToolButton:checked {{ background: {selection}; color: {selectionText}; border-color: {accent}; }}
    QToolButton:disabled {{ color: {mutedText}; }}
    QLineEdit {{
        background: {base}; border: 1px solid {border}; border-radius: 6px;
        padding: 5px 8px; color: {text}; selection-background-color: {accent};
        selection-color: {accentText};
    }}
    QLineEdit:focus {{ border-color: {accent}; }}
    QTableView {{
        background: {base}; alternate-background-color: {alternateBase};
        gridline-color: {grid}; border: none; color: {text};
        selection-background-color: {selection}; selection-color: {selectionText};
    }}
    QTableView QTableCornerButton::section {{
        background: {header}; border: none;
        border-right: 1px solid {border}; border-bottom: 1px solid {border};
    }}
    QHeaderView {{ background: {header}; }}
    QHeaderView::section {{
        background: {header}; color: {headerText}; border: none;
        border-right: 1px solid {grid}; border-bottom: 1px solid {border};
        padding: 4px 8px;
    }}
    QHeaderView::section:horizontal:hover {{ background: {hover}; }}
    QHeaderView::section:checked {{ background: {selection}; color: {selectionText}; }}
    QTabBar#sheetTabs {{ background: {window}; }}
    QTabBar#sheetTabs::tab {{
        background: transparent; color: {mutedText}; border: none;
        border-top: 3px solid transparent; padding: 6px 16px; margin-right: 2px;
    }}
    QTabBar#sheetTabs::tab:hover {{ color: {text}; background: {hover}; }}
    QTabBar#sheetTabs::tab:selected {{
        color: {accent}; background: {base}; border-top: 3px solid {accent}; font-weight: 600;
    }}
    QWidget#sheetBar {{ background: {window}; border-top: 1px solid {border}; }}
    QStatusBar {{ background: {window}; color: {mutedText}; border-top: 1px solid {border}; }}
    QStatusBar QLabel {{ color: {mutedText}; padding: 0 6px; }}
    QFrame#filterPopup {{ background: {base}; border: 1px solid {border}; border-radius: 8px; }}
    QLabel#popupTitle {{ font-weight: 600; color: {text}; padding-bottom: 2px; }}
    QLabel#popupNote {{ color: {mutedText}; }}
    QPushButton {{
        background: {header}; color: {text}; border: 1px solid {border};
        border-radius: 6px; padding: 5px 12px; text-align: left;
    }}
    QPushButton:hover {{ background: {hover}; }}
    QPushButton:disabled {{ color: {mutedText}; }}
    QPushButton#primaryButton {{
        background: {accent}; color: {accentText}; border-color: {accent}; text-align: center;
    }}
    QListWidget {{ background: {base}; border: 1px solid {border}; border-radius: 6px; color: {text}; }}
    QListWidget::indicator {{
        width: 13px; height: 13px; border: 1px solid {checkBorder}; border-radius: 3px; background: {base};
    }}
    QListWidget::indicator:checked {{ background: {accent}; border-color: {accent}; image: url({checkImage}); }}
    QListWidget::indicator:indeterminate {{ background: {accent}; border-color: {accent}; image: url({dashImage}); }}
    QWidget#welcomePage {{ background: {window}; }}
    QLabel#welcomeTitle {{ font-size: 26pt; font-weight: 600; color: {text}; }}
    QLabel#welcomeSubtitle {{ font-size: 11pt; color: {mutedText}; }}
    QLabel#recentTitle {{ font-weight: 600; color: {mutedText}; padding-top: 12px; }}
    QPushButton#bigOpenButton {{
        background: {accent}; color: {accentText}; border: none; border-radius: 8px;
        padding: 10px 28px; font-size: 11pt; font-weight: 600; text-align: center;
    }}
    QPushButton#recentButton {{
        background: transparent; border: none; color: {accent}; padding: 3px 4px; text-align: left;
    }}
    QPushButton#recentButton:hover {{ text-decoration: underline; }}
    QMenu {{ background: {base}; color: {text}; border: 1px solid {border}; padding: 4px; }}
    QMenu::item {{ padding: 5px 24px 5px 20px; border-radius: 4px; }}
    QMenu::item:selected {{ background: {hover}; }}
    QMenu::separator {{ height: 1px; background: {border}; margin: 4px 8px; }}
    QMenuBar {{ background: {window}; color: {text}; }}
    QMenuBar::item:selected {{ background: {hover}; border-radius: 4px; }}
    QToolTip {{ background: {base}; color: {text}; border: 1px solid {border}; padding: 4px; }}
    """.format(**colors)


def drawIndicatorImage(path, scale, strokeColor, points):
    """Draws a check mark or dash as a 13x13 PNG (times scale), as a line through the given points."""
    size = 13 * scale
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(strokeColor))
    pen.setWidthF(1.8 * scale)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    for pointIndex in range(len(points) - 1):
        start = points[pointIndex]
        end = points[pointIndex + 1]
        painter.drawLine(QLineF(start[0] * scale, start[1] * scale, end[0] * scale, end[1] * scale))
    painter.end()
    image.save(path, "PNG")


def writeIndicatorImages(colors):
    """Style sheets need image files for check marks, so write tiny PNGs to the temp folder.

    The @2x files are picked up automatically on high-DPI screens.
    """
    folder = os.path.join(tempfile.gettempdir(), "pexcel")
    os.makedirs(folder, exist_ok=True)
    stroke = colors["accentText"]
    suffix = stroke.replace("#", "")
    checkPoints = [(3.0, 6.8), (5.4, 9.2), (10.0, 3.8)]
    dashPoints = [(3.5, 6.5), (9.5, 6.5)]
    checkPath = os.path.join(folder, "check_" + suffix + ".png")
    dashPath = os.path.join(folder, "dash_" + suffix + ".png")
    drawIndicatorImage(checkPath, 1, stroke, checkPoints)
    drawIndicatorImage(checkPath.replace(".png", "@2x.png"), 2, stroke, checkPoints)
    drawIndicatorImage(dashPath, 1, stroke, dashPoints)
    drawIndicatorImage(dashPath.replace(".png", "@2x.png"), 2, stroke, dashPoints)
    return checkPath.replace("\\", "/"), dashPath.replace("\\", "/")


def applyTheme(app, themeName):
    colors = dict(resolveColors(app, themeName))
    checkPath, dashPath = writeIndicatorImages(colors)
    colors["checkImage"] = checkPath
    colors["dashImage"] = dashPath
    app.setPalette(buildPalette(colors))
    app.setStyleSheet(buildStyleSheet(colors))
    return colors
