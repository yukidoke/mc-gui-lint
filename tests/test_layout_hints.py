import unittest

from mc_gui_lint.config import parse_elements
from mc_gui_lint.lint import lint_layout, resolve_elements
from mc_gui_lint.model import Screen
from mc_gui_lint.text_metrics import ApproxMinecraftFontMetrics


class LayoutHintsTest(unittest.TestCase):
    def test_centered_text_region_with_element_and_screen_scale(self):
        doc = {
            "screen_scale": 0.5,
            "elements": [
                {"type": "text", "id": "title", "x": 50, "y": 10, "text": "abcd"}
            ],
            "element_overrides": {"title": {"scale": 0.5}},
            "text_regions": {
                "title": {"x": 18, "y": 4, "w": 14, "h": 8, "align": "center"}
            },
        }
        elements = parse_elements(doc)
        resolved = resolve_elements(elements, {}, {}, ApproxMinecraftFontMetrics())

        self.assertEqual(len(resolved), 1)
        text = resolved[0]
        self.assertAlmostEqual(text.rect.x, 9.5)
        self.assertAlmostEqual(text.rect.y, 2.5)
        self.assertAlmostEqual(text.rect.w, 6.0)
        self.assertAlmostEqual(text.rect.h, 2.25)

        issues = lint_layout(Screen(100, 50), elements, [], {}, {})
        self.assertFalse(any(i.code == "TEXT_REGION_OVERFLOW" for i in issues), issues)

    def test_text_region_overflow_is_error(self):
        doc = {
            "elements": [
                {"type": "text", "id": "label", "x": 10, "y": 5, "text": "abcdef"}
            ],
            "text_regions": {
                "label": {"x": 10, "y": 5, "w": 20, "h": 9}
            },
        }
        issues = lint_layout(Screen(100, 50), parse_elements(doc), [], {}, {})
        self.assertTrue(any(i.code == "TEXT_REGION_OVERFLOW" for i in issues), issues)

    def test_screen_and_element_scale_both_scale_coordinates(self):
        doc = {
            "screen_scale": 0.5,
            "elements": [
                {"type": "fill", "id": "box", "x": 20, "y": 10, "w": 40, "h": 20}
            ],
            "element_overrides": {"box": {"scale": 0.5}},
        }
        resolved = resolve_elements(
            parse_elements(doc), {}, {}, ApproxMinecraftFontMetrics()
        )[0]
        self.assertAlmostEqual(resolved.rect.x, 5.0)
        self.assertAlmostEqual(resolved.rect.y, 2.5)
        self.assertAlmostEqual(resolved.rect.w, 10.0)
        self.assertAlmostEqual(resolved.rect.h, 5.0)

    def test_float_rounding_at_region_edge_does_not_overflow(self):
        doc = {
            "elements": [
                {"type": "text", "id": "label", "x": 0, "y": 0, "text": "abcd"}
            ],
            "element_overrides": {"label": {"scale": 0.8}},
            "text_regions": {
                "label": {"x": 0, "y": 0, "w": 19.2, "h": 7.2}
            },
        }
        issues = lint_layout(Screen(100, 50), parse_elements(doc), [], {}, {})
        self.assertFalse(any(i.code == "TEXT_REGION_OVERFLOW" for i in issues), issues)


if __name__ == "__main__":
    unittest.main()
