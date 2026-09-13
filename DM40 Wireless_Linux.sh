#!/usr/bin/env bash
#
# DM40 Wireless - Linux launcher.
#
#   "./DM40 Wireless_Linux.sh"                    start the app
#   "./DM40 Wireless_Linux.sh" --help             forwarded to app.py
#   DM40_VENV=/path "./DM40 Wireless_Linux.sh"    use a specific virtualenv
#
# Checks that the environment is ready and starts the app - under a second.
# For a first run, or to repair the environment, use ./install_Linux.sh.

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "$(readlink -f -- "$0")")" && pwd)"

# --- output ----------------------------------------------------------------

if [ -t 1 ]; then
    RST=$'\033[0m'; BOLD=$'\033[97m'; GRAY=$'\033[90m'
    GREEN=$'\033[92m'; RED=$'\033[91m'
else
    RST=; BOLD=; GRAY=; GREEN=; RED=
fi

TAG_ERROR="${RED}[ERROR]${RST}"
TAG_SKIP="${GRAY}[SKIP]${RST}"

step() { printf '\n%s%s%s\n\n' "$BOLD" "$1" "$RST"; }
skip() { printf '  %s %s\n' "$TAG_SKIP" "$*"; }
die()  { printf '\n%s %s\n' "$TAG_ERROR" "$*" >&2; exit 1; }

# --- locate the environment ------------------------------------------------

if [ -n "${DM40_VENV:-}" ]; then
    VENV="$DM40_VENV"
elif [ -x "$ROOT/.venv/bin/python" ]; then
    VENV="$ROOT/.venv"
elif [ -x "$ROOT/venv/bin/python" ]; then
    VENV="$ROOT/venv"
else
    die "No virtualenv found.
      Run the installer first:

          ./install_Linux.sh"
fi

PY="$VENV/bin/python"

# --- check it is ready -----------------------------------------------------

step "Checking the environment"

"$PY" -c "import tkinter" >/dev/null 2>&1 \
    || die "tkinter is missing from $VENV.
      Run the installer, it explains which package to add:

          ./install_Linux.sh"

"$PY" -c "import bleak, PIL" >/dev/null 2>&1 \
    || die "bleak and Pillow are missing from $VENV.
      Run the installer:

          ./install_Linux.sh"

skip "Environment ready: $VENV"

# --- launch ----------------------------------------------------------------

step "Starting DM40 Wireless"

cd "$ROOT"
exec "$PY" "$ROOT/app.py" "$@"
