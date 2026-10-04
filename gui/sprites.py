"""PNG sprite loading and mapping."""

from __future__ import annotations

import math
from pathlib import Path
import tkinter as tk

from core.config import IMAGES_DIR
from gui.theme import RGB_COLORS

MODE_BTN_DIR = IMAGES_DIR / "MODE_buttons"
RANGE_MENU_DIR = IMAGES_DIR / "range_menu_screen"
SETTINGS_DIR = IMAGES_DIR / "settings"
DISPLAY_UNIT_DIR = IMAGES_DIR / "aux_unit"
MAIN_UNIT_DIR = IMAGES_DIR / "main_unit"
from core.save_units import SAVE_AREA_DIR

TOP_BAR_DIR = IMAGES_DIR / "top_bar"

MAIN_UNIT_NATURAL_W = 133
MAIN_UNIT_NATURAL_H = 68

CMD_KEY_TO_MODE_IMAGE: dict[str, str] = {
    "VDC": "VDC.png",
    "VAC": "VAC.png",
    "VDC+VAC": "VDC+VAC.png",
    "ADC": "ADC.png",
    "AAC": "AAC.png",
    "ADC+AAC": "ADC+AAC.png",
    "OHM": "OHM.png",
    "OHM_ONLINE": "OHM_ONLINE.png",
    "CAP": "CAP.png",
    "DIODE": "DIODE_and_CONT.png",
    "CONT": "DIODE_and_CONT.png",
    "HZ": "HZ.png",
    "TEMP": "TEMP.png",
}

KIND_CHAR_ICON: dict[str, str] = {
    "VDC": "char_dc.png",
    "VAC": "char_ac.png",
    "VDC+AC": "char_ac+dc.png",
    "ADC": "char_dc.png",
    "AAC": "char_ac.png",
    "ADC+AC": "char_ac+dc.png",
}

KIND_SPECIAL_UNITS: dict[str, tuple[str, str]] = {
    "DIODE": ("diode.png", "V.png"),
    "CONT": ("cont.png", "ohm.png"),
}

RANGE_TOP_IMAGES: dict[str, str] = {
    "AUTO+": "auto+.png",
    "AUTO": "auto.png",
}

UNIT_TO_FILE: dict[str, str] = {
    "V": "V.png",
    "mV": "mV.png",
    "A": "A.png",
    "mA": "mA.png",
    "uA": "uA.png",
    "Ω": "ohm.png",
    "KΩ": "Kohm.png",
    "MΩ": "Mohm.png",
    "%": "percent.png",
    "Hz": "Hz.png",
    "KHz": "KHz.png",
    "MHz": "MHz.png",
    "nF": "nF.png",
    "uF": "uF.png",
    "mF": "mF.png",
    "°C": "degC.png",
    "°F": "degF.png",
}


def unit_icon_filename(unit: str) -> str | None:
    if not unit:
        return None
    if unit in UNIT_TO_FILE:
        return UNIT_TO_FILE[unit]
    for key, fname in UNIT_TO_FILE.items():
        if key.lower() == unit.lower():
            return fname
    return None


def aux_char_filename(name: str) -> str:
    """Top AUX displays – smaller char_*.png variants."""
    if name.endswith("_aux.png"):
        return name
    return name.replace(".png", "_aux.png")


# Main display – one PNG per mode + unit (images/main_unit/)
MAIN_KIND_PREFIX: dict[str, str] = {
    "VDC": "dc",
    "VAC": "ac",
    "VDC+AC": "ac_dc",
    "ADC": "dc",
    "AAC": "ac",
    "ADC+AC": "ac_dc",
}

MAIN_UNIT_SUFFIX: dict[str, str] = {
    "V": "v",
    "mV": "mv",
    "A": "a",
    "mA": "ma",
    "uA": "ua",
    "Ω": "ohm",
    "kΩ": "k_ohm",
    "MΩ": "m_ohm",
    "nF": "n_f",
    "uF": "u_f",
    "mF": "m_f",
    "Hz": "hz",
    "kHz": "khz",
    "MHz": "mhz",
    "°C": "deg_c",
    "°F": "deg_f",
}

MAIN_UNIT_STANDALONE: dict[str, str] = {
    "DIODE": "diode.png",
    "CONT": "cont.png",
}


def _main_unit_suffix(display_unit: str) -> str | None:
    if not display_unit:
        return None
    if display_unit in MAIN_UNIT_SUFFIX:
        return MAIN_UNIT_SUFFIX[display_unit]
    lower = display_unit.lower()
    for key, val in MAIN_UNIT_SUFFIX.items():
        if key.lower() == lower:
            return val
    return None


def main_unit_filename(kind: str, display_unit: str) -> str | None:
    """File in ``images/main_unit/`` for the given mode and measurement unit."""
    if kind in MAIN_UNIT_STANDALONE:
        fname = MAIN_UNIT_STANDALONE[kind]
        return fname if (MAIN_UNIT_DIR / fname).is_file() else None

    suffix = _main_unit_suffix(display_unit)
    if not suffix:
        return None

    candidates: list[str] = []
    if prefix := MAIN_KIND_PREFIX.get(kind):
        candidates.append(f"{prefix}_{suffix}.png")
    candidates.append(f"{suffix}.png")

    for fname in candidates:
        if (MAIN_UNIT_DIR / fname).is_file():
            return fname
    return None


def aux_unit_icon_filename(unit: str) -> str | None:
    """Top AUX displays – smaller unit variants (Hz_aux.png, …)."""
    fname = unit_icon_filename(unit)
    if not fname:
        return None
    if fname.endswith("_aux.png"):
        return fname
    return fname.replace(".png", "_aux.png")


def _rounded_corners(w: int, h: int, r: int, steps: int = 16) -> list[tuple[float, float]]:
    """Corner path for a rounded rectangle - `steps` segments per quarter circle.

    Fed to a canvas polygon rather than ImageDraw.rounded_rectangle: Tk fills a
    polygon by pixel centres, so a path on the exact geometry rasterises to the
    true arc, while Pillow's inscribed corner approximation flattens into a
    straight 45° chamfer at small radii (5 and 6 among them).
    """
    pts: list[tuple[float, float]] = []
    for cx, cy, a0, a1 in ((w - r, r, -90, 0), (w - r, h - r, 0, 90),
                           (r, h - r, 90, 180), (r, r, 180, 270)):
        for i in range(steps + 1):
            a = math.radians(a0 + (a1 - a0) * i / steps)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


_round_cache: dict[tuple, tk.PhotoImage] = {}


def _rasterise(width: int, height: int, r: int, fill: tuple) -> tk.PhotoImage | None:
    """Rasterise the corner path into an image, or None when nothing can.

    aggdraw covers the edge in one pass at the target size. Without it Pillow
    fills the very same path with no anti-aliasing, so the corner keeps its true
    shape and only loses the grey ramp - that is what a machine aggdraw has no
    wheel for gets, in exchange for the fallback staying one call.
    """
    try:
        from PIL import Image, ImageDraw, ImageTk
    except ImportError:
        return None
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    xy = [c for p in _rounded_corners(width, height, r) for c in p]
    try:
        import aggdraw
    except ImportError:
        ImageDraw.Draw(img).polygon(xy, fill=fill)
        return ImageTk.PhotoImage(img)
    draw = aggdraw.Draw(img)
    draw.polygon(xy, None, aggdraw.Brush(fill))
    draw.flush()
    return ImageTk.PhotoImage(img)


def rounded_photo(
    color_name: str, width: int, height: int, radius: int,
) -> tk.PhotoImage | None:
    """Anti-aliased rounded rectangle image, cached per colour and size.

    Tk canvas items carry no alpha, so a grey edge has to be baked into an
    image. The path itself stays exact (_rounded_corners) - that is what keeps
    small radii from flattening into a chamfer the way an inscribed corner
    approximation does.
    """
    if width < 2 or height < 2:
        return None
    r = max(1, min(radius, width // 2, height // 2))
    key = (color_name, width, height, r)
    if key in _round_cache:
        return _round_cache[key]
    rgb = RGB_COLORS.get(color_name, RGB_COLORS["buttons"])
    photo = _rasterise(width, height, r, (*rgb, 255))
    if photo is None:
        return None
    _round_cache[key] = photo
    return photo


def rounded_item(
    canvas: tk.Canvas, x: int, y: int, w: int, h: int,
    radius: int, color_name: str, *, tags: tuple = (),
) -> int | None:
    """Draw a rounded rectangle with its top-left at (x, y).

    Returns the canvas item id, or None when the box is too small to carry a
    corner (callers then draw nothing, same as before).
    """
    photo = rounded_photo(color_name, w, h, radius)
    if photo is None:
        return None
    return canvas.create_image(x, y, anchor="nw", image=photo, tags=tags)


class SpriteCache:
    def __init__(self) -> None:
        self._cache: dict[tuple, tk.PhotoImage] = {}

    def load(
        self,
        path: Path,
        scale: float,
        *,
        max_width: int | None = None,
        max_height: int | None = None,
    ) -> tk.PhotoImage | None:
        if not path.is_file():
            return None
        key = (str(path), scale, max_width, max_height)
        if key in self._cache:
            return self._cache[key]
        try:
            from PIL import Image, ImageTk
        except ImportError:
            return None
        try:
            img = Image.open(path).convert("RGBA")
            w, h = img.size
            if max_width or max_height:
                tw = max_width or w
                th = max_height or h
                ratio = min(tw / w, th / h)
                nw, nh = max(1, int(w * ratio)), max(1, int(h * ratio))
                img = img.resize((nw, nh), Image.Resampling.LANCZOS)
            elif scale != 1.0:
                img = img.resize(
                    (max(1, int(w * scale)), max(1, int(h * scale))),
                    Image.Resampling.LANCZOS,
                )
        except (OSError, ValueError):
            # Corrupt / truncated image – treat as missing so callers can
            # fall back (e.g. text-only mode buttons).
            return None
        photo = ImageTk.PhotoImage(img)
        self._cache[key] = photo
        return photo

    def mode_button(self, cmd_key: str, scale: float, max_w: int, max_h: int) -> tk.PhotoImage | None:
        fname = CMD_KEY_TO_MODE_IMAGE.get(cmd_key)
        if not fname:
            return None
        return self.load(MODE_BTN_DIR / fname, scale, max_width=max_w, max_height=max_h)

    def top_bar(self, name: str, scale: float, max_w: int, max_h: int) -> tk.PhotoImage | None:
        return self.load(TOP_BAR_DIR / name, scale, max_width=max_w, max_height=max_h)

    def display_unit(self, fname: str, scale: float, max_h: int = 32) -> tk.PhotoImage | None:
        return self.load(DISPLAY_UNIT_DIR / fname, scale, max_height=max_h)

    def display_unit_aux(self, fname: str, scale: float, max_h: int = 12) -> tk.PhotoImage | None:
        """AUX sprite – prefers *_aux.png, falls back to main version if missing."""
        path = DISPLAY_UNIT_DIR / fname
        if not path.is_file() and fname.endswith("_aux.png"):
            return self.display_unit(fname.replace("_aux.png", ".png"), scale, max_h=max_h)
        return self.display_unit(fname, scale, max_h=max_h)

    def main_unit_sprite(
        self, fname: str, scale: float, max_w: int, max_h: int,
    ) -> tk.PhotoImage | None:
        return self.load(MAIN_UNIT_DIR / fname, scale, max_width=max_w, max_height=max_h)

    def save_area_sprite(self, fname: str, scale: float, max_h: int = 12) -> tk.PhotoImage | None:
        return self.load(SAVE_AREA_DIR / fname, scale, max_height=max_h)

    def range_menu_sprite(
        self, fname: str, scale: float, *, max_w: int | None = None, max_h: int | None = None,
    ) -> tk.PhotoImage | None:
        return self.load(RANGE_MENU_DIR / fname, scale, max_width=max_w, max_height=max_h)

    def settings_sprite(
        self, fname: str, scale: float, *, max_w: int | None = None, max_h: int | None = None,
    ) -> tk.PhotoImage | None:
        return self.load(SETTINGS_DIR / fname, scale, max_width=max_w, max_height=max_h)

    def range_sprite(self, label: str, scale: float, max_w: int, max_h: int) -> tk.PhotoImage | None:
        fname = RANGE_TOP_IMAGES.get(label.strip())
        if not fname:
            return None
        return self.top_bar(fname, scale, max_w, max_h)

    def battery_sprite(self, bars: int, charging: bool, scale: float, max_w: int, max_h: int) -> tk.PhotoImage | None:
        if charging:
            return self.top_bar("battery_charging.png", scale, max_w, max_h)
        level = max(0, min(5, bars)) * 20
        return self.top_bar(f"battery_{level}perc.png", scale, max_w, max_h)
