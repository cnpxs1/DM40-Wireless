"""Graph with auto-scaling, MAX/REL/MIN – rendered on shared canvas."""

from __future__ import annotations

from collections import deque
from typing import Callable

import tkinter as tk

from core.controller import COMMANDS
from core.graph_format import axis_mul_for_unit, format_graph_scale_label, format_graph_value
from core.i18n import t
from core.parsing import Measurement
from gui import layout as L
from gui.assets import CLICK_HOTSPOT_TAG
from gui.fonts import gui_font_data, gui_font_ui
from gui.sprites import rounded_item
from gui.theme import rgb_hex


class GraphPanel:
    TAG = "graph"

    def __init__(
        self,
        canvas: tk.Canvas,
        scale_fn: Callable[[float], int],
        *,
        on_ble_command: Callable[[list[int]], None],
        root: tk.Misc,
        settings: dict | None = None,
    ) -> None:
        self.canvas = canvas
        self._s = scale_fn
        self._send_ble = on_ble_command
        self._root = root
        self._settings = settings

        self._buf: deque[float] = deque(maxlen=L.GRAPH_SAMPLE_MAX)
        self._pad = 0.0
        self._axis_unit = ""
        self._axis_mul = 1.0
        self._decimals = 3
        self._last_trace_key: int | None = None

        self._relative_active = False
        self._relative_offset = 0.0
        self._session_min: float | None = None
        self._session_max: float | None = None

        self._area_px = (0, 0, 0, 0)
        self._plot_px = (0, 0, 0, 0)
        self._x_step = 1.0
        self._y_lo = 0.0
        self._y_hi = 1.0
        # Two independent reasons to hide the trace: not enough samples to draw a
        # line, and the panel being off-screen (mini mode). Only their
        # combination decides, so neither may be cached into the canvas alone.
        self._plot_visible = False
        self._panel_hidden = False

        # One press state shared by every hotspot: Tk delivers the release to
        # whichever item is under the pointer, so the two cannot be independent.
        self._press_tag: str | None = None
        self._press_after: str | None = None
        self._press_fired = False
        self._redraw_after: str | None = None

        self._bg_id: int | None = None
        self._grid_ids: list[int] = []
        self._trace_id: int | None = None
        self._scale_ids: dict[str, int] = {}
        self._sidebar_ids: dict[str, int] = {}
        self._rel_bg_id: int | None = None
        self._rel_bg_color_name: str | None = None
        self._rel_hover = False

    def _data_font(self) -> tuple[str, int, str]:
        return gui_font_data(self._settings, self._s(L.GRAPH_FONT), "normal")

    def _rel_font(self) -> tuple[str, int, str]:
        return gui_font_ui(self._settings, self._s(L.GRAPH_FONT), "bold")

    def install(self) -> None:
        font = self._data_font()
        layout = L.graph_layout()
        gx, gy, gw, gh = L.GRAPH_AREA
        self._area_px = (self._s(gx), self._s(gy), self._s(gw), self._s(gh))
        px, py, pw, ph = layout["plot"]
        self._plot_px = (self._s(px), self._s(py), self._s(pw), self._s(ph))

        self._place_graph_bg()

        for frac in L.GRAPH_GRID_FRACS:
            self._grid_ids.append(self.canvas.create_line(
                0, 0, 0, 0, fill=rgb_hex("graph_grid"), width=1,
                tags=(self.TAG, "graph_grid"),
            ))

        self._trace_id = self.canvas.create_line(
            0, 0, 0, 0, fill=rgb_hex("orange_main"), width=2,
            state="hidden", tags=(self.TAG, "graph_trace"),
        )

        pad = self._s(L.GRAPH_SCALE_PAD_X)
        _, _, _, ph_s = self._plot_px
        self._scale_ids["top"] = self.canvas.create_text(
            pad, pad, text="", anchor="nw", font=font,
            fill=rgb_hex("graph_text"), tags=(self.TAG, "graph_scale"),
        )
        self._scale_ids["mid"] = self.canvas.create_text(
            pad, ph_s // 2, text="", anchor="w", font=font,
            fill=rgb_hex("graph_text"), tags=(self.TAG, "graph_scale"),
        )
        self._scale_ids["bot"] = self.canvas.create_text(
            pad, 0, text="", anchor="sw", font=font,
            fill=rgb_hex("graph_text"), tags=(self.TAG, "graph_scale"),
        )

        sx, sy, sw, sh = layout["sidebar"]
        rx, ry, rw, rh = layout["rel_btn"]
        sx, sy, sw, sh = self._s(sx), self._s(sy), self._s(sw), self._s(sh)
        self._sidebar_ids["max"] = self.canvas.create_text(
            sx + sw // 2, sy + self._s(6), text="",
            anchor="n", font=font, fill=rgb_hex("text_primary"),
            tags=(self.TAG, "graph_max"),
        )
        self._sidebar_ids["min"] = self.canvas.create_text(
            sx + sw // 2, sy + sh - self._s(6), text="",
            anchor="s", font=font, fill=rgb_hex("text_primary"),
            tags=(self.TAG, "graph_min"),
        )

        rel_text = t("graph.rel")
        rel_font = self._rel_font()
        rcx = self._s(rx + rw // 2)
        rcy = self._s(ry + rh // 2)
        self._sidebar_ids["rel"] = self.canvas.create_text(
            rcx, rcy, text=rel_text, anchor="center", font=rel_font,
            fill=rgb_hex("text_primary"), tags=(self.TAG, "graph_rel_text"),
        )
        self._refresh_rel_bg()
        self._bind_interactions(layout)
        self._layout_static()

    def _place_graph_bg(self) -> None:
        ax, ay, aw, ah = self._area_px
        self._bg_id = rounded_item(
            self.canvas, ax, ay, aw, ah, self._s(L.GRAPH_RADIUS), "save_area",
            tags=(self.TAG, "graph_bg"),
        )

    def _rel_bg_color(self) -> str:
        if self._relative_active:
            return "buttons_active"
        if self._rel_hover:
            return "buttons_hover"
        return "buttons"

    def _refresh_rel_bg(self) -> None:
        color = self._rel_bg_color()
        if color == self._rel_bg_color_name:
            return
        self._rel_bg_color_name = color
        layout = L.graph_layout()
        rx, ry, rw, rh = layout["rel_btn"]
        rx, ry, rw, rh = self._s(rx), self._s(ry), self._s(rw), self._s(rh)
        if self._rel_bg_id is not None:
            self.canvas.delete(self._rel_bg_id)
            self._rel_bg_id = None
        bg_id = rounded_item(
            self.canvas, rx, ry, rw, rh, self._s(L.GRAPH_REL_RADIUS), color,
            tags=(self.TAG, "graph_rel_bg"),
        )
        if bg_id is not None:
            self._rel_bg_id = bg_id
            self.canvas.tag_lower(bg_id, self._sidebar_ids["rel"])

    def _layout_static(self) -> None:
        px, py, pw, ph = self._plot_px
        pad = self._s(L.GRAPH_SCALE_PAD_X)
        self.canvas.coords(self._scale_ids["top"], px + pad, py + pad)
        self.canvas.coords(self._scale_ids["mid"], px + pad, py + ph // 2)
        self.canvas.coords(self._scale_ids["bot"], px + pad, py + ph - pad)
        cap = max(16, min(pw, L.GRAPH_SAMPLE_MAX))
        self._buf = deque(self._buf, maxlen=cap)
        self._x_step = (pw - 1) / max(1, cap - 1) if pw > 1 else 1.0
        self._update_grid_lines()

    def _mid_grid_start_x(self) -> int:
        px, _, pw, _ = self._plot_px
        margin = self._s(L.GRAPH_SCALE_LABEL_MARGIN)
        mid_bbox = self.canvas.bbox(self._scale_ids["mid"])
        if mid_bbox:
            return min(mid_bbox[2] + margin, px + pw)
        return px + self._s(L.GRAPH_SCALE_PAD_X) + margin

    def _update_grid_lines(self) -> None:
        px, py, pw, ph = self._plot_px
        h1 = max(1, ph - 1)
        mid_x1 = self._mid_grid_start_x()
        for i, (gid, frac) in enumerate(zip(self._grid_ids, L.GRAPH_GRID_FRACS)):
            y = py + int(h1 * frac)
            x1 = mid_x1 if frac == 0.5 else px
            self.canvas.coords(gid, x1, y, px + pw, y)

    def _bind_interactions(self, layout: dict) -> None:
        ax, ay, aw, ah = self._area_px
        self._bind_press_release(
            ax, ay, aw, ah,
            "graph_hit_reset", None, self._on_graph_long_press,
        )
        rx, ry, rw, rh = layout["rel_btn"]
        self._bind_press_release(
            self._s(rx), self._s(ry), self._s(rw), self._s(rh),
            "graph_hit_rel", self._on_rel_click, self._on_rel_long_press,
        )
        self.canvas.tag_bind("graph_hit_rel", "<Enter>", self._on_rel_enter)
        self.canvas.tag_bind("graph_hit_rel", "<Leave>", self._on_rel_leave)
        self.canvas.tag_raise("graph_hit_rel")

    def _bind_press_release(
        self,
        x: int, y: int, w: int, h: int,
        tag: str,
        on_click: Callable[[], None] | None,
        on_long: Callable[[], None] | None,
    ) -> None:
        self.canvas.create_rectangle(
            x, y, x + w, y + h,
            fill="", outline="", tags=(tag, CLICK_HOTSPOT_TAG, self.TAG),
        )

        def on_press(_event) -> None:
            self.cancel_press()         # a new press owns the interaction
            self._press_tag = tag
            self._press_after = self._root.after(L.GRAPH_LONG_PRESS_MS, _fire_long)

        def _fire_long() -> None:
            self._press_after = None
            self._press_fired = True
            if on_long:
                on_long()

        def on_release(_event) -> None:
            # A drag that started on the other hotspot arrives here with
            # _press_tag still naming where it started. Cancel either way;
            # the click only runs when press and release agree.
            pressed = self._press_tag
            fired = self._press_fired
            self.cancel_press()
            if pressed == tag and not fired and on_click:
                on_click()

        self.canvas.tag_bind(tag, "<ButtonPress-1>", on_press)
        self.canvas.tag_bind(tag, "<ButtonRelease-1>", on_release)

    def cancel_press(self) -> None:
        """Drop the pending long press, whoever notices the interaction ended."""
        if self._press_after is not None:
            self._root.after_cancel(self._press_after)
        self._press_after = None
        self._press_fired = False
        self._press_tag = None

    def refresh_rel_text(self) -> None:
        """Refresh REL button text (called on language change)."""
        rid = self._sidebar_ids.get("rel")
        if rid:
            text = t("graph.rel")
            self.canvas.itemconfig(rid, text=text, font=self._rel_font())

    def clear(self) -> None:
        """Drop the session trace: samples, MIN/MAX and all they drew.

        The line's coordinates go too, and redraw() clears the scale labels -
        hiding the line alone leaves the old shape one stray state change away.
        """
        self._buf.clear()
        self._reset_min_max()
        if self._trace_id is not None:
            self.canvas.coords(self._trace_id, 0, 0, 0, 0)
        self.redraw()

    def _reset_min_max(self) -> None:
        self._session_min = None
        self._session_max = None
        self._update_sidebar_texts()

    def _on_graph_long_press(self) -> None:
        self.clear()

    def _on_rel_enter(self, _event=None) -> None:
        self._rel_hover = True
        self._refresh_rel_bg()

    def _on_rel_leave(self, _event=None) -> None:
        self._rel_hover = False
        self._refresh_rel_bg()

    def _on_rel_click(self) -> None:
        self._relative_active = True
        if self._buf:
            self._relative_offset = self._buf[-1]
        self._send_ble(COMMANDS["RELATIVE"])
        self._refresh_rel_bg()
        self.redraw()

    def _on_rel_long_press(self) -> None:
        self._relative_active = False
        self._relative_offset = 0.0
        self._send_ble(COMMANDS["RELATIVE_OFF"])
        self._refresh_rel_bg()
        self.redraw()

    def _plot_value(self, norm_value: float) -> float:
        if self._relative_active:
            return norm_value - self._relative_offset
        return norm_value

    def _track_min_max(self, norm_value: float) -> None:
        if self._session_min is None or norm_value < self._session_min:
            self._session_min = norm_value
        if self._session_max is None or norm_value > self._session_max:
            self._session_max = norm_value

    def push_measurement(self, m: Measurement, trace_key: int) -> None:
        if m.overload or m.norm_value is None:
            return

        if self._last_trace_key is not None and trace_key != self._last_trace_key:
            self.clear()
        self._last_trace_key = trace_key

        self._pad = m.vertical_pad
        self._axis_unit = m.display_unit
        self._axis_mul = axis_mul_for_unit(m.display_unit)
        self._decimals = m.decimals

        plotted = self._plot_value(m.norm_value)
        self._buf.append(plotted)
        self._track_min_max(plotted)
        self._update_sidebar_texts()
        self._schedule_redraw()

    def _schedule_redraw(self) -> None:
        if self._redraw_after is not None:
            return
        self._redraw_after = self._root.after(50, self._run_redraw)

    def _run_redraw(self) -> None:
        self._redraw_after = None
        self.redraw()

    def _update_sidebar_texts(self) -> None:
        unit = self._axis_unit
        dec = self._decimals
        if self._session_max is not None:
            text = format_graph_value(self._session_max, unit, dec)
            self.canvas.itemconfigure(
                self._sidebar_ids["max"], text=text, font=self._data_font(),
            )
        else:
            self.canvas.itemconfigure(self._sidebar_ids["max"], text="")
        if self._session_min is not None:
            text = format_graph_value(self._session_min, unit, dec)
            self.canvas.itemconfigure(
                self._sidebar_ids["min"], text=text, font=self._data_font(),
            )
        else:
            self.canvas.itemconfigure(self._sidebar_ids["min"], text="")

    def _scale_label(self, norm_value: float) -> str:
        return format_graph_scale_label(norm_value, self._axis_unit, self._decimals)

    def _set_plot_visible(self, visible: bool) -> None:
        self._plot_visible = visible
        self._sync_trace_state()

    def _sync_trace_state(self) -> None:
        """Recompute the trace state from both reasons - never cache it alone."""
        if self._trace_id is None:
            return
        shown = self._plot_visible and not self._panel_hidden
        self.canvas.itemconfigure(
            self._trace_id, state="normal" if shown else "hidden",
        )

    def set_view_mode_hidden(self, hidden: bool) -> None:
        """The tag covers the trace too, so its state is re-applied after."""
        self._panel_hidden = hidden
        self.canvas.itemconfigure(self.TAG, state="hidden" if hidden else "normal")
        self._sync_trace_state()

    def redraw(self) -> None:
        px, py, pw, ph = self._plot_px
        h1 = max(1, ph - 1)
        values = list(self._buf)
        if len(values) < 2 or pw < 2:
            self._set_plot_visible(False)
            self.canvas.itemconfigure(self._scale_ids["top"], text="")
            self.canvas.itemconfigure(self._scale_ids["mid"], text="")
            self.canvas.itemconfigure(self._scale_ids["bot"], text="")
            self._update_grid_lines()
            return

        self._set_plot_visible(True)
        lo = min(values) - self._pad
        hi = max(values) + self._pad
        if hi <= lo:
            hi = lo + self._axis_mul
        self._y_lo, self._y_hi = lo, hi

        y_scale = h1 / (hi - lo)
        y0 = hi * y_scale
        pts: list[float] = []
        for i, v in enumerate(values):
            pts.extend((px + i * self._x_step, py + y0 - v * y_scale))
        if self._trace_id is not None:
            self.canvas.coords(self._trace_id, *pts)

        top_text = self._scale_label(hi)
        bot_text = self._scale_label(lo)
        self.canvas.itemconfigure(
            self._scale_ids["top"], text=top_text, font=self._data_font(),
        )
        self.canvas.itemconfigure(
            self._scale_ids["bot"], text=bot_text, font=self._data_font(),
        )
        mid_val = 0.0 if self._relative_active else (hi + lo) / 2
        mid_text = self._scale_label(mid_val)
        self.canvas.itemconfigure(
            self._scale_ids["mid"], text=mid_text, font=self._data_font(),
        )
        self._update_grid_lines()
