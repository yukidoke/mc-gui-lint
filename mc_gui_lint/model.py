from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    def intersects(self, other: "Rect") -> bool:
        return (
            self.x < other.right
            and self.right > other.x
            and self.y < other.bottom
            and self.bottom > other.y
        )

    def touches(self, other: "Rect") -> bool:
        horizontal_touch = (
            (self.right == other.x or other.right == self.x)
            and self.y < other.bottom
            and self.bottom > other.y
        )
        vertical_touch = (
            (self.bottom == other.y or other.bottom == self.y)
            and self.x < other.right
            and self.right > other.x
        )
        return horizontal_touch or vertical_touch

    def contains(self, other: "Rect") -> bool:
        return (
            other.x >= self.x
            and other.y >= self.y
            and other.right <= self.right
            and other.bottom <= self.bottom
        )


@dataclass
class Viewport:
    physical_width: int
    physical_height: int
    gui_scale: int

    @property
    def logical_width(self) -> int:
        return (self.physical_width + self.gui_scale - 1) // self.gui_scale

    @property
    def logical_height(self) -> int:
        return (self.physical_height + self.gui_scale - 1) // self.gui_scale


@dataclass
class Screen:
    image_width: int
    image_height: int

    def left_pos(self, viewport: Viewport) -> int:
        return (viewport.logical_width - self.image_width) // 2

    def top_pos(self, viewport: Viewport) -> int:
        return (viewport.logical_height - self.image_height) // 2


@dataclass
class Element:
    type: str
    id: str
    x: int
    y: int
    w: int = 0
    h: int = 0
    data: dict[str, Any] = field(default_factory=dict)

    def local_rect(self) -> Rect:
        return Rect(self.x, self.y, self.w, self.h)


@dataclass
class MenuSlot:
    index: int
    name: str
    x: int
    y: int
    w: int = 16
    h: int = 16

    def local_rect(self) -> Rect:
        return Rect(self.x, self.y, self.w, self.h)


@dataclass
class LintIssue:
    severity: str
    code: str
    message: str
    element_ids: tuple[str, ...] = ()

    def format(self, number: int) -> str:
        ids = f" [{', '.join(self.element_ids)}]" if self.element_ids else ""
        return f"GUI-{number:03d} {self.severity} {self.code}{ids}\n  {self.message}"
