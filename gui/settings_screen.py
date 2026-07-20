"""SETTINGS obrazovka – canvas GUI ve stylu RANGE menu."""

from __future__ import annotations

import tkinter as tk

from core.config import SCREEN_HEIGHT, SCREEN_WIDTH
from core.i18n import t, get_i18n, i18n_dir
from gui import layout as L
from gui import settings_layout as SL
from gui.assets import bind_clickable, raise_click_hotspots
from gui.settings import save_settings
from gui.sprites import SpriteCache
from gui.theme import rgb_hex


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
        font = ("sans-serif", self._s(SL.SETTINGS_TITLE_FONT), "bold")
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
            self.app.show_main_screen, tag="settings_hit_back",
        )

    def rebuild(self) -> None:
        self.canvas.delete("settings_row")
        label_font = ("sans-serif", self._s(SL.SETTINGS_LABEL_FONT), "normal")
        state_font = ("sans-serif", self._s(SL.SETTINGS_STATE_FONT), "bold")

        for (key, label), (x, y, w, h) in zip(SL.setting_rows(), SL.settings_row_slots()):
            if key == "language":
                self._place_language_row(x, y, w, h, key, label, label_font, state_font)
            else:
                enabled = bool(self.app.settings.get(key, False))
                self._place_row(x, y, w, h, key, label, enabled, label_font, state_font)

        self.raise_click_layer()

    def _place_row(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        key: str,
        label: str,
        enabled: bool,
        label_font: tuple,
        state_font: tuple,
    ) -> None:
        rx, ry, rw, rh = self._s(x), self._s(y), self._s(w), self._s(h)
        self.canvas.create_rectangle(
            rx, ry, rx + rw, ry + rh,
            fill=rgb_hex("range_buttons"), outline="", tags=("settings_row", f"settings_bg_{key}"),
        )
        cy = ry + rh // 2
        pad_l = self._s(SL.SETTINGS_ROW_MARGIN)
        self.canvas.create_text(
            rx + pad_l, cy, text=label,
            fill=rgb_hex("text_primary"), anchor="w", font=label_font,
            tags=("settings_row", f"settings_lbl_{key}"),
        )

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
            lambda k=key: self._toggle(k), tag=f"settings_hit_{key}",
        )

    def _toggle(self, key: str) -> None:
        self.app.settings[key] = not bool(self.app.settings.get(key, False))
        save_settings(self.app.settings)
        self.app.apply_settings()
        self.rebuild()

    def _toggle_language(self) -> None:
        """打开文件对话框导入语言配置文件，更新 settings.json。"""
        from tkinter import filedialog, messagebox
        from pathlib import Path

        path = filedialog.askopenfilename(
            title=t("settings.import_title"),
            filetypes=[("TOML language files", "*.toml"), ("All files", "*.*")],
        )
        if not path:
            return

        src = Path(path)
        if not src.is_file():
            return

        lang_code = src.stem

        # 读取内容验证 TOML 格式
        try:
            content = src.read_text("utf-8")
            import tomllib
            tomllib.loads(content)
        except OSError as exc:
            messagebox.showerror(
                t("settings.import_error_title"),
                t("settings.import_error_msg", error=exc),
            )
            return
        except tomllib.TOMLDecodeError as exc:
            messagebox.showerror(
                t("settings.import_error_title"),
                t("settings.import_error_msg", error=str(exc)),
            )
            return

        # 写入 i18n/ 目录
        dest_dir = i18n_dir()
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        try:
            dest.write_text(content, "utf-8")
        except OSError as exc:
            messagebox.showerror(
                t("settings.import_error_title"),
                t("settings.import_error_msg", error=exc),
            )
            return

        # 切换语言并刷新
        self.app.reload_language(lang_code)

    def _place_language_row(
        self, x: int, y: int, w: int, h: int, key: str, label: str,
        label_font: tuple, state_font: tuple,
    ) -> None:
        """绘制语言行：显示 settings.json 中的当前语言代码，点击导入新语言文件。"""
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
        # 从 settings.json 读取当前语言代码作为显示
        lang_code = (self.app.settings.get("language") or "").strip() or "en-us"
        i18n = get_i18n()
        available = i18n.available_languages()
        display = available.get(lang_code, lang_code)
        pad_r = self._s(SL.SETTINGS_ROW_MARGIN)
        self.canvas.create_text(
            rx + rw - pad_r, cy, text=display,
            fill=rgb_hex("buttons_active"), anchor="e", font=state_font,
            tags=("settings_row", f"settings_state_{key}"),
        )
        bind_clickable(
            self.canvas, rx, ry, rw, rh,
            self._toggle_language, tag=f"settings_hit_{key}",
        )
