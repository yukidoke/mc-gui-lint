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


def resolve_elements(
    elements: list[Element],
    state: dict[str, Any],
    widgets: dict[str, Any],
    metrics: ApproxMinecraftFontMetrics,
) -> list[ResolvedElement]:
    result: list[ResolvedElement] = []

    for e in elements:
        if e.type == "text":
            text = render_text(str(e.data.get("text", "")), state)
            w = metrics.width(text)
            h = metrics.height
            result.append(ResolvedElement(e, Rect(e.x, e.y, w, h), "text", text))
        else:
            result.append(ResolvedElement(e, e.local_rect(), e.type))

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
