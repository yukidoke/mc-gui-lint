import tempfile
import unittest
from pathlib import Path

from mc_gui_lint.java_extract import JavaIntEvaluator, extract_java


class JavaExprTest(unittest.TestCase):
    def test_coordinates(self):
        ev = JavaIntEvaluator({"leftPos": 0, "topPos": 0, "col": 3})
        self.assertEqual(ev.eval("this.leftPos + 8 + col * 18"), 62)

    def test_java_integer_division(self):
        ev = JavaIntEvaluator()
        self.assertEqual(ev.eval("5 / 2"), 2)
        self.assertEqual(ev.eval("-5 / 2"), -2)


class JavaExtractTest(unittest.TestCase):
    def test_screen_and_menu(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            screen = td / "TestScreen.java"
            menu = td / "TestMenu.java"

            screen.write_text(
                """
                class TestScreen {
                  TestScreen() {
                    this.imageWidth = 176;
                    this.imageHeight = 179;
                  }
                  void draw(GuiGraphics graphics) {
                    graphics.drawString(font, "Power: " + menu.getPower() + " FE", 8, 20, 0);
                    graphics.fill(leftPos + 8, topPos + 30, leftPos + 40, topPos + 35, 0);
                    graphics.blit(TEXTURE, leftPos, topPos, 0, 0, imageWidth, imageHeight);
                  }
                }
                """,
                encoding="utf-8",
            )
            menu.write_text(
                """
                class TestMenu {
                  void init() {
                    this.addSlot(new Slot(c, 0, 44, 62));
                    for (int col = 0; col < 3; col++) {
                      this.addSlot(new Slot(c, col, 8 + col * 18, 100));
                    }
                  }
                }
                """,
                encoding="utf-8",
            )

            doc = extract_java(screen, menu)
            self.assertEqual(doc["screen"]["image_width"], 176)
            self.assertEqual(doc["screen"]["image_height"], 179)
            self.assertTrue(any(e["type"] == "text" and e["text"] == "Power: {power} FE"
                                for e in doc["elements"]))
            self.assertTrue(any(e["type"] == "fill" and e["x"] == 8 and e["w"] == 32
                                for e in doc["elements"]))
            self.assertTrue(any(e["type"] == "blit" and e["w"] == 176 and e["h"] == 179
                                for e in doc["elements"]))

            self.assertEqual((doc["menu_slots"][0]["x"], doc["menu_slots"][0]["y"]), (44, 62))
            self.assertEqual((doc["menu_slots"][1]["x"], doc["menu_slots"][1]["y"]), (8, 100))
            coords = {(s["x"], s["y"]) for s in doc["menu_slots"]}
            self.assertIn((44, 62), coords)
            self.assertIn((8, 100), coords)
            self.assertIn((26, 100), coords)
            self.assertIn((44, 100), coords)


if __name__ == "__main__":
    unittest.main()
