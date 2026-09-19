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


def _rect_spec(value: Any, *, path: str) -> dict[str, float]:
    """Normalize a rectangle constraint from mapping or [x, y, w, h]."""
    if isinstance(value, (list, tuple)):
        if len(value) != 4:
            raise ValueError(f"{path} must contain exactly [x, y, w, h]")
        x, y, w, h = value
        return {"x": _number(x), "y": _number(y), "w": _number(w), "h": _number(h)}
    if isinstance(value, dict):
        return {
            "x": _number(value.get("x", 0)),
            "y": _number(value.get("y", 0)),
            "w": _number(value.get("w", 0)),
            "h": _number(value.get("h", 0)),
        }
    raise TypeError(f"{path} must be a mapping or [x, y, w, h]")


def parse_elements(doc: dict[str, Any]) -> list[Element]:
    """Parse GUI elements and attach optional overlay-only layout hints.

    Auxiliary configuration is deliberately kept outside the extracted
    ``elements`` list so an overlay can patch one element without replacing the
    entire Java-extracted list::

        screen_scale: 0.9
        element_overrides:
          text_1:
            scale: 0.8
        constraints:
          text_1:
            inside: [80, 18, 88, 10]
            align: center
          start_button:
            below: progress
            gap: 4

    Legacy ``text_regions`` remains supported and is normalized into the same
    constraint representation. Constraint coordinates are GUI-local coordinates
    before ``screen_scale`` is applied.
    """
    elements: list[Element] = []
    overrides = doc.get("element_overrides", {}) or {}
    text_regions = doc.get("text_regions", {}) or {}
    constraints = doc.get("constraints", {}) or {}
    if not isinstance(constraints, dict):
        raise TypeError("constraints must be a mapping")
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

        # v0.1.5 compatibility: text_regions is the text-only predecessor of
        # generic layout constraints. Explicit constraints take precedence.
        normalized_constraint: dict[str, Any] = {}
        region = text_regions.get(element_id)
        if region is not None:
            if not isinstance(region, dict):
                raise TypeError(f"text_regions.{element_id} must be a mapping")
            normalized_constraint["inside"] = _rect_spec(
                region, path=f"text_regions.{element_id}"
            )
            normalized_constraint["legacy_text_region"] = True
            if "align" in region:
                normalized_constraint["align"] = str(region["align"])

        constraint = constraints.get(element_id)
        if constraint is not None:
            if not isinstance(constraint, dict):
                raise TypeError(f"constraints.{element_id} must be a mapping")
            if "inside" in constraint:
                normalized_constraint["inside"] = _rect_spec(
                    constraint["inside"], path=f"constraints.{element_id}.inside"
                )
                normalized_constraint["legacy_text_region"] = False
            for key in ("align", "right_of", "below", "left_of", "above"):
                if key in constraint:
                    normalized_constraint[key] = str(constraint[key])
            if "gap" in constraint:
                normalized_constraint["gap"] = _number(constraint["gap"])

        if normalized_constraint:
            data["layout_constraint"] = normalized_constraint
            # For text, alignment also describes how x is interpreted as a text
            # anchor (matching drawCenteredString-style layouts).
            if raw.get("type") == "text" and "align" in normalized_constraint:
                data["align"] = normalized_constraint["align"]
            # Keep the old internal key for callers that inspect it directly.
            if normalized_constraint.get("legacy_text_region") and "inside" in normalized_constraint:
                data["expected_region"] = normalized_constraint["inside"]

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
