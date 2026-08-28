import tempfile
import unittest
from pathlib import Path

from mc_gui_lint.config import deep_merge, load_document, resolve_preset
from mc_gui_lint.java_extract import extract_java
from mc_gui_lint.localization import (
    apply_language,
    load_language,
    resolve_dynamic_translations,
)

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "examples" / "dynamic_translation_key"


class DynamicTranslationKeyTest(unittest.TestCase):
    def _base_doc(self):
        return deep_merge(
            extract_java(FIX / "FormationScreen.java", FIX / "FormationMenu.java"),
            load_document(FIX / "overlay.yaml"),
        )

    def test_extracts_literal_plus_menu_state_as_dynamic_key_template(self):
        doc = self._base_doc()
        text = next(e for e in doc["elements"] if e["type"] == "text")
        self.assertEqual(
            text["translation_key_template"],
            "gui.example.formation.{formation}",
        )
        self.assertFalse(
            any("APPROXIMATED_TEXT" in w for w in doc["_extraction"]["warnings"]),
            doc["_extraction"]["warnings"],
        )

    def test_six_formations_resolve_in_japanese_and_english(self):
        expected = {
            "ja_jp": ["単縦陣", "複縦陣", "輪形陣", "梯形陣", "単横陣", "警戒陣"],
            "en_us": [
                "Line Ahead",
                "Double Line",
                "Diamond",
                "Echelon",
                "Line Abreast",
                "Vanguard",
            ],
        }
        base = self._base_doc()
        for locale, labels in expected.items():
            translations = load_language(FIX / f"{locale}.json")
            localized = apply_language(base, translations, locale)
            for formation, expected_label in enumerate(labels):
                resolved = resolve_preset(localized, f"formation_{formation}")
                resolved = resolve_dynamic_translations(
                    resolved, translations, locale
                )
                text = next(e for e in resolved["elements"] if e["type"] == "text")
                self.assertEqual(
                    text["translation_key"],
                    f"gui.example.formation.{formation}",
                )
                self.assertEqual(text["text"], expected_label)
                self.assertEqual(
                    (resolved.get("_localization") or {}).get("warnings"),
                    [],
                )

    def test_missing_state_keeps_placeholder_and_warns(self):
        doc = extract_java(FIX / "FormationScreen.java", FIX / "FormationMenu.java")
        doc["state"].pop("formation", None)
        translations = load_language(FIX / "ja_jp.json")
        localized = apply_language(doc, translations, "ja_jp")
        resolved = resolve_dynamic_translations(localized, translations, "ja_jp")
        text = next(e for e in resolved["elements"] if e["type"] == "text")
        self.assertEqual(text["text"], "gui.example.formation.{formation}")
        warnings = (resolved.get("_localization") or {}).get("warnings") or []
        self.assertTrue(
            any("UNRESOLVED_DYNAMIC_TRANSLATION_KEY" in w for w in warnings)
        )

    def test_non_integer_state_is_not_coerced(self):
        doc = self._base_doc()
        doc["state"]["formation"] = "0"
        translations = load_language(FIX / "en_us.json")
        localized = apply_language(doc, translations, "en_us")
        resolved = resolve_dynamic_translations(localized, translations, "en_us")
        warnings = (resolved.get("_localization") or {}).get("warnings") or []
        self.assertTrue(any("non-integer state" in w for w in warnings))

    def test_arbitrary_java_expression_remains_approximated(self):
        with tempfile.TemporaryDirectory() as td:
            screen = Path(td) / "BadScreen.java"
            screen.write_text(
                """class BadScreen extends AbstractContainerScreen<X> {
 void renderLabels(GuiGraphics graphics, int x, int y) {
  graphics.drawString(font, Component.translatable("gui.example.formation." + (menu.formation() + 1)), 8, 20, 0);
 }
}
""",
                encoding="utf-8",
            )
            doc = extract_java(screen)
            self.assertTrue(
                any(
                    "APPROXIMATED_TEXT" in w
                    for w in doc["_extraction"]["warnings"]
                )
            )


if __name__ == "__main__":
    unittest.main()
