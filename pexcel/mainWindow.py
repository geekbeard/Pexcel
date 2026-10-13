"""Main application window."""

import os

from PySide6.QtCore import QEvent, QObject, QPoint, QSettings, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QFont, QGuiApplication, QKeySequence, QPageLayout
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton, QSizePolicy, QStackedWidget,
    QTabBar, QTableView, QToolBar, QVBoxLayout, QWidget,
)

from pexcel import __version__
from pexcel.exporters import TableSnapshot, createPdfPrinter, exportCsv, paintTable
from pexcel.filterPopup import FilterPopup
from pexcel.sheetModel import SheetFilterProxy, SheetModel
from pexcel.theme import THEME_DARK, THEME_LIGHT, THEME_SYSTEM, applyTheme
from pexcel.workbookLoader import SUPPORTED_EXTENSIONS, isNumberValue, isSupportedFile, loadWorkbook

MAX_RECENT_FILES = 10
MAX_STATS_CELLS = 500000
MIN_FONT_SIZE = 6
MAX_FONT_SIZE = 28
DEFAULT_FONT_SIZE = 10


class LoadWorker(QObject):
    """Reads a workbook on a background thread so the window stays responsive."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            workbook = loadWorkbook(self.path)
            self.finished.emit(workbook)
        except Exception as error:
            self.failed.emit(str(error))


class SheetState:
    """Model, proxy and header choice for one sheet. Kept while switching tabs."""

    def __init__(self, model, proxy):
        self.model = model
        self.proxy = proxy


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.settings = QSettings("Pexcel", "Pexcel")
        self.workbook = None
        self.sheetStates = {}
        self.headerRowOverrides = {}
        self.currentSheetIndex = -1
        self.loadThread = None
        self.loadWorker = None
        self.loadingPath = None
        self.activePopup = None

        self.useHeaderRow = self.readBoolSetting("useHeaderRow", True)
        self.themeName = self.settings.value("theme", THEME_SYSTEM)
        self.fontSize = int(self.settings.value("fontSize", DEFAULT_FONT_SIZE))

        self.setWindowTitle("Pexcel")
        self.setAcceptDrops(True)
        self.resize(1280, 800)

        self.createActions()
        self.createMenus()
        self.createToolBar()
        self.createCentralArea()
        self.createStatusBar()
        self.applyCurrentTheme()
        self.applyFontSize()
        self.updateActionStates()
        self.refreshRecentFiles()

        try:
            self.app.styleHints().colorSchemeChanged.connect(self.onSystemColorSchemeChanged)
        except AttributeError:
            pass

        geometry = self.settings.value("windowGeometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    # ------------------------------------------------------------------ setup

    def readBoolSetting(self, key, defaultValue):
        value = self.settings.value(key, defaultValue)
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)

    def createActions(self):
        self.openAction = QAction("Open...", self)
        self.openAction.setShortcut(QKeySequence.Open)
        self.openAction.setToolTip("Open a spreadsheet (Ctrl+O)")
        self.openAction.triggered.connect(self.onOpenFile)

        self.reloadAction = QAction("Reload", self)
        self.reloadAction.setShortcut(QKeySequence("F5"))
        self.reloadAction.setToolTip("Read the file again from disk (F5)")
        self.reloadAction.triggered.connect(self.onReload)

        self.exportCsvAction = QAction("Export CSV...", self)
        self.exportCsvAction.setShortcut(QKeySequence("Ctrl+E"))
        self.exportCsvAction.setToolTip("Save the visible rows of this sheet as CSV (Ctrl+E)")
        self.exportCsvAction.triggered.connect(self.onExportCsv)

        self.exportPdfAction = QAction("Export PDF...", self)
        self.exportPdfAction.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self.exportPdfAction.setToolTip("Save the visible rows of this sheet as PDF (Ctrl+Shift+E)")
        self.exportPdfAction.triggered.connect(self.onExportPdf)

        self.printAction = QAction("Print...", self)
        self.printAction.setShortcut(QKeySequence.Print)
        self.printAction.setToolTip("Print preview and print (Ctrl+P)")
        self.printAction.triggered.connect(self.onPrint)

        self.exitAction = QAction("Exit", self)
        self.exitAction.setShortcut(QKeySequence("Alt+F4"))
        self.exitAction.triggered.connect(self.close)

        self.copyAction = QAction("Copy", self)
        self.copyAction.setShortcut(QKeySequence.Copy)
        self.copyAction.triggered.connect(self.onCopy)

        self.findAction = QAction("Search", self)
        self.findAction.setShortcut(QKeySequence.Find)
        self.findAction.triggered.connect(self.onFocusSearch)

        self.headerRowAction = QAction("First Row as Header", self)
        self.headerRowAction.setCheckable(True)
        self.headerRowAction.setChecked(self.useHeaderRow)
        self.headerRowAction.setShortcut(QKeySequence("Ctrl+H"))
        self.headerRowAction.setToolTip("Use the first filled row as column titles (Ctrl+H)")
        self.headerRowAction.toggled.connect(self.onHeaderRowToggled)

        self.clearFiltersAction = QAction("Clear Filters", self)
        self.clearFiltersAction.setShortcut(QKeySequence("Ctrl+Shift+L"))
        self.clearFiltersAction.setToolTip("Remove all filters and the search on this sheet (Ctrl+Shift+L)")
        self.clearFiltersAction.triggered.connect(self.onClearFilters)

        self.resetSortAction = QAction("Original Order", self)
        self.resetSortAction.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self.resetSortAction.setToolTip("Undo sorting, back to file order (Ctrl+Shift+R)")
        self.resetSortAction.triggered.connect(self.onResetSort)

        self.autoFitAction = QAction("Fit Columns", self)
        self.autoFitAction.setToolTip("Resize columns to their content")
        self.autoFitAction.triggered.connect(self.onAutoFitColumns)

        self.zoomInAction = QAction("Zoom In", self)
        self.zoomInAction.setShortcuts([QKeySequence.ZoomIn, QKeySequence("Ctrl+=")])
        self.zoomInAction.triggered.connect(self.onZoomIn)

        self.zoomOutAction = QAction("Zoom Out", self)
        self.zoomOutAction.setShortcut(QKeySequence.ZoomOut)
        self.zoomOutAction.triggered.connect(self.onZoomOut)

        self.zoomResetAction = QAction("Reset Zoom", self)
        self.zoomResetAction.setShortcut(QKeySequence("Ctrl+0"))
        self.zoomResetAction.triggered.connect(self.onZoomReset)

        self.nextSheetAction = QAction("Next Sheet", self)
        self.nextSheetAction.setShortcut(QKeySequence("Ctrl+PgDown"))
        self.nextSheetAction.triggered.connect(self.onNextSheet)

        self.previousSheetAction = QAction("Previous Sheet", self)
        self.previousSheetAction.setShortcut(QKeySequence("Ctrl+PgUp"))
        self.previousSheetAction.triggered.connect(self.onPreviousSheet)

        self.themeGroup = QActionGroup(self)
        self.themeActions = {}
        for themeKey, themeLabel in [(THEME_SYSTEM, "System"), (THEME_LIGHT, "Light"), (THEME_DARK, "Dark")]:
            action = QAction(themeLabel, self)
            action.setCheckable(True)
            action.setChecked(themeKey == self.themeName)
            action.setData(themeKey)
            action.triggered.connect(self.onThemeChosen)
            self.themeGroup.addAction(action)
            self.themeActions[themeKey] = action

        self.aboutAction = QAction("About Pexcel", self)
        self.aboutAction.triggered.connect(self.onAbout)

    def createMenus(self):
        menuBar = self.menuBar()

        fileMenu = menuBar.addMenu("&File")
        fileMenu.addAction(self.openAction)
        self.recentMenu = fileMenu.addMenu("Open Recent")
        fileMenu.addAction(self.reloadAction)
        fileMenu.addSeparator()
        fileMenu.addAction(self.exportCsvAction)
        fileMenu.addAction(self.exportPdfAction)
        fileMenu.addAction(self.printAction)
        fileMenu.addSeparator()
        fileMenu.addAction(self.exitAction)

        editMenu = menuBar.addMenu("&Edit")
        editMenu.addAction(self.copyAction)
        editMenu.addAction(self.findAction)

        dataMenu = menuBar.addMenu("&Data")
        dataMenu.addAction(self.headerRowAction)
        dataMenu.addAction(self.clearFiltersAction)
        dataMenu.addAction(self.resetSortAction)

        viewMenu = menuBar.addMenu("&View")
        viewMenu.addAction(self.zoomInAction)
        viewMenu.addAction(self.zoomOutAction)
        viewMenu.addAction(self.zoomResetAction)
        viewMenu.addSeparator()
        viewMenu.addAction(self.autoFitAction)
        viewMenu.addSeparator()
        viewMenu.addAction(self.nextSheetAction)
        viewMenu.addAction(self.previousSheetAction)
        viewMenu.addSeparator()
        themeMenu = viewMenu.addMenu("Theme")
        for themeKey in [THEME_SYSTEM, THEME_LIGHT, THEME_DARK]:
            themeMenu.addAction(self.themeActions[themeKey])

        helpMenu = menuBar.addMenu("&Help")
        helpMenu.addAction(self.aboutAction)

    def createToolBar(self):
        toolBar = QToolBar("Main")
        toolBar.setMovable(False)
        toolBar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(toolBar)

        toolBar.addAction(self.openAction)
        toolBar.addSeparator()
        toolBar.addAction(self.exportCsvAction)
        toolBar.addAction(self.exportPdfAction)
        toolBar.addAction(self.printAction)
        toolBar.addSeparator()
        toolBar.addAction(self.headerRowAction)
        toolBar.addAction(self.clearFiltersAction)
        toolBar.addAction(self.resetSortAction)
        toolBar.addAction(self.autoFitAction)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolBar.addWidget(spacer)

        self.searchEdit = QLineEdit()
        self.searchEdit.setPlaceholderText("Search all cells  (Ctrl+F)")
        self.searchEdit.setClearButtonEnabled(True)
        self.searchEdit.setFixedWidth(280)
        self.searchEdit.textChanged.connect(self.onSearchTextChanged)
        toolBar.addWidget(self.searchEdit)

        self.searchTimer = QTimer(self)
        self.searchTimer.setSingleShot(True)
        self.searchTimer.setInterval(250)
        self.searchTimer.timeout.connect(self.applySearch)

    def createCentralArea(self):
        centralArea = QWidget()
        centralArea.setObjectName("centralArea")
        centralLayout = QVBoxLayout(centralArea)
        centralLayout.setContentsMargins(0, 0, 0, 0)
        centralLayout.setSpacing(0)

        self.stack = QStackedWidget()
        self.welcomePage = self.createWelcomePage()
        self.stack.addWidget(self.welcomePage)

        self.tableView = QTableView()
        self.tableView.setAlternatingRowColors(True)
        self.tableView.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tableView.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.tableView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tableView.setWordWrap(False)
        self.tableView.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tableView.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tableView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tableView.customContextMenuRequested.connect(self.onTableContextMenu)
        self.tableView.viewport().installEventFilter(self)

        horizontalHeader = self.tableView.horizontalHeader()
        horizontalHeader.setSectionsClickable(True)
        horizontalHeader.setHighlightSections(True)
        horizontalHeader.setSortIndicatorShown(False)
        horizontalHeader.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        horizontalHeader.setResizeContentsPrecision(200)
        horizontalHeader.setStretchLastSection(False)
        horizontalHeader.setMinimumSectionSize(40)
        horizontalHeader.setSectionResizeMode(QHeaderView.Interactive)
        horizontalHeader.sectionClicked.connect(self.onHeaderClicked)

        verticalHeader = self.tableView.verticalHeader()
        verticalHeader.setSectionResizeMode(QHeaderView.Fixed)
        verticalHeader.setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        verticalHeader.setContextMenuPolicy(Qt.CustomContextMenu)
        verticalHeader.customContextMenuRequested.connect(self.onRowHeaderContextMenu)
        verticalHeader.setToolTip("Right-click a row number to use that row as the header")

        self.stack.addWidget(self.tableView)

        self.emptySheetLabel = QLabel("")
        self.emptySheetLabel.setAlignment(Qt.AlignCenter)
        self.emptySheetLabel.setObjectName("welcomeSubtitle")
        self.stack.addWidget(self.emptySheetLabel)

        centralLayout.addWidget(self.stack, 1)

        self.sheetBar = QWidget()
        self.sheetBar.setObjectName("sheetBar")
        sheetBarLayout = QHBoxLayout(self.sheetBar)
        sheetBarLayout.setContentsMargins(6, 0, 6, 0)
        self.sheetTabs = QTabBar()
        self.sheetTabs.setObjectName("sheetTabs")
        self.sheetTabs.setExpanding(False)
        self.sheetTabs.setDrawBase(False)
        self.sheetTabs.setUsesScrollButtons(True)
        self.sheetTabs.currentChanged.connect(self.onSheetTabChanged)
        sheetBarLayout.addWidget(self.sheetTabs, 1)
        self.sheetBar.setVisible(False)
        centralLayout.addWidget(self.sheetBar)

        self.setCentralWidget(centralArea)

    def createWelcomePage(self):
        page = QWidget()
        page.setObjectName("welcomePage")
        outerLayout = QVBoxLayout(page)
        outerLayout.addStretch(1)

        innerLayout = QVBoxLayout()
        innerLayout.setSpacing(10)

        titleLabel = QLabel("Pexcel")
        titleLabel.setObjectName("welcomeTitle")
        titleLabel.setAlignment(Qt.AlignCenter)
        innerLayout.addWidget(titleLabel)

        subtitleLabel = QLabel("Open any Excel file to view it. Or drop one on this window.")
        subtitleLabel.setObjectName("welcomeSubtitle")
        subtitleLabel.setAlignment(Qt.AlignCenter)
        innerLayout.addWidget(subtitleLabel)

        openButton = QPushButton("Open File")
        openButton.setObjectName("bigOpenButton")
        openButton.setCursor(Qt.PointingHandCursor)
        openButton.clicked.connect(self.onOpenFile)
        buttonRow = QHBoxLayout()
        buttonRow.addStretch(1)
        buttonRow.addWidget(openButton)
        buttonRow.addStretch(1)
        innerLayout.addSpacing(8)
        innerLayout.addLayout(buttonRow)

        self.recentTitleLabel = QLabel("Recent files")
        self.recentTitleLabel.setObjectName("recentTitle")
        self.recentTitleLabel.setAlignment(Qt.AlignCenter)
        innerLayout.addWidget(self.recentTitleLabel)

        self.recentListLayout = QVBoxLayout()
        self.recentListLayout.setSpacing(0)
        innerLayout.addLayout(self.recentListLayout)

        centerRow = QHBoxLayout()
        centerRow.addStretch(1)
        centerRow.addLayout(innerLayout)
        centerRow.addStretch(1)
        outerLayout.addLayout(centerRow)
        outerLayout.addStretch(2)
        return page

    def createStatusBar(self):
        statusBar = self.statusBar()
        statusBar.setSizeGripEnabled(True)
        self.rowsLabel = QLabel("")
        self.selectionLabel = QLabel("")
        statusBar.addWidget(self.rowsLabel, 1)
        statusBar.addPermanentWidget(self.selectionLabel)

    # ------------------------------------------------------------- theme/zoom

    def applyCurrentTheme(self):
        applyTheme(self.app, self.themeName)

    def onSystemColorSchemeChanged(self, scheme):
        if self.themeName == THEME_SYSTEM:
            self.applyCurrentTheme()

    def onThemeChosen(self):
        action = self.sender()
        self.themeName = action.data()
        self.settings.setValue("theme", self.themeName)
        self.applyCurrentTheme()

    def applyFontSize(self):
        font = QFont(self.app.font())
        font.setPointSize(self.fontSize)
        self.tableView.setFont(font)
        self.tableView.horizontalHeader().setFont(font)
        self.tableView.verticalHeader().setFont(font)
        rowHeight = self.tableView.fontMetrics().height() + 10
        self.tableView.verticalHeader().setDefaultSectionSize(rowHeight)
        self.tableView.verticalHeader().setMinimumSectionSize(rowHeight)
        self.settings.setValue("fontSize", self.fontSize)

    def onZoomIn(self):
        if self.fontSize < MAX_FONT_SIZE:
            self.fontSize += 1
            self.applyFontSize()

    def onZoomOut(self):
        if self.fontSize > MIN_FONT_SIZE:
            self.fontSize -= 1
            self.applyFontSize()

    def onZoomReset(self):
        self.fontSize = DEFAULT_FONT_SIZE
        self.applyFontSize()

    def eventFilter(self, watched, event):
        # Ctrl + mouse wheel over the table zooms, like in Excel.
        if watched is self.tableView.viewport() and event.type() == QEvent.Wheel:
            if event.modifiers() & Qt.ControlModifier:
                if event.angleDelta().y() > 0:
                    self.onZoomIn()
                elif event.angleDelta().y() < 0:
                    self.onZoomOut()
                return True
        return super().eventFilter(watched, event)

    # ----------------------------------------------------------- open / load

    def onOpenFile(self):
        patterns = " ".join("*" + extension for extension in SUPPORTED_EXTENSIONS)
        startFolder = self.settings.value("lastFolder", "")
        path, unusedFilter = QFileDialog.getOpenFileName(
            self, "Open Spreadsheet", startFolder,
            "Spreadsheets ({});;All files (*.*)".format(patterns),
        )
        if path:
            self.openPath(path)

    def onReload(self):
        if self.workbook is not None:
            self.openPath(self.workbook.path)

    def openPath(self, path):
        if self.loadThread is not None:
            return
        if not os.path.isfile(path):
            QMessageBox.warning(self, "Pexcel", "File not found:\n{}".format(path))
            self.removeRecentFile(path)
            return
        self.settings.setValue("lastFolder", os.path.dirname(path))
        self.loadingPath = path
        self.rowsLabel.setText("Loading {} ...".format(os.path.basename(path)))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.setLoadingState(True)

        self.loadThread = QThread(self)
        self.loadWorker = LoadWorker(path)
        self.loadWorker.moveToThread(self.loadThread)
        self.loadThread.started.connect(self.loadWorker.run)
        self.loadWorker.finished.connect(self.onLoadFinished)
        self.loadWorker.failed.connect(self.onLoadFailed)
        self.loadThread.start()

    def stopLoadThread(self):
        QApplication.restoreOverrideCursor()
        self.loadThread.quit()
        self.loadThread.wait()
        self.loadWorker.deleteLater()
        self.loadThread.deleteLater()
        self.loadWorker = None
        self.loadThread = None
        self.setLoadingState(False)

    def onLoadFinished(self, workbook):
        self.stopLoadThread()
        self.showWorkbook(workbook)
        self.addRecentFile(workbook.path)

    def onLoadFailed(self, message):
        path = self.loadingPath
        self.stopLoadThread()
        self.updateRowsLabel()
        QMessageBox.critical(
            self, "Could not open file",
            "Pexcel could not read this file:\n{}\n\n{}".format(path, message),
        )

    def setLoadingState(self, isLoading):
        self.openAction.setEnabled(not isLoading)
        self.recentMenu.setEnabled(not isLoading)
        if isLoading:
            self.reloadAction.setEnabled(False)
        else:
            self.updateActionStates()

    def showWorkbook(self, workbook):
        self.closePopup()
        self.workbook = workbook
        self.sheetStates = {}
        self.headerRowOverrides = {}
        self.currentSheetIndex = -1
        self.searchEdit.blockSignals(True)
        self.searchEdit.clear()
        self.searchEdit.blockSignals(False)

        self.sheetTabs.blockSignals(True)
        while self.sheetTabs.count() > 0:
            self.sheetTabs.removeTab(0)
        firstVisibleIndex = 0
        foundVisible = False
        for sheetIndex, sheet in enumerate(workbook.sheets):
            label = sheet.name
            if sheet.isHidden:
                label = sheet.name + " (hidden)"
            self.sheetTabs.addTab(label)
            if sheet.isHidden:
                self.sheetTabs.setTabToolTip(sheetIndex, "This sheet is hidden in the file")
            elif not foundVisible:
                firstVisibleIndex = sheetIndex
                foundVisible = True
        self.sheetTabs.setCurrentIndex(firstVisibleIndex)
        self.sheetTabs.blockSignals(False)
        self.sheetBar.setVisible(len(workbook.sheets) > 0)

        self.setWindowTitle("{} - Pexcel".format(workbook.fileName))
        self.showSheet(firstVisibleIndex)

    # ----------------------------------------------------------------- sheets

    def getSheetState(self, sheetIndex):
        if sheetIndex not in self.sheetStates:
            sheet = self.workbook.sheets[sheetIndex]
            headerRowIndex = None
            if sheetIndex in self.headerRowOverrides:
                headerRowIndex = self.headerRowOverrides[sheetIndex]
            elif self.useHeaderRow:
                headerRowIndex = sheet.guessHeaderRow()
            model = SheetModel(sheet, headerRowIndex, self)
            proxy = SheetFilterProxy(self)
            proxy.setSourceModel(model)
            self.sheetStates[sheetIndex] = SheetState(model, proxy)
        return self.sheetStates[sheetIndex]

    def currentState(self):
        if self.workbook is None or self.currentSheetIndex < 0:
            return None
        return self.sheetStates.get(self.currentSheetIndex)

    def onSheetTabChanged(self, sheetIndex):
        if self.workbook is None or sheetIndex < 0:
            return
        self.showSheet(sheetIndex)

    def showSheet(self, sheetIndex):
        self.closePopup()
        if sheetIndex < 0 or sheetIndex >= len(self.workbook.sheets):
            return
        self.currentSheetIndex = sheetIndex
        sheet = self.workbook.sheets[sheetIndex]

        if sheet.loadError is not None or sheet.columnCount == 0:
            if sheet.loadError is not None:
                self.emptySheetLabel.setText("This sheet has no cells to show (for example a chart sheet).")
            else:
                self.emptySheetLabel.setText("This sheet is empty.")
            self.stack.setCurrentWidget(self.emptySheetLabel)
            self.tableView.setModel(None)
            self.updateRowsLabel()
            self.updateActionStates()
            return

        isNewState = sheetIndex not in self.sheetStates
        state = self.getSheetState(sheetIndex)
        self.tableView.setModel(state.proxy)
        self.tableView.selectionModel().selectionChanged.connect(self.onSelectionChanged)
        self.stack.setCurrentWidget(self.tableView)

        self.searchEdit.blockSignals(True)
        self.searchEdit.setText(state.proxy.searchText)
        self.searchEdit.blockSignals(False)

        self.updateSortIndicator()
        if isNewState:
            self.onAutoFitColumns()
        self.updateRowsLabel()
        self.updateSelectionLabel()
        self.updateActionStates()

    def onNextSheet(self):
        if self.sheetTabs.count() > 0:
            self.sheetTabs.setCurrentIndex((self.sheetTabs.currentIndex() + 1) % self.sheetTabs.count())

    def onPreviousSheet(self):
        if self.sheetTabs.count() > 0:
            self.sheetTabs.setCurrentIndex((self.sheetTabs.currentIndex() - 1) % self.sheetTabs.count())

    def onAutoFitColumns(self):
        state = self.currentState()
        if state is None:
            return
        header = self.tableView.horizontalHeader()
        maxWidth = 420
        columnCount = state.model.columnCount()
        # Fitting thousands of columns is slow; fit the first ones and leave the rest at default.
        fitCount = min(columnCount, 300)
        for column in range(fitCount):
            self.tableView.resizeColumnToContents(column)
            if header.sectionSize(column) > maxWidth:
                header.resizeSection(column, maxWidth)
            elif header.sectionSize(column) < 60:
                header.resizeSection(column, 60)

    def onHeaderRowToggled(self, isChecked):
        self.useHeaderRow = isChecked
        self.settings.setValue("useHeaderRow", isChecked)
        if self.workbook is None:
            return
        # Header choice changes which rows are data, so filters and sorting start fresh.
        self.headerRowOverrides = {}
        self.sheetStates = {}
        sheetIndex = self.currentSheetIndex
        self.currentSheetIndex = -1
        self.showSheet(sheetIndex)

    def onRowHeaderContextMenu(self, position):
        state = self.currentState()
        if state is None:
            return
        verticalHeader = self.tableView.verticalHeader()
        proxyRow = verticalHeader.logicalIndexAt(position)
        menu = QMenu(self)
        if proxyRow >= 0:
            sourceRow = state.proxy.mapToSource(state.proxy.index(proxyRow, 0)).row()
            sheetRow = state.model.sheetRowAt(sourceRow)
            useRowAction = menu.addAction("Use Row {} as Header".format(sheetRow + 1))
            useRowAction.triggered.connect(lambda: self.setHeaderRow(sheetRow))
        if state.model.headerRowIndex is not None:
            noHeaderAction = menu.addAction("No Header Row (show all rows)")
            noHeaderAction.triggered.connect(lambda: self.setHeaderRow(None))
        menu.exec(verticalHeader.mapToGlobal(position))

    def setHeaderRow(self, sheetRow):
        """Manually choose the header row for the current sheet. Resets that sheet's filters and sort."""
        sheetIndex = self.currentSheetIndex
        self.headerRowOverrides[sheetIndex] = sheetRow
        if sheetIndex in self.sheetStates:
            del self.sheetStates[sheetIndex]
        self.currentSheetIndex = -1
        self.showSheet(sheetIndex)

    # --------------------------------------------------------- sort / filter

    def onHeaderClicked(self, column):
        state = self.currentState()
        if state is None:
            return
        self.closePopup()
        values = state.proxy.valuesForColumn(column)
        currentFilter = state.proxy.columnFilters.get(column)
        popup = FilterPopup(column, state.model.columnLabel(column), values, currentFilter, self)
        popup.sortRequested.connect(self.onSortRequested)
        popup.filterApplied.connect(self.onFilterApplied)

        header = self.tableView.horizontalHeader()
        sectionX = header.sectionViewportPosition(column)
        popupPosition = header.mapToGlobal(QPoint(max(0, sectionX), header.height()))
        popup.adjustSize()
        screen = QGuiApplication.screenAt(popupPosition)
        if screen is not None:
            available = screen.availableGeometry()
            if popupPosition.x() + popup.width() > available.right():
                popupPosition.setX(available.right() - popup.width())
            if popupPosition.y() + popup.height() > available.bottom():
                popupPosition.setY(available.bottom() - popup.height())
        popup.move(popupPosition)
        self.activePopup = popup
        popup.show()

    def closePopup(self):
        if self.activePopup is not None:
            self.activePopup.close()
            self.activePopup.deleteLater()
            self.activePopup = None

    def onSortRequested(self, column, order):
        state = self.currentState()
        if state is None:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        state.proxy.sort(column, order)
        QApplication.restoreOverrideCursor()
        self.updateSortIndicator()

    def onResetSort(self):
        state = self.currentState()
        if state is None:
            return
        state.proxy.resetSort()
        self.updateSortIndicator()

    def updateSortIndicator(self):
        header = self.tableView.horizontalHeader()
        state = self.currentState()
        if state is None or state.proxy.sortColumn < 0:
            header.setSortIndicatorShown(False)
            return
        header.setSortIndicatorShown(True)
        header.setSortIndicator(state.proxy.sortColumn, state.proxy.sortOrderValue)

    def onFilterApplied(self, column, allowedValues):
        state = self.currentState()
        if state is None:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        state.proxy.setColumnFilter(column, allowedValues)
        QApplication.restoreOverrideCursor()
        self.updateRowsLabel()
        self.updateActionStates()

    def onClearFilters(self):
        state = self.currentState()
        if state is None:
            return
        self.searchEdit.blockSignals(True)
        self.searchEdit.clear()
        self.searchEdit.blockSignals(False)
        state.proxy.clearAllFilters()
        self.updateRowsLabel()
        self.updateActionStates()

    def onSearchTextChanged(self, text):
        self.searchTimer.start()

    def applySearch(self):
        state = self.currentState()
        if state is None:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        state.proxy.setSearchText(self.searchEdit.text())
        QApplication.restoreOverrideCursor()
        self.updateRowsLabel()
        self.updateActionStates()

    def onFocusSearch(self):
        self.searchEdit.setFocus()
        self.searchEdit.selectAll()

    # ------------------------------------------------------- selection / copy

    def onSelectionChanged(self, selected, deselected):
        self.updateSelectionLabel()

    def updateSelectionLabel(self):
        state = self.currentState()
        selectionModel = self.tableView.selectionModel()
        if state is None or selectionModel is None or self.tableView.model() is None:
            self.selectionLabel.setText("")
            return
        selection = selectionModel.selection()
        cellCount = 0
        for selectionRange in selection:
            cellCount += selectionRange.width() * selectionRange.height()
        if cellCount <= 1:
            self.selectionLabel.setText("")
            return
        if cellCount > MAX_STATS_CELLS:
            self.selectionLabel.setText("Cells: {:,}".format(cellCount))
            return

        filledCount = 0
        numberCount = 0
        total = 0.0
        proxy = state.proxy
        model = state.model
        for selectionRange in selection:
            for proxyRow in range(selectionRange.top(), selectionRange.bottom() + 1):
                sourceRow = proxy.mapToSource(proxy.index(proxyRow, 0)).row()
                for column in range(selectionRange.left(), selectionRange.right() + 1):
                    value = model.rawValue(sourceRow, column)
                    if value is None or value == "":
                        continue
                    filledCount += 1
                    if isNumberValue(value):
                        numberCount += 1
                        total += value

        parts = ["Count: {:,}".format(filledCount)]
        if numberCount > 0:
            parts.append("Sum: {}".format(formatStatNumber(total)))
            parts.append("Average: {}".format(formatStatNumber(total / numberCount)))
        self.selectionLabel.setText("    ".join(parts))

    def onCopy(self):
        if self.searchEdit.hasFocus():
            self.searchEdit.copy()
            return
        state = self.currentState()
        if state is None:
            return
        indexes = self.tableView.selectionModel().selectedIndexes()
        if not indexes:
            return
        rows = sorted(set(index.row() for index in indexes))
        columns = sorted(set(index.column() for index in indexes))
        selectedSet = set((index.row(), index.column()) for index in indexes)
        lines = []
        for row in rows:
            cells = []
            for column in columns:
                if (row, column) in selectedSet:
                    cells.append(state.proxy.index(row, column).data())
                else:
                    cells.append("")
            lines.append("\t".join(cells))
        QGuiApplication.clipboard().setText("\r\n".join(lines))

    def onTableContextMenu(self, position):
        if self.currentState() is None:
            return
        menu = QMenu(self)
        menu.addAction(self.copyAction)
        menu.addSeparator()
        index = self.tableView.indexAt(position)
        if index.isValid():
            column = index.column()
            filterValueAction = menu.addAction("Filter by This Value")
            filterValueAction.triggered.connect(lambda: self.onFilterByCellValue(index))
            sortUpAction = menu.addAction("Sort Column Ascending")
            sortUpAction.triggered.connect(lambda: self.onSortRequested(column, Qt.AscendingOrder))
            sortDownAction = menu.addAction("Sort Column Descending")
            sortDownAction.triggered.connect(lambda: self.onSortRequested(column, Qt.DescendingOrder))
            menu.addSeparator()
        menu.addAction(self.clearFiltersAction)
        menu.addAction(self.resetSortAction)
        menu.exec(self.tableView.viewport().mapToGlobal(position))

    def onFilterByCellValue(self, index):
        text = index.data()
        if text is None:
            text = ""
        self.onFilterApplied(index.column(), {text})

    # ------------------------------------------------------------ status bar

    def updateRowsLabel(self, *unusedArgs):
        if self.workbook is None:
            self.rowsLabel.setText("")
            return
        state = self.currentState()
        sheet = self.workbook.sheets[self.currentSheetIndex] if self.currentSheetIndex >= 0 else None
        if state is None or sheet is None:
            self.rowsLabel.setText(self.workbook.fileName)
            return
        totalRows = state.model.rowCount()
        shownRows = state.proxy.rowCount()
        parts = [self.workbook.fileName]
        if shownRows == totalRows:
            parts.append("{:,} rows".format(totalRows))
        else:
            parts.append("{:,} of {:,} rows shown".format(shownRows, totalRows))
        parts.append("{:,} columns".format(sheet.columnCount))
        if state.model.headerRowIndex is not None:
            parts.append("header: row {}".format(state.model.headerRowIndex + 1))
        if state.proxy.hasActiveFilters():
            parts.append("filtered")
        self.rowsLabel.setText("   |   ".join(parts))

    def updateActionStates(self):
        hasTable = self.currentState() is not None and self.stack.currentWidget() is self.tableView
        self.reloadAction.setEnabled(self.workbook is not None)
        self.exportCsvAction.setEnabled(hasTable)
        self.exportPdfAction.setEnabled(hasTable)
        self.printAction.setEnabled(hasTable)
        self.copyAction.setEnabled(hasTable)
        self.autoFitAction.setEnabled(hasTable)
        self.resetSortAction.setEnabled(hasTable)
        hasFilters = hasTable and self.currentState().proxy.hasActiveFilters()
        self.clearFiltersAction.setEnabled(hasFilters)

    # ----------------------------------------------------------------- export

    def buildSnapshot(self):
        state = self.currentState()
        proxy = state.proxy
        model = state.model
        displayRows = []
        rawRows = []
        for proxyRow in range(proxy.rowCount()):
            sourceRow = proxy.mapToSource(proxy.index(proxyRow, 0)).row()
            sheetRow = model.sheetRowAt(sourceRow)
            displayRows.append(model.sheet.displayRows[sheetRow])
            rawRows.append(model.sheet.rows[sheetRow])
        sheetName = self.workbook.sheets[self.currentSheetIndex].name
        title = "{}  -  {}".format(self.workbook.fileName, sheetName)
        return TableSnapshot(title, model.headerLabels(), displayRows, rawRows)

    def suggestedExportPath(self, extension):
        baseName = os.path.splitext(self.workbook.fileName)[0]
        sheetName = self.workbook.sheets[self.currentSheetIndex].name
        if len(self.workbook.sheets) > 1:
            baseName = baseName + " - " + sheetName
        for character in '<>:"/\\|?*':
            baseName = baseName.replace(character, "_")
        folder = self.settings.value("lastExportFolder", os.path.dirname(self.workbook.path))
        return os.path.join(folder, baseName + extension)

    def onExportCsv(self):
        if self.currentState() is None:
            return
        path, unusedFilter = QFileDialog.getSaveFileName(
            self, "Export CSV", self.suggestedExportPath(".csv"), "CSV files (*.csv)",
        )
        if not path:
            return
        self.settings.setValue("lastExportFolder", os.path.dirname(path))
        snapshot = self.buildSnapshot()
        includeHeader = self.currentState().model.headerRowIndex is not None
        try:
            exportCsv(path, snapshot, includeHeader)
        except OSError as error:
            QMessageBox.critical(self, "Export failed", "Could not write the CSV file:\n{}".format(error))
            return
        self.statusBar().showMessage("Saved {:,} rows to {}".format(len(snapshot.rows), path), 6000)

    def onExportPdf(self):
        if self.currentState() is None:
            return
        path, unusedFilter = QFileDialog.getSaveFileName(
            self, "Export PDF", self.suggestedExportPath(".pdf"), "PDF files (*.pdf)",
        )
        if not path:
            return
        self.settings.setValue("lastExportFolder", os.path.dirname(path))
        snapshot = self.buildSnapshot()
        printer = createPdfPrinter(path)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        isPainted = paintTable(printer, snapshot)
        QApplication.restoreOverrideCursor()
        if not isPainted:
            QMessageBox.critical(self, "Export failed", "Could not write the PDF file:\n{}".format(path))
            return
        self.statusBar().showMessage("Saved PDF to {}".format(path), 6000)

    def onPrint(self):
        if self.currentState() is None:
            return
        snapshot = self.buildSnapshot()
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageOrientation(QPageLayout.Landscape)
        dialog = QPrintPreviewDialog(printer, self)
        dialog.setWindowTitle("Print Preview")
        dialog.resize(1000, 760)
        dialog.paintRequested.connect(lambda targetPrinter: paintTable(targetPrinter, snapshot))
        dialog.exec()

    # ------------------------------------------------------------ recent files

    def recentFiles(self):
        value = self.settings.value("recentFiles", [])
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return list(value)

    def addRecentFile(self, path):
        path = os.path.normpath(path)
        files = [existing for existing in self.recentFiles() if os.path.normcase(existing) != os.path.normcase(path)]
        files.insert(0, path)
        self.settings.setValue("recentFiles", files[:MAX_RECENT_FILES])
        self.refreshRecentFiles()

    def removeRecentFile(self, path):
        files = [existing for existing in self.recentFiles() if os.path.normcase(existing) != os.path.normcase(os.path.normpath(path))]
        self.settings.setValue("recentFiles", files)
        self.refreshRecentFiles()

    def refreshRecentFiles(self):
        files = self.recentFiles()

        self.recentMenu.clear()
        for path in files:
            action = self.recentMenu.addAction(path)
            action.triggered.connect(lambda checked=False, filePath=path: self.openPath(filePath))
        if files:
            self.recentMenu.addSeparator()
            clearAction = self.recentMenu.addAction("Clear Recent Files")
            clearAction.triggered.connect(self.onClearRecentFiles)
        self.recentMenu.setEnabled(len(files) > 0)

        while self.recentListLayout.count() > 0:
            item = self.recentListLayout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for path in files[:6]:
            button = QPushButton(os.path.basename(path))
            button.setObjectName("recentButton")
            button.setToolTip(path)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, filePath=path: self.openPath(filePath))
            self.recentListLayout.addWidget(button, 0, Qt.AlignHCenter)
        self.recentTitleLabel.setVisible(len(files) > 0)

    def onClearRecentFiles(self):
        self.settings.setValue("recentFiles", [])
        self.refreshRecentFiles()

    # ------------------------------------------------------------ drag & drop

    def dragEnterEvent(self, event):
        if self.findDroppedFile(event.mimeData()) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event):
        path = self.findDroppedFile(event.mimeData())
        if path is not None:
            event.acceptProposedAction()
            self.openPath(path)

    def findDroppedFile(self, mimeData):
        if not mimeData.hasUrls():
            return None
        for url in mimeData.urls():
            if url.isLocalFile() and isSupportedFile(url.toLocalFile()):
                return url.toLocalFile()
        return None

    # ------------------------------------------------------------------ misc

    def onAbout(self):
        QMessageBox.about(
            self, "About Pexcel",
            "<b>Pexcel {}</b><br><br>A fast, read-only spreadsheet viewer.<br>"
            "Opens xlsx, xlsm, xlsb, xls, ods and csv files.<br>"
            "Everything runs locally on this computer.".format(__version__),
        )

    def closeEvent(self, event):
        self.settings.setValue("windowGeometry", self.saveGeometry())
        if self.loadThread is not None:
            self.loadThread.quit()
            self.loadThread.wait(2000)
        super().closeEvent(event)


def formatStatNumber(number):
    if float(number).is_integer() and abs(number) < 1e15:
        return "{:,}".format(int(number))
    return "{:,.4f}".format(number).rstrip("0").rstrip(".")
