# Pexcel

## Original brief

This is a local app. Python packed into exe.

It is an excel files viewer. Any excel file, opens it and shows it in an excel-like layout. no need to edit or do formulas. It's just to replace excel with a nice, easy to use, modern looking excel viewer app.

would still be nice to be able to sort rows and filter. but no need to edit the file itself or save it.

good to produce csv maybe and print pdf.

shoul open all excel files.

run fully locally.

development done withing venv. no deployment on the home server.

---

## Product spec

Pexcel is a read-only, fast, modern spreadsheet viewer for Windows. It never changes the opened file. Everything runs locally; no network access.

### Supported files
- Excel: `.xlsx .xlsm .xltx .xltm .xlsb .xls .xlt .xla .xlam`
- OpenDocument: `.ods`
- Text: `.csv .tsv .txt` (delimiter auto-detected among `, ; tab |`; encoding utf-8 / utf-16 / cp1252 fallback). In `;` files a decimal comma (`12,50`) is read as a number. Values with leading zeros (`007`) or a leading `+` stay text.
- Cell values are shown as computed values (cached formula results). Formulas, cell formatting (colors, fonts, number formats) and merged-cell spans are not shown; a merged cell's value appears in its top-left cell.

### Opening files
- Welcome screen with big "Open File" button and up to 6 recent files (click to open).
- File > Open (Ctrl+O), File > Open Recent (10 files, "Clear Recent Files"), Reload (F5).
- Drag and drop a file onto the window.
- Command line / Explorer "Open with": `Pexcel.exe path\to\file.xlsx`.
- Loading happens on a background thread; status bar shows "Loading ..." and a wait cursor. Errors show a dialog with the reason.
- Missing recent files are removed from the list when clicked.

### Viewing
- Excel-like grid: row numbers on the left (always the original row number in the file, also after sorting), column headers on top, alternating row shading, numbers right-aligned, TRUE/FALSE centered.
- Sheet tabs at the bottom, like Excel. Hidden sheets are listed as "Name (hidden)". The first visible sheet opens by default. Ctrl+PgDown / Ctrl+PgUp switch sheets. Chart sheets and empty sheets show a short message instead of a grid.
- Each sheet keeps its own filters, search and sort while switching tabs.
- Header row: "First Row as Header" (toolbar / Data menu / Ctrl+H, remembered). When on, Pexcel guesses the header row: the first row in the top 20 that is at least half as full as the fullest row (so a title like "Quarterly report" above a table is skipped). Rows above the header are not shown as data. Right-click a row number to "Use Row N as Header" or "No Header Row (show all rows)" for that sheet. When off, columns are labeled A, B, C...
- Columns are auto-fitted on first view (max 420px, first 300 columns); "Fit Columns" re-fits. Columns can be resized by dragging.
- Long cell text is shown as a tooltip.
- Zoom: Ctrl+wheel, Ctrl+= / Ctrl+-, Ctrl+0 reset (remembered).
- Theme: View > Theme > System / Light / Dark (remembered). System follows Windows light/dark live. Accent color is green.
- Dates show as `YYYY-MM-DD` (plus time when not midnight), times as `HH:MM[:SS]`, floats with up to 10 significant digits.

### Sort and filter
- Click any column header to open the dropdown: Sort A to Z, Sort Z to A, Clear filter, a value search box, and a checklist of the column's distinct values with "(Select All)" and "(Blanks)".
- The value list only contains values from rows that pass the other columns' filters (like Excel). Over 20,000 distinct values: first 20,000 listed, with a note to use search.
- With the search box in the dropdown used, OK keeps only the checked values that match the search.
- Filtered columns show a bold header with a small down-triangle.
- Sorting is stable, so sorting by column B then column A gives A-then-B order. Order: numbers, dates/times, text (case-insensitive), TRUE/FALSE; blank cells always at the bottom in both directions. Sort indicator shown on the header.
- "Original Order" (Ctrl+Shift+R) undoes sorting.
- Global search box in the toolbar (Ctrl+F): shows rows where any cell contains the text (case-insensitive), 250ms debounce. Combines with column filters.
- "Clear Filters" (Ctrl+Shift+L) removes all column filters and the search on the current sheet.
- Right-click a cell: Copy, Filter by This Value, Sort Column Ascending/Descending, Clear Filters, Original Order.

### Selection and copy
- Select cells like Excel (click, drag, shift, ctrl). Ctrl+C copies as tab-separated text (pastes into Excel as cells).
- Status bar right side shows Count (filled cells), Sum and Average (numeric cells) of the selection, like Excel. Skipped above 500,000 cells (shows only the cell count).
- Status bar left side: file name, rows shown of total, column count, header row, "filtered".

### Export and print
- Export CSV (Ctrl+E): visible rows of the current sheet in current sort order, header row included when a header is used. UTF-8 with BOM so Excel reads accents. Numbers are written with full precision (whole numbers without `.0`).
- Export PDF (Ctrl+Shift+E): visible rows, landscape, title "file - sheet", header row on every page with shaded background, striped rows, grid lines, "Page X of Y" footer. Wide tables continue on extra pages (all rows for the first columns, then the next columns). Long text is cut with "...".
- Print (Ctrl+P): print preview dialog with the same layout; choose any printer.
- Default export name: "file - sheet.csv/pdf" in the last export folder.

---

## Tech spec

- Python 3.10, venv in `.venv`. GUI: PySide6-Essentials (Qt 6, Fusion style). Reader: python-calamine (Rust, reads all Excel formats and ods). Packaging: PyInstaller one-file windowed exe.
- No home server deployment, no Docker.

### Layout
```
main.py                   entry point, app setup, opens argv[1]
pexcel/__init__.py        __version__
pexcel/workbookLoader.py  file reading -> WorkbookData / SheetData (no Qt); value formatting, sortKey, columnLetter
pexcel/sheetModel.py      SheetModel (QAbstractTableModel, owns row order + sorting), SheetFilterProxy (filters + search)
pexcel/filterPopup.py     header dropdown (sort buttons, value checklist)
pexcel/exporters.py       TableSnapshot, exportCsv, paintTable (QPainter pagination for PDF and printing)
pexcel/mainWindow.py      MainWindow: menus, toolbar, sheet tabs, status bar, loading thread, recent files, drag/drop
pexcel/theme.py           light/dark palettes + stylesheet; writes checkbox PNGs to %TEMP%\pexcel
pexcel/appIcon.py         icon drawn in code (window icon + .ico source)
tools/makeIcon.py         writes assets/pexcel.ico
tools/makeSamples.py      writes samples/sample.xlsx (People, Report with title row, Big 100k rows, Empty, hidden Secret) and samples/sample.csv
build.ps1                 builds dist\Pexcel.exe
```

### Design notes
- `SheetData` stores raw values (`rows`) and precomputed display strings (`displayRows`), built on the loader thread. Search text per row (`searchRows`) is built lazily on first search.
- Sorting is done in `SheetModel.sortByColumn` with Python `list.sort` on a `rowOrder` index list (fast, stable), not in the proxy's `lessThan`. The proxy's `sort()` forwards to the model.
- Filters compare display strings, so what you see is what you filter.
- Calamine is called with `skip_empty_area=False` so row/column positions match Excel.
- Settings (QSettings "Pexcel/Pexcel", Windows registry): theme, fontSize, useHeaderRow, recentFiles, lastFolder, lastExportFolder, windowGeometry.
- Performance on the 100k-row sample: load ~1s, sort ~0.25s, search ~0.5s.

### Dev commands
```
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe tools\makeSamples.py
.\.venv\Scripts\python.exe main.py samples\sample.xlsx
.\build.ps1        -> dist\Pexcel.exe (~35 MB)
```
- Code style: camelCase names, explicit simple code, no emojis in output.
- Install only `PySide6-Essentials`, not the full `PySide6` meta package (keeps the exe small; WebEngine etc. not needed).

### Public repo
- Published as a public repo. `README.md` is the user-facing pitch ("You don't need Excel to view Excel", sarcastic/fun tone), with screenshots in `docs/` (`screenshot-light.png`, `screenshot-dark.png`, `filter-popup.png`, `icon.png`).
- `.gitignore` excludes `samples/` and all spreadsheet/csv/pdf files so real personal data never gets committed. Demo data comes from `tools/makeSamples.py`. `assets/pexcel.ico` is generated by `build.ps1`.
- Repo: https://github.com/geekbeard/Pexcel (public, MIT license, branch `main`).
- The built `dist/Pexcel.exe` is committed on purpose (`.gitignore` uses `dist/*` + `!dist/Pexcel.exe`); the rest of `dist/` stays ignored.
- Release flow: bump `__version__` in `pexcel/__init__.py`, run `.\build.ps1`, commit the new exe, then `gh release create vX.Y.Z dist/Pexcel.exe`. README links to releases/latest.
- v1.0.0 released 2026-10-13.

### Known limits / ideas
- No cell formatting, merged spans, formulas display, images or charts.
- Rows above a chosen header row are hidden.
- Possible next: file association installer, freeze panes, column hide, per-cell number formats.
