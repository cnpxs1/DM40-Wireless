"""SETTINGS screen – canvas GUI styled like the RANGE menu."""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk

from core.config import SCREEN_HEIGHT, SCREEN_WIDTH
from core.i18n import t, get_i18n, i18n_dir
from gui import layout as L
from gui import settings_layout as SL
from gui.assets import bind_clickable, raise_click_hotspots
from gui.settings import save_settings
from gui.sprites import SpriteCache
from gui.fonts import gui_font
from gui.theme import rgb_hex


_HIT_GROUP = "settings_hits"   # lets rebuild() drop every hit area at once
_POPUP_GAP = 2                 # px between the selector row and the dropdown


def _inside(box: tuple[int, int, int, int], x: int, y: int) -> bool:
    bx, by, bw, bh = box
    return bx <= x < bx + bw and by <= y < by + bh


def _make_borderless(popup: tk.Toplevel) -> None:
    """Drop the title bar without asking to be pinned over everything.

    mutter puts override-redirect windows - and menu, popup_menu, tooltip,
    notification, combo and dnd window types with them - in its topmost layer,
    above every other application. toolbar is the one type hint that stays
    borderless and in the normal layer, so other applications can cover it.
    """
    if sys.platform == "win32":
        popup.overrideredirect(True)        # Windows has no EWMH type hints
        return
    try:
        popup.attributes("-type", "toolbar")
    except tk.TclError:                     # window manager without type hints
        popup.overrideredirect(True)


def _reveal_in_file_manager(path: str) -> None:
    """Open a folder in the platform's file manager. Never raises.

    The caller arms a focus hook right after this returns, so a missing
    xdg-open must not abort it - the language list would stop refreshing.
    """
    try:
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.Popen(
                ["xdg-open", path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    except OSError:
        pass


class SettingsScreen(tk.Frame):
    def __init__(self, master, app, scale: float) -> None:
        super().__init__(master, bg=rgb_hex("background"))
        self.app = app
        self.scale = scale
        self.sprites = SpriteCache()
        w, h = int(SCREEN_WIDTH * scale), int(SCREEN_HEIGHT * scale)
        self.configure(width=w, height=h)
        self.pack_propagate(False)

        self.canvas = tk.Canvas(self, width=w, height=h, highlightthickness=0, bg=rgb_hex("background"))
        self.canvas.pack()

        self._title_id: int | None = None
        self._back_sprite_id: int | None = None
        self._lang_popup: tk.Toplevel | None = None
        self._lang_anchor: tuple[int, int, int, int] | None = None   # selector, canvas px
        self._lang_size: tuple[int, int] | None = None                # popup, px
        self._lang_binds: list[tuple[str, str]] = []   # (sequence, funcid) on the root
        self._folder_focus_bind: str | None = None

        self._draw_top_bar()
        self._bind_back()

    def _s(self, v: float) -> int:
        return int(v * self.scale)

    def raise_click_layer(self) -> None:
        raise_click_hotspots(self.canvas)

    def _draw_top_bar(self) -> None:
        self.canvas.create_rectangle(
            0, 0, self._s(L.SCREEN_W), self._s(L.TOP_BAR_H),
            fill=rgb_hex("top_bar_background"), outline="", tags="settings_chrome",
        )
        font = gui_font(self.app.settings, self._s(SL.SETTINGS_TITLE_FONT), "normal")
        self._title_id = self.canvas.create_text(
            self._s(L.SCREEN_W // 2), self._s(SL.SETTINGS_TITLE_Y), text=t("settings.title"),
            fill=rgb_hex("text_primary"), anchor="center", font=font, tags="settings_chrome",
        )
        self._place_back_icon()

    def _place_back_icon(self) -> None:
        if self._back_sprite_id is not None:
            self.canvas.delete(self._back_sprite_id)
            self._back_sprite_id = None
        max_h = self._s(L.TOP_BAR_H - 12)
        photo = self.sprites.range_menu_sprite("back.png", self.scale, max_h=max_h)
        if photo:
            self._back_sprite_id = self.canvas.create_image(
                self._s(SL.SETTINGS_BACK_IMG[0]), self._s(SL.SETTINGS_BACK_IMG[1]),
                anchor="nw", image=photo, tags="settings_chrome",
            )

    def _bind_back(self) -> None:
        bx, by, bw, bh = SL.settings_back_hit()
        bind_clickable(
            self.canvas, self._s(bx), self._s(by), self._s(bw), self._s(bh),
            self.app.go_back_from_settings, tag="settings_hit_back",
        )

    def rebuild(self) -> None:
        self._close_lang_popup()
        if self._title_id is not None:
            self.canvas.itemconfig(self._title_id, text=t("settings.title"))
        self.canvas.delete("settings_row")
        self.canvas.delete(_HIT_GROUP)
        label_font = gui_font(self.app.settings, self._s(SL.SETTINGS_LABEL_FONT), "normal")
        state_font = gui_font(self.app.settings, self._s(SL.SETTINGS_STATE_FONT), "normal")

        for (key, label), (x, y, w, h) in zip(SL.setting_rows(), SL.settings_row_slots()):
            if key == "language":
                self._place_language_row(x, y, w, h, key, label, label_font, state_font)
            else:
                enabled = bool(self.app.settings.get(key, False))
                self._place_row(x, y, w, h, key, label, enabled, label_font, state_font)

        self.raise_click_layer()

    def _row_frame(self, key: str, x: int, y: int, w: int, h: int, label: str, label_font: tuple) -> tuple[int, int, int, int, int]:
        rx, ry, rw, rh = self._s(x), self._s(y), self._s(w), self._s(h)
        self.canvas.create_rectangle(
            rx, ry, rx + rw, ry + rh,
            fill=rgb_hex("range_buttons"), outline="",
            tags=("settings_row", f"settings_bg_{key}"),
        )
        cy = ry + rh // 2
        pad_l = self._s(SL.SETTINGS_ROW_MARGIN)
        self.canvas.create_text(
            rx + pad_l, cy, text=label,
            fill=rgb_hex("text_primary"), anchor="w", font=label_font,
            tags=("settings_row", f"settings_lbl_{key}"),
        )
        return rx, ry, rw, rh, cy

    def _place_row(
        self,
        x: int, y: int, w: int, h: int,
        key: str, label: str, enabled: bool,
        label_font: tuple, state_font: tuple,
    ) -> None:
        rx, ry, rw, rh, cy = self._row_frame(key, x, y, w, h, label, label_font)

        switch = self.sprites.settings_sprite(
            "switch_on.png" if enabled else "switch_off.png",
            self.scale,
            max_h=self._s(SL.SETTINGS_SWITCH_MAX_H),
        )
        state_text = t("settings.state_on") if enabled else t("settings.state_off")
        state_color = rgb_hex("buttons_active") if enabled else rgb_hex("text_secondary")
        gap = self._s(SL.SETTINGS_SWITCH_GAP)
        pad_r = self._s(SL.SETTINGS_ROW_MARGIN)

        if switch:
            switch_x = rx + rw - pad_r - switch.width()
            self.canvas.create_image(
                switch_x, cy, anchor="w", image=switch,
                tags=("settings_row", f"settings_sw_{key}"),
            )
            state_x = switch_x - gap
        else:
            state_x = rx + rw - pad_r

        self.canvas.create_text(
            state_x, cy, text=state_text,
            fill=state_color, anchor="e", font=state_font,
            tags=("settings_row", f"settings_state_{key}"),
        )
        bind_clickable(
            self.canvas, rx, ry, rw, rh,
            lambda k=key: self._toggle(k), tag=f"settings_hit_{key}", group=_HIT_GROUP,
        )

    def _toggle(self, key: str) -> None:
        self.app.settings[key] = not bool(self.app.settings.get(key, False))
        save_settings(self.app.settings)
        self.app.apply_settings()
        self.rebuild()

    def _close_lang_popup(self) -> None:
        """Drop the dropdown; safe to call when it is not open."""
        popup, self._lang_popup = self._lang_popup, None
        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass
        self._lang_anchor = None
        self._lang_size = None
        for sequence, funcid in self._lang_binds:
            self.app.root.unbind(sequence, funcid)
        self._lang_binds.clear()

    def _place_lang_popup(self) -> None:
        """Park the popup under the selector, in screen coordinates."""
        if self._lang_popup is None or self._lang_anchor is None or self._lang_size is None:
            return
        rx, ry, rw, rh = self._lang_anchor
        popup_w, popup_h = self._lang_size
        x = self.canvas.winfo_rootx() + rx + rw - popup_w
        y = self.canvas.winfo_rooty() + ry + rh + self._s(_POPUP_GAP)
        self._lang_popup.geometry(f"{popup_w}x{popup_h}+{x}+{y}")

    def _lift_lang_popup(self) -> None:
        """Lift the popup back above our window.

        overrideredirect drops the owner that ``transient`` sets, so nothing
        else keeps it in front of the main window it partly overlaps.
        """
        if self._lang_popup is not None:
            self._lang_popup.lift()

    def _on_root_configure(self, event: tk.Event) -> None:
        """Keep the popup glued to the window while that is dragged.

        A Toplevel does not follow its master on Windows, and child widgets
        raise <Configure> too - hence the widget check.
        """
        if event.widget is self.app.root:
            self._place_lang_popup()
            self._lift_lang_popup()

    def _on_root_focus_in(self, _event: tk.Event) -> None:
        """Our window came forward; the popup goes back in front of it."""
        self._lift_lang_popup()

    def _on_lang_outside_click(self, event: tk.Event) -> None:
        """Close the dropdown on a click that missed it and the selector.

        Clicks inside the popup never get here - it is a separate window.
        """
        if self._lang_popup is None or self._lang_anchor is None:
            return
        rx, ry, rw, rh = self._lang_anchor
        selector = (
            self.canvas.winfo_rootx() + rx, self.canvas.winfo_rooty() + ry, rw, rh,
        )
        if _inside(selector, event.x_root, event.y_root):
            return
        self._close_lang_popup()

    def _open_i18n_folder(self) -> None:
        """Open i18n/ in the file manager; refresh language list on refocus."""
        self._close_lang_popup()
        folder = i18n_dir()
        folder.mkdir(parents=True, exist_ok=True)
        _reveal_in_file_manager(str(folder))
        self._unbind_folder_focus()

        def on_focus(_event=None) -> None:
            self._unbind_folder_focus()
            self.rebuild()

        self._folder_focus_bind = self.app.root.bind("<FocusIn>", on_focus, add="+")

    def _unbind_folder_focus(self) -> None:
        """Drop the pending "app regained focus" hook, if one is armed.

        Unbinds by funcid: a bare ``unbind("<FocusIn>")`` would also remove the
        title-bar handler registered in :mod:`gui.win_titlebar`.
        """
        if self._folder_focus_bind:
            self.app.root.unbind("<FocusIn>", self._folder_focus_bind)
            self._folder_focus_bind = None

    def _select_language(self, lang_code: str) -> None:
        current = (self.app.settings.get("language") or "").strip() or "en-US"
        self._close_lang_popup()
        if lang_code == current:
            return
        self.app.reload_language(lang_code)

    def _toggle_lang_popup(self, rx: int, ry: int, rw: int, rh: int) -> None:
        if self._lang_popup is not None:
            self._close_lang_popup()
            return
        self._show_lang_popup(rx, ry, rw, rh)

    def _show_lang_popup(self, rx: int, ry: int, rw: int, rh: int) -> None:
        """Open the language list as its own window, hung under the selector.

        The canvas cannot draw it - a list this tall is clipped at the window
        edge - and it is positioned while still hidden, or it would flash at the
        screen origin for a frame.
        """
        languages = get_i18n().available_languages()
        if not languages:
            return

        current = (self.app.settings.get("language") or "").strip() or "en-US"
        pad = self._s(SL.LANGUAGE_POPUP_PAD)
        item_h = self._s(SL.LANGUAGE_ITEM_H)
        item_gap = self._s(SL.LANGUAGE_ITEM_GAP)
        popup_w = max(rw, self._s(180))
        popup_h = pad * 2 + len(languages) * item_h + max(0, len(languages) - 1) * item_gap

        popup = tk.Toplevel(self.app.root)
        popup.withdraw()                    # hidden until it has a position
        _make_borderless(popup)
        popup.transient(self.app.root)
        popup.configure(bg=rgb_hex("buttons_active"))

        inner = tk.Frame(popup, bg=rgb_hex("background"), padx=pad, pady=pad)
        inner.pack(fill="both", expand=True)

        popup_font = gui_font(self.app.settings, self._s(SL.SETTINGS_STATE_FONT), "normal")
        margin = self._s(SL.SETTINGS_ROW_MARGIN)
        last = len(languages) - 1

        for index, (lang_code, display) in enumerate(languages.items()):
            active = lang_code == current
            bg = rgb_hex("buttons_active") if active else rgb_hex("range_buttons")
            row = tk.Frame(inner, bg=bg, height=item_h)
            # No gap under the last row - popup_h above counts n-1 of them.
            row.pack(fill="x", pady=(0, 0 if index == last else item_gap))
            row.pack_propagate(False)

            lbl = tk.Label(
                row, text=display, bg=bg, fg=rgb_hex("text_primary"), anchor="w",
                font=popup_font, padx=margin,
            )
            lbl.pack(fill="both", expand=True)

            def paint(hex_color: str, r=row, l=lbl) -> None:
                r.configure(bg=hex_color)
                l.configure(bg=hex_color)

            def on_pick(_event=None, code=lang_code):
                self._select_language(code)

            # Defaults capture each pass: paint is rebound every iteration.
            def on_enter(_event=None, is_active=active, hover=rgb_hex("buttons_hover"),
                         repaint=paint):
                if not is_active:       # the selected row keeps its blue
                    repaint(hover)

            def on_leave(_event=None, restore=bg, repaint=paint):
                repaint(restore)

            for widget in (row, lbl):
                widget.bind("<Button-1>", on_pick)
                widget.bind("<Enter>", on_enter)
                widget.bind("<Leave>", on_leave)

        self._lang_popup = popup
        self._lang_anchor = (rx, ry, rw, rh)
        self._lang_size = (popup_w, popup_h)
        self._place_lang_popup()
        popup.deiconify()                   # positioned - showing it now is safe
        popup.lift()                        # and above our own window

        root = self.app.root
        self._lang_binds = [
            (seq, root.bind(seq, handler, add="+"))
            for seq, handler in (
                ("<Configure>", self._on_root_configure),
                ("<FocusIn>", self._on_root_focus_in),
                ("<Button-1>", self._on_lang_outside_click),
            )
        ]

    def _place_language_row(
        self, x: int, y: int, w: int, h: int, key: str, label: str,
        label_font: tuple, state_font: tuple,
    ) -> None:
        rx, ry, rw, rh, cy = self._row_frame(key, x, y, w, h, label, label_font)
        pad_l = self._s(SL.SETTINGS_ROW_MARGIN)
        pad_r = self._s(SL.SETTINGS_ROW_MARGIN)

        lang_icon = self.sprites.settings_sprite(
            "lang_icon.png", self.scale, max_h=self._s(SL.LANGUAGE_LANG_ICON_MAX_H),
        )
        lbl_id = self.canvas.find_withtag(f"settings_lbl_{key}")
        if lang_icon and lbl_id:
            bbox = self.canvas.bbox(lbl_id[0])
            if bbox:
                icon_x = bbox[2] + self._s(SL.LANGUAGE_LANG_ICON_GAP)
                self.canvas.create_image(
                    icon_x, cy, anchor="w", image=lang_icon,
                    tags=("settings_row", f"settings_lang_icon_{key}"),
                )

        folder_icon = self.sprites.settings_sprite(
            "folder.png", self.scale, max_h=self._s(SL.LANGUAGE_FOLDER_ICON_MAX_H),
        )
        folder_pad = self._s(4)
        if folder_icon:
            folder_x = rx + rw - pad_r - folder_icon.width()
            folder_y = cy - folder_icon.height() // 2
            self.canvas.create_image(
                folder_x, folder_y, anchor="nw", image=folder_icon,
                tags=("settings_row", f"settings_folder_{key}"),
            )
            bind_clickable(
                self.canvas,
                folder_x, folder_y,
                folder_icon.width(), folder_icon.height(),
                self._open_i18n_folder,
                tag=f"settings_folder_hit_{key}", group=_HIT_GROUP,
            )
            selector_right = folder_x - folder_pad
        else:
            selector_right = rx + rw - pad_r

        lang_code = (self.app.settings.get("language") or "").strip() or "en-US"
        display = get_i18n().available_languages().get(lang_code, lang_code)
        selector_left = rx + self._s(120)
        selector_top = ry + self._s(6)
        selector_bottom = ry + rh - self._s(6)
        selector_h = selector_bottom - selector_top
        selector_w = max(self._s(80), selector_right - selector_left)

        self.canvas.create_rectangle(
            selector_left, selector_top,
            selector_left + selector_w, selector_bottom,
            fill=rgb_hex("buttons"), outline="",
            tags=("settings_row", f"settings_selector_bg_{key}"),
        )
        self.canvas.create_text(
            selector_left + selector_w // 2, cy,
            text=f"{display}  ▼", anchor="center", font=state_font,
            fill=rgb_hex("text_primary"),
            tags=("settings_row", f"settings_selector_txt_{key}"),
        )
        bind_clickable(
            self.canvas,
            selector_left, selector_top, selector_w, selector_h,
            lambda: self._toggle_lang_popup(selector_left, selector_top, selector_w, selector_h),
            tag=f"settings_selector_hit_{key}", group=_HIT_GROUP,
        )
