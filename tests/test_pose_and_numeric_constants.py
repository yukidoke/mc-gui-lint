import tempfile
import unittest
from pathlib import Path

from mc_gui_lint.config import parse_elements
from mc_gui_lint.java_extract import JavaIntEvaluator, extract_java
from mc_gui_lint.lint import resolve_elements
from mc_gui_lint.text_metrics import ApproxMinecraftFontMetrics


class NumericConstantTest(unittest.TestCase):
    def test_float_arithmetic_and_math_round(self):
        ev = JavaIntEvaluator({"SCALE": 0.8})
        self.assertAlmostEqual(ev.eval_number("SCALE * 10"), 8.0)
        self.assertEqual(ev.eval("Math.round(SCALE * 13)"), 10)
        self.assertEqual(ev.eval("Math.round(-1.5F)"), -1)
        self.assertAlmostEqual(ev.eval_number("5 / 2.0F"), 2.5)

    def test_private_static_final_float_and_round_are_extracted(self):
        with tempfile.TemporaryDirectory() as td:
            screen = Path(td) / "ScaledScreen.java"
            screen.write_text(
                """
                class ScaledScreen {
                    private static final float SCALE = 0.8F;
                    private static final int LABEL_X = Math.round(10 * SCALE);
                    void render(GuiGraphics graphics) {
                        graphics.drawString(font, "X", LABEL_X, 4, 0xFFFFFF);
                    }
                }
                """,
                encoding="utf-8",
            )
            doc = extract_java(screen)

        text = next(e for e in doc["elements"] if e["type"] == "text")
        self.assertEqual(text["x"], 8)


class PoseTransformTest(unittest.TestCase):
    def test_linear_pose_stack_is_attached_to_direct_draw_calls(self):
        with tempfile.TemporaryDirectory() as td:
            screen = Path(td) / "PoseScreen.java"
            screen.write_text(
                """
                class PoseScreen {
                    private static final float SCALE = 0.5F;

                    void render(GuiGraphics graphics) {
                        graphics.pose().pushPose();
                        graphics.pose().translate(10, 20, 0);
                        graphics.pose().scale(SCALE, SCALE, 1.0F);
                        graphics.drawString(font, "abcd", 20, 10, 0xFFFFFF);
                        graphics.pose().popPose();
                        graphics.drawString(font, "abcd", 20, 10, 0xFFFFFF);
                    }
                }
                """,
                encoding="utf-8",
            )
            doc = extract_java(screen)

        raw_texts = [e for e in doc["elements"] if e["type"] == "text"]
        self.assertEqual(len(raw_texts), 2)
        self.assertEqual(
            raw_texts[0]["pose_transform"],
            {
                "scale_x": 0.5,
                "scale_y": 0.5,
                "translate_x": 10.0,
                "translate_y": 20.0,
            },
        )
        self.assertNotIn("pose_transform", raw_texts[1])

        resolved = resolve_elements(
            parse_elements(doc), {}, {}, ApproxMinecraftFontMetrics()
        )
        texts = [r for r in resolved if r.kind == "text"]
        self.assertAlmostEqual(texts[0].rect.x, 20.0)
        self.assertAlmostEqual(texts[0].rect.y, 25.0)
        self.assertAlmostEqual(texts[0].rect.w, 12.0)
        self.assertAlmostEqual(texts[1].rect.x, 20.0)
        self.assertAlmostEqual(texts[1].rect.y, 10.0)
        self.assertAlmostEqual(texts[1].rect.w, 24.0)

    def test_draw_centered_string_resolves_x_as_center_anchor(self):
        with tempfile.TemporaryDirectory() as td:
            screen = Path(td) / "CenteredScreen.java"
            screen.write_text(
                """
                class CenteredScreen {
                    void render(GuiGraphics graphics) {
                        graphics.drawCenteredString(font, "abcd", 50, 10, 0xFFFFFF);
                    }
                }
                """,
                encoding="utf-8",
            )
            doc = extract_java(screen)

        resolved = resolve_elements(
            parse_elements(doc), {}, {}, ApproxMinecraftFontMetrics()
        )
        text = next(r for r in resolved if r.kind == "text")
        self.assertEqual(text.element.data.get("align"), "center")
        self.assertAlmostEqual(text.rect.x, 38.0)
        self.assertAlmostEqual(text.rect.w, 24.0)

    def test_scale_then_translate_uses_pose_stack_order(self):
        with tempfile.TemporaryDirectory() as td:
            screen = Path(td) / "PoseOrderScreen.java"
            screen.write_text(
                """
                class PoseOrderScreen {
                    void render(GuiGraphics graphics) {
                        graphics.pose().scale(0.5F, 0.5F, 1.0F);
                        graphics.pose().translate(10, 0, 0);
                        graphics.drawString(font, "X", 20, 0, 0xFFFFFF);
                    }
                }
                """,
                encoding="utf-8",
            )
            doc = extract_java(screen)

        resolved = resolve_elements(
            parse_elements(doc), {}, {}, ApproxMinecraftFontMetrics()
        )
        text = next(r for r in resolved if r.kind == "text")
        # M = Scale * Translate => 0.5 * (20 + 10) = 15.
        self.assertAlmostEqual(text.rect.x, 15.0)


if __name__ == "__main__":
    unittest.main()
