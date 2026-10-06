"""Load / save settings.json."""

import json
import math
import re
from copy import deepcopy
from typing import Any

from core.config import SETTINGS_PATH
from core.parsing import MODEL, apply_model
from core.protocol_constants import MODEL_TABLE

DEFAULTS: dict[str, Any] = {
    "target_mac": "",
    "model_name": "",
    "device_counts": 0,
    "window_scale": 1.0,
    "show_graph": False,
    "debug_click_hotspots": False,
    "debug_display_layout": False,
    "mini_app": False,
    "always_on_top": False,
    "raw_console": False,
    "language": "en-US",
    "gui_font_ui": "Arial",
    "gui_font_data": "Arial",
}


# Hand-edited settings.json can hold the wrong type or an out-of-range number;
# reading one must never raise, or the packaged build (no console) dies silently.
MIN_WINDOW_SCALE = 0.5

# Repaired by type alone; target_mac, model_name and device_counts have their own
# rules below. The bool settings are absent - bool() never fails on any value.
_TEXT_KEYS = ("language", "gui_font_ui", "gui_font_data")

# Six colon-separated hex pairs - Windows and BlueZ report the same form, so one
# pattern covers both. Dashes are accepted for hand-edited files.
_MAC_PATTERN = re.compile(r"^[0-9A-F]{2}([:-][0-9A-F]{2}){5}$", re.IGNORECASE)


def as_text(value: Any, default: str = "") -> str:
    """``value`` stripped when it is a string, else ``default``."""
    return value.strip() if isinstance(value, str) else default


def as_int(value: Any, default: int = 0) -> int:
    """``int(value)`` when that works, else ``default``."""
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def resolve_window_scale(settings: dict) -> float:
    """Window scale to use - always finite and large enough to be clickable.

    Not only a type check: json.loads accepts NaN/Infinity, and 0 or a negative
    scales the window away without raising until the geometry call.
    """
    try:
        value = float(settings.get("window_scale", 1.0))
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(value) or value < MIN_WINDOW_SCALE:
        return 1.0
    return value


def is_valid_mac(value: str) -> bool:
    """True when ``value`` is an address a BLE stack can act on."""
    return bool(_MAC_PATTERN.match(value))


def resolve_model_name(value: Any) -> str:
    """Canonical spelling of a known model, or "" when it names none.

    Case is ignored, so "dm40a" is repaired rather than dropped.
    """
    name = as_text(value).upper()
    for model_name, _counts in MODEL_TABLE:
        if model_name.upper() == name:
            return model_name
    return ""


def model_device_counts(model_name: str) -> int:
    """Full-scale counts of a known model; 0 for an unknown one."""
    for name, counts in MODEL_TABLE:
        if name == model_name:
            return counts
    return 0


def sanitize_settings(settings: dict) -> bool:
    """Replace unusable values with their defaults, in place; True if changed.

    Repairing the file, not just the in-memory copy, leaves the next start clean
    and shows the user which value was rejected.
    """
    fixed: dict[str, Any] = {
        key: as_text(settings[key], DEFAULTS[key]) for key in _TEXT_KEYS if key in settings
    }

    if "target_mac" in settings:
        # A malformed address fails every connect and keeps DM40App from ever
        # showing device setup - dropping it returns the user to the scan screen.
        mac = as_text(settings["target_mac"])
        fixed["target_mac"] = mac if is_valid_mac(mac) else ""

    if "model_name" in settings:
        # The model is what decides the counts, so the pair is repaired together.
        model = resolve_model_name(settings["model_name"])
        fixed["model_name"] = model
        fixed["device_counts"] = model_device_counts(model)
    elif "device_counts" in settings:
        fixed["device_counts"] = as_int(
            settings["device_counts"], DEFAULTS["device_counts"],
        )

    if "window_scale" in settings:
        fixed["window_scale"] = resolve_window_scale(settings)

    changed = any(settings.get(key) != value for key, value in fixed.items())
    settings.update(fixed)

    # The old single font key moves to the ui slot; both old keys are dropped.
    if "gui_font" in settings:
        if not as_text(settings.get("gui_font_ui")):
            settings["gui_font_ui"] = as_text(settings["gui_font"]) or DEFAULTS["gui_font_ui"]
        del settings["gui_font"]
        changed = True
    if "gui_font_nonlatin" in settings:
        del settings["gui_font_nonlatin"]
        changed = True
    return changed


def apply_saved_model(settings: dict) -> None:
    """Loads the saved multimeter model (RANGE counts) before connecting."""
    name = as_text(settings.get("model_name"))
    counts = as_int(settings.get("device_counts"))
    if name and counts > 0:
        apply_model(name, counts)


def persist_device(settings: dict, *, mac: str, model_name: str, device_counts: int) -> bool:
    """Saves MAC and model to settings; returns True on change."""
    changed = False
    mac = mac.strip()
    if mac and settings.get("target_mac") != mac:
        settings["target_mac"] = mac
        changed = True
    if model_name and settings.get("model_name") != model_name:
        settings["model_name"] = model_name
        settings["device_counts"] = device_counts
        changed = True
    if changed:
        save_settings(settings)
    return changed


def load_settings() -> dict:
    """Merged settings; a missing or incomplete file is written back complete."""
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}                     # first run - everything below gets filled in
    except (OSError, json.JSONDecodeError):
        return deepcopy(DEFAULTS)     # a damaged file is left untouched
    if not isinstance(data, dict):
        return deepcopy(DEFAULTS)
    merged = deepcopy(DEFAULTS)
    merged.update(data)
    if any(key not in data for key in DEFAULTS):
        save_settings(merged)         # write back the keys added since
    return merged


def save_settings(settings: dict) -> bool:
    """Atomic write (temp then replace, avoids corruption).

    Non-ASCII stays readable for hand-editing.
    """
    import tempfile
    tmp = SETTINGS_PATH.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        tmp.replace(SETTINGS_PATH)
        return True
    except OSError:
        return False
