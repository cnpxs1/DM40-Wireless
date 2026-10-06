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
from gui.assets import bind_clickable, make_scrollbar, raise_click_hotspots
from gui.settings import MIN_WINDOW_SCALE, as_text, save_settings
from gui.sprites import SpriteCache
from gui.fonts import gui_font
from gui.theme import rgb_hex


_HIT_GROUP = "settings_hits"   # lets rebuild() drop every hit area at once
_POPUP_GAP = 2                 # px between the selector row and the dropdown


def _inside(box: tuple[int, int, int, int], x: int, y: int) -> bool:
    bx, by, bw, bh = box
    return bx <= x < bx + bw and by <= y < by + bh


def _make_borderless(popup: tk.Toplevel) -> None:
    """Drop the title bar; overrideredirect is the only portable way.

    The ``-type`` hint only works under mutter. KWin decorates every hint it
    knows (toolbar, menu, popup_menu, tooltip, ...) and force-centres its
    splash type, so it cannot follow an anchor. The price is that the popup
    outranks normal windows - _on_root_focus_out closes it as soon as our own
    window loses the focus.
    """
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
        self._scale_entry: tk.Entry | None = None
        self._scale_hint_id: int | None = None
        self._scale_item_id: int | None = None   # canvas window item; survives rebuild()
        # Registered once: register() leaks a Tcl command per call.
        self._scale_vcmd = (self.register(self._scale_input_ok), "%P")

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
            self._leave_settings, tag="settings_hit_back",
        )

    def _leave_settings(self) -> None:
        """Back arrow: commit the field, then leave."""
        self.commit_pending_scale()
        self.app.go_back_from_settings()

    def rebuild(self) -> None:
        self._close_lang_popup()
        # Another row's click rebuilds without a <FocusOut>; commit the value.
        self._commit_scale()
        if self._title_id is not None:
            self.canvas.itemconfig(self._title_id, text=t("settings.title"))
        self.canvas.delete("settings_row")
        self.canvas.delete(_HIT_GROUP)
        label_font = gui_font(self.app.settings, self._s(SL.SETTINGS_LABEL_FONT), "normal")
        state_font = gui_font(self.app.settings, self._s(SL.SETTINGS_STATE_FONT), "normal")

        for (key, label), (x, y, w, h) in zip(SL.setting_rows(), SL.settings_row_slots()):
            if key == "language":
                self._place_language_row(x, y, w, h, key, label, label_font, state_font)
            elif key == "window_scale":
                self._place_scale_row(x, y, w, h, key, label, label_font, state_font)
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
        else keeps it in front of the main window it partly overlaps. Pinning
        is done at creation; reading ``-topmost`` here would re-enter the
        <Configure> handler that calls us.
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

    def _on_root_focus_out(self, event: tk.Event) -> None:
        """Our window lost the focus - take the popup down with it.

        The popup is override-redirect: it sits above every normal window and
        nothing else would ever close it once the user switches away. Child
        widgets raise <FocusOut> too, and clicking the popup hands the focus
        to the popup - neither means the user left us.
        """
        if event.widget is not self.app.root:
            return
        focused = self.app.root.focus_get()
        if focused is not None and focused.winfo_toplevel() is self._lang_popup:
            return
        self._close_lang_popup()

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
        current = as_text(self.app.settings.get("language")) or "en-US"
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

        current = as_text(self.app.settings.get("language")) or "en-US"
        pad = self._s(SL.LANGUAGE_POPUP_PAD)
        item_h = self._s(SL.LANGUAGE_ITEM_H)
        item_gap = self._s(SL.LANGUAGE_ITEM_GAP)
        popup_w = max(rw, self._s(180))
        # A longer list scrolls rather than growing - past the visible limit the
        # popup would simply run off the bottom of the screen.
        shown = min(len(languages), SL.LANGUAGE_MAX_VISIBLE)
        list_h = shown * item_h + max(0, shown - 1) * item_gap
        content_h = len(languages) * item_h + max(0, len(languages) - 1) * item_gap
        popup_h = pad * 2 + list_h

        popup = tk.Toplevel(self.app.root)
        popup.withdraw()                    # hidden until it has a position
        _make_borderless(popup)
        popup.transient(self.app.root)
        # Match a pinned window - topmost outranks the normal layer and lift()
        # cannot cross layers. Set once here, never in the Configure handler,
        # which would loop on the window manager's own reconfigure.
        popup.attributes("-topmost", bool(self.app.root.attributes("-topmost")))
        popup.configure(bg=rgb_hex("buttons_active"))

        body = tk.Frame(popup, bg=rgb_hex("background"), padx=pad, pady=pad)
        body.pack(fill="both", expand=True)

        scrolling = len(languages) > SL.LANGUAGE_MAX_VISIBLE
        bar = make_scrollbar(body, self.scale) if scrolling else None
        if bar is not None:
            bar.pack(side="right", fill="y")

        list_canvas = tk.Canvas(
            body, bg=rgb_hex("background"), highlightthickness=0, borderwidth=0,
            height=list_h, width=popup_w - 2 * pad,
        )
        list_canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(list_canvas, bg=rgb_hex("background"))
        inner_id = list_canvas.create_window((0, 0), window=inner, anchor="nw")
        list_canvas.configure(scrollregion=(0, 0, popup_w, content_h))
        list_canvas.bind(
            "<Configure>",
            lambda event: list_canvas.itemconfigure(inner_id, width=event.width),
        )
        if bar is not None:
            bar.config(command=list_canvas.yview)
            list_canvas.configure(yscrollcommand=bar.set)

        def on_wheel(event) -> None:
            """Tk sends the wheel to the widget under the pointer, never to the
            canvas that scrolls, so every widget down here carries this."""
            if event.num == 4:
                step = -1
            elif event.num == 5:
                step = 1
            else:
                step = -1 if event.delta > 0 else 1
            list_canvas.yview_scroll(step, "units")

        for container in (popup, list_canvas, inner):
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                container.bind(sequence, on_wheel, add="+")

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
                for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                    widget.bind(sequence, on_wheel, add="+")

        self._lang_popup = popup
        self._lang_anchor = (rx, ry, rw, rh)
        self._lang_size = (popup_w, popup_h)
        self._place_lang_popup()
        popup.deiconify()                   # positioned - showing it now is safe
        self._lift_lang_popup()             # and above our own window

        root = self.app.root
        self._lang_binds = [
            (seq, root.bind(seq, handler, add="+"))
            for seq, handler in (
                ("<Configure>", self._on_root_configure),
                ("<FocusIn>", self._on_root_focus_in),
                ("<FocusOut>", self._on_root_focus_out),
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

        lang_code = as_text(self.app.settings.get("language")) or "en-US"
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

    def _place_scale_row(
        self,
        x: int, y: int, w: int, h: int,
        key: str, label: str, label_font: tuple, state_font: tuple,
    ) -> None:
        """Label plus a text field, with a hint while a restart is pending.

        No whole-row hit area: it would swallow the field's own clicks. The
        field is created once and reused - remapping it blinks on X11.
        """
        rx, ry, rw, rh, cy = self._row_frame(key, x, y, w, h, label, label_font)

        # Field hugs the right edge like the switch; hint grows leftwards from it.
        field_w = self._s(SL.WINDOW_SCALE_FIELD_W)
        field_x = rx + rw - self._s(SL.SETTINGS_ROW_MARGIN) - field_w

        # Also the "field built" flag; set together with _scale_entry.
        if self._scale_item_id is None:
            entry = tk.Entry(
                self.canvas,
                bg=rgb_hex("buttons"), fg=rgb_hex("text_primary"),
                insertbackground=rgb_hex("text_primary"),
                highlightthickness=0, borderwidth=0, justify="center",
                font=state_font, validate="key", validatecommand=self._scale_vcmd,
            )
            entry.insert(0, self._scale_text())
            entry.bind("<Return>", self._commit_scale)
            entry.bind("<FocusOut>", self._commit_scale)
            self._scale_entry = entry
            # No "settings_row" tag: rebuild() must keep this item alive.
            self._scale_item_id = self.canvas.create_window(
                field_x + field_w // 2, cy, anchor="center",
                width=field_w, height=self._s(SL.SETTINGS_ROW_H - 16),
                window=entry, tags=(f"settings_entry_{key}",),
            )
            # Tk keeps the focus on the entry when a canvas item is clicked, so
            # <FocusOut> alone would leave a typed value uncommitted.
            self.canvas.bind("<Button-1>", self._commit_scale, add="+")
        else:
            self.canvas.coords(self._scale_item_id, field_x + field_w // 2, cy)

        self._scale_hint_id = self.canvas.create_text(
            field_x - self._s(SL.SETTINGS_SWITCH_GAP), cy,
            text=self._scale_hint_text(), anchor="e", font=state_font,
            fill=rgb_hex("text_secondary"),
            tags=("settings_row", f"settings_scale_hint_{key}"),
        )

    def _saved_scale(self) -> float:
        """window_scale straight from settings; sanitize_settings vetted it."""
        return float(self.app.settings.get("window_scale", 1.0))

    def _scale_text(self) -> str:
        """The value spelled the way settings.json stores it (1.0, not 1)."""
        return str(self._saved_scale())

    def _scale_hint_text(self) -> str:
        """Warn while the saved scale differs from the one this session runs at."""
        return (t("settings.restart_required")
                if self._saved_scale() != self.app.scale else "")

    @staticmethod
    def _scale_input_ok(proposed: str) -> bool:
        """Digits and one dot; the range is left to commit, so a value already
        out of range in settings.json stays editable."""
        return proposed.count(".") <= 1 and all(c.isdigit() or c == "." for c in proposed)

    def _commit_scale(self, _event: tk.Event | None = None) -> None:
        """Store a valid value on Enter or focus loss; anything else snaps back."""
        entry = self._scale_entry
        if entry is None:
            return
        try:
            value = float(entry.get().strip())
        except ValueError:
            value = None
        if value is not None and not MIN_WINDOW_SCALE <= value <= SL.WINDOW_SCALE_MAX:
            value = None
        entry.delete(0, "end")
        entry.insert(0, self._scale_text() if value is None else str(value))
        if value is None or value == self._saved_scale():
            return
        self.app.settings["window_scale"] = value
        save_settings(self.app.settings)
        if self._scale_hint_id is not None:
            self.canvas.itemconfig(self._scale_hint_id, text=self._scale_hint_text())

    def commit_pending_scale(self) -> None:
        """Store a typed scale before the screen goes away.

        The back arrow and the close button both bypass the field's own hooks.
        """
        self._commit_scale()
