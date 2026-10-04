"""Connect (cold run) – DM40 device selection in the main app window."""

from __future__ import annotations

import queue
import threading

import tkinter as tk

from ble.discovery import DM40Device, scan_dm40_devices_sync
from core.config import SCREEN_HEIGHT, SCREEN_WIDTH
from core.i18n import t
from gui import connect_layout as CL
from gui import layout as L
from gui.assets import bind_clickable, make_scrollbar, raise_click_hotspots
from gui.sprites import SpriteCache, rounded_item, rounded_photo
from gui.fonts import gui_font
from gui.theme import rgb_hex


class ConnectScreen(tk.Frame):
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

        self._devices: list[DM40Device] = []
        self._selected = -1
        self._list_offset = 0               # first device row on screen
        self._scanning = False
        self._scan_queue: queue.Queue = queue.Queue()
        self._sprite_ids: dict[str, int] = {}
        self._ble_pulse_on = True
        self._ble_pulse_after: str | None = None
        self._status_id: int | None = None
        self._connect_btn_bg_ids: dict[int, int] = {}

        self._list_scroll = make_scrollbar(self.canvas, scale)
        self._list_scroll.config(command=self._on_list_scroll)
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind(sequence, self._on_list_wheel, add="+")

        self._draw_chrome()
        self._draw_bottom_buttons()

    def _s(self, v: float) -> int:
        return int(v * self.scale)

    def raise_click_layer(self) -> None:
        raise_click_hotspots(self.canvas)

    def _draw_chrome(self) -> None:
        self.canvas.create_rectangle(
            0, 0, self._s(L.SCREEN_W), self._s(L.TOP_BAR_H),
            fill=rgb_hex("top_bar_background"), outline="", tags="connect_chrome",
        )
        font = gui_font(self.app.settings, self._s(CL.SETUP_TITLE_FONT), "bold")
        self.canvas.create_text(
            self._s(L.SCREEN_W // 2), self._s(CL.SETUP_TITLE_Y), text=t("setup.title"),
            fill=rgb_hex("text_primary"), anchor="center", font=font, tags="connect_chrome",
        )
        hint_font = gui_font(self.app.settings, self._s(CL.SETUP_HINT_FONT), "normal")
        self.canvas.create_text(
            self._s(L.SCREEN_W // 2), self._s(CL.SETUP_HINT_Y),
            text=t("setup.hint"),
            fill=rgb_hex("text_secondary"), anchor="center", font=hint_font, tags="connect_chrome",
        )
        status_font = gui_font(self.app.settings, self._s(CL.SETUP_STATUS_FONT), "normal")
        # width= makes Tk wrap overlong messages instead of clipping them
        self._status_id = self.canvas.create_text(
            self._s(L.SCREEN_W // 2), self._s(CL.SETUP_STATUS_Y), text="",
            fill=rgb_hex("text_primary"), anchor="center", font=status_font,
            width=self._s(CL.SETUP_STATUS_MAX_W),
            tags="connect_chrome",
        )
        self._set_status(t("setup.status_initial"))
        self._place_settings_icon()

    def _place_settings_icon(self) -> None:
        """Settings icon in the top bar (same position as main screen)."""
        photo = self._top_bar_icon("settings.png", L.TOP_BAR_ICON_SLOT)
        if photo:
            self._place_top_icon("settings", photo, L.TOP_BAR_SETTINGS_X)
        sx, sy, sw, sh = L.SETTINGS_HIT
        bind_clickable(
            self.canvas, self._s(sx), self._s(sy), self._s(sw), self._s(sh),
            self.app.show_settings_screen, tag="connect_hit_settings",
            group="connect_chrome",
        )

    def _set_status(self, text: str) -> None:
        if self._status_id is not None:
            self.canvas.itemconfigure(self._status_id, text=text)

    def _top_bar_icon(self, name: str, max_w: int) -> tk.PhotoImage | None:
        return self.sprites.top_bar(
            name, self.scale,
            max_w=self._s(max_w), max_h=self._s(L.TOP_BAR_ICON_H),
        )

    def _show_sprite(self, key: str, photo: tk.PhotoImage, x: int, y: int,
                     anchor: str = "nw") -> None:
        if key in self._sprite_ids:
            self.canvas.delete(self._sprite_ids[key])
        self._sprite_ids[key] = self.canvas.create_image(
            x, y, anchor=anchor, image=photo, tags="connect_chrome",
        )

    def _place_top_icon(self, key: str, photo: tk.PhotoImage, x: float) -> None:
        """Centre a top bar icon in its slot, as the main screen does."""
        cx, cy = L.top_icon_pos(x)
        self._show_sprite(key, photo, self._s(cx), self._s(cy), anchor="center")

    def _hide_sprite(self, key: str) -> None:
        item = self._sprite_ids.pop(key, None)
        if item is not None:
            self.canvas.delete(item)

    def _show_bt_icon(self) -> None:
        photo = self._top_bar_icon("bluetooth.png", L.TOP_BAR_ICON_SLOT)
        if photo:
            self._place_top_icon("bt", photo, L.TOP_BAR_BT_X)

    def _stop_bt_pulse(self) -> None:
        if self._ble_pulse_after is not None:
            self.app.root.after_cancel(self._ble_pulse_after)
            self._ble_pulse_after = None

    def _bt_pulse_tick(self) -> None:
        if not self._scanning:
            return
        if self._ble_pulse_on:
            self._show_bt_icon()
        else:
            self._hide_sprite("bt")
        self._ble_pulse_on = not self._ble_pulse_on
        self._ble_pulse_after = self.app.root.after(550, self._bt_pulse_tick)

    def _start_bt_pulse(self) -> None:
        self._stop_bt_pulse()
        self._ble_pulse_on = True
        self._bt_pulse_tick()

    def _stop_scan_ui(self) -> None:
        self._scanning = False
        self._stop_bt_pulse()
        self._show_bt_icon()

    def _set_connect_btn_hover(self, index: int, hovered: bool) -> None:
        bg_id = self._connect_btn_bg_ids.get(index)
        if bg_id is None:
            return
        _x, _y, w, h = CL.setup_button_slots()[index]
        photo = rounded_photo(
            "buttons_active" if hovered else "buttons",
            self._s(w), self._s(h), self._s(L.MODE_BTN_RADIUS),
        )
        if photo is not None:
            self.canvas.itemconfig(bg_id, image=photo)

    def _draw_bottom_buttons(self) -> None:
        self._connect_btn_bg_ids.clear()
        font = gui_font(self.app.settings, self._s(13), "normal")
        for i, (label, (x, y, w, h)) in enumerate(zip(CL.setup_btn_labels(), CL.setup_button_slots())):
            rx, ry, rw, rh = self._s(x), self._s(y), self._s(w), self._s(h)
            hit_tag = f"connect_hit_{i}"
            bg_id = rounded_item(
                self.canvas, rx, ry, rw, rh, self._s(L.MODE_BTN_RADIUS), "buttons",
                tags=("connect_btn", f"connect_btn_{i}"),
            )
            if bg_id is not None:
                self._connect_btn_bg_ids[i] = bg_id
            self.canvas.create_text(
                rx + rw // 2, ry + rh // 2, text=label,
                fill=rgb_hex("text_primary"), anchor="center", font=font,
                tags=("connect_btn", f"connect_btn_txt_{i}"),
            )
            cmd = self.start_scan if i == 0 else self._on_connect
            bind_clickable(
                self.canvas, rx, ry, rw, rh, cmd, tag=hit_tag,
                group="connect_btn",
            )
            self.canvas.tag_bind(hit_tag, "<Enter>", lambda _e, idx=i: self._set_connect_btn_hover(idx, True))
            self.canvas.tag_bind(hit_tag, "<Leave>", lambda _e, idx=i: self._set_connect_btn_hover(idx, False))

    def refresh_all(self) -> None:
        """Rebuild all translatable text; keep device list and scan state."""
        self.canvas.delete("connect_chrome")
        self.canvas.delete("connect_btn")
        self._connect_btn_bg_ids.clear()
        self._sprite_ids.clear()
        self._draw_chrome()
        self._draw_bottom_buttons()
        if self._scanning:
            self._set_status(t("setup.status_scanning"))
        elif self._devices:
            n = len(self._devices)
            if n == 1:
                self._set_status(t("setup.status_one_device"))
            else:
                self._set_status(t("setup.status_many_devices", count=n))
        else:
            self._set_status(t("setup.status_initial"))
        self._rebuild_device_list()

    def on_show(self, *, auto_scan: bool = False) -> None:
        self._show_bt_icon()
        if auto_scan:
            self.app.root.after(300, self.start_scan)

    def on_hide(self) -> None:
        self._stop_scan_ui()

    def start_scan(self) -> None:
        if self._scanning:
            return
        self._scanning = True
        self._devices = []
        self._selected = -1
        self._list_offset = 0
        self.canvas.delete("connect_row")
        self._set_status(t("setup.status_scanning"))
        self._start_bt_pulse()
        threading.Thread(target=self._scan_worker, daemon=True).start()
        self._poll_scan_result()

    def _scan_worker(self) -> None:
        error: str | None = None
        devices: list[DM40Device] = []
        try:
            devices = scan_dm40_devices_sync(timeout=12.0)
        except Exception as exc:
            error = str(exc)
        self._scan_queue.put((devices, error))

    def _poll_scan_result(self) -> None:
        if not self.winfo_exists():
            return
        try:
            devices, error = self._scan_queue.get_nowait()
        except queue.Empty:
            if self._scanning:
                self.app.root.after(100, self._poll_scan_result)
            return
        self._scan_done(devices, error)

    def _scan_done(self, devices: list[DM40Device], error: str | None) -> None:
        self._stop_scan_ui()
        self._devices = devices
        self._selected = 0 if devices else -1
        self._rebuild_device_list()
        if error:
            self._set_status(t("setup.status_scan_error", error=error))
        elif not devices:
            self._set_status(t("setup.status_no_device"))
        elif len(devices) == 1:
            self._set_status(t("setup.status_one_device"))
        else:
            self._set_status(t("setup.status_many_devices", count=len(devices)))

    def _rebuild_device_list(self) -> None:
        self.canvas.delete("connect_row")
        visible = CL.setup_visible_rows()
        count = len(self._devices)
        self._list_offset = max(0, min(self._list_offset, max(0, count - visible)))
        self._sync_list_scrollbar(visible)
        if not self._devices:
            self.raise_click_layer()
            return

        font = gui_font(self.app.settings, self._s(CL.SETUP_ROW_FONT), "normal")
        x = CL.SETUP_LIST_MARGIN
        # The bar sits inside the list area, so the rows give up its width.
        bar_w = CL.SETUP_SCROLLBAR_W if count > visible else 0
        w = L.SCREEN_W - 2 * CL.SETUP_LIST_MARGIN - bar_w
        row_h = CL.SETUP_ROW_H + CL.SETUP_ROW_GAP

        for slot in range(visible):
            index = self._list_offset + slot
            if index >= count:
                break
            dev = self._devices[index]
            y = CL.SETUP_LIST_TOP + slot * row_h
            active = index == self._selected
            rx, ry, rw, rh = self._s(x), self._s(y), self._s(w), self._s(CL.SETUP_ROW_H)
            bg = "buttons_active" if active else "range_buttons"
            self.canvas.create_rectangle(
                rx, ry, rx + rw, ry + rh,
                fill=rgb_hex(bg), outline="", tags=("connect_row", f"connect_row_{slot}"),
            )
            self.canvas.create_text(
                rx + self._s(CL.SETUP_ROW_PAD_LEFT), ry + rh // 2,
                text=dev.list_label(), anchor="w", font=font,
                fill=rgb_hex("text_primary"), tags=("connect_row", f"connect_txt_{slot}"),
            )
            # Tags follow the slot, so scrolling rebinds the same few hot areas;
            # the device the click selects is still named by absolute index.
            bind_clickable(
                self.canvas, rx, ry, rw, rh,
                lambda idx=index: self._select_device(idx), tag=f"connect_row_hit_{slot}",
                group="connect_row",
            )

        self.raise_click_layer()

    def _sync_list_scrollbar(self, visible: int) -> None:
        """Show the bar only while devices overflow, parked at the list's right."""
        count = len(self._devices)
        if count <= visible:
            self._list_scroll.place_forget()
            return
        self._list_scroll.place(
            x=self._s(L.SCREEN_W - CL.SETUP_LIST_MARGIN - CL.SETUP_SCROLLBAR_W),
            y=self._s(CL.SETUP_LIST_TOP),
            width=self._s(CL.SETUP_SCROLLBAR_W),
            height=self._s(CL.setup_list_bottom() - CL.SETUP_LIST_TOP),
        )
        self._list_scroll.set(
            self._list_offset / count, (self._list_offset + visible) / count,
        )

    def _set_list_offset(self, offset: int) -> None:
        visible = CL.setup_visible_rows()
        offset = max(0, min(offset, max(0, len(self._devices) - visible)))
        if offset == self._list_offset:
            return
        self._list_offset = offset
        self._rebuild_device_list()

    def _on_list_scroll(self, *args) -> None:
        """Scrollbar protocol: ("moveto", frac) or ("scroll", n, "units"|"pages")."""
        if not self._devices or not args:
            return
        if args[0] == "moveto":
            offset = round(float(args[1]) * len(self._devices))
        elif args[0] == "scroll":
            step = int(args[1])
            if len(args) > 2 and args[2] == "pages":
                step *= CL.setup_visible_rows()
            offset = self._list_offset + step
        else:
            return
        self._set_list_offset(offset)

    def _on_list_wheel(self, event) -> None:
        """Wheel over the list scrolls it; over the rest of the screen it does not."""
        if not self._devices:
            return
        if not self._s(CL.SETUP_LIST_TOP) <= event.y <= self._s(CL.setup_list_bottom()):
            return
        if event.num == 4:
            step = -1
        elif event.num == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        self._set_list_offset(self._list_offset + step)

    def _select_device(self, index: int) -> None:
        if index < 0 or index >= len(self._devices):
            return
        self._selected = index
        self._rebuild_device_list()

    def _on_connect(self) -> None:
        if self._selected < 0 or self._selected >= len(self._devices):
            self._set_status(t("setup.status_select_first"))
            return
        self.app.complete_device_setup(self._devices[self._selected])
