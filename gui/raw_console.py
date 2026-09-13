"""RAW BLE console below the main screen."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui import layout as L
from gui.theme import rgb_hex


class RawConsole(tk.Frame):
    def __init__(self, master, scale: float) -> None:
        super().__init__(master, bg=rgb_hex("background"))
        self.scale = scale
        self._autoscroll = True
        h = int(L.RAW_CONSOLE_H * scale)
        self.configure(height=h)
        self.pack_propagate(False)

        font_size = max(8, int(L.RAW_CONSOLE_FONT * scale))
        border = rgb_hex("top_bar_background")
        self._body = tk.Frame(self, bg=rgb_hex("background"))
        self._body.pack(fill="both", expand=True, padx=int(4 * scale), pady=int(2 * scale))

        self._scrollbar = self._create_scrollbar(self._body)
        self._scrollbar.pack(side="right", fill="y")

        self._text = tk.Text(
            self._body,
            height=1,
            wrap="none",
            state="disabled",
            bg=rgb_hex("background"),
            fg=rgb_hex("text_secondary"),
            insertbackground=rgb_hex("text_secondary"),
            font=("Consolas", font_size),
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=border,
            highlightcolor=border,
            yscrollcommand=self._on_yview,
        )
        self._text.pack(side="left", fill="both", expand=True)
        self._scrollbar.config(command=self._text.yview)

        for widget in (self._text, self._body, self._scrollbar):
            widget.bind("<MouseWheel>", self._on_wheel, add=True)
            widget.bind("<Button-4>", self._on_wheel, add=True)
            widget.bind("<Button-5>", self._on_wheel, add=True)

    def _create_scrollbar(self, master: tk.Misc) -> ttk.Scrollbar:
        """ttk scrollbar coloured through the 'clam' theme.

        The classic tk.Scrollbar cannot be coloured cross-platform: Windows
        draws it with the native theme engine, which discards bg/troughcolor,
        so the same options came out flat on X11 and system-styled on Windows.
        clam is the built-in theme that honours them on both. Width follows
        arrowsize - clam sizes the trough from its arrow elements.
        """
        style = ttk.Style(master)
        style.theme_use("clam")
        trough = rgb_hex("top_bar_background")
        thumb = rgb_hex("buttons")
        hover = rgb_hex("graph_grid")
        style.configure(
            "Vertical.TScrollbar",
            background=thumb,
            troughcolor=trough,
            bordercolor=trough,
            lightcolor=thumb,   # same as the thumb -> flat, no 3D bevel
            darkcolor=thumb,
            arrowcolor=rgb_hex("text_secondary"),
            arrowsize=max(10, int(11 * self.scale)),   # clam sizes the trough from this
        )
        style.map(
            "Vertical.TScrollbar",
            background=[("active", hover)],
            lightcolor=[("active", hover)],
            darkcolor=[("active", hover)],
        )
        return ttk.Scrollbar(master, orient="vertical", style="Vertical.TScrollbar")

    def _on_yview(self, first: str | float, last: str | float) -> None:
        # Tk hands the two fractions over as strings ("0.0", "1.0"); the float
        # in the annotation only satisfies the typeshed stub for yscrollcommand.
        self._scrollbar.set(first, last)
        self._autoscroll = float(last) >= 0.99

    def _on_wheel(self, _event) -> None:
        self.after_idle(self._sync_autoscroll)

    def _sync_autoscroll(self) -> None:
        _, bottom = self._text.yview()
        self._autoscroll = bottom >= 0.99

    def append(self, text: str) -> None:
        follow = self._autoscroll
        self._text.configure(state="normal")
        self._text.insert("end", text)
        self._trim_lines()
        if follow:
            self._text.see("end")
            self._autoscroll = True
        self._text.configure(state="disabled")

    def append_lines(self, lines: list[str]) -> None:
        if not lines:
            return
        self.append("".join(lines))

    def _trim_lines(self) -> None:
        end_line = int(self._text.index("end-1c").split(".")[0])
        excess = end_line - L.RAW_CONSOLE_MAX_LINES
        if excess > 0:
            self._text.delete("1.0", f"{excess + 1}.0")

    def clear(self) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")
        self._autoscroll = True
