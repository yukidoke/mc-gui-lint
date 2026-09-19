import tempfile
import unittest
from pathlib import Path

from mc_gui_lint.conditions import evaluate_state_condition, normalize_java_condition
from mc_gui_lint.config import parse_elements, resolve_preset
from mc_gui_lint.java_extract import extract_java


class ConditionExpressionTest(unittest.TestCase):
    def test_normalizes_common_menu_conditions(self):
        expr = normalize_java_condition(
            "menu.isWorking() && menu.getPower() > 0 && !menu.isBroken()"
        )
        self.assertEqual(
            expr,
            "is_working and power > 0 and not is_broken",
        )
        self.assertTrue(
            evaluate_state_condition(
                expr,
                {"is_working": True, "power": 1, "is_broken": False},
            )
        )
        self.assertFalse(
            evaluate_state_condition(
                expr,
                {"is_working": True, "power": 0, "is_broken": False},
            )
        )

    def test_missing_state_is_unknown(self):
        expr = normalize_java_condition("menu.isWorking()")
        self.assertIsNotNone(expr)
        self.assertIsNone(evaluate_state_condition(expr, {}))

    def test_boolean_evaluation_short_circuits_and_uses_java_int_division(self):
        expr = normalize_java_condition("menu.getDenom() != 0 && menu.getPower() / menu.getDenom() > 2")
        self.assertFalse(evaluate_state_condition(expr, {"denom": 0, "power": 10}))
        self.assertFalse(evaluate_state_condition(expr, {"denom": 2, "power": 5}))
        self.assertTrue(evaluate_state_condition(expr, {"denom": 2, "power": 6}))


class ConditionalRenderingTest(unittest.TestCase):
    def _extract(self, source: str):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "ConditionalScreen.java"
        path.write_text(source, encoding="utf-8")
        return extract_java(path)

    @staticmethod
    def _texts(doc, state):
        return [
            e.data.get("text")
            for e in parse_elements(doc, state)
            if e.type == "text"
        ]

    def test_if_else_visibility_uses_state(self):
        doc = self._extract(
            """
            class ConditionalScreen {
              void render(GuiGraphics graphics) {
                if (menu.isWorking()) {
                  graphics.drawString(font, "Working", 8, 8, 0xffffff);
                } else {
                  graphics.drawString(font, "Idle", 8, 8, 0xffffff);
                }
              }
            }
            """
        )

        self.assertEqual(self._texts(doc, {"is_working": True}), ["Working"])
        self.assertEqual(self._texts(doc, {"is_working": False}), ["Idle"])

        raw_texts = [e for e in doc["elements"] if e["type"] == "text"]
        self.assertEqual(len(raw_texts), 2)
        self.assertTrue(all(e.get("visibility_conditions") for e in raw_texts))
        self.assertIn("is_working", doc["state"])

    def test_else_if_chain_selects_one_branch(self):
        doc = self._extract(
            """
            class ConditionalScreen {
              void render(GuiGraphics graphics) {
                if (menu.getPower() > 100) {
                  graphics.drawString(font, "High", 8, 8, 0xffffff);
                } else if (menu.getPower() > 0) {
                  graphics.drawString(font, "Low", 8, 8, 0xffffff);
                } else {
                  graphics.drawString(font, "Off", 8, 8, 0xffffff);
                }
              }
            }
            """
        )
        self.assertEqual(self._texts(doc, {"power": 200}), ["High"])
        self.assertEqual(self._texts(doc, {"power": 10}), ["Low"])
        self.assertEqual(self._texts(doc, {"power": 0}), ["Off"])

    def test_unbraced_if_and_boolean_operators(self):
        doc = self._extract(
            """
            class ConditionalScreen {
              void render(GuiGraphics graphics) {
                if (menu.getPower() > 0 && !menu.isBroken())
                  graphics.drawString(font, "Ready", 8, 8, 0xffffff);
                graphics.drawString(font, "Always", 8, 20, 0xffffff);
              }
            }
            """
        )
        self.assertEqual(
            self._texts(doc, {"power": 10, "is_broken": False}),
            ["Ready", "Always"],
        )
        self.assertEqual(
            self._texts(doc, {"power": 10, "is_broken": True}),
            ["Always"],
        )

    def test_preset_state_is_applied_before_visibility_filter(self):
        doc = self._extract(
            """
            class ConditionalScreen {
              void render(GuiGraphics graphics) {
                if (menu.isWorking()) {
                  graphics.drawString(font, "Working", 8, 8, 0xffffff);
                } else {
                  graphics.drawString(font, "Idle", 8, 8, 0xffffff);
                }
              }
            }
            """
        )
        doc["presets"] = {
            "idle": {"state": {"is_working": False}},
            "working": {"state": {"is_working": True}},
        }
        working = resolve_preset(doc, "working")
        idle = resolve_preset(doc, "idle")
        self.assertEqual(self._texts(working, working["state"]), ["Working"])
        self.assertEqual(self._texts(idle, idle["state"]), ["Idle"])


    def test_numeric_constant_in_condition_is_bound(self):
        doc = self._extract(
            """
            class ConditionalScreen {
              private static final int MIN_POWER = 20;
              void render(GuiGraphics graphics) {
                if (menu.getPower() >= MIN_POWER) {
                  graphics.drawString(font, "Enough", 8, 8, 0xffffff);
                }
              }
            }
            """
        )
        raw = next(e for e in doc["elements"] if e["type"] == "text")
        self.assertEqual(raw["visibility_conditions"][0]["expr"], "power >= 20")
        self.assertEqual(self._texts(doc, {"power": 19}), [])
        self.assertEqual(self._texts(doc, {"power": 20}), ["Enough"])

    def test_bare_boolean_screen_predicate_is_supported(self):
        doc = self._extract(
            """
            class ConditionalScreen {
              void render(GuiGraphics graphics) {
                if (isCompact()) {
                  graphics.drawString(font, "Compact", 8, 8, 0xffffff);
                }
              }
            }
            """
        )
        self.assertEqual(self._texts(doc, {"is_compact": True}), ["Compact"])
        self.assertEqual(self._texts(doc, {"is_compact": False}), [])

    def test_unsupported_condition_keeps_element_visible_and_warns(self):
        doc = self._extract(
            """
            class ConditionalScreen {
              void render(GuiGraphics graphics) {
                if (menu.getMode() == Mode.ACTIVE) {
                  graphics.drawString(font, "Mode", 8, 8, 0xffffff);
                }
              }
            }
            """
        )
        self.assertEqual(self._texts(doc, {}), ["Mode"])
        warnings = (doc.get("_extraction") or {}).get("warnings") or []
        self.assertTrue(any("UNRESOLVED_IF_CONDITION" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
