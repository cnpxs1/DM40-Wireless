"""Internationalization module – TOML-based multilingual support, zero extra dependencies.

Pure translation engine; does not read or write config files directly. Language code is passed in by the caller.

Usage::

    from core.i18n import t, get_i18n

    # Initialize at app startup (language code from settings.json)
    i18n = get_i18n()
    i18n.init("en-US")            # or i18n.init("zh-CN")

    # Fetch translation
    msg = t("setup.status_scan_error", error="Bluetooth unavailable")

    # Switch language
    i18n.load_language("zh-CN")

    # List available languages
    langs = i18n.available_languages()  # {"en-US": "English (US)", "zh-CN": "简体中文", ...}

Language files live in ``i18n/``, named in BCP 47 format (e.g. ``en-US.toml``, ``zh-CN.toml``).
The first-line comment ``# language name: <display name>`` is shown in the Settings language picker.
"""

from __future__ import annotations

import locale
import os
import sys
import tomllib
from pathlib import Path
from typing import Any, cast


def i18n_dir() -> Path:
    """Return the external i18n/ directory path (user-editable, preferred)."""
    from core.config import PROJECT_ROOT
    return PROJECT_ROOT / "i18n"


def _embedded_i18n_dir() -> Path:
    """Return the embedded i18n/ directory inside the exe (read-only fallback)."""
    from core.config import EMBEDDED_I18N_DIR
    return EMBEDDED_I18N_DIR


class _I18n:
    """Not thread-safe singleton; all GUI access runs on the main thread."""

    def __init__(self) -> None:
        self._lang: str = ""
        self._strings: dict[str, str] = {}
        self._fallback: dict[str, str] = {}
        self._initialized = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def init(self, language: str) -> None:
        """Initialize with the given language code (first load). Must run before the first ``t()`` call.

        Loads ``en-US.toml`` as fallback, then the file for ``language``.
        External ``i18n/`` is preferred; embedded copy inside exe is used as fallback.
        """
        if self._initialized:
            return
        self._initialized = True

        # Load English fallback (external → embedded), then the target language.
        self._load_fallback()

        lang = language.strip() if language else "en-US"
        self._strings = dict(self._fallback)
        if lang != "en-US" or not self._fallback:
            if not self.load_language(lang):
                lang = "en-US"
        self._lang = lang

    def t(self, key: str, **fmt_kwargs: Any) -> str:
        """Return translation for ``key``, applying ``**fmt_kwargs`` placeholder substitution.

        Fallback chain: current language → English → key itself.
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
        """Current language code."""
        return self._lang

    def available_languages(self) -> dict[str, str]:
        """Scan ``i18n/`` and return ``{language_code: display_name}``.

        External ``i18n/`` is preferred; languages missing from it (e.g. a file the
        user deleted) are filled in from the embedded copy inside the exe.
        """
        result: dict[str, str] = {}
        # External i18n/ wins; the embedded copy fills in files the user deleted.
        for directory, only_missing in (
            (i18n_dir(), False), (_embedded_i18n_dir(), True),
        ):
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.toml")):
                code = path.stem
                if code and not (only_missing and code in result):
                    result[code] = self._read_lang_name(path)
        return dict(result)

    def load_language(self, lang: str) -> bool:
        """Load language from ``i18n/{lang}.toml``. Returns True on success.

        Does not affect the fallback dict; on failure current strings are unchanged.
        External ``i18n/`` is preferred; the embedded copy inside the exe is used when
        the external file is missing, unreadable, or malformed.
        """
        for path in self._candidate_paths(f"{lang}.toml"):
            if self._load_toml(path, lang):
                return True
        return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _candidate_paths(filename: str) -> list[Path]:
        """Language file candidates in lookup order: external ``i18n/``, then embedded.

        Both entries coincide when running from source, in which case the path is
        listed once. Callers must try each candidate until one parses - an external
        file that exists but is empty, malformed, or non-UTF-8 must not shadow the
        embedded copy.
        """
        ext = i18n_dir() / filename
        emb = _embedded_i18n_dir() / filename
        return [ext] if emb == ext else [ext, emb]

    @staticmethod
    def _read_lang_name(path: Path) -> str:
        """Extract language display name from the first-line TOML comment.

        Supported formats: ``# language name: English`` or ``# language name:简体中文``.
        """
        try:
            first_line = path.read_text("utf-8").split("\n", 1)[0].strip()
        except (OSError, ValueError):
            return path.stem
        lower = first_line.lower()
        marker = lower.find("language name:")
        if first_line.startswith("#") and marker >= 0:
            name = first_line[marker + len("language name:"):].strip().lstrip(":").strip()
            if name:
                return name
        return path.stem

    @staticmethod
    def _read_strings(path: Path) -> dict[str, str]:
        """Flatten a TOML file; empty when it is unreadable or malformed."""
        try:
            return _I18n._flatten(tomllib.loads(path.read_text("utf-8")))
        except (OSError, ValueError):
            # ValueError covers non-UTF-8 bytes and malformed TOML
            return {}

    def _load_toml(self, path: Path, label: str) -> bool:
        """Load and flatten TOML file into self._strings."""
        strings = self._read_strings(path)
        if not strings:
            return False
        self._lang = label
        self._strings = strings
        return True

    def _load_fallback(self) -> None:
        """Load the English fallback dictionary from the first readable candidate."""
        self._fallback = {}
        for path in self._candidate_paths("en-US.toml"):
            strings = self._read_strings(path)
            if strings:
                self._fallback = strings
                return

    @staticmethod
    def _flatten(data: dict, prefix: str = "") -> dict[str, str]:
        """Recursively flatten nested TOML tables into ``section.key`` flat dict."""
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
    """Get (or create) the ``_I18n`` singleton."""
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = _I18n()
    assert _i18n_instance is not None
    return _i18n_instance


def _system_locale() -> str:
    """OS locale tag (BCP 47 on Windows, LANG-style elsewhere)."""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Control Panel\International",
            ) as key:
                value, _kind = winreg.QueryValueEx(key, "LocaleName")
                if value:
                    return str(value)
        except (ImportError, OSError, ValueError):
            pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "").strip()
        if value and value not in ("C", "POSIX"):
            return value
    # Windows' getlocale() names the language in words ("Chinese (Simplified)_China"),
    # which cannot be matched; getdefaultlocale() still returns the code ("zh_CN").
    get_default = cast(Any, getattr(locale, "getdefaultlocale", None))
    if get_default is not None:
        try:
            name = get_default()[0] or ""
        except (ValueError, OSError):
            name = ""
        if name:
            return name
    try:
        return locale.getlocale()[0] or ""
    except (ValueError, OSError):
        return ""


def match_language(tag: str, available: dict[str, str]) -> str:
    """Available code matching ``tag``; en-US when nothing matches."""
    tag = (tag or "").split(".", 1)[0].split("@", 1)[0].replace("_", "-").strip().lower()
    if not tag:
        return "en-US"
    for code in available:
        if code.lower() == tag:
            return code
    parts = tag.split("-")
    if len(parts) > 1:
        region = parts[-1]
        for code in available:
            if code.lower().endswith("-" + region):
                return code
    for code in available:
        if code.lower().split("-", 1)[0] == parts[0]:
            return code
    return "en-US"


def system_language() -> str:
    """Best installed language for the OS locale; en-US when none matches."""
    return match_language(_system_locale(), get_i18n().available_languages())


def toml_key(name: str) -> str:
    """Normalize a runtime identifier into a TOML key segment.

    TOML bare keys cannot contain ``+``, so it is spelled ``_plus_``
    (``VDC+VAC`` → ``VDC_plus_VAC``). Every dynamic ``t(f"...")`` lookup goes
    through this helper, so the escaping rule lives in exactly one place.
    """
    return name.replace("+", "_plus_")


def t(key: str, **fmt_kwargs: Any) -> str:
    """Shortcut: return translation. Same as ``get_i18n().t(key, ...)``."""
    return get_i18n().t(key, **fmt_kwargs)
