@echo off
cd /d "%~dp0"

rem No argument: launch without a console. Pass "debug" to keep the console,
rem which is the only way to see the print() output (BLE log, diagnostics).
if /i "%~1"=="debug" (
    if exist .venv\Scripts\python.exe (
        .venv\Scripts\python.exe app.py
    ) else (
        python app.py
    )
    goto :eof
)

if exist .venv\Scripts\pythonw.exe (
    start "" .venv\Scripts\pythonw.exe app.pyw
) else (
    start "" pythonw app.pyw
)
