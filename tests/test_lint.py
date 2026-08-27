import unittest

from mc_gui_lint.lint import lint_layout
from mc_gui_lint.model import Element, MenuSlot, Screen


class LintTest(unittest.TestCase):
    def test_slot_frame_match(self):
        screen = Screen(176, 179)
        elements = [
            Element(
                type="slot_frame",
                id="frame",
                x=43,
                y=61,
                w=18,
                h=18,
                data={"menu_slot": 0, "expected_inset": {"x": 1, "y": 1}},
            )
        ]
        slots = [MenuSlot(index=0, name="fuel", x=44, y=62)]
        issues = lint_layout(screen, elements, slots, {}, {})
        self.assertFalse(any(i.code == "SLOT_FRAME_MISMATCH" for i in issues))

    def test_slot_frame_mismatch(self):
        screen = Screen(176, 179)
        elements = [
            Element(
                type="slot_frame",
                id="frame",
                x=43,
                y=61,
                w=18,
                h=18,
                data={"menu_slot": 0},
            )
        ]
        slots = [MenuSlot(index=0, name="fuel", x=46, y=62)]
        issues = lint_layout(screen, elements, slots, {}, {})
        self.assertTrue(any(i.code == "SLOT_FRAME_MISMATCH" for i in issues))

    def test_text_clipping(self):
        screen = Screen(40, 40)
        elements = [
            Element(
                type="text",
                id="text",
                x=30,
                y=2,
                data={"text": "abcdef"},
            )
        ]
        issues = lint_layout(screen, elements, [], {}, {})
        self.assertTrue(any(i.code == "TEXT_RIGHT_CLIPPED" for i in issues))


if __name__ == "__main__":
    unittest.main()
