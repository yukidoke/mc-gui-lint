from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
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
        # Layout transforms can introduce harmless binary floating-point noise
        # (for example 24 * 0.8). Do not turn that into a clipping error.
        eps = 1e-9
        return (
            other.x >= self.x - eps
            and other.y >= self.y - eps
            and other.right <= self.right + eps
            and other.bottom <= self.bottom + eps
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
    x: float
    y: float
    w: float = 0.0
    h: float = 0.0
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
