"""GUI font families from settings.json.

Two slots: ``gui_font_data`` for readings, graph scales and the range readout,
``gui_font_ui`` for every other text. Both default to Arial.
"""

from gui.settings import as_text

DEFAULT_GUI_FONT = "Arial"


def _family(settings: dict | None, key: str) -> str:
    if settings:
        name = as_text(settings.get(key))
        if name:
            return name
    return DEFAULT_GUI_FONT


def gui_font_ui(settings: dict | None, size: int, weight: str = "normal") -> tuple[str, int, str]:
    """Tk font tuple for UI texts."""
    return _family(settings, "gui_font_ui"), size, weight


def gui_font_data(settings: dict | None, size: int, weight: str = "normal") -> tuple[str, int, str]:
    """Tk font tuple for data texts."""
    return _family(settings, "gui_font_data"), size, weight
