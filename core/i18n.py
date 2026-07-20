"""国际化模块 – 基于 TOML 的多语言支持，零额外依赖。

纯翻译引擎，不直接读写配置文件。语言代码由调用方传入。

用法::

    from core.i18n import t, get_i18n

    # 初始化（应用启动时，语言代码来自 settings.json）
    i18n = get_i18n()
    i18n.init("en-US")            # 或 i18n.init("zh-CN")

    # 获取翻译
    msg = t("setup.status_scan_error", error="蓝牙不可用")

    # 切换语言
    i18n.load_language("zh-CN")

    # 列出可用语言
    langs = i18n.available_languages()  # {"en-US": "English (US)", "zh-CN": "简体中文", ...}

语言文件存放于 ``i18n/`` 目录，按 BCP 47 格式命名（如 ``en-US.toml``、``zh-CN.toml``）。
文件首行注释 ``# language name: <显示名称>`` 用于在设置界面展示语言名称。
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def i18n_dir() -> Path:
    """返回 i18n/ 目录路径，兼容开发环境和 PyInstaller 打包。"""
    from core.config import PROJECT_ROOT
    return PROJECT_ROOT / "i18n"


class _I18n:
    """线程不安全的单例；所有 GUI 访问均在主线程上。"""

    def __init__(self) -> None:
        self._lang: str = ""
        self._strings: dict[str, str] = {}
        self._fallback: dict[str, str] = {}
        self._available: dict[str, str] = {}
        self._initialized = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def init(self, language: str) -> None:
        """用给定语言代码初始化（首次加载）。必须在首次调用 ``t()`` 之前调用。

        先加载 ``en-US.toml`` 作为回退，再加载 ``language`` 对应的文件。
        """
        if self._initialized:
            return
        self._initialized = True

        # 加载英文回退
        en_path = i18n_dir() / "en-US.toml"
        self._load_fallback(en_path)

        # 加载目标语言
        lang = language.strip() if language else "en-US"
        if lang != "en-US" or not self._strings:
            if not self.load_language(lang):
                self._strings = dict(self._fallback)
                lang = "en-US"
        self._lang = lang
        self.available_languages()

    def t(self, key: str, **fmt_kwargs: Any) -> str:
        """获取 ``key`` 的翻译文本，应用 ``**fmt_kwargs`` 占位符替换。

        回退链：当前语言 → 英文 → key 本身。
        """
        template = self._strings.get(key) or self._fallback.get(key) or key
        if not fmt_kwargs:
            return template
        try:
            return template.format(**fmt_kwargs)
        except (KeyError, ValueError, IndexError):
            return template

    @property
    def language(self) -> str:
        """当前语言代码。"""
        return self._lang

    def available_languages(self) -> dict[str, str]:
        """扫描 ``i18n/`` 目录，返回 ``{语言代码: 显示名称}``。"""
        d = i18n_dir()
        if not d.is_dir():
            self._available = {}
            return {}
        result: dict[str, str] = {}
        for path in sorted(d.glob("*.toml")):
            code = path.stem
            if not code:
                continue
            result[code] = self._read_lang_name(path)
        self._available = result
        return dict(result)

    def load_language(self, lang: str) -> bool:
        """从 ``i18n/{lang}.toml`` 加载语言。返回 True 表示成功。

        不影响回退字典，加载失败时当前翻译保持不变。
        """
        path = i18n_dir() / f"{lang}.toml"
        return self._load_toml(path, lang)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _read_lang_name(path: Path) -> str:
        """从 TOML 文件首行注释提取语言显示名称。

        支持的格式：``# language name: English`` 或 ``# language name:简体中文``。
        """
        try:
            first_line = path.read_text("utf-8").split("\n", 1)[0].strip()
        except OSError:
            return path.stem
        if first_line.startswith("#") and "language name:" in first_line.lower():
            idx = first_line.lower().find("language name:")
            name = first_line[idx + len("language name:"):].strip()
            name = name.lstrip(":").strip()
            if name:
                return name
        return path.stem

    def _load_toml(self, path: Path, label: str) -> bool:
        """加载并展平 TOML 文件到 self._strings。"""
        try:
            raw = tomllib.loads(path.read_text("utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return False
        strings = self._flatten(raw)
        if not strings:
            return False
        self._lang = label
        self._strings = strings
        return True

    def _load_fallback(self, path: Path) -> None:
        """加载英文回退字典。"""
        try:
            raw = tomllib.loads(path.read_text("utf-8"))
            self._fallback = self._flatten(raw)
        except (OSError, tomllib.TOMLDecodeError):
            self._fallback = {}

    @staticmethod
    def _flatten(data: dict, prefix: str = "") -> dict[str, str]:
        """递归展平嵌套 TOML 表为 ``section.key`` 格式的扁平字典。"""
        result: dict[str, str] = {}
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                result.update(_I18n._flatten(value, full_key))
            elif isinstance(value, str):
                result[full_key] = value
        return result


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_i18n_instance: _I18n | None = None


def get_i18n() -> _I18n:
    """获取（或创建）``_I18n`` 单例。"""
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = _I18n()
    return _i18n_instance


def t(key: str, **fmt_kwargs: Any) -> str:
    """便捷函数：获取翻译文本。等价于 ``get_i18n().t(key, ...)``。"""
    return get_i18n().t(key, **fmt_kwargs)
