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

    def test_generic_inside_constraint_accepts_list_form(self):
        doc = {
            "elements": [
                {"type": "fill", "id": "panel", "x": 10, "y": 8, "w": 20, "h": 10}
            ],
            "constraints": {"panel": {"inside": [8, 6, 30, 20]}},
        }
        issues = lint_layout(Screen(100, 50), parse_elements(doc), [], {}, {})
        self.assertFalse(any(i.code == "ELEMENT_OUT_OF_REGION" for i in issues), issues)

    def test_generic_inside_constraint_reports_overflow(self):
        doc = {
            "elements": [
                {"type": "button", "id": "start", "x": 20, "y": 10, "w": 30, "h": 20, "text": "Start"}
            ],
            "constraints": {
                "start": {"inside": {"x": 20, "y": 10, "w": 25, "h": 20}}
            },
        }
        issues = lint_layout(Screen(100, 50), parse_elements(doc), [], {}, {})
        self.assertTrue(any(i.code == "ELEMENT_OUT_OF_REGION" for i in issues), issues)

    def test_center_alignment_constraint_applies_to_non_text_elements(self):
        good = {
            "elements": [
                {"type": "fill", "id": "box", "x": 40, "y": 5, "w": 20, "h": 10}
            ],
            "constraints": {"box": {"inside": [20, 0, 60, 20], "align": "center"}},
        }
        issues = lint_layout(Screen(100, 50), parse_elements(good), [], {}, {})
        self.assertFalse(any(i.code == "ELEMENT_ALIGNMENT_MISMATCH" for i in issues), issues)

        bad = {
            "elements": [
                {"type": "fill", "id": "box", "x": 35, "y": 5, "w": 20, "h": 10}
            ],
            "constraints": {"box": {"inside": [20, 0, 60, 20], "align": "center"}},
        }
        issues = lint_layout(Screen(100, 50), parse_elements(bad), [], {}, {})
        self.assertTrue(any(i.code == "ELEMENT_ALIGNMENT_MISMATCH" for i in issues), issues)

    def test_right_of_constraint_enforces_minimum_gap(self):
        doc = {
            "elements": [
                {"type": "fill", "id": "icon", "x": 10, "y": 10, "w": 8, "h": 8},
                {"type": "text", "id": "label", "x": 20, "y": 10, "text": "A"},
            ],
            "constraints": {"label": {"right_of": "icon", "gap": 4}},
        }
        issues = lint_layout(Screen(100, 50), parse_elements(doc), [], {}, {})
        gap_issues = [i for i in issues if i.code == "GAP_TOO_SMALL"]
        self.assertEqual(len(gap_issues), 1, issues)
        self.assertEqual(gap_issues[0].element_ids, ("label", "icon"))

    def test_below_constraint_passes_with_exact_gap(self):
        doc = {
            "elements": [
                {"type": "progress", "id": "progress", "x": 8, "y": 10, "w": 30, "h": 4},
                {"type": "button", "id": "button", "x": 8, "y": 18, "w": 30, "h": 10, "text": "Go"},
            ],
            "constraints": {"button": {"below": "progress", "gap": 4}},
        }
        issues = lint_layout(Screen(100, 50), parse_elements(doc), [], {}, {})
        self.assertFalse(any(i.code == "GAP_TOO_SMALL" for i in issues), issues)

    def test_relative_constraint_missing_target_is_error(self):
        doc = {
            "elements": [
                {"type": "fill", "id": "box", "x": 10, "y": 10, "w": 10, "h": 10}
            ],
            "constraints": {"box": {"right_of": "missing", "gap": 2}},
        }
        issues = lint_layout(Screen(100, 50), parse_elements(doc), [], {}, {})
        self.assertTrue(any(i.code == "CONSTRAINT_TARGET_NOT_FOUND" for i in issues), issues)

    def test_constraint_gap_and_region_follow_screen_scale(self):
        doc = {
            "screen_scale": 0.5,
            "elements": [
                {"type": "fill", "id": "a", "x": 10, "y": 10, "w": 10, "h": 10},
                {"type": "fill", "id": "b", "x": 24, "y": 10, "w": 10, "h": 10},
            ],
            "constraints": {
                "a": {"inside": [10, 10, 10, 10]},
                "b": {"right_of": "a", "gap": 4},
            },
        }
        issues = lint_layout(Screen(100, 50), parse_elements(doc), [], {}, {})
        self.assertFalse(any(i.code in {"ELEMENT_OUT_OF_REGION", "GAP_TOO_SMALL"} for i in issues), issues)


if __name__ == "__main__":
    unittest.main()
