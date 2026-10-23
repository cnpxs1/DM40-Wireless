"""Load / save settings.json."""

import json
import math
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from core.config import SETTINGS_PATH
from core.i18n import system_language
from core.parsing import apply_model
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
    "range_auto_return": True,
    "mode_auto_return": False,
    "language": system_language(),
    "gui_font_ui": "Arial",
    "gui_font_data": "Arial",
}


# Never raise on a hand-edited file: the packaged build has no console.
MIN_WINDOW_SCALE = 0.5

# Type-only repairs; MAC, model pair and bools have their own checks below.
_TEXT_KEYS = ("language", "gui_font_ui", "gui_font_data")
_BOOL_KEYS = (
    "show_graph", "debug_click_hotspots", "debug_display_layout",
    "mini_app", "always_on_top", "raw_console",
    "range_auto_return", "mode_auto_return",
)

# Added after the first release: an older file without them is still complete.
OPTIONAL_KEYS = frozenset({"range_auto_return", "mode_auto_return"})

# Six hex pairs; dashes are accepted because the file is hand-edited.
_MAC_PATTERN = re.compile(r"^[0-9A-F]{2}([:-][0-9A-F]{2}){5}$", re.IGNORECASE)

ISSUE_FILE = "file"
ISSUE_MISSING = "missing"
ISSUE_INVALID = "invalid"
ISSUE_LEGACY_MOVED = "legacy_moved"
ISSUE_LEGACY_DROPPED = "legacy_dropped"
ISSUE_UNKNOWN_LANGUAGE = "unknown_language"


@dataclass(frozen=True)
class SettingsIssue:
    """One settings.json problem; ``value`` was rejected in favour of ``default``."""

    kind: str
    key: str = ""
    value: Any = None
    default: Any = None
    error: str = ""


def _note(issues: list[SettingsIssue] | None, kind: str, **fields: Any) -> None:
    """Append an issue when the caller asked for a report."""
    if issues is not None:
        issues.append(SettingsIssue(kind, **fields))


def as_text(value: Any) -> str:
    """``value`` stripped when it is a string, else ``""``."""
    return value.strip() if isinstance(value, str) else ""


def setting_bool(settings: dict, key: str, default: bool) -> bool:
    """``settings[key]`` only when it is a real bool; hand-edited text keeps ``default``."""
    value = settings.get(key)
    return value if isinstance(value, bool) else default


def resolve_window_scale(value: Any) -> float:
    """Window scale to use - always finite and large enough to be clickable.

    Not only a type check: json.loads accepts NaN/Infinity, and 0 or a negative
    scales the window away without raising until the geometry call.
    """
    try:
        scale = float(value)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(scale) or scale < MIN_WINDOW_SCALE:
        return 1.0
    return scale


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


def _same(left: Any, right: Any) -> bool:
    """Type-sensitive equality - True must not pass for 1, nor 1 for 1.0."""
    return type(left) is type(right) and left == right


def sanitize_settings(
    settings: dict,
    issues: list[SettingsIssue] | None = None,
) -> None:
    """Replace unusable values in memory; reported issues are left to the caller."""
    original = dict(settings)

    for key in _TEXT_KEYS:
        if key not in settings:
            continue
        value = original[key]
        replacement = as_text(value) or DEFAULTS[key]
        settings[key] = replacement
        if not isinstance(value, str) or not value.strip():
            _note(issues, ISSUE_INVALID, key=key, value=value, default=replacement)

    if "target_mac" in settings:
        value = original["target_mac"]
        mac = as_text(value)
        # Blank is a valid "no saved device" state; only a malformed address is bad.
        replacement = mac if is_valid_mac(mac) else ""
        settings["target_mac"] = replacement
        if not (isinstance(value, str) and value.strip() == replacement):
            _note(issues, ISSUE_INVALID, key="target_mac", value=value, default=replacement)

    if "model_name" in settings:
        value = original["model_name"]
        text = as_text(value)
        model = resolve_model_name(value)
        # Blank is a valid "not saved yet" state; wrong type or unknown name is not.
        settings["model_name"] = model
        if not isinstance(value, str) or (text and not model):
            _note(issues, ISSUE_INVALID, key="model_name", value=value, default=model)
        # The model decides the counts, so the pair is repaired together.
        derived = model_device_counts(model)
        settings["device_counts"] = derived
        # 0 is the "not set" default, so a key missing from the file is not an error.
        if ("device_counts" in settings
                and not _same(original["device_counts"], DEFAULTS["device_counts"])
                and not _same(original["device_counts"], derived)):
            _note(issues, ISSUE_INVALID, key="device_counts",
                  value=original["device_counts"], default=derived)
    elif "device_counts" in settings:
        value = original["device_counts"]
        if isinstance(value, int) and not isinstance(value, bool):
            settings["device_counts"] = value
        else:
            settings["device_counts"] = DEFAULTS["device_counts"]
            _note(issues, ISSUE_INVALID, key="device_counts",
                  value=value, default=DEFAULTS["device_counts"])

    if "window_scale" in settings:
        value = original["window_scale"]
        numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        replacement = resolve_window_scale(value) if numeric else 1.0
        settings["window_scale"] = replacement
        if not numeric or not math.isfinite(value) or value < MIN_WINDOW_SCALE:
            _note(issues, ISSUE_INVALID, key="window_scale", value=value, default=replacement)

    for key in _BOOL_KEYS:
        if key not in settings:
            continue
        value = original[key]
        if isinstance(value, bool):
            settings[key] = value
        else:
            settings[key] = DEFAULTS[key]
            _note(issues, ISSUE_INVALID, key=key, value=value, default=DEFAULTS[key])


def apply_saved_model(settings: dict) -> None:
    """Loads the saved multimeter model (RANGE counts) before connecting."""
    name = as_text(settings.get("model_name"))
    try:
        counts = int(settings.get("device_counts", 0))
    except (TypeError, ValueError, OverflowError):
        counts = 0
    if name and counts > 0:
        apply_model(name, counts)


def persist_device(
    settings: dict,
    *,
    mac: str,
    model_name: str,
    device_counts: int,
    save: bool = True,
) -> bool:
    """Update MAC and model in memory; with ``save=False`` nothing is written."""
    changed = False
    mac = mac.strip()
    if mac and settings.get("target_mac") != mac:
        settings["target_mac"] = mac
        changed = True
    if model_name and settings.get("model_name") != model_name:
        settings["model_name"] = model_name
        settings["device_counts"] = device_counts
        changed = True
    if changed and save:
        save_settings(settings)
    return changed


def load_settings(issues: list[SettingsIssue] | None = None) -> dict:
    """Merged settings; only a missing file is created, problems go to ``issues``."""
    try:
        raw = SETTINGS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        fresh = deepcopy(DEFAULTS)
        if not save_settings(fresh):
            _note(issues, ISSUE_FILE, error="could not create the file")
        return fresh
    except (OSError, ValueError) as exc:
        _note(issues, ISSUE_FILE, error=str(exc))
        return deepcopy(DEFAULTS)

    try:
        data = json.loads(raw)
    except (ValueError, RecursionError):
        # ValueError also covers JSONDecodeError, the int-digit limit and deep nesting.
        _note(issues, ISSUE_FILE, error="invalid JSON")
        return deepcopy(DEFAULTS)

    if not isinstance(data, dict):
        _note(issues, ISSUE_FILE, error="top level is not a JSON object")
        return deepcopy(DEFAULTS)

    # The old single font key moves to the ui slot; both old keys are dropped.
    if "gui_font" in data:
        if not as_text(data.get("gui_font_ui")):
            data["gui_font_ui"] = as_text(data["gui_font"]) or DEFAULTS["gui_font_ui"]
            _note(issues, ISSUE_LEGACY_MOVED, key="gui_font", value="gui_font_ui")
        else:
            _note(issues, ISSUE_LEGACY_DROPPED, key="gui_font")
        del data["gui_font"]
    if "gui_font_nonlatin" in data:
        del data["gui_font_nonlatin"]
        _note(issues, ISSUE_LEGACY_DROPPED, key="gui_font_nonlatin")

    merged = deepcopy(DEFAULTS)
    merged.update(data)
    for key in DEFAULTS:
        if key not in data and key not in OPTIONAL_KEYS:
            _note(issues, ISSUE_MISSING, key=key, default=DEFAULTS[key])
    return merged


def save_settings(settings: dict) -> bool:
    """Atomic write; non-ASCII stays readable for hand-editing."""
    tmp = SETTINGS_PATH.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        tmp.replace(SETTINGS_PATH)
        return True
    except (OSError, ValueError, TypeError, RecursionError):
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False
