from __future__ import annotations

import unicodedata


class ApproxMinecraftFontMetrics:
    """Minecraft Fontの完全再現ではなく、レイアウト監査用の概算幅。"""

    height = 9

    def char_width(self, ch: str) -> int:
        if ch == " ":
            return 4
        if ch in ".,:;!'|iIl":
            return 2
        if ch in "[](){}":
            return 4
        if ch in "0123456789":
            return 6
        if ord(ch) < 128:
            return 6

        east = unicodedata.east_asian_width(ch)
        if east in {"W", "F"}:
            return 9
        return 7

    def width(self, text: str) -> int:
        return sum(self.char_width(ch) for ch in text)
