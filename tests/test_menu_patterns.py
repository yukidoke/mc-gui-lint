import tempfile
import unittest
from pathlib import Path

from mc_gui_lint.java_extract import _extract_java_string, extract_menu_java


class MenuPatternTest(unittest.TestCase):
    def test_unbraced_and_nested_for_slots(self):
        source = """
        class ExampleMenu extends AbstractContainerMenu {
            static final int EQUIPMENT_SLOTS = 6;
            void init() {
                for (int slot = 0; slot < EQUIPMENT_SLOTS; slot++) {
                    addSlot(new SlotItemHandler(equipment, slot, 26 + slot * 22, 35));
                }
                for (int row = 0; row < 3; row++) for (int column = 0; column < 9; column++)
                    addSlot(new Slot(inv, column + row * 9 + 9, 8 + column * 18, 84 + row * 18));
                for (int column = 0; column < 9; column++)
                    addSlot(new Slot(inv, column, 8 + column * 18, 142));
            }
        }
        """
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ExampleMenu.java"
            path.write_text(source, encoding="utf-8")
            doc = extract_menu_java(path)

        self.assertEqual(len(doc["menu_slots"]), 42)
        self.assertEqual(doc["screen"]["image_width"], 176)
        self.assertEqual(doc["screen"]["image_height"], 166)
        self.assertEqual(doc["_extraction"]["warnings"], [])
        self.assertEqual((doc["menu_slots"][0]["x"], doc["menu_slots"][0]["y"]), (26, 35))
        self.assertEqual((doc["menu_slots"][41]["x"], doc["menu_slots"][41]["y"]), (152, 142))

    def test_tall_machine_layout_infers_179_height(self):
        source = """
        class ExampleMenu extends AbstractContainerMenu {
            void init() {
                for (int slot = 0; slot < 4; slot++) addSlot(new SlotItemHandler(c, slot, 14 + slot * 22, 35));
                addSlot(new SlotItemHandler(c, FUEL_SLOT, 36, 58));
                addSlot(new SlotItemHandler(c, OUTPUT_SLOT, 82, 58));
                for (int row = 0; row < 3; row++) for (int column = 0; column < 9; column++)
                    addSlot(new Slot(inv, column + row * 9 + 9, 8 + column * 18, 97 + row * 18));
                for (int column = 0; column < 9; column++)
                    addSlot(new Slot(inv, column, 8 + column * 18, 155));
            }
        }
        """
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ExampleMenu.java"
            path.write_text(source, encoding="utf-8")
            doc = extract_menu_java(path)

        self.assertEqual(len(doc["menu_slots"]), 42)
        self.assertEqual(doc["screen"]["image_width"], 176)
        self.assertEqual(doc["screen"]["image_height"], 179)
        self.assertEqual(doc["_extraction"]["warnings"], [])

    def test_menu_method_call_becomes_state_placeholder(self):
        self.assertEqual(
            _extract_java_string('"Power: " + menu.powerRemaining() + " FE"'),
            "Power: {power_remaining} FE",
        )
        self.assertEqual(
            _extract_java_string('"Progress: " + menu.progressTicks()'),
            "Progress: {progress_ticks}",
        )


if __name__ == "__main__":
    unittest.main()
