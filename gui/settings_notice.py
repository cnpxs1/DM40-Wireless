"""Format settings.json issues for the startup prompt, free of Tk."""

from __future__ import annotations

import json
from typing import Any

from core.i18n import t
from gui.settings import (
    ISSUE_FILE,
    ISSUE_INVALID,
    ISSUE_LEGACY_DROPPED,
    ISSUE_LEGACY_MOVED,
    ISSUE_MISSING,
    ISSUE_UNKNOWN_LANGUAGE,
    SettingsIssue,
)

_MAX_INVALID_LINES = 8
_MAX_MISSING_KEYS = 6
_MAX_VALUE_CHARS = 60
_MAX_ERROR_CHARS = 160


def _clip(text: str, limit: int) -> str:
    """Single-line, length-limited text for a non-scrolling messagebox."""
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[:limit - 1] + "…"
    return text


def _display(value: Any) -> str:
    """JSON spelling of a value, so "" and "false" stay distinguishable."""
    try:
        text = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(value)
    return _clip(text, _MAX_VALUE_CHARS)


def format_settings_issues(issues: list[SettingsIssue]) -> str:
    """Message text listing every problem; empty string when there is none."""
    if not issues:
        return ""

    missing = [issue for issue in issues if issue.kind == ISSUE_MISSING]
    invalid = [issue for issue in issues if issue.kind == ISSUE_INVALID]
    others = [
        issue for issue in issues
        if issue.kind not in (ISSUE_MISSING, ISSUE_INVALID)
    ]

    lines: list[str] = []

    if missing:
        keys = ", ".join(issue.key for issue in missing[:_MAX_MISSING_KEYS])
        extra = len(missing) - _MAX_MISSING_KEYS
        if extra > 0:
            keys += " " + t("config.more", count=extra)
        lines.append(t("config.missing", count=len(missing), keys=keys))

    for issue in invalid[:_MAX_INVALID_LINES]:
        lines.append(t("config.invalid",
                       name=issue.key,
                       value=_display(issue.value),
                       default=_display(issue.default)))
    extra = len(invalid) - _MAX_INVALID_LINES
    if extra > 0:
        lines.append(t("config.more", count=extra))

    for issue in others:
        if issue.kind == ISSUE_LEGACY_MOVED:
            lines.append(t("config.legacy_moved",
                           name=issue.key,
                           new_key=str(issue.value)))
        elif issue.kind == ISSUE_LEGACY_DROPPED:
            lines.append(t("config.legacy_dropped", name=issue.key))
        elif issue.kind == ISSUE_FILE:
            lines.append(t("config.file_problem",
                           error=_clip(issue.error, _MAX_ERROR_CHARS)))
        elif issue.kind == ISSUE_UNKNOWN_LANGUAGE:
            lines.append(t("config.unknown_language",
                           value=_display(issue.value),
                           default=_display(issue.default)))

    return t("config.intro") + "\n\n" + "\n".join(lines)
