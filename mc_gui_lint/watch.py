from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Iterable


@dataclass(frozen=True)
class FileStamp:
    """Small, editor-friendly signature for a watched input file."""

    exists: bool
    mtime_ns: int | None
    size: int | None


def file_stamp(path: Path) -> FileStamp:
    """Return a signature that also detects delete/recreate and atomic saves."""

    try:
        stat = path.stat()
    except FileNotFoundError:
        return FileStamp(False, None, None)
    return FileStamp(True, stat.st_mtime_ns, stat.st_size)


def normalize_watch_paths(paths: Iterable[Path | None]) -> list[Path]:
    """Return stable, absolute, de-duplicated input paths."""

    result: list[Path] = []
    seen: set[Path] = set()
    for value in paths:
        if value is None:
            continue
        path = Path(value).expanduser().resolve(strict=False)
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result


class FileWatcher:
    """Dependency-free polling watcher for the CLI input files."""

    def __init__(self, paths: Iterable[Path]):
        self.paths = normalize_watch_paths(paths)
        self._snapshot = {path: file_stamp(path) for path in self.paths}

    def poll(self) -> list[Path]:
        """Return changed files since the previous poll and update the snapshot."""

        changed: list[Path] = []
        for path in self.paths:
            current = file_stamp(path)
            previous = self._snapshot.get(path)
            if current != previous:
                changed.append(path)
                self._snapshot[path] = current
        return changed

    def wait_for_change(self, interval: float) -> list[Path]:
        """Block until at least one watched file changes."""

        interval = max(0.05, interval)
        while True:
            time.sleep(interval)
            changed = self.poll()
            if changed:
                return changed

    def settle(self, interval: float, rounds: int = 2) -> list[Path]:
        """Collect rapid follow-up writes from atomic/editor saves before rerendering."""

        interval = max(0.05, interval)
        collected: list[Path] = []
        seen: set[Path] = set()
        for _ in range(max(0, rounds)):
            time.sleep(interval)
            for path in self.poll():
                if path not in seen:
                    seen.add(path)
                    collected.append(path)
        return collected
