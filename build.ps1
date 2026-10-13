# Builds dist\Pexcel.exe (single file). Run from the project folder: .\build.ps1
$ErrorActionPreference = "Stop"
$python = ".\.venv\Scripts\python.exe"

& $python tools\makeIcon.py
& $python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name Pexcel `
    --icon assets\pexcel.ico `
    --exclude-module tkinter `
    --exclude-module unittest `
    --exclude-module pydoc `
    --exclude-module openpyxl `
    --exclude-module PySide6.QtNetwork `
    --exclude-module PySide6.QtQml `
    --exclude-module PySide6.QtQuick `
    --exclude-module PySide6.QtOpenGL `
    main.py

Write-Host "Built dist\Pexcel.exe"
