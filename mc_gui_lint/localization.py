from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


_PRINTF_TOKEN = re.compile(r"%%|%(?:(\d+)\$)?s")


def load_language(path: str | Path) -> dict[str, str]:
    """Load a Minecraft language JSON file."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("language JSON must contain an object")
    return {str(k): str(v) for k, v in raw.items()}


def format_translation(template: str, args: list[str]) -> str:
    """Convert Minecraft-style %s / %1$s placeholders to our state template.

    This intentionally implements only the string placeholder forms used by
    Component.translatable. Unknown or missing arguments remain visible rather
    than being silently discarded.
    """
    sequential_index = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal sequential_index
        if match.group(0) == "%%":
            return "%"

        explicit = match.group(1)
        if explicit is not None:
            index = int(explicit) - 1
        else:
            index = sequential_index
            sequential_index += 1

        if 0 <= index < len(args):
            return args[index]
        return "{?}"

    return _PRINTF_TOKEN.sub(repl, template)


def apply_language(doc: dict[str, Any], translations: dict[str, str], locale: str) -> dict[str, Any]:
    """Return a localized copy of extracted/config IR."""
    localized = deepcopy(doc)
    warnings: list[str] = []
    resolved_count = 0

    for element in localized.get("elements", []):
        key = element.get("translation_key")
        if not key:
            continue

        template = translations.get(str(key))
        if template is None:
            warnings.append(f"MISSING_TRANSLATION: {key}")
            continue

        args = [str(v) for v in element.get("translation_args", [])]
        element["text"] = format_translation(template, args)
        element["locale"] = locale
        resolved_count += 1

    # Resolve the normal screen title when a unique matching container key can
    # be inferred from the Screen class name. Dynamic translations such as
    # "%s Equipment" are intentionally left unresolved.
    extraction = localized.get("_extraction") or {}
    screen_source = extraction.get("screen_source")
    state = localized.setdefault("state", {})
    if screen_source and state.get("screen_title") in (None, "Title"):
        stem = Path(str(screen_source)).stem
        if stem.endswith("Screen"):
            base = stem[:-6]
            snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", base).lower()
            candidates = [
                (key, value)
                for key, value in translations.items()
                if key.startswith("container.") and key.endswith("." + snake)
            ]
            if len(candidates) == 1 and "%" not in candidates[0][1]:
                state["screen_title"] = candidates[0][1]

    localized["_localization"] = {
        "locale": locale,
        "resolved": resolved_count,
        "warnings": warnings,
    }
    return localized
