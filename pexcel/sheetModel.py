"""Qt table model for one sheet, plus the proxy that applies filters and search."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QFont

from pexcel.workbookLoader import columnLetter, isEmptyValue, isNumberValue, sortKey

FILTER_MARK = "  ▾"


class SheetModel(QAbstractTableModel):
    """Shows sheet rows. Rows above and including the header row are not part of the data."""

    def __init__(self, sheet, headerRowIndex, parent=None):
        super().__init__(parent)
        self.sheet = sheet
        self.headerRowIndex = headerRowIndex
        if headerRowIndex is None:
            self.firstDataRow = 0
        else:
            self.firstDataRow = headerRowIndex + 1
        self.rowOrder = list(range(self.firstDataRow, len(sheet.rows)))
        self.filteredColumns = set()
        self.boldFont = QFont()
        self.boldFont.setBold(True)

    # ----- basic model API -----

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.rowOrder)

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return self.sheet.columnCount

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        sheetRow = self.rowOrder[index.row()]
        column = index.column()
        if role == Qt.DisplayRole:
            return self.sheet.displayRows[sheetRow][column]
        if role == Qt.TextAlignmentRole:
            value = self.sheet.rows[sheetRow][column]
            if isNumberValue(value):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            if isinstance(value, bool):
                return int(Qt.AlignCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        if role == Qt.ToolTipRole:
            text = self.sheet.displayRows[sheetRow][column]
            if len(text) > 40:
                return text
            return None
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                label = self.columnLabel(section)
                if section in self.filteredColumns:
                    label = label + FILTER_MARK
                return label
            if role == Qt.ToolTipRole:
                tip = "Column " + columnLetter(section)
                if section in self.filteredColumns:
                    tip = tip + " (filtered)"
                return tip + "\nClick for sort and filter options"
            if role == Qt.FontRole and section in self.filteredColumns:
                return self.boldFont
            return None
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            # Show the original Excel row number so it matches the file.
            return str(self.rowOrder[section] + 1)
        return None

    # ----- helpers used by the window, proxy and exporters -----

    def columnLabel(self, column):
        if self.headerRowIndex is None:
            return columnLetter(column)
        text = self.sheet.displayRows[self.headerRowIndex][column]
        if text == "":
            return columnLetter(column)
        return text

    def headerLabels(self):
        return [self.columnLabel(column) for column in range(self.sheet.columnCount)]

    def sheetRowAt(self, row):
        return self.rowOrder[row]

    def rawValue(self, row, column):
        return self.sheet.rows[self.rowOrder[row]][column]

    def displayText(self, row, column):
        return self.sheet.displayRows[self.rowOrder[row]][column]

    def setFilteredColumns(self, columns):
        self.filteredColumns = set(columns)
        if self.sheet.columnCount > 0:
            self.headerDataChanged.emit(Qt.Horizontal, 0, self.sheet.columnCount - 1)

    def sortByColumn(self, column, order):
        """Stable sort, so sorting by several columns one after another works like Excel."""
        self.layoutAboutToBeChanged.emit()
        rows = self.sheet.rows
        filledRows = []
        blankRows = []
        for sheetRow in self.rowOrder:
            if isEmptyValue(rows[sheetRow][column]):
                blankRows.append(sheetRow)
            else:
                filledRows.append(sheetRow)
        reverse = order == Qt.DescendingOrder
        filledRows.sort(key=lambda sheetRow: sortKey(rows[sheetRow][column]), reverse=reverse)
        # Blank cells always go to the bottom, in both directions.
        self.rowOrder = filledRows + blankRows
        self.layoutChanged.emit()

    def resetSort(self):
        self.layoutAboutToBeChanged.emit()
        self.rowOrder = list(range(self.firstDataRow, len(self.sheet.rows)))
        self.layoutChanged.emit()


class SheetFilterProxy(QSortFilterProxyModel):
    """Applies per-column value filters and the global search box. Sorting lives in SheetModel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.columnFilters = {}
        self.searchText = ""
        self.sortColumn = -1
        self.sortOrderValue = Qt.AscendingOrder

    def filterAcceptsRow(self, sourceRow, sourceParent):
        model = self.sourceModel()
        sheetRow = model.rowOrder[sourceRow]
        rowTexts = model.sheet.displayRows[sheetRow]
        for column, allowedValues in self.columnFilters.items():
            if rowTexts[column] not in allowedValues:
                return False
        if self.searchText != "":
            searchRows = model.sheet.getSearchRows()
            if self.searchText not in searchRows[sheetRow]:
                return False
        return True

    def sort(self, column, order=Qt.AscendingOrder):
        self.sortColumn = column
        self.sortOrderValue = order
        self.sourceModel().sortByColumn(column, order)

    def resetSort(self):
        self.sortColumn = -1
        self.sourceModel().resetSort()

    def setColumnFilter(self, column, allowedValues):
        """allowedValues is a set of display strings, or None to remove the filter."""
        if allowedValues is None:
            if column in self.columnFilters:
                del self.columnFilters[column]
        else:
            self.columnFilters[column] = allowedValues
        self.sourceModel().setFilteredColumns(self.columnFilters.keys())
        self.invalidateRowsFilter()

    def clearAllFilters(self):
        self.columnFilters = {}
        self.searchText = ""
        self.sourceModel().setFilteredColumns([])
        self.invalidateRowsFilter()

    def setSearchText(self, text):
        self.searchText = text.strip().lower()
        self.invalidateRowsFilter()

    def hasActiveFilters(self):
        return len(self.columnFilters) > 0 or self.searchText != ""

    def valuesForColumn(self, column):
        """Values offered in a column's filter list: rows that pass every other filter, like Excel."""
        model = self.sourceModel()
        displayRows = model.sheet.displayRows
        rawRows = model.sheet.rows
        otherFilters = []
        for otherColumn, allowedValues in self.columnFilters.items():
            if otherColumn != column:
                otherFilters.append((otherColumn, allowedValues))
        searchRows = None
        if self.searchText != "":
            searchRows = model.sheet.getSearchRows()

        valuesByText = {}
        for sheetRow in model.rowOrder:
            rowTexts = displayRows[sheetRow]
            passes = True
            for otherColumn, allowedValues in otherFilters:
                if rowTexts[otherColumn] not in allowedValues:
                    passes = False
                    break
            if passes and searchRows is not None and self.searchText not in searchRows[sheetRow]:
                passes = False
            if passes:
                text = rowTexts[column]
                if text not in valuesByText:
                    valuesByText[text] = rawRows[sheetRow][column]

        texts = list(valuesByText.keys())
        texts.sort(key=lambda text: sortKey(valuesByText[text]))
        return texts
