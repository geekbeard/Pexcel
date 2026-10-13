"""Excel-style dropdown shown when a column header is clicked: sort buttons plus a value checklist."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout,
)

BLANK_LABEL = "(Blanks)"
SELECT_ALL_LABEL = "(Select All)"
MAX_LISTED_VALUES = 20000


class FilterPopup(QFrame):
    sortRequested = Signal(int, object)        # column, Qt.SortOrder
    filterApplied = Signal(int, object)        # column, set of texts or None

    def __init__(self, column, columnTitle, values, currentFilter, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setObjectName("filterPopup")
        self.setFrameShape(QFrame.StyledPanel)
        self.column = column
        self.isUpdatingChecks = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        titleLabel = QLabel(columnTitle)
        titleLabel.setObjectName("popupTitle")
        layout.addWidget(titleLabel)

        sortAscendingButton = QPushButton("Sort A → Z  /  smallest first")
        sortDescendingButton = QPushButton("Sort Z → A  /  largest first")
        sortAscendingButton.clicked.connect(self.onSortAscending)
        sortDescendingButton.clicked.connect(self.onSortDescending)
        layout.addWidget(sortAscendingButton)
        layout.addWidget(sortDescendingButton)

        clearButton = QPushButton("Clear filter")
        clearButton.setEnabled(currentFilter is not None)
        clearButton.clicked.connect(self.onClearFilter)
        layout.addWidget(clearButton)

        self.searchEdit = QLineEdit()
        self.searchEdit.setPlaceholderText("Search values...")
        self.searchEdit.setClearButtonEnabled(True)
        self.searchEdit.textChanged.connect(self.onSearchChanged)
        layout.addWidget(self.searchEdit)

        self.valueList = QListWidget()
        self.valueList.setMinimumHeight(220)
        self.valueList.setUniformItemSizes(True)
        layout.addWidget(self.valueList)

        self.selectAllItem = QListWidgetItem(SELECT_ALL_LABEL)
        self.selectAllItem.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        self.valueList.addItem(self.selectAllItem)

        hasBlank = "" in values
        listedValues = [text for text in values if text != ""]
        self.isTruncated = len(listedValues) > MAX_LISTED_VALUES
        if self.isTruncated:
            listedValues = listedValues[:MAX_LISTED_VALUES]
        if hasBlank:
            listedValues.append("")

        for text in listedValues:
            label = text
            if text == "":
                label = BLANK_LABEL
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, text)
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            isChecked = currentFilter is None or text in currentFilter
            item.setCheckState(Qt.Checked if isChecked else Qt.Unchecked)
            self.valueList.addItem(item)
        self.updateSelectAllState()
        self.valueList.itemChanged.connect(self.onItemChanged)

        if self.isTruncated:
            noteLabel = QLabel("Showing first {} values. Use search to narrow.".format(MAX_LISTED_VALUES))
            noteLabel.setObjectName("popupNote")
            layout.addWidget(noteLabel)

        buttonRow = QHBoxLayout()
        buttonRow.addStretch(1)
        cancelButton = QPushButton("Cancel")
        okButton = QPushButton("OK")
        okButton.setObjectName("primaryButton")
        okButton.setDefault(True)
        cancelButton.clicked.connect(self.close)
        okButton.clicked.connect(self.onOk)
        buttonRow.addWidget(cancelButton)
        buttonRow.addWidget(okButton)
        layout.addLayout(buttonRow)

        self.setMinimumWidth(280)
        self.searchEdit.setFocus()

    def valueItems(self):
        items = []
        for rowIndex in range(1, self.valueList.count()):
            items.append(self.valueList.item(rowIndex))
        return items

    def onSearchChanged(self, text):
        needle = text.strip().lower()
        for item in self.valueItems():
            isVisible = needle == "" or needle in item.text().lower()
            item.setHidden(not isVisible)
        self.updateSelectAllState()

    def onItemChanged(self, changedItem):
        if self.isUpdatingChecks:
            return
        self.isUpdatingChecks = True
        if changedItem is self.selectAllItem:
            newState = changedItem.checkState()
            if newState == Qt.PartiallyChecked:
                newState = Qt.Checked
            for item in self.valueItems():
                if not item.isHidden():
                    item.setCheckState(newState)
        self.isUpdatingChecks = False
        self.updateSelectAllState()

    def updateSelectAllState(self):
        checkedCount = 0
        visibleCount = 0
        for item in self.valueItems():
            if item.isHidden():
                continue
            visibleCount += 1
            if item.checkState() == Qt.Checked:
                checkedCount += 1
        self.isUpdatingChecks = True
        if visibleCount > 0 and checkedCount == visibleCount:
            self.selectAllItem.setCheckState(Qt.Checked)
        elif checkedCount == 0:
            self.selectAllItem.setCheckState(Qt.Unchecked)
        else:
            self.selectAllItem.setCheckState(Qt.PartiallyChecked)
        self.isUpdatingChecks = False

    def onSortAscending(self):
        self.sortRequested.emit(self.column, Qt.AscendingOrder)
        self.close()

    def onSortDescending(self):
        self.sortRequested.emit(self.column, Qt.DescendingOrder)
        self.close()

    def onClearFilter(self):
        self.filterApplied.emit(self.column, None)
        self.close()

    def onOk(self):
        isSearching = self.searchEdit.text().strip() != ""
        allowedValues = set()
        everythingChecked = not self.isTruncated and not isSearching
        for item in self.valueItems():
            if item.isHidden():
                continue
            if item.checkState() == Qt.Checked:
                allowedValues.add(item.data(Qt.UserRole))
            else:
                everythingChecked = False
        if everythingChecked:
            self.filterApplied.emit(self.column, None)
        else:
            self.filterApplied.emit(self.column, allowedValues)
        self.close()
