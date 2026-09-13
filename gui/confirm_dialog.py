"""Modal yes/no popup, drawn to match the app's dark canvas look.

``messagebox`` would be one line, but the rest of the UI is self-drawn, so the
confirmation is built the same way the language dropdown is: a borderless
Toplevel positioned under the widget that opened it, dismissed by clicking
outside.
"""

from __future__ import annotations

import tkinter as tk

from gui import layout as L
from gui.fonts import gui_font
from gui.sprites import SpriteCache
from gui.theme import rgb_hex

_BTN_W = 78
_BTN_H = 28
_BTN_GAP = 8
_PAD = 16
_TEXT_W = 250


def ask_confirm(
    root: tk.Tk,
    sprites: SpriteCache,
    settings: dict | None,
    *,
    title: str,
    message: str,
    yes_text: str,
    no_text: str,
    scale: float = 1.0,
) -> bool:
    """Ask a yes/no question in a popup centred on the main window.

    Returns True only for the affirmative button; a click outside counts as
    cancel, matching the language dropdown. Blocks until the popup closes.
    """
    def s(value: float) -> int:
        return int(value * scale)

    result = {"ok": False}
    dismiss_bind: str | None = None
    follow_bind: str | None = None

    popup = tk.Toplevel(root)
    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    popup.configure(bg=rgb_hex("buttons_active"))   # reads as a 1 px border

    body = tk.Frame(popup, bg=rgb_hex("background"), padx=s(_PAD), pady=s(_PAD))
    body.pack(padx=1, pady=1)

    tk.Label(
        body, text=title, bg=rgb_hex("background"), fg=rgb_hex("text_primary"),
        font=gui_font(settings, s(15), "bold"), anchor="w",
    ).pack(fill="x")

    tk.Label(
        body, text=message, bg=rgb_hex("background"), fg=rgb_hex("text_secondary"),
        font=gui_font(settings, s(13), "normal"), anchor="w", justify="left",
        wraplength=s(_TEXT_W),
    ).pack(fill="x", pady=(s(6), s(14)))

    row = tk.Frame(body, bg=rgb_hex("background"))
    row.pack(anchor="e")

    def close() -> None:
        if dismiss_bind is not None:
            root.unbind("<Button-1>", dismiss_bind)
        if follow_bind is not None:
            root.unbind("<Configure>", follow_bind)
        popup.destroy()

    def pick(confirmed: bool) -> None:
        result["ok"] = confirmed
        close()

    # Cancel first, affirmative second - the confirm stays on the right.
    # The image needs no reference on the widget: SpriteCache holds it.
    for label, color, is_confirm in ((no_text, "buttons", False),
                                     (yes_text, "buttons_active", True)):
        photo = sprites.rounded_button(color, s(_BTN_W), s(_BTN_H), s(L.MODE_BTN_RADIUS))
        button = tk.Label(
            row, text=label, bg=rgb_hex("background"), fg=rgb_hex("text_primary"),
            font=gui_font(settings, s(13), "normal"), bd=0,
            **({"image": photo, "compound": "center"} if photo else {}),
        )
        button.pack(side="left", padx=((s(_BTN_GAP), 0) if is_confirm else 0))
        button.bind("<Button-1>", lambda _e, c=is_confirm: pick(c))

    def dismiss(event: tk.Event) -> None:
        px, py = popup.winfo_rootx(), popup.winfo_rooty()
        inside = (px <= event.x_root <= px + popup.winfo_width()
                  and py <= event.y_root <= py + popup.winfo_height())
        if not inside:
            pick(False)

    root.update_idletasks()
    popup.update_idletasks()
    w, h = body.winfo_reqwidth() + 2, body.winfo_reqheight() + 2

    def reposition(_event=None) -> None:
        """Keep the popup centred while the window underneath it moves."""
        x = root.winfo_rootx() + (root.winfo_width() - w) // 2
        y = root.winfo_rooty() + (root.winfo_height() - h) // 2
        popup.geometry(f"+{x}+{y}")

    reposition()
    follow_bind = root.bind("<Configure>", reposition, add="+")
    dismiss_bind = root.bind("<Button-1>", dismiss, add="+")
    root.wait_window(popup)
    return result["ok"]
