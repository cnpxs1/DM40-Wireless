#!/usr/bin/env bash
#
# DM40 Wireless - Linux installer.
#
#   ./install_Linux.sh                    prepare the environment
#   DM40_VENV=/path ./install_Linux.sh    use a specific virtualenv
#
# Checks the Python toolchain, creates the virtualenv and installs the
# requirements. Safe to re-run: every step is skipped when already satisfied.
#
# Virtualenv location: .venv/ by default. This repository is also used on
# Windows, whose .venv/ holds Scripts/ instead of bin/, so that directory is
# left alone and venv/ is used instead - the two platforms never share one.

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "$(readlink -f -- "$0")")" && pwd)"
MIN_PY_MAJOR=3
MIN_PY_MINOR=11          # core/i18n.py uses tomllib, added in 3.11

# --- output ----------------------------------------------------------------

if [ -t 1 ]; then
    RST=$'\033[0m'; BOLD=$'\033[97m'; CYAN=$'\033[96m'; GRAY=$'\033[90m'
    GREEN=$'\033[92m'; RED=$'\033[91m'; ORANGE=$'\033[33m'; YELLOW=$'\033[93m'
else
    RST=; BOLD=; CYAN=; GRAY=; GREEN=; RED=; ORANGE=; YELLOW=
fi

TAG_SUCCESS="${GREEN}[SUCCESS]${RST}"
TAG_ERROR="${RED}[ERROR]${RST}"
TAG_WARNING="${ORANGE}[WARNING]${RST}"
TAG_INFO="${GRAY}[INFO]${RST}"
TAG_SKIP="${GRAY}[SKIP]${RST}"

step()  { printf '\n%s[%s]%s %s%s\n\n' "$CYAN" "$1" "$RST" "$BOLD" "$2$RST"; }
info()  { printf '  %s %s\n' "$TAG_INFO" "$*"; }
skip()  { printf '  %s %s\n' "$TAG_SKIP" "$*"; }
warn()  { printf '  %s %s\n' "$TAG_WARNING" "$*" >&2; }
die()   { printf '\n%s %s\n' "$TAG_ERROR" "$*" >&2; exit 1; }

# A venv built while ensurepip was unavailable leaves bin/python behind but no
# pip, so testing for the interpreter alone would accept a broken environment.
venv_usable() {
    [ -x "$1/bin/python" ] && "$1/bin/python" -c "import pip" >/dev/null 2>&1
}

# --- 1. Python toolchain ---------------------------------------------------

step "1/3" "Checking the Python toolchain"

command -v python3 >/dev/null 2>&1 \
    || die "python3 not found. Install Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ first."

PY_SYS="$(command -v python3)"
if "$PY_SYS" -c "import sys; raise SystemExit(0 if sys.version_info >= (${MIN_PY_MAJOR}, ${MIN_PY_MINOR}) else 1)"; then
    skip "$("$PY_SYS" --version 2>&1) at $PY_SYS"
else
    die "$("$PY_SYS" --version 2>&1) is too old - ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ required (core/i18n.py needs tomllib)."
fi

if "$PY_SYS" -c "import tkinter" >/dev/null 2>&1; then
    skip "tkinter available"
else
    die "tkinter is missing - the GUI cannot start.
      Debian/Ubuntu : sudo apt install python3-tk
      Fedora        : sudo dnf install python3-tkinter
      Arch          : sudo pacman -S tk"
fi

# --- 2. virtualenv ---------------------------------------------------------

step "2/3" "Preparing the virtual environment"

if [ -n "${DM40_VENV:-}" ]; then
    VENV="$DM40_VENV"
elif [ -d "$ROOT/.venv/Scripts" ]; then
    VENV="$ROOT/venv"
    info "$ROOT/.venv is a Windows virtualenv - leaving it alone, using $VENV"
else
    VENV="$ROOT/.venv"
fi

if venv_usable "$VENV"; then
    skip "Reusing $VENV"
elif [ -e "$VENV" ]; then
    die "$VENV exists but has no working pip.
      It is most likely a venv left half-built while ensurepip was missing.
      Remove it and run this script again:

          rm -rf $VENV"
else
    info "Creating $VENV ..."
    if ! "$PY_SYS" -m venv "$VENV"; then
        rm -rf "$VENV"       # drop the half-made venv this run created
        die "Failed to create the virtualenv.
      Debian/Ubuntu needs the venv module: sudo apt install python3-venv"
    fi
    printf '  %s Created\n' "$TAG_SUCCESS"
fi

PY="$VENV/bin/python"
venv_usable "$VENV" || die "$VENV has no working python+pip - remove it and re-run."

# --- 3. dependencies -------------------------------------------------------

step "3/3" "Installing dependencies"

if "$PY" -c "import bleak, PIL" >/dev/null 2>&1; then
    skip "bleak and Pillow are already installed"
else
    info "Installing from requirements.txt ..."
    "$PY" -m pip install --upgrade pip --quiet --disable-pip-version-check \
        || die "Could not upgrade pip inside $VENV."
    "$PY" -m pip install -r "$ROOT/requirements.txt" --disable-pip-version-check \
        || die "Package install failed."
    printf '  %s Dependencies installed\n' "$TAG_SUCCESS"
fi

# Optional extras - the app runs without them, with reduced functionality.
if ! command -v xdg-open >/dev/null 2>&1; then
    warn "xdg-open not found: the 'open i18n folder' button will do nothing."
    warn "Install it with: sudo apt install xdg-utils"
fi

if command -v fc-list >/dev/null 2>&1 && ! fc-list :lang=zh 2>/dev/null | grep -q .; then
    warn "fc-list reports no Chinese-capable font."
    warn "If the interface shows boxes instead of Chinese: sudo apt install fonts-noto-cjk"
fi

printf '\n  %s Environment ready.\n' "$TAG_SUCCESS"
printf '  Start the app with:  ./DM40 Wireless_Linux.sh\n'
