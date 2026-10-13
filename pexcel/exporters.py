"""CSV export and table painting for PDF export / printing."""

import csv

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPageLayout, QPen
from PySide6.QtPrintSupport import QPrinter

from pexcel.workbookLoader import isNumberValue


class TableSnapshot:
    """The rows currently visible in the view (after filter and sort), ready to export."""

    def __init__(self, title, headers, rows, rawRows):
        self.title = title
        self.headers = headers
        self.rows = rows          # display strings
        self.rawRows = rawRows    # original values, used for CSV numbers and alignment


def exportCsv(path, snapshot, includeHeader):
    # utf-8-sig so Excel opens accented characters correctly.
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        if includeHeader:
            writer.writerow(snapshot.headers)
        for rowIndex in range(len(snapshot.rows)):
            outputRow = []
            displayRow = snapshot.rows[rowIndex]
            rawRow = snapshot.rawRows[rowIndex]
            for column in range(len(displayRow)):
                value = rawRow[column]
                if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
                    outputRow.append(str(int(value)))
                elif isNumberValue(value):
                    outputRow.append(repr(value))
                else:
                    outputRow.append(displayRow[column])
            writer.writerow(outputRow)


def createPdfPrinter(path):
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(path)
    printer.setPageOrientation(QPageLayout.Landscape)
    return printer


def paintTable(printer, snapshot):
    """Draws the table across as many pages as needed: all rows for the first columns, then the next columns."""
    painter = QPainter()
    if not painter.begin(printer):
        return False

    resolution = printer.resolution()
    pageRect = printer.pageLayout().paintRectPixels(resolution)
    pageWidth = pageRect.width()
    pageHeight = pageRect.height()

    bodyFont = QFont("Segoe UI", 8)
    headerFont = QFont("Segoe UI", 8)
    headerFont.setBold(True)
    titleFont = QFont("Segoe UI", 11)
    titleFont.setBold(True)
    footerFont = QFont("Segoe UI", 7)

    painter.setFont(bodyFont)
    bodyMetrics = painter.fontMetrics()
    painter.setFont(headerFont)
    headerMetrics = painter.fontMetrics()
    painter.setFont(titleFont)
    titleHeight = painter.fontMetrics().height() * 1.6
    painter.setFont(footerFont)
    footerHeight = painter.fontMetrics().height() * 1.6

    padding = bodyMetrics.averageCharWidth()
    rowHeight = bodyMetrics.height() * 1.45
    columnCount = len(snapshot.headers)

    # Measure columns from the header and a sample of rows.
    maxColumnWidth = pageWidth * 0.45
    minColumnWidth = bodyMetrics.averageCharWidth() * 4
    columnWidths = []
    sampleRows = snapshot.rows[:400]
    for column in range(columnCount):
        width = headerMetrics.horizontalAdvance(snapshot.headers[column])
        for row in sampleRows:
            textWidth = bodyMetrics.horizontalAdvance(row[column])
            if textWidth > width:
                width = textWidth
        width = width + padding * 2
        width = max(minColumnWidth, min(maxColumnWidth, width))
        columnWidths.append(width)

    # Split columns into groups that each fit on one page width.
    columnGroups = []
    currentGroup = []
    currentWidth = 0
    for column in range(columnCount):
        if currentGroup and currentWidth + columnWidths[column] > pageWidth:
            columnGroups.append(currentGroup)
            currentGroup = []
            currentWidth = 0
        currentGroup.append(column)
        currentWidth += columnWidths[column]
    if currentGroup:
        columnGroups.append(currentGroup)
    if not columnGroups:
        columnGroups = [[]]

    usableHeight = pageHeight - titleHeight - footerHeight - rowHeight
    rowsPerPage = max(1, int(usableHeight // rowHeight))
    totalRows = len(snapshot.rows)
    pagesPerGroup = max(1, (totalRows + rowsPerPage - 1) // rowsPerPage)
    totalPages = pagesPerGroup * len(columnGroups)

    gridPen = QPen(QColor("#c8ccd0"))
    gridPen.setWidthF(max(1.0, resolution / 300))
    headerFill = QColor("#e8f1ec")
    stripeFill = QColor("#f6f8f7")
    textColor = QColor("#1b1f23")

    pageNumber = 0
    for group in columnGroups:
        for pageInGroup in range(pagesPerGroup):
            if pageNumber > 0:
                printer.newPage()
            pageNumber += 1

            painter.setPen(textColor)
            painter.setFont(titleFont)
            painter.drawText(QRectF(0, 0, pageWidth, titleHeight), Qt.AlignLeft | Qt.AlignVCenter, snapshot.title)

            y = titleHeight
            x = 0.0
            painter.setFont(headerFont)
            for column in group:
                cellRect = QRectF(x, y, columnWidths[column], rowHeight)
                painter.fillRect(cellRect, headerFill)
                painter.setPen(gridPen)
                painter.drawRect(cellRect)
                painter.setPen(textColor)
                textRect = cellRect.adjusted(padding, 0, -padding, 0)
                text = headerMetrics.elidedText(snapshot.headers[column], Qt.ElideRight, int(textRect.width()))
                painter.drawText(textRect, Qt.AlignLeft | Qt.AlignVCenter, text)
                x += columnWidths[column]
            y += rowHeight

            painter.setFont(bodyFont)
            firstRow = pageInGroup * rowsPerPage
            lastRow = min(totalRows, firstRow + rowsPerPage)
            for rowIndex in range(firstRow, lastRow):
                x = 0.0
                for column in group:
                    cellRect = QRectF(x, y, columnWidths[column], rowHeight)
                    if rowIndex % 2 == 1:
                        painter.fillRect(cellRect, stripeFill)
                    painter.setPen(gridPen)
                    painter.drawRect(cellRect)
                    painter.setPen(textColor)
                    textRect = cellRect.adjusted(padding, 0, -padding, 0)
                    text = bodyMetrics.elidedText(snapshot.rows[rowIndex][column], Qt.ElideRight, int(textRect.width()))
                    alignment = Qt.AlignLeft | Qt.AlignVCenter
                    if isNumberValue(snapshot.rawRows[rowIndex][column]):
                        alignment = Qt.AlignRight | Qt.AlignVCenter
                    painter.drawText(textRect, alignment, text)
                    x += columnWidths[column]
                y += rowHeight

            painter.setFont(footerFont)
            painter.setPen(QColor("#6a737d"))
            footerRect = QRectF(0, pageHeight - footerHeight, pageWidth, footerHeight)
            footerText = "Page {} of {}".format(pageNumber, totalPages)
            painter.drawText(footerRect, Qt.AlignRight | Qt.AlignVCenter, footerText)
            if totalRows == 0 and pageNumber == 1:
                painter.drawText(footerRect, Qt.AlignLeft | Qt.AlignVCenter, "No rows to show")

    painter.end()
    return True
