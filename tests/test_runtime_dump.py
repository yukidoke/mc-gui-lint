import unittest

from mc_gui_lint.runtime_dump import apply_runtime_dump


class RuntimeDumpTest(unittest.TestCase):
    def test_runtime_slot_and_state_win(self):
        doc = {
            "screen": {"image_width": 176, "image_height": 166},
            "state": {"power": 0},
            "menu_slots": [{"index": 0, "name": "slot_0", "x": 1, "y": 2}],
        }
        dump = {
            "screen": {"image_width": 180, "image_height": 170, "left_pos": 12, "top_pos": 8},
            "state": {"power": 999},
            "menu_slots": [{"index": 0, "name": "slot_0", "x": 44, "y": 62, "w": 16, "h": 16}],
        }
        merged = apply_runtime_dump(doc, dump)
        self.assertEqual(merged["screen"]["image_width"], 180)
        self.assertEqual(merged["state"]["power"], 999)
        self.assertEqual(merged["menu_slots"][0]["x"], 44)
        self.assertEqual(merged["_runtime"]["screen"]["left_pos"], 12)


if __name__ == "__main__":
    unittest.main()
