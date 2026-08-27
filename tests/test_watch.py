import tempfile
import unittest
from pathlib import Path

from mc_gui_lint.watch import FileWatcher, normalize_watch_paths


class WatchTest(unittest.TestCase):
    def test_normalize_deduplicates_paths(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Screen.java"
            paths = normalize_watch_paths([path, path, None])
            self.assertEqual(paths, [path.resolve(strict=False)])

    def test_poll_detects_write(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Screen.java"
            path.write_text("a", encoding="utf-8")
            watcher = FileWatcher([path])
            self.assertEqual(watcher.poll(), [])

            # Size changes too, so this remains deterministic on coarse-mtime filesystems.
            path.write_text("abc", encoding="utf-8")
            self.assertEqual(watcher.poll(), [path.resolve(strict=False)])
            self.assertEqual(watcher.poll(), [])

    def test_poll_detects_delete_and_recreate(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "lang.json"
            path.write_text("{}", encoding="utf-8")
            watcher = FileWatcher([path])

            path.unlink()
            self.assertEqual(watcher.poll(), [path.resolve(strict=False)])

            path.write_text('{"x":"y"}', encoding="utf-8")
            self.assertEqual(watcher.poll(), [path.resolve(strict=False)])


if __name__ == "__main__":
    unittest.main()
