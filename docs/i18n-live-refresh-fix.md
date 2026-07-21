# i18n Live Refresh Fix — Analysis & Solution

## Problem Description

After switching language, the following two UI texts do not update in real-time:

| # | Location | Issue |
|---|------|------|
| 1 | Settings screen title | Title stays in the old language after language switch |
| 2 | Main screen REL button | REL text remains in old language after returning from settings |

---

## Root Cause Analysis

### Call Chain Overview

```
User taps language option
  → SettingsScreen._select_language()          # gui/settings_screen.py:178
    → DM40App.reload_language()                # gui/app_window.py:122
      → get_i18n().load_language()             # loads new language TOML
      → save_settings()                        # persists `language` field
      → self.root.title(t("app.title"))        # window title refreshes ✓ (app_window.py:133)
      → self._refresh_visible_screen()         # app_window.py:138
        → settings_screen.rebuild()            # only rebuilds settings_row tagged elements (settings_screen.py:76)
    → self.rebuild()                           # redundant second rebuild() (settings_screen.py:184)
```

### Issue #1: Settings Screen Title

**Location**: `gui/settings_screen.py`

**Root Cause**: The title is created in `_draw_top_bar()` (lines 45-53) with `tags="settings_chrome"`, but `rebuild()` (lines 76-81) only deletes elements tagged `settings_row`. The title text is never updated.

```python
# settings_screen.py:45-53  _draw_top_bar()
self._title_id = self.canvas.create_text(
    ..., text=t("settings.title"), ...,
    tags="settings_chrome",           # ← title tag
)

# settings_screen.py:76-81  rebuild()
def rebuild(self) -> None:
    self._close_lang_popup()
    self.canvas.delete("settings_row")  # ← only deletes settings_row, not settings_chrome
```

**Conclusion**: The title is tagged `settings_chrome` while `rebuild()` only operates on `settings_row`. The title is never updated after initialization.

### Issue #2: Main Screen REL Button

**Location**: `gui/app_window.py:138-147` + `gui/graph_panel.py:261-265`

**Root Cause**: `_refresh_visible_screen()` (line 138) only refreshes the currently visible screen. When switching language from the settings screen, the current screen is `"settings"` (line 145), so only `settings_screen.rebuild()` is called. `main_screen.refresh_all()` never executes.

When returning to the main screen, `show_main_screen()` (lines 285-296) does not detect the language change or trigger a refresh.

```python
# app_window.py:138-147  _refresh_visible_screen()
def _refresh_visible_screen(self) -> None:
    if self._current_screen == "main":
        self.main_screen.refresh_all()         # would call _graph.refresh_rel_text()
    elif self._current_screen == "settings":
        self.settings_screen.rebuild()         # ← only refreshes settings, main skipped

# app_window.py:285-296  show_main_screen()
def show_main_screen(self) -> None:
    self._current_screen = "main"
    ...
    self.apply_settings()                      # no text refresh
    self.main_screen.raise_click_layer()       # no text refresh
```

Although `GraphPanel.refresh_rel_text()` (`graph_panel.py:261-265`) is correctly implemented, it is only called from `MainScreen.refresh_all()`, which never fires during language switch.

**Conclusion**: `show_main_screen()` lacks the "detect language change → trigger text refresh" logic.

---

## Fix

### Fix A: Settings Screen Title

**File**: `gui/settings_screen.py:76-81`

```python
def rebuild(self) -> None:
    self._close_lang_popup()
    # Refresh title text (tagged settings_chrome, needs separate update)
    if self._title_id is not None:
        self.canvas.itemconfig(self._title_id, text=t("settings.title"))
    self.canvas.delete("settings_row")
    ...
```

### Fix B: Main Screen REL Button

**File**: `gui/app_window.py`

Introduce a `_pending_lang_refresh` flag:

```python
# __init__ (line 71)
self._pending_lang_refresh = False

# reload_language() (line 135)
self._pending_lang_refresh = True

# show_main_screen() (lines 293-295)
if self._pending_lang_refresh:
    self.main_screen.refresh_all()
    self._pending_lang_refresh = False
```