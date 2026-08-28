import tempfile
import unittest
from pathlib import Path

from mc_gui_lint.java_extract import (
    JavaIntEvaluator,
    _extract_public_static_final_int_constants,
    extract_java,
)


class CrossClassConstantTest(unittest.TestCase):
    def test_evaluator_resolves_qualified_constant(self):
        evaluator = JavaIntEvaluator({"FleetCommandMenu.BUTTON_ALPHA": 3})
        self.assertEqual(evaluator.eval("FleetCommandMenu.BUTTON_ALPHA"), 3)

    def test_public_static_final_integral_constants_only(self):
        code = """
        public final class FleetCommandMenu {
            public static final int BUTTON_ALPHA = 0;
            public static final int BUTTON_BETA = BUTTON_ALPHA + 1;
            public static final long BUTTON_GAMMA = 2L;
            static final int PACKAGE_PRIVATE = 9;
            public static int MUTABLE = 10;
            public static final Integer BOXED = 11;
            public static final int RUNTIME = calculateRuntime();
        }
        """
        constants = _extract_public_static_final_int_constants(
            code,
            "FleetCommandMenu",
        )
        self.assertEqual(constants["FleetCommandMenu.BUTTON_ALPHA"], 0)
        self.assertEqual(constants["FleetCommandMenu.BUTTON_BETA"], 1)
        self.assertEqual(constants["FleetCommandMenu.BUTTON_GAMMA"], 2)
        self.assertNotIn("FleetCommandMenu.PACKAGE_PRIVATE", constants)
        self.assertNotIn("FleetCommandMenu.MUTABLE", constants)
        self.assertNotIn("FleetCommandMenu.BOXED", constants)
        self.assertNotIn("FleetCommandMenu.RUNTIME", constants)

    def test_button_helper_accepts_menu_public_static_final_ids(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            screen = td / "FleetCommandScreen.java"
            menu = td / "FleetCommandMenu.java"

            menu.write_text(
                """
                public final class FleetCommandMenu extends AbstractContainerMenu {
                    public static final int BUTTON_ALPHA = 0;
                    public static final int BUTTON_BETA = BUTTON_ALPHA + 1;
                    public static final int BUTTON_GAMMA = BUTTON_BETA + 1;
                    public static final int BUTTON_DELTA = BUTTON_GAMMA + 1;
                }
                """,
                encoding="utf-8",
            )
            screen.write_text(
                """
                public final class FleetCommandScreen extends AbstractContainerScreen<FleetCommandMenu> {
                    @Override protected void init() {
                        super.init();
                        addCommandButton(FleetCommandMenu.BUTTON_ALPHA, leftPos + 8, topPos + 20);
                        addCommandButton(FleetCommandMenu.BUTTON_BETA, leftPos + 60, topPos + 20);
                        addCommandButton(FleetCommandMenu.BUTTON_GAMMA, leftPos + 8, topPos + 46);
                        addCommandButton(FleetCommandMenu.BUTTON_DELTA, leftPos + 60, topPos + 46);
                    }

                    private void addCommandButton(int id, int x, int y) {
                        addRenderableWidget(
                            Button.builder(Component.literal("Action"), b -> send(id))
                                .bounds(x, y, 50, 20)
                                .build()
                        );
                    }

                    private void send(int id) {}
                }
                """,
                encoding="utf-8",
            )

            doc = extract_java(screen, menu)

        buttons = [e for e in doc["elements"] if e["type"] == "button"]
        self.assertEqual(len(buttons), 4)
        self.assertEqual(
            [(b["x"], b["y"]) for b in buttons],
            [(8, 20), (60, 20), (8, 46), (60, 46)],
        )
        warnings = doc["_extraction"]["warnings"]
        self.assertFalse(
            any("UNRESOLVED_BUTTON_HELPER_ARGUMENT" in warning for warning in warnings),
            warnings,
        )

    def test_runtime_constant_stays_unresolved(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            screen = td / "Screen.java"
            menu = td / "FleetCommandMenu.java"
            menu.write_text(
                """
                public final class FleetCommandMenu {
                    public static final int BUTTON_DYNAMIC = calculateRuntime();
                }
                """,
                encoding="utf-8",
            )
            screen.write_text(
                """
                class Screen {
                    void init() {
                        addButton(FleetCommandMenu.BUTTON_DYNAMIC, leftPos + 8, topPos + 20);
                    }
                    void addButton(int id, int x, int y) {
                        Button.builder(Component.literal("X"), b -> {}).bounds(x, y, 40, 20).build();
                    }
                }
                """,
                encoding="utf-8",
            )
            doc = extract_java(screen, menu)

        self.assertTrue(
            any(
                "UNRESOLVED_BUTTON_HELPER_ARGUMENT" in warning
                for warning in doc["_extraction"]["warnings"]
            )
        )


if __name__ == "__main__":
    unittest.main()
