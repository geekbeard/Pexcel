"""Reads spreadsheet files into plain Python data (no Qt dependency)."""

import csv
import datetime
import os

from python_calamine import CalamineWorkbook, SheetVisibleEnum

EXCEL_EXTENSIONS = [
    ".xlsx", ".xlsm", ".xltx", ".xltm", ".xlsb",
    ".xls", ".xlt", ".xla", ".xlam", ".ods",
]
TEXT_EXTENSIONS = [".csv", ".tsv", ".txt"]
SUPPORTED_EXTENSIONS = EXCEL_EXTENSIONS + TEXT_EXTENSIONS


class SheetData:
    def __init__(self, name, rows, isHidden=False, loadError=None):
        self.name = name
        self.isHidden = isHidden
        self.loadError = loadError
        self.columnCount = 0
        for row in rows:
            if len(row) > self.columnCount:
                self.columnCount = len(row)
        # Make every row the same width so the table is rectangular.
        for row in rows:
            while len(row) < self.columnCount:
                row.append("")
        self.rows = rows
        self.displayRows = [[formatValue(value) for value in row] for row in rows]
        self.searchRows = None

    def getSearchRows(self):
        """Lower-cased joined row text, built on first search."""
        if self.searchRows is None:
            self.searchRows = ["\x1f".join(row).lower() for row in self.displayRows]
        return self.searchRows

    def guessHeaderRow(self):
        """Pick the first row that looks like column titles.

        Title rows like "Quarterly report" above a table fill only one cell, so we take the
        first row (within the top 20) that is at least half as full as the fullest row there.
        """
        filledCounts = []
        for row in self.displayRows[:20]:
            filledCount = 0
            for text in row:
                if text != "":
                    filledCount += 1
            filledCounts.append(filledCount)
        if not filledCounts or max(filledCounts) == 0:
            return None
        threshold = max(1, max(filledCounts) / 2)
        for rowIndex, filledCount in enumerate(filledCounts):
            if filledCount >= threshold:
                return rowIndex
        return None


class WorkbookData:
    def __init__(self, path, sheets):
        self.path = path
        self.fileName = os.path.basename(path)
        self.sheets = sheets


def isSupportedFile(path):
    extension = os.path.splitext(path)[1].lower()
    return extension in SUPPORTED_EXTENSIONS


def loadWorkbook(path):
    extension = os.path.splitext(path)[1].lower()
    if extension in TEXT_EXTENSIONS:
        return loadTextFile(path, extension)
    return loadExcelFile(path)


def loadExcelFile(path):
    workbook = CalamineWorkbook.from_path(path)
    hiddenNames = set()
    try:
        for metadata in workbook.sheets_metadata:
            if metadata.visible != SheetVisibleEnum.Visible:
                hiddenNames.add(metadata.name)
    except Exception:
        hiddenNames = set()

    sheets = []
    for name in workbook.sheet_names:
        isHidden = name in hiddenNames
        try:
            sheet = workbook.get_sheet_by_name(name)
            rows = sheet.to_python(skip_empty_area=False)
            sheets.append(SheetData(name, [list(row) for row in rows], isHidden))
        except Exception as error:
            # Chart sheets and other non-grid sheets cannot be read as cells.
            sheets.append(SheetData(name, [], isHidden, loadError=str(error)))
    workbook.close()
    return WorkbookData(path, sheets)


def loadTextFile(path, extension):
    text = readTextWithFallback(path)
    if extension == ".tsv":
        delimiter = "\t"
    else:
        delimiter = detectDelimiter(text[:65536])

    # Semicolon files usually come from European Excel, where the decimal mark is a comma.
    usesDecimalComma = delimiter == ";"
    rows = []
    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    for row in reader:
        rows.append([convertTextValue(cell, usesDecimalComma) for cell in row])

    sheetName = os.path.splitext(os.path.basename(path))[0]
    return WorkbookData(path, [SheetData(sheetName, rows)])


def readTextWithFallback(path):
    with open(path, "rb") as file:
        rawBytes = file.read()
    for encoding in ["utf-8-sig", "utf-16", "cp1252"]:
        try:
            text = rawBytes.decode(encoding)
            if encoding == "utf-16" and not rawBytes.startswith((b"\xff\xfe", b"\xfe\xff")):
                continue
            return text
        except UnicodeDecodeError:
            continue
    return rawBytes.decode("latin-1")


def detectDelimiter(sample):
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def convertTextValue(cell, usesDecimalComma=False):
    """CSV cells come in as text; turn plain numbers into numbers so they sort correctly."""
    stripped = cell.strip()
    if usesDecimalComma and "," in stripped and "." not in stripped:
        stripped = stripped.replace(",", ".")
    if stripped == "":
        return ""
    # Keep values like "007" or "+31..." as text, the way they were written.
    if len(stripped) > 1 and stripped[0] == "0" and stripped[1].isdigit():
        return cell
    if stripped[0] == "+":
        return cell
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        number = float(stripped)
        if number != number or number in (float("inf"), float("-inf")):
            return cell
        return number
    except ValueError:
        return cell


def isEmptyValue(value):
    return value is None or value == ""


def isNumberValue(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def formatValue(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 1e15:
            return str(int(value))
        return "{:.10g}".format(value)
    if isinstance(value, datetime.datetime):
        if value.hour == 0 and value.minute == 0 and value.second == 0 and value.microsecond == 0:
            return value.strftime("%Y-%m-%d")
        if value.second == 0:
            return value.strftime("%Y-%m-%d %H:%M")
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, datetime.date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, datetime.time):
        if value.second == 0:
            return value.strftime("%H:%M")
        return value.strftime("%H:%M:%S")
    if isinstance(value, datetime.timedelta):
        totalSeconds = int(value.total_seconds())
        hours = totalSeconds // 3600
        minutes = (totalSeconds % 3600) // 60
        seconds = totalSeconds % 60
        return "{}:{:02d}:{:02d}".format(hours, minutes, seconds)
    return str(value)


def sortKey(value):
    """Excel-like ordering: numbers, then dates/times, then text, then TRUE/FALSE."""
    if isinstance(value, bool):
        return (3, 1.0 if value else 0.0, "")
    if isNumberValue(value):
        return (0, float(value), "")
    if isinstance(value, datetime.datetime):
        return (1, value.timestamp() if value.tzinfo else (value - datetime.datetime(1900, 1, 1)).total_seconds(), "")
    if isinstance(value, datetime.date):
        return (1, (datetime.datetime(value.year, value.month, value.day) - datetime.datetime(1900, 1, 1)).total_seconds(), "")
    if isinstance(value, datetime.time):
        return (1, value.hour * 3600 + value.minute * 60 + value.second, "")
    if isinstance(value, datetime.timedelta):
        return (1, value.total_seconds(), "")
    return (2, 0.0, str(value).casefold())


def columnLetter(columnIndex):
    letters = ""
    number = columnIndex + 1
    while number > 0:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters
