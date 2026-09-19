from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from .model import Element, MenuSlot, Screen, Viewport


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_document(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def resolve_preset(doc: dict[str, Any], preset: str | None) -> dict[str, Any]:
    resolved = deepcopy(doc)
    if preset is None:
        return resolved

    presets = doc.get("presets", {})
    if preset not in presets:
        raise KeyError(f"unknown preset: {preset}")

    p = presets[preset] or {}
    for section in ("state", "slots", "widgets"):
        if section in p:
            resolved[section] = deep_merge(resolved.get(section, {}), p[section])

    return resolved


def parse_viewport(doc: dict[str, Any]) -> Viewport:
    v = doc.get("viewport", {})
    return Viewport(
        physical_width=int(v.get("width", 1920)),
        physical_height=int(v.get("height", 1080)),
        gui_scale=max(1, int(v.get("gui_scale", 3))),
    )


def parse_screen(doc: dict[str, Any]) -> Screen:
    s = doc["screen"]
    return Screen(
        image_width=int(s["image_width"]),
        image_height=int(s["image_height"]),
    )


def _number(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


def parse_elements(doc: dict[str, Any]) -> list[Element]:
    """Parse GUI elements and attach optional overlay-only layout hints.

    Auxiliary configuration is deliberately kept outside the extracted
    ``elements`` list so an overlay can patch one element without replacing the
    entire Java-extracted list::

        screen_scale: 0.9
        element_overrides:
          text_1:
            scale: 0.8
        text_regions:
          text_1:
            x: 80
            y: 18
            w: 88
            h: 10
            align: center

    ``text_regions`` coordinates are GUI-local coordinates before
    ``screen_scale`` is applied.
    """
    elements: list[Element] = []
    overrides = doc.get("element_overrides", {}) or {}
    text_regions = doc.get("text_regions", {}) or {}
    screen_scale = float(doc.get("screen_scale", 1.0) or 1.0)

    for raw in doc.get("elements", []):
        known = {"type", "id", "x", "y", "w", "h"}
        data = {k: v for k, v in raw.items() if k not in known}
        element_id = str(raw["id"])

        override = overrides.get(element_id, {}) or {}
        if "scale" in override:
            data["scale"] = float(override["scale"])
        if "align" in override:
            data["align"] = str(override["align"])

        region = text_regions.get(element_id)
        if region is not None:
            if not isinstance(region, dict):
                raise TypeError(f"text_regions.{element_id} must be a mapping")
            data["expected_region"] = {
                "x": _number(region.get("x", 0)),
                "y": _number(region.get("y", 0)),
                "w": _number(region.get("w", 0)),
                "h": _number(region.get("h", 0)),
            }
            if "align" in region:
                data["align"] = str(region["align"])

        if screen_scale != 1.0:
            data["screen_scale"] = screen_scale

        elements.append(
            Element(
                type=str(raw["type"]),
                id=element_id,
                x=_number(raw.get("x", 0)),
                y=_number(raw.get("y", 0)),
                w=_number(raw.get("w", 0)),
                h=_number(raw.get("h", 0)),
                data=data,
            )
        )
    return elements


def parse_menu_slots(doc: dict[str, Any]) -> list[MenuSlot]:
    result: list[MenuSlot] = []
    for raw in doc.get("menu_slots", []):
        result.append(
            MenuSlot(
                index=int(raw["index"]),
                name=str(raw.get("name", f"slot_{raw['index']}")),
                x=int(raw["x"]),
                y=int(raw["y"]),
                w=int(raw.get("w", 16)),
                h=int(raw.get("h", 16)),
            )
        )
    return result
