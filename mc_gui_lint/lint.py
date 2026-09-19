from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .model import Element, LintIssue, MenuSlot, Rect, Screen
from .resolve import render_text
from .text_metrics import ApproxMinecraftFontMetrics


@dataclass
class ResolvedElement:
    element: Element
    rect: Rect
    kind: str
    text: str | None = None
    scale_x: float = 1.0
    scale_y: float = 1.0


def _pose_values(element: Element) -> tuple[float, float, float, float]:
    pose = element.data.get("pose_transform") or {}
    return (
        float(pose.get("scale_x", 1.0)),
        float(pose.get("scale_y", 1.0)),
        float(pose.get("translate_x", 0.0)),
        float(pose.get("translate_y", 0.0)),
    )


def _screen_scale(element: Element) -> float:
    return float(element.data.get("screen_scale", 1.0) or 1.0)


def _element_scale(element: Element) -> float:
    return float(element.data.get("scale", 1.0) or 1.0)


def _transform_point(element: Element, x: float, y: float) -> tuple[float, float]:
    sx, sy, tx, ty = _pose_values(element)
    element_scale = _element_scale(element)
    screen_scale = _screen_scale(element)
    # Overlay ``scale`` is a fallback for an otherwise-unseen PoseStack.scale
    # (for example a helper/lambda wrapper), so it scales both coordinates and
    # extents about the GUI origin just like a direct scale() call would.
    return (
        (x * sx + tx) * element_scale * screen_scale,
        (y * sy + ty) * element_scale * screen_scale,
    )


def _transform_rect(element: Element, rect: Rect) -> Rect:
    x1, y1 = _transform_point(element, rect.x, rect.y)
    x2, y2 = _transform_point(element, rect.right, rect.bottom)
    x = min(x1, x2)
    y = min(y1, y2)
    w = abs(x2 - x1)
    h = abs(y2 - y1)

    return Rect(x, y, w, h)


def layout_constraint(element: Element) -> dict[str, Any]:
    value = element.data.get("layout_constraint")
    return value if isinstance(value, dict) else {}


def expected_constraint_region(element: Element) -> Rect | None:
    constraint = layout_constraint(element)
    region = constraint.get("inside")
    if not isinstance(region, dict):
        # Compatibility with v0.1.5 callers/config parsing.
        region = element.data.get("expected_region")
    if not isinstance(region, dict):
        return None
    scale = _screen_scale(element)
    return Rect(
        float(region.get("x", 0.0)) * scale,
        float(region.get("y", 0.0)) * scale,
        float(region.get("w", 0.0)) * scale,
        float(region.get("h", 0.0)) * scale,
    )


def expected_text_region(element: Element) -> Rect | None:
    """Backward-compatible alias for the v0.1.5 text-only helper."""
    return expected_constraint_region(element)


def _alignment_error(rect: Rect, region: Rect, align: str) -> float | None:
    align = align.lower()
    if align == "left":
        return rect.x - region.x
    if align == "center":
        return (rect.x + rect.w / 2.0) - (region.x + region.w / 2.0)
    if align == "right":
        return rect.right - region.right
    return None


def resolve_elements(
    elements: list[Element],
    state: dict[str, Any],
    widgets: dict[str, Any],
    metrics: ApproxMinecraftFontMetrics,
) -> list[ResolvedElement]:
    result: list[ResolvedElement] = []

    for e in elements:
        pose_sx, pose_sy, _, _ = _pose_values(e)
        screen_scale = _screen_scale(e)
        element_scale = _element_scale(e)

        if e.type == "text":
            text = render_text(str(e.data.get("text", "")), state)
            scale_x = abs(pose_sx) * element_scale * screen_scale
            scale_y = abs(pose_sy) * element_scale * screen_scale
            w = metrics.width(text) * scale_x
            h = metrics.height * scale_y
            anchor_x, anchor_y = _transform_point(e, e.x, e.y)
            align = str(e.data.get("align", "left")).lower()
            if align == "center":
                x = anchor_x - w / 2.0
            elif align == "right":
                x = anchor_x - w
            else:
                x = anchor_x
            result.append(
                ResolvedElement(e, Rect(x, anchor_y, w, h), "text", text, scale_x, scale_y)
            )
        else:
            rect = _transform_rect(e, e.local_rect())
            result.append(
                ResolvedElement(
                    e,
                    rect,
                    e.type,
                    scale_x=abs(pose_sx) * element_scale * screen_scale,
                    scale_y=abs(pose_sy) * element_scale * screen_scale,
                )
            )

    return result



def _source_suffix(*elements: Element) -> str:
    parts = []
    for e in elements:
        line = e.data.get("source_line")
        if line is not None:
            parts.append(f"{e.id}:line {line}")
    return ("; source " + ", ".join(parts)) if parts else ""

def lint_layout(
    screen: Screen,
    elements: list[Element],
    menu_slots: list[MenuSlot],
    state: dict[str, Any],
    widgets: dict[str, Any],
) -> list[LintIssue]:
    issues: list[LintIssue] = []
    metrics = ApproxMinecraftFontMetrics()
    resolved = resolve_elements(elements, state, widgets, metrics)
    image = Rect(0, 0, screen.image_width, screen.image_height)

    by_id = {r.element.id: r for r in resolved}

    # GUI領域外
    for r in resolved:
        if not image.contains(r.rect):
            code = "TEXT_RIGHT_CLIPPED" if r.kind == "text" and r.rect.right > image.right else "OUT_OF_GUI_BOUNDS"
            issues.append(
                LintIssue(
                    "ERROR",
                    code,
                    f"{r.kind} bounds={r.rect} is outside image={image}" + _source_suffix(r.element),
                    (r.element.id,),
                )
            )

    # Explicit containment/alignment constraints from overlay/config.
    for r in resolved:
        constraint = layout_constraint(r.element)
        expected = expected_constraint_region(r.element)
        if expected is None:
            continue
        if not expected.contains(r.rect):
            legacy_text = bool(constraint.get("legacy_text_region")) and r.kind == "text"
            code = "TEXT_REGION_OVERFLOW" if legacy_text else "ELEMENT_OUT_OF_REGION"
            label = f"text {r.text!r}" if r.kind == "text" else r.kind
            issues.append(
                LintIssue(
                    "ERROR",
                    code,
                    f"{label} bounds={r.rect} does not fit expected region={expected}"
                    + _source_suffix(r.element),
                    (r.element.id,),
                )
            )

        align = constraint.get("align")
        if align is not None:
            delta = _alignment_error(r.rect, expected, str(align))
            if delta is None:
                issues.append(
                    LintIssue(
                        "ERROR",
                        "UNKNOWN_ALIGNMENT",
                        f"unsupported alignment {align!r}; expected left, center, or right"
                        + _source_suffix(r.element),
                        (r.element.id,),
                    )
                )
            elif abs(delta) > 1e-9:
                issues.append(
                    LintIssue(
                        "ERROR",
                        "ELEMENT_ALIGNMENT_MISMATCH",
                        f"{r.kind} bounds={r.rect} is not {str(align).lower()} aligned "
                        f"within region={expected} (delta={delta:g}px)"
                        + _source_suffix(r.element),
                        (r.element.id,),
                    )
                )

    # Relative layout constraints. A gap is a minimum spacing in GUI-local
    # pixels. Negative actual gaps naturally report overlaps as GAP_TOO_SMALL.
    for r in resolved:
        constraint = layout_constraint(r.element)
        if not constraint:
            continue
        required_gap = float(constraint.get("gap", 0.0)) * _screen_scale(r.element)
        relations = (
            ("right_of", lambda a, b: a.rect.x - b.rect.right, "horizontal"),
            ("left_of", lambda a, b: b.rect.x - a.rect.right, "horizontal"),
            ("below", lambda a, b: a.rect.y - b.rect.bottom, "vertical"),
            ("above", lambda a, b: b.rect.y - a.rect.bottom, "vertical"),
        )
        for key, measure, axis in relations:
            target_id = constraint.get(key)
            if target_id is None:
                continue
            target = by_id.get(str(target_id))
            if target is None:
                issues.append(
                    LintIssue(
                        "ERROR",
                        "CONSTRAINT_TARGET_NOT_FOUND",
                        f"{key} references unknown element {target_id!r}"
                        + _source_suffix(r.element),
                        (r.element.id, str(target_id)),
                    )
                )
                continue
            actual_gap = float(measure(r, target))
            if actual_gap + 1e-9 < required_gap:
                issues.append(
                    LintIssue(
                        "ERROR",
                        "GAP_TOO_SMALL",
                        f"{r.element.id} must be {key} {target.element.id} with gap>={required_gap:g}px; "
                        f"actual {axis} gap={actual_gap:g}px"
                        + _source_suffix(r.element, target.element),
                        (r.element.id, target.element.id),
                    )
                )

    # Menu slot領域外・slot同士
    for slot in menu_slots:
        rect = slot.local_rect()
        if not image.contains(rect):
            issues.append(
                LintIssue(
                    "ERROR",
                    "SLOT_OUTSIDE_IMAGE",
                    f"menu slot #{slot.index} ({slot.name}) bounds={rect} is outside image={image}",
                    (f"menu:{slot.name}",),
                )
            )

    for i, a in enumerate(menu_slots):
        for b in menu_slots[i + 1:]:
            if a.local_rect().intersects(b.local_rect()):
                issues.append(
                    LintIssue(
                        "ERROR",
                        "SLOT_OVERLAP",
                        f"slot #{a.index} {a.local_rect()} overlaps slot #{b.index} {b.local_rect()}",
                        (f"menu:{a.name}", f"menu:{b.name}"),
                    )
                )

    # Screen枠 vs Menu実slot
    slots_by_index = {s.index: s for s in menu_slots}
    matched_slot_frames: set[str] = set()
    mismatched_slot_frames: set[str] = set()

    for r in resolved:
        if r.kind != "slot_frame":
            continue
        slot_index = r.element.data.get("menu_slot")
        if slot_index is None:
            continue
        slot = slots_by_index.get(int(slot_index))
        if slot is None:
            issues.append(
                LintIssue(
                    "ERROR",
                    "SLOT_FRAME_MISSING_MENU_SLOT",
                    f"slot frame references missing Menu slot #{slot_index}",
                    (r.element.id,),
                )
            )
            mismatched_slot_frames.add(r.element.id)
            continue

        inset = r.element.data.get("expected_inset", {"x": 1, "y": 1})
        inset_x = int(inset.get("x", 1))
        inset_y = int(inset.get("y", 1))
        expected = Rect(
            r.rect.x + inset_x,
            r.rect.y + inset_y,
            r.rect.w - 2 * inset_x,
            r.rect.h - 2 * inset_y,
        )
        actual = slot.local_rect()

        if expected != actual:
            issues.append(
                LintIssue(
                    "ERROR",
                    "SLOT_FRAME_MISMATCH",
                    f"frame={r.rect}, expected menu slot={expected}, actual menu slot={actual}" + _source_suffix(r.element),
                    (r.element.id, f"menu:{slot.name}"),
                )
            )
            mismatched_slot_frames.add(r.element.id)
        else:
            matched_slot_frames.add(r.element.id)

    # Button label width. Minecraft can scroll long button labels, so this is
    # a layout/UX warning rather than a hard rendering error.
    for r in resolved:
        if r.kind != "button":
            continue
        label = render_text(str(r.element.data.get("text", "")), state)
        label_width = metrics.width(label)
        available = max(0, r.rect.w - 6)
        if label_width > available:
            issues.append(
                LintIssue(
                    "WARNING",
                    "BUTTON_TEXT_OVERFLOW",
                    f"button text {label!r} width={label_width}px exceeds available={available}px in bounds={r.rect}" + _source_suffix(r.element),
                    (r.element.id,),
                )
            )

    # Button click bounds
    for r in resolved:
        if r.kind != "button":
            continue
        click = r.element.data.get("click_bounds")
        if click is None:
            continue
        click_rect = Rect(
            int(click.get("x", r.rect.x)),
            int(click.get("y", r.rect.y)),
            int(click.get("w", r.rect.w)),
            int(click.get("h", r.rect.h)),
        )
        if click_rect != r.rect:
            issues.append(
                LintIssue(
                    "ERROR",
                    "CLICK_RENDER_MISMATCH",
                    f"render bounds={r.rect}, click bounds={click_rect}" + _source_suffix(r.element),
                    (r.element.id,),
                )
            )

    # 意味のある組み合わせだけ衝突判定
    collision_kinds = {
        frozenset(("text", "slot_frame")): "TEXT_SLOT_OVERLAP",
        frozenset(("text", "button")): "TEXT_BUTTON_OVERLAP",
        frozenset(("text", "progress")): "TEXT_PROGRESS_OVERLAP",
        frozenset(("button", "slot_frame")): "BUTTON_SLOT_OVERLAP",
    }

    colliding_ids: set[str] = set()
    for i, a in enumerate(resolved):
        for b in resolved[i + 1:]:
            code = collision_kinds.get(frozenset((a.kind, b.kind)))
            if code is None:
                continue
            if a.rect.intersects(b.rect):
                issues.append(
                    LintIssue(
                        "ERROR",
                        code,
                        f"{a.kind} {a.rect} overlaps {b.kind} {b.rect}" + _source_suffix(a.element, b.element),
                        (a.element.id, b.element.id),
                    )
                )
                colliding_ids.update((a.element.id, b.element.id))
            elif a.rect.touches(b.rect):
                issues.append(
                    LintIssue(
                        "WARNING",
                        "ELEMENT_TOUCHING",
                        f"{a.kind} {a.rect} touches {b.kind} {b.rect} with 0px spacing" + _source_suffix(a.element, b.element),
                        (a.element.id, b.element.id),
                    )
                )
                colliding_ids.update((a.element.id, b.element.id))

    return issues
