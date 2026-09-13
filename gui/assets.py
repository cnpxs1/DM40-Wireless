"""PNG loading and canvas click areas."""

from pathlib import Path
from typing import Callable

import tkinter as tk

from core.config import IMAGES_DIR

CLICK_HOTSPOT_TAG = "click_hotspot"


def load_background_photo(path: Path, scale: float = 1.0):
    if not path.is_file():
        return None
    try:
        from PIL import Image, ImageTk
    except ImportError:
        return None
    img = Image.open(path)
    if scale != 1.0:
        w, h = img.size
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(img)


def bind_clickable(
    canvas: tk.Canvas,
    x: int,
    y: int,
    w: int,
    h: int,
    command,
    *,
    tag: str | None = None,
    group: str | None = None,
    debug: bool = False,
    debug_color: str = "#4080ff",
) -> int:
    """Transparent hit area; must sit above sprites (raise_click_hotspots).

    ``group`` adds one extra tag, so a screen that rebuilds its rows can drop
    every hit area it made with a single ``canvas.delete(group)``. Without it
    the rebuilt rows leave their old rectangles behind.
    """
    hit_tag = tag or f"hit_{x}_{y}"
    tags = (hit_tag, CLICK_HOTSPOT_TAG) if group is None else (hit_tag, CLICK_HOTSPOT_TAG, group)
    rid = canvas.create_rectangle(
        x, y, x + w, y + h,
        fill=debug_color if debug else "",
        outline=debug_color if debug else "",
        width=1 if debug else 0,
        stipple="gray50" if debug else "",
        tags=tags,
    )

    def _on_click(_event) -> None:
        command()

    canvas.tag_bind(hit_tag, "<Button-1>", _on_click)
    return rid


def raise_click_hotspots(canvas: tk.Canvas) -> None:
    """Raise click layer on top – transparent PNG otherwise swallows clicks."""
    canvas.tag_raise(CLICK_HOTSPOT_TAG)


class HoverGroup:
    """Hover state for a screen that rebuilds its rows.

    The screen registers one entry per row - its box plus the hit tag it just
    bound - and supplies ``on_change(previous, current)``, which it uses to
    repaint both keys the way that screen paints. This class owns the
    enter/leave bookkeeping and the post-rebuild restore, which re-checks the
    pointer position: deleting the row under the cursor does not make Tk send
    a <Leave>, so a remembered key alone would leave a stale hover behind.
    """

    def __init__(
        self,
        canvas: tk.Canvas,
        on_change: Callable[[str | None, str | None], None],
    ) -> None:
        self._canvas = canvas
        self._on_change = on_change
        self._boxes: dict[str, tuple[int, int, int, int]] = {}
        self.hovered: str | None = None

    def clear(self) -> None:
        self._boxes.clear()
        self.hovered = None

    def add(self, key: str, box: tuple[int, int, int, int], hit_tag: str) -> None:
        self._boxes[key] = box
        self._canvas.tag_bind(hit_tag, "<Enter>", lambda _e, k=key: self._change(k))
        self._canvas.tag_bind(hit_tag, "<Leave>", lambda _e, k=key: self._leave(k))

    def box(self, key: str) -> tuple[int, int, int, int] | None:
        return self._boxes.get(key)

    def is_hovered(self, key: str) -> bool:
        return self.hovered == key

    def restore(self) -> None:
        """Re-apply hover after a rebuild - the pointer may still be on a row."""
        self.hovered = None
        px = self._canvas.winfo_pointerx() - self._canvas.winfo_rootx()
        py = self._canvas.winfo_pointery() - self._canvas.winfo_rooty()
        for key, (rx, ry, rw, rh) in self._boxes.items():
            if rx <= px < rx + rw and ry <= py < ry + rh:
                self._change(key)
                return

    def _change(self, new: str | None) -> None:
        if self.hovered == new:
            return
        previous = self.hovered
        self.hovered = new
        self._on_change(previous, new)

    def _leave(self, key: str) -> None:
        if self.hovered == key:
            self._change(None)
