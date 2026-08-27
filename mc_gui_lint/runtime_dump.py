from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .config import deep_merge


def load_runtime_dump(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def apply_runtime_dump(doc: dict[str, Any], dump: dict[str, Any]) -> dict[str, Any]:
    """Overlay exact runtime values onto statically extracted/configured IR.

    Runtime data intentionally wins for Menu slot coordinates and synchronized state.
    Screen logical dimensions are retained as metadata; image dimensions may override
    the static result when the dump provides them.
    """
    result = deepcopy(doc)

    runtime_screen = dump.get("screen") or {}
    if runtime_screen:
        screen_override: dict[str, Any] = {}
        if "image_width" in runtime_screen:
            screen_override["image_width"] = int(runtime_screen["image_width"])
        if "image_height" in runtime_screen:
            screen_override["image_height"] = int(runtime_screen["image_height"])
        if screen_override:
            result["screen"] = deep_merge(result.get("screen", {}), screen_override)

    if "menu_slots" in dump:
        result["menu_slots"] = deepcopy(dump.get("menu_slots") or [])

    if "state" in dump:
        result["state"] = deep_merge(result.get("state", {}), dump.get("state") or {})

    if "slots" in dump:
        result["slots"] = deep_merge(result.get("slots", {}), dump.get("slots") or {})

    # If the runtime helper knows physical viewport information, use it.
    runtime_viewport = dump.get("viewport") or {}
    viewport_override: dict[str, Any] = {}
    for key in ("width", "height", "gui_scale"):
        if key in runtime_viewport:
            viewport_override[key] = int(runtime_viewport[key])
    if viewport_override:
        result["viewport"] = deep_merge(result.get("viewport", {}), viewport_override)

    result["_runtime"] = {
        "source": dump.get("source"),
        "screen": runtime_screen,
    }
    return result
