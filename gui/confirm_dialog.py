"""Modal confirmation drawn on top of a screen's own canvas.

Drawn on the canvas rather than in a Toplevel so it is part of the window: it
moves with it and never flickers.
"""

from __future__ import annotations

import tkinter as tk

from gui import layout as L
from gui.fonts import gui_font
from gui.sprites import SpriteCache
from gui.theme import rgb_hex

TAG = "confirm_dialog"      # carried by every item of the overlay
_BTN_W = 78
_BTN_H = 28
_BTN_GAP = 8
_PANEL_W = 300
_PAD = 16
_TITLE_H = 28               # gap below the title before the body starts

_pending: "tk.BooleanVar | None" = None     # the question on screen, if any


def cancel_pending() -> None:
    """Answer "no" to an open confirmation, if there is one.

    Call before destroying the window: ``wait_variable`` never returns once the
    interpreter is gone, so the process would hang instead of exiting.
    """
    if _pending is not None:
        _pending.set(False)


def raise_overlay(canvas: tk.Canvas) -> None:
    """Lift the overlay back above the click hotspots.

    Screens raise the hotspots on every repaint; without this they end up over
    the dialog and steal its clicks.
    """
    canvas.tag_raise(TAG)


def ask_confirm(
    canvas: tk.Canvas,
    sprites: SpriteCache,
    settings: dict | None,
    *,
    title: str,
    message: str,
    yes_text: str,
    no_text: str,
    scale: float = 1.0,
) -> bool:
    """Ask a yes/no question over ``canvas``; True only for the yes button.

    Clicking outside the panel cancels. Blocks the caller through
    ``wait_variable``, not the event loop, so the window keeps repainting.
    """
    def s(value: float) -> int:
        return int(value * scale)

    global _pending
    result = tk.BooleanVar(master=canvas, value=False)
    cw, ch = canvas.winfo_width(), canvas.winfo_height()

    # Invisible on purpose: it only swallows clicks aimed at the screen below.
    # Tk has no alpha on canvas items, and stipple would shred the readout.
    canvas.create_rectangle(
        0, 0, cw, ch, fill="", outline="", tags=(TAG, f"{TAG}_veil"),
    )

    panel_w = s(_PANEL_W)
    panel_x = (cw - panel_w) // 2
    panel_y = ch // 3
    inner_w = panel_w - 2 * s(_PAD)

    title_id = canvas.create_text(
        panel_x + s(_PAD), panel_y + s(_PAD), text=title, anchor="nw",
        fill=rgb_hex("text_primary"), font=gui_font(settings, s(15), "bold"),
        width=inner_w, tags=TAG,
    )
    body_id = canvas.create_text(
        panel_x + s(_PAD), panel_y + s(_PAD) + s(_TITLE_H), text=message, anchor="nw",
        fill=rgb_hex("text_secondary"), font=gui_font(settings, s(13), "normal"),
        width=inner_w, tags=TAG,
    )

    # The body wraps at inner_w, so its height is only known once measured.
    canvas.update_idletasks()
    body_bottom = canvas.bbox(body_id)[3]
    panel_h = (body_bottom - panel_y) + s(_PAD + _BTN_H + _PAD)

    panel_id = canvas.create_image(
        panel_x, panel_y, anchor="nw",
        image=sprites.rounded_button("buttons", panel_w, panel_h, s(L.MODE_BTN_RADIUS)),
        tags=(TAG, f"{TAG}_panel"),
    )
    for item in (panel_id, title_id, body_id):
        canvas.tag_raise(item)          # panel under, text on top

    def close() -> None:
        canvas.delete(TAG)

    def pick(confirmed: bool) -> None:
        result.set(confirmed)
        close()

    top = panel_y + panel_h - s(_PAD + _BTN_H)
    # Cancel left, confirm right. Cancel uses range_buttons because "buttons" is
    # the panel's own colour and would make the button invisible.
    buttons = ((no_text, "range_buttons", False), (yes_text, "buttons_active", True))
    for index, (label, color, is_confirm) in enumerate(buttons):
        bw, bh = s(_BTN_W), s(_BTN_H)
        bx = panel_x + panel_w - s(_PAD) - (2 - index) * (bw + s(_BTN_GAP)) + s(_BTN_GAP)
        photo = sprites.rounded_button(color, bw, bh, s(L.MODE_BTN_RADIUS))
        if photo:
            canvas.create_image(bx, top, anchor="nw", image=photo, tags=(TAG, f"{TAG}_btn"))
        canvas.create_text(
            bx + bw // 2, top + bh // 2, text=label, anchor="center",
            fill=rgb_hex("text_primary"), font=gui_font(settings, s(13), "normal"),
            tags=(TAG, f"{TAG}_btn"),
        )
        hit = f"{TAG}_hit_{index}"
        canvas.create_rectangle(
            bx, top, bx + bw, top + bh, fill="", outline="", tags=(TAG, hit),
        )
        canvas.tag_bind(hit, "<Button-1>", lambda _e, c=is_confirm: pick(c))

    canvas.tag_bind(f"{TAG}_veil", "<Button-1>", lambda _e: pick(False))
    raise_overlay(canvas)

    _pending = result
    canvas.wait_variable(result)
    _pending = None
    return result.get()
