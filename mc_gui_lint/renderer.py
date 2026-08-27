from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .lint import resolve_elements
from .model import Element, LintIssue, MenuSlot, Rect, Screen, Viewport
from .resolve import render_text, state_value
from .text_metrics import ApproxMinecraftFontMetrics


def _font_path() -> str | None:
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/YuGothR.ttc",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _load_font(size: int = 9) -> ImageFont.ImageFont:
    path = _font_path()
    if path:
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _local_to_screen(rect: Rect, left: int, top: int) -> Rect:
    return Rect(rect.x + left, rect.y + top, rect.w, rect.h)


def _draw_rect(draw: ImageDraw.ImageDraw, rect: Rect, *, outline, width=1, fill=None):
    draw.rectangle(
        [rect.x, rect.y, rect.right - 1, rect.bottom - 1],
        outline=outline,
        width=width,
        fill=fill,
    )


def render(
    screen: Screen,
    viewport: Viewport,
    elements: list[Element],
    menu_slots: list[MenuSlot],
    state: dict[str, Any],
    slot_state: dict[str, Any],
    widgets: dict[str, Any],
    issues: list[LintIssue],
    output: Path,
    *,
    debug: bool,
) -> None:
    logical_w = viewport.logical_width
    logical_h = viewport.logical_height

    image = Image.new("RGBA", (logical_w, logical_h), (32, 32, 32, 255))
    draw = ImageDraw.Draw(image)
    font = _load_font(9)
    font_small = _load_font(7)

    left = screen.left_pos(viewport)
    top = screen.top_pos(viewport)
    gui_rect = Rect(left, top, screen.image_width, screen.image_height)

    # GUI background placeholder
    _draw_rect(draw, gui_rect, outline=(145, 145, 145, 255), fill=(198, 198, 198, 255))

    metrics = ApproxMinecraftFontMetrics()
    resolved = resolve_elements(elements, state, widgets, metrics)
    by_id = {r.element.id: r for r in resolved}

    # Actual GUI elements
    for r in resolved:
        e = r.element
        rect = _local_to_screen(r.rect, left, top)

        if e.type == "fill":
            color = tuple(e.data.get("color", [90, 90, 90, 255]))
            _draw_rect(draw, rect, outline=color, fill=color)

        elif e.type == "blit":
            # Destination placeholder only. Texture atlas/sampling is outside MVP scope.
            _draw_rect(draw, rect, outline=(95, 95, 110, 255), fill=(180, 180, 190, 255))

        elif e.type == "text":
            text = r.text or ""
            tx = rect.x
            if e.data.get("align") == "center":
                tx = rect.x - max(0, r.rect.w // 2)
            color = tuple(e.data.get("color", [30, 30, 30, 255]))
            draw.text((tx, rect.y - 1), text, fill=color, font=font)

        elif e.type == "slot_frame":
            _draw_rect(draw, rect, outline=(80, 80, 80, 255), fill=(150, 150, 150, 255))
            inner = Rect(rect.x + 1, rect.y + 1, max(1, rect.w - 2), max(1, rect.h - 2))
            _draw_rect(draw, inner, outline=(215, 215, 215, 255), fill=(105, 105, 105, 255))

        elif e.type == "button":
            wstate = widgets.get(e.id, {})
            if isinstance(wstate, str):
                state_name = wstate
            else:
                state_name = str(wstate.get("state", e.data.get("state", "normal")))

            fill = {
                "normal": (120, 120, 120, 255),
                "hover": (145, 145, 145, 255),
                "pressed": (90, 90, 90, 255),
                "disabled": (80, 80, 80, 255),
            }.get(state_name, (120, 120, 120, 255))
            _draw_rect(draw, rect, outline=(35, 35, 35, 255), fill=fill)
            label = render_text(str(e.data.get("text", "")), state)
            label_width = metrics.width(label)
            tx = rect.x + max(3, (rect.w - label_width) // 2)
            draw.text((tx, rect.y + 4), label, fill=(245, 245, 245, 255), font=font)

        elif e.type == "progress":
            value = state_value(e.data.get("value", 0), state)
            max_value = state_value(e.data.get("max", 1), state, 1)
            ratio = 0 if max_value <= 0 else max(0.0, min(1.0, value / max_value))
            if e.data.get("style") == "fill":
                inner_w = max(0, int(rect.w * ratio))
                if inner_w > 0:
                    inner = Rect(rect.x, rect.y, inner_w, rect.h)
                    color = tuple(e.data.get("color", [135, 80, 160, 255]))
                    _draw_rect(draw, inner, outline=color, fill=color)
            else:
                _draw_rect(draw, rect, outline=(50, 50, 50, 255), fill=(65, 65, 65, 255))
                inner_w = max(0, int((rect.w - 2) * ratio))
                if inner_w > 0:
                    inner = Rect(rect.x + 1, rect.y + 1, inner_w, max(1, rect.h - 2))
                    _draw_rect(draw, inner, outline=(135, 80, 160, 255), fill=(135, 80, 160, 255))

    # Menu slots + fake items
    slot_by_index = {s.index: s for s in menu_slots}
    for slot in menu_slots:
        local = slot.local_rect()
        rect = _local_to_screen(local, left, top)
        if debug:
            _draw_rect(draw, rect, outline=(40, 120, 255, 255), width=1)

        stack = slot_state.get(slot.name, {}) or {}
        item = stack.get("item")
        count = int(stack.get("count", 0) or 0)
        if item or count > 0:
            icon = Rect(rect.x + 1, rect.y + 1, max(1, rect.w - 2), max(1, rect.h - 2))
            _draw_rect(draw, icon, outline=(45, 45, 45, 255), fill=(170, 145, 85, 255))
            token = (str(item).split(":")[-1][:1] if item else "?").upper()
            draw.text((icon.x + 4, icon.y + 1), token, fill=(20, 20, 20, 255), font=font)
            if count > 1:
                label = str(count)
                draw.text((icon.right - 3 * len(label), icon.bottom - 7), label, fill=(255, 255, 255, 255), font=font_small)

    if debug:
        issue_ids = {eid for issue in issues for eid in issue.element_ids}

        # Slot frame match/mismatch overlay
        for r in resolved:
            if r.kind != "slot_frame":
                continue
            frame = _local_to_screen(r.rect, left, top)
            idx = r.element.data.get("menu_slot")
            if idx is None:
                continue
            slot = slot_by_index.get(int(idx))
            if slot is None:
                _draw_rect(draw, frame, outline=(255, 60, 60, 255), width=2)
                continue
            inset = r.element.data.get("expected_inset", {"x": 1, "y": 1})
            ix = int(inset.get("x", 1))
            iy = int(inset.get("y", 1))
            expected = Rect(r.rect.x + ix, r.rect.y + iy, r.rect.w - 2 * ix, r.rect.h - 2 * iy)
            color = (45, 210, 80, 255) if expected == slot.local_rect() else (255, 60, 60, 255)
            _draw_rect(draw, frame, outline=color, width=2)

        # Dynamic regions purple, collisions/errors yellow
        for r in resolved:
            rect = _local_to_screen(r.rect, left, top)
            if r.kind == "progress":
                _draw_rect(draw, rect, outline=(190, 80, 220, 255), width=1)
            if r.element.id in issue_ids:
                _draw_rect(draw, rect, outline=(255, 215, 40, 255), width=1)

        # click bounds blue
        for r in resolved:
            if r.kind != "button":
                continue
            click = r.element.data.get("click_bounds")
            if click:
                click_rect = Rect(
                    int(click.get("x", r.rect.x)) + left,
                    int(click.get("y", r.rect.y)) + top,
                    int(click.get("w", r.rect.w)),
                    int(click.get("h", r.rect.h)),
                )
                _draw_rect(draw, click_rect, outline=(40, 120, 255, 255), width=1)

        draw.text(
            (2, 2),
            f"GUI {logical_w}x{logical_h} scale={viewport.gui_scale} left={left} top={top}",
            fill=(255, 255, 255, 255),
            font=font_small,
        )

    # nearest-neighborで物理解像度へ
    final = image.resize(
        (viewport.physical_width, viewport.physical_height),
        resample=Image.Resampling.NEAREST,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    final.convert("RGB").save(output)
