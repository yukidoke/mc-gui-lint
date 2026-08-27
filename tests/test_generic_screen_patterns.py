import unittest
from pathlib import Path

from mc_gui_lint.config import parse_elements, parse_menu_slots, parse_screen, resolve_preset
from mc_gui_lint.java_extract import extract_java
from mc_gui_lint.lint import lint_layout
from mc_gui_lint.localization import apply_language, load_language

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "examples" / "generic_machine"


class GenericScreenPatternTest(unittest.TestCase):
    def test_generic_machine_has_42_matching_slot_frames(self):
        doc = extract_java(FIX / "MachineScreen.java", FIX / "MachineMenu.java")
        frames = [e for e in doc["elements"] if e["type"] == "slot_frame"]
        self.assertEqual(len(frames), 42)
        self.assertEqual(len(doc["menu_slots"]), 42)
        self.assertEqual(doc["_extraction"]["warnings"], [])
        for frame in frames:
            slot = doc["menu_slots"][frame["menu_slot"]]
            self.assertEqual((frame["x"] + 1, frame["y"] + 1), (slot["x"], slot["y"]))

    def test_generic_machine_extracts_progress_buttons_and_presets(self):
        doc = extract_java(FIX / "MachineScreen.java", FIX / "MachineMenu.java")
        progress = [e for e in doc["elements"] if e["type"] == "progress"]
        buttons = [e for e in doc["elements"] if e["type"] == "button"]
        self.assertEqual(len(progress), 1)
        self.assertEqual((progress[0]["x"], progress[0]["y"], progress[0]["w"], progress[0]["h"]), (8, 78, 88, 4))
        self.assertEqual(len(buttons), 2)
        self.assertIn("almost_finished", doc["presets"])

    def test_japanese_translation_resolves_power_label(self):
        doc = extract_java(FIX / "MachineScreen.java", FIX / "MachineMenu.java")
        localized = apply_language(doc, load_language(FIX / "ja_jp.json"), "ja_jp")
        labels = [str(e.get("text", "")) for e in localized.get("elements", []) if e.get("type") == "text"]
        self.assertTrue(any("電力:" in label for label in labels))

    def test_localized_max_power_fixture_is_clean(self):
        doc = extract_java(FIX / "MachineScreen.java", FIX / "MachineMenu.java")
        for locale in ("ja_jp", "en_us"):
            localized = apply_language(doc, load_language(FIX / f"{locale}.json"), locale)
            resolved = resolve_preset(localized, "almost_finished")
            issues = lint_layout(
                parse_screen(resolved),
                parse_elements(resolved),
                parse_menu_slots(resolved),
                resolved.get("state", {}),
                resolved.get("widgets", {}),
            )
            self.assertFalse(any(i.severity == "ERROR" for i in issues), issues)



if __name__ == "__main__":
    unittest.main()
