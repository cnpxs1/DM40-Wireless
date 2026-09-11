@echo off
chcp 65001 >nul
setlocal EnableExtensions

REM --- ANSI colors ---
for /F %%a in ('echo prompt $E^| cmd') do set "ESC=%%a"

set "RST=%ESC%[0m"
set "RED=%ESC%[91m"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "ORANGE=%ESC%[33m"
set "BLUE=%ESC%[94m"
set "CYAN=%ESC%[96m"
set "WHITE=%ESC%[97m"
set "GRAY=%ESC%[90m"

REM --- Message tags ---
set "STEP=%CYAN%"
set "SUCCESS=%GREEN%[SUCCESS]%RST%"
set "ERROR=%RED%[ERROR]%RST%"
set "WARNING=%ORANGE%[WARNING]%RST%"
set "NOTE=%YELLOW%[NOTE]%RST%"
set "INFO=%GRAY%[INFO]%RST%"
set "SKIP=%GRAY%[SKIP]%RST%"

cd /d "%~dp0"

echo %CYAN%╔════════════════════════════════════════════════════════════════════════╗%RST%
echo %CYAN%║%RST%               %WHITE%DM40 Wireless - Nuitka + MSVC Onefile Build%RST%              %CYAN%║%RST%
echo %CYAN%║%RST%                   %GRAY%Bluetooth Multimeter Desktop App%RST%                     %CYAN%║%RST%
echo %CYAN%╚════════════════════════════════════════════════════════════════════════╝%RST%
echo.

echo %CYAN%██████╗ ███╗   ███╗██╗  ██╗ ██████╗%RST%
echo %CYAN%██╔══██╗████╗ ████║██║  ██║██╔═████╗%RST%
echo %CYAN%██║  ██║██╔████╔██║███████║██║██╔██║%RST%
echo %CYAN%██║  ██║██║╚██╔╝██║╚════██║████╔╝██║%RST%
echo %CYAN%██████╔╝██║ ╚═╝ ██║     ██║╚██████╔╝%RST%
echo %CYAN%╚═════╝ ╚═╝     ╚═╝     ╚═╝ ╚═════╝ %RST%
echo.
echo %BLUE%██╗    ██╗██╗██████╗ ███████╗██╗     ███████╗███████╗███████╗%RST%
echo %BLUE%██║    ██║██║██╔══██╗██╔════╝██║     ██╔════╝██╔════╝██╔════╝%RST%
echo %BLUE%██║ █╗ ██║██║██████╔╝█████╗  ██║     █████╗  ███████╗███████╗%RST%
echo %BLUE%██║███╗██║██║██╔══██╗██╔══╝  ██║     ██╔══╝  ╚════██║╚════██║%RST%
echo %BLUE%╚███╔███╔╝██║██║  ██║███████╗███████╗███████╗███████║███████║%RST%
echo %BLUE% ╚══╝╚══╝ ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚══════╝╚══════╝%RST%
echo.

REM --- Validate virtual environment ---
if not exist .venv\Scripts\python.exe (
    echo %ERROR% Virtual environment not found. Run install.bat first.
    pause
    exit /b 1
)

set "PY=.venv\Scripts\python.exe"

REM --- Kill running instance (avoids file-lock errors) ---
taskkill /IM "DM40 Wireless.exe" /F >nul 2>&1
timeout /t 1 /nobreak >nul

REM --- Ensure Nuitka is installed ---
echo %STEP%[1/4]%RST% %WHITE%Checking Nuitka installation...%RST%
REM Run pip in a fresh console: it only draws its progress bar on a real terminal.
REM Keep that console open on failure so the error stays readable (RC preserves the exit code).
start "Nuitka install" /wait cmd /v:on /c ""%PY%" -m pip install --upgrade nuitka & set "RC=!errorlevel!" & if !RC! neq 0 pause & exit /b !RC!"
if errorlevel 1 (
    echo %ERROR% Failed to install Nuitka.
    pause
    exit /b 1
)
echo %SUCCESS% Nuitka is installed and up to date.

REM --- Auto-detect and activate MSVC compiler toolchain ---
echo.
echo %STEP%[2/4]%RST% %WHITE%Activating MSVC compiler...%RST%
echo.
set "MSVC_VARS="

REM Priority 1: vswhere.exe (VS installer tool). It reads the VS registry, so
REM it finds VS wherever it is installed and always reports the newest one.
set "VSWHERE="
if defined ProgramFiles(x86) set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not defined MSVC_VARS if exist "%VSWHERE%" (
    for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -property installationPath 2^>nul`) do (
        if not defined MSVC_VARS if exist "%%i\VC\Auxiliary\Build\vcvars64.bat" (
            set "MSVC_VARS=%%i\VC\Auxiliary\Build\vcvars64.bat"
        )
    )
)

REM Priority 2: scan a custom install root. Set VS_ROOT to your Visual Studio
REM root folder (the one holding the version folders, e.g. 2026\ or 2022\) if VS
REM lives outside Program Files. Versions are discovered, newest scanned first.
if not defined MSVC_VARS if defined VS_ROOT (
    for /f "delims=" %%y in ('dir /b /ad /o-n "%VS_ROOT%" 2^>nul') do (
        for %%e in (Professional Community Enterprise BuildTools) do (
            if not defined MSVC_VARS if exist "%VS_ROOT%\%%y\%%e\VC\Auxiliary\Build\vcvars64.bat" (
                set "MSVC_VARS=%VS_ROOT%\%%y\%%e\VC\Auxiliary\Build\vcvars64.bat"
            )
        )
    )
)

REM Priority 3: default Program Files installs, newest version first
if not defined MSVC_VARS (
    for /f "delims=" %%y in ('dir /b /ad /o-n "%ProgramFiles%\Microsoft Visual Studio" 2^>nul') do (
        for %%e in (Professional Community Enterprise BuildTools) do (
            if not defined MSVC_VARS if exist "%ProgramFiles%\Microsoft Visual Studio\%%y\%%e\VC\Auxiliary\Build\vcvars64.bat" (
                set "MSVC_VARS=%ProgramFiles%\Microsoft Visual Studio\%%y\%%e\VC\Auxiliary\Build\vcvars64.bat"
            )
        )
    )
)

if not defined MSVC_VARS (
    echo %ERROR% MSVC vcvars64.bat not found.
    echo Install Visual Studio 2022+ with "Desktop development with C++" workload.
    echo If VS is installed outside Program Files, set VS_ROOT to its root folder and retry.
    pause
    exit /b 1
)

echo Found: %MSVC_VARS%
call "%MSVC_VARS%"
if errorlevel 1 (
    echo %ERROR% MSVC environment setup failed.
    pause
    exit /b 1
)

REM --- Nuitka build (onefile: single exe; slower cold start, AV may flag it) ---
echo.
echo %STEP%[3/4]%RST% %WHITE%Building with Nuitka --onefile...%RST%
echo.
if exist "dist\DM40 Wireless.exe" del /F /Q "dist\DM40 Wireless.exe"

"%PY%" -m nuitka ^
  --onefile ^
  --windows-console-mode=disable ^
  --windows-icon-from-ico=images/app.ico ^
  --company-name="Urobotos" ^
  --product-name="DM40 Wireless" ^
  --file-description="DM40 Wireless - Bluetooth multimeter desktop app" ^
  --file-version=1.2.0 ^
  --product-version=1.2.0 ^
  --copyright="Copyright (C) 2026 Urobotos" ^
  --enable-plugin=tk-inter ^
  --include-data-dir=images=images ^
  --include-data-files=i18n/en-US.toml=i18n/en-US.toml ^
  --include-package=bleak ^
  --include-package=winrt ^
  --output-dir=dist ^
  --output-filename="DM40 Wireless.exe" ^
  --assume-yes-for-downloads ^
  --remove-output ^
  --msvc=latest ^
  app.pyw

if errorlevel 1 (
    echo.
    echo %ERROR% Build failed.
    pause
    exit /b 1
)

REM --- Verify output and prepare distribution folder ---
echo.
echo %STEP%[4/4]%RST% %WHITE%Verifying output and copying external assets...%RST%
if not exist "dist\DM40 Wireless.exe" (
    echo %ERROR% Output exe not found in dist\.
    pause
    exit /b 1
)

REM Remove intermediate Nuitka folders left by onefile builds
if exist "dist\DM40 Wireless.build" rmdir /S /Q "dist\DM40 Wireless.build"
if exist "dist\DM40 Wireless.onefile-build" rmdir /S /Q "dist\DM40 Wireless.onefile-build"

REM Move exe into the unified distribution folder (same layout as --standalone)
if exist "dist\DM40 Wireless" rmdir /S /Q "dist\DM40 Wireless"
mkdir "dist\DM40 Wireless"
move /Y "dist\DM40 Wireless.exe" "dist\DM40 Wireless\DM40 Wireless.exe" >nul
if errorlevel 1 (
    echo %ERROR% Failed to move exe into dist\DM40 Wireless\
    pause
    exit /b 1
)

REM Copy i18n language files next to the exe (external, editable;
REM en-US.toml is also embedded inside the exe as a read-only fallback)
if exist "i18n" (
    if not exist "dist\DM40 Wireless\i18n" mkdir "dist\DM40 Wireless\i18n"
    xcopy /Y /E "i18n\*.toml" "dist\DM40 Wireless\i18n\" >nul 2>&1
    echo %INFO% i18n\ copied to: dist\DM40 Wireless\i18n\
)

REM Copy settings template as default config
if not exist "dist\DM40 Wireless\settings.json" (
    copy /Y "settings.example.json" "dist\DM40 Wireless\settings.json" >nul 2>&1
    echo %INFO% settings.example.json copied to: dist\DM40 Wireless\settings.json
)

echo.
echo %CYAN%╔════════════════════════════════════════════════════════════════════════╗%RST%
echo %CYAN%║%RST%                            %GREEN%Build succeeded! %RST%                           %CYAN%║%RST%
echo %CYAN%╟————————————————————————————————————————————————————————————————————————╢%RST%
echo %CYAN%║%RST%  %WHITE%Output folder:%RST% dist\DM40 Wireless\                                    %CYAN%║%RST%
echo %CYAN%║%RST%                                                                        %CYAN%║%RST%
echo %CYAN%║%RST%  %WHITE%Distribution folder contents:%RST%                                         %CYAN%║%RST%
echo %CYAN%║%RST%    DM40 Wireless\                                                      %CYAN%║%RST%
echo %CYAN%║%RST%    ├── DM40 Wireless.exe  (self-contained exe)                         %CYAN%║%RST%
echo %CYAN%║%RST%    ├── i18n\      (language files - editable)                          %CYAN%║%RST%
echo %CYAN%║%RST%    └── settings.json                                                   %CYAN%║%RST%
echo %CYAN%║%RST%                                                                        %CYAN%║%RST%
echo %CYAN%╚════════════════════════════════════════════════════════════════════════╝%RST%
echo.
echo %NOTE% The exe is self-contained, but settings and language files are stored next to it.
echo %NOTE% Keep the whole folder together - do not move the exe alone.
echo.
echo %WARNING% --onefile extracts to a temp folder at startup (slower cold start) and is
echo %WARNING% more likely to trigger antivirus false positives. Prefer build_exe.bat
echo %WARNING% (--standalone) if this becomes an issue.
pause
