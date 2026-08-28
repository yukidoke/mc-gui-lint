import tempfile
import unittest
from pathlib import Path

from mc_gui_lint.java_extract import extract_java


ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "examples" / "button_helper"


class ButtonHelperTest(unittest.TestCase):
    def test_four_buttons_expand_through_helpers(self):
        doc = extract_java(
            FIX / "ButtonHelperScreen.java",
            FIX / "ButtonHelperMenu.java",
        )
        buttons = [e for e in doc["elements"] if e["type"] == "button"]
        self.assertEqual(len(buttons), 4)
        self.assertEqual(
            [(b["x"], b["y"], b["w"], b["h"]) for b in buttons],
            [
                (8, 20, 50, 20),
                (60, 20, 50, 20),
                (8, 46, 50, 20),
                (60, 46, 50, 20),
            ],
        )
        self.assertEqual(
            [b.get("translation_key") for b in buttons],
            [
                "gui.example.action.0",
                "gui.example.action.1",
                "gui.example.action.2",
                "gui.example.action.3",
            ],
        )
        warnings = doc["_extraction"]["warnings"]
        self.assertFalse(
            any("UNRESOLVED_BUTTON" in w for w in warnings),
            warnings,
        )

    def test_unresolved_numeric_helper_argument_warns(self):
        with tempfile.TemporaryDirectory() as td:
            screen = Path(td) / "BadScreen.java"
            screen.write_text(
                '''class BadScreen extends AbstractContainerScreen<X> {
 protected void init() {
  addActionButton(calculateX(), topPos + 20, Component.literal("Go"));
 }
 private void addActionButton(int x, int y, Component label) {
  addRenderableWidget(Button.builder(label, b -> {}).bounds(x, y, 40, 20).build());
 }
}
''',
                encoding="utf-8",
            )
            doc = extract_java(screen)
            warnings = doc["_extraction"]["warnings"]
            self.assertTrue(
                any("UNRESOLVED_BUTTON_HELPER_ARGUMENT" in w for w in warnings),
                warnings,
            )
            self.assertTrue(
                any("UNRESOLVED_BUTTON_BOUNDS" in w for w in warnings),
                warnings,
            )

    def test_direct_button_still_extracts(self):
        with tempfile.TemporaryDirectory() as td:
            screen = Path(td) / "DirectScreen.java"
            screen.write_text(
                '''class DirectScreen extends AbstractContainerScreen<X> {
 protected void init() {
  addRenderableWidget(Button.builder(Component.literal("Go"), b -> {})
      .bounds(leftPos + 10, topPos + 12, 50, 20).build());
 }
}
''',
                encoding="utf-8",
            )
            doc = extract_java(screen)
            buttons = [e for e in doc["elements"] if e["type"] == "button"]
            self.assertEqual(len(buttons), 1)
            self.assertEqual(
                (buttons[0]["x"], buttons[0]["y"], buttons[0]["w"], buttons[0]["h"]),
                (10, 12, 50, 20),
            )


if __name__ == "__main__":
    unittest.main()
