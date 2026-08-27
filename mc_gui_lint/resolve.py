from __future__ import annotations

from typing import Any


class SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render_text(template: str, state: dict[str, Any]) -> str:
    return template.format_map(SafeFormatDict(state))


def state_value(value: Any, state: dict[str, Any], default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        if value.startswith("state."):
            return float(state.get(value[6:], default))
        try:
            return float(value)
        except ValueError:
            return default
    return default
