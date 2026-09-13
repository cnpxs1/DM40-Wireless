"""MODE button logic (rotation, group memory)."""

import json
import time

from .config import NOTIFY_CONFIRM_WINDOW_S, UI_STATE_PATH
from .controller import COMMANDS, create_command
from .ranges import kind_from_mode_cmd_key

MODE_CYCLE_GROUPS = (
    ("VDC", ("VDC", "VAC", "VDC+VAC")),
    ("ADC", ("ADC", "AAC", "ADC+AAC")),
    ("OHM", ("OHM", "OHM_ONLINE")),
    ("CAP", ("CAP",)),
    ("DIODE", ("DIODE", "CONT")),
    ("Hz", ("HZ", "TEMP")),
)

KIND_TO_CMD = {
    "VDC": "VDC",
    "VAC": "VAC",
    "VDC+AC": "VDC+VAC",
    "ADC": "ADC",
    "AAC": "AAC",
    "ADC+AC": "ADC+AAC",
    "RES": "OHM",
    "RES_ONLINE": "OHM_ONLINE",
    "CAP": "CAP",
    "DIODE": "DIODE",
    "CONT": "CONT",
    "FREQ": "HZ",
    "TEMP": "TEMP",
}

# Inverse of KIND_TO_CMD: a command key traced back to its measurement kind.
# Spelled out separately from core.ranges.kind_from_mode_cmd_key(), which
# covers only the range-capable modes - MODE buttons cover all of them
# (CAP / DIODE / CONT / HZ / TEMP included).
CMD_TO_KIND = {cmd: kind for kind, cmd in KIND_TO_CMD.items()}

# MODE button text-fallback whitelist (see btn_label). Values are unused –
# the actual label always comes from ``mode_btn.*`` in the i18n TOML files.
# Command keys absent here render as the raw key (VDC / VAC / ADC / …).
BTN_LABELS = {
    "HZ": "Hz",
    "OHM_ONLINE": "OHM\nONLINE",
    "VDC+VAC": "VDC+VAC",
    "ADC+AAC": "ADC+AAC",
    "CAP": "CAP",
    "DIODE": "DIODE",
    "CONT": "CONT",
    "TEMP": "TEMP",
}


def btn_label(cmd_key: str) -> str:
    """Return display label for mode button (with i18n fallback).

    The command key is normalized via :func:`core.i18n.toml_key` before the
    lookup (``VDC+VAC`` → ``mode_btn.VDC_plus_VAC``). Returns ``cmd_key`` itself
    for command keys without a translatable label (VDC / VAC / OHM / …).
    """
    from core.i18n import t, toml_key
    if cmd_key not in BTN_LABELS:
        return cmd_key
    return t(f"mode_btn.{toml_key(cmd_key)}")


class ModeState:
    def __init__(self) -> None:
        self.groups: dict[str, dict] = {}
        self.active_group: str | None = None
        self.last_kind: str | None = None
        self._pending_cmd_key: str | None = None
        self._pending_until: float = 0.0

    def register_group(self, group_id: str, options: tuple[str, ...]) -> None:
        self.groups[group_id] = {"options": options, "index": 0}

    def load(self) -> None:
        try:
            data = json.loads(UI_STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for group_id, idx in data.get("mode_index", {}).items():
            group = self.groups.get(group_id)
            if group and isinstance(idx, int) and 0 <= idx < len(group["options"]):
                group["index"] = idx

    def save(self) -> None:
        data = {"mode_index": {gid: g["index"] for gid, g in self.groups.items()}}
        try:
            UI_STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def get_active_kind(self) -> str | None:
        if self.last_kind:
            return self.last_kind
        if not self.active_group:
            return None
        group = self.groups.get(self.active_group)
        if not group:
            return None
        return kind_from_mode_cmd_key(group["options"][group["index"]])

    def current_cmd_key(self, group_id: str) -> str:
        group = self.groups[group_id]
        return group["options"][group["index"]]

    def cycle_group(self, group_id: str) -> bytes:
        group = self.groups[group_id]
        options = group["options"]
        if self.active_group == group_id and len(options) > 1:
            group["index"] = (group["index"] + 1) % len(options)
        self.active_group = group_id
        cmd_key = group["options"][group["index"]]
        self.expect_cmd(cmd_key)
        # Optimistic: last_kind is what get_active_kind() reads first, and
        # _pick_subtype already advances it on a local switch - stay in step.
        kind = CMD_TO_KIND.get(cmd_key)
        if kind:
            self.last_kind = kind
        self.save()
        return create_command(COMMANDS[cmd_key])

    def expect_cmd(self, cmd_key: str) -> None:
        """Declare the mode a locally issued command is switching to.

        Arms the confirmation window for ``NOTIFY_CONFIRM_WINDOW_S``.
        Notifications reporting any *other* mode until then are the device
        echoing the pre-switch mode, and ``sync_from_kind`` drops them.
        """
        self._pending_cmd_key = cmd_key
        self._pending_until = time.monotonic() + NOTIFY_CONFIRM_WINDOW_S

    def _is_stale(self, cmd_key: str) -> bool:
        """True while a notification is just an echo of the pre-switch mode.

        Notifications matching the expected mode pass through without clearing
        the window, so it keeps filtering for its full duration.
        """
        if self._pending_cmd_key is None:
            return False
        if time.monotonic() >= self._pending_until:
            # Device never confirmed. Stop guarding, trust it from here on.
            self._pending_cmd_key = None
            return False
        return cmd_key != self._pending_cmd_key

    def sync_from_kind(self, kind: str) -> bool:
        """Sync MODE state from measurement kind; True = buttons need redraw."""
        cmd_key = KIND_TO_CMD.get(kind)
        if not cmd_key:
            return False
        if self._is_stale(cmd_key):
            return False
        for group_id, group in self.groups.items():
            if cmd_key in group["options"]:
                new_index = group["options"].index(cmd_key)
                changed = self.active_group != group_id or group["index"] != new_index
                group["index"] = new_index
                self.active_group = group_id
                if changed:
                    self.save()
                return changed
        return False

    def apply_notify(self, kind: str) -> bool:
        """Feed the device-reported mode from a BLE notification. True = redraw.

        A stale echo is dropped whole - neither ``last_kind`` nor the active
        group move - so the UI never renders the pre-switch mode, not even for
        the few hundred ms until the device catches up.
        """
        cmd_key = KIND_TO_CMD.get(kind)
        if cmd_key and self._is_stale(cmd_key):
            return False
        self.last_kind = kind
        return self.sync_from_kind(kind)
