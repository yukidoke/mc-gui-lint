from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import yaml

from .config import (
    deep_merge,
    load_document,
    parse_elements,
    parse_menu_slots,
    parse_screen,
    parse_viewport,
    resolve_preset,
)
from .java_extract import extract_java, extract_menu_java
from .lint import lint_layout
from .localization import apply_language, load_language, resolve_dynamic_translations
from .renderer import render
from .runtime_dump import apply_runtime_dump, load_runtime_dump
from .watch import FileWatcher, normalize_watch_paths


def _load_source(source: Path, menu: Path | None, overlay: Path | None, runtime_dump: Path | None = None) -> dict:
    if source.suffix.lower() == ".java":
        source_text = source.read_text(encoding="utf-8")
        if menu is None and "extends AbstractContainerMenu" in source_text:
            doc = extract_menu_java(source)
        else:
            doc = extract_java(source, menu)
    else:
        doc = load_document(source)

    if overlay is not None:
        doc = deep_merge(doc, load_document(overlay))
    if runtime_dump is not None:
        doc = apply_runtime_dump(doc, load_runtime_dump(runtime_dump))
    return doc


def run_one(
    source: Path,
    doc: dict,
    preset: str | None,
    output_dir: Path,
    translations: dict[str, str] | None = None,
    locale: str | None = None,
) -> tuple[str, list, list[str]]:
    resolved = resolve_preset(doc, preset)
    if translations is not None and locale is not None:
        resolved = resolve_dynamic_translations(resolved, translations, locale)
    runtime_localization_warnings = list(
        (resolved.get("_localization") or {}).get("warnings") or []
    )
    screen = parse_screen(resolved)
    viewport = parse_viewport(resolved)
    elements = parse_elements(resolved)
    menu_slots = parse_menu_slots(resolved)
    state = resolved.get("state", {}) or {}
    slots = resolved.get("slots", {}) or {}
    widgets = resolved.get("widgets", {}) or {}

    issues = lint_layout(screen, elements, menu_slots, state, widgets)

    name = preset or "default"
    render(screen, viewport, elements, menu_slots, state, slots, widgets, issues, output_dir / f"{name}.png", debug=False)
    render(screen, viewport, elements, menu_slots, state, slots, widgets, issues, output_dir / f"{name}.debug.png", debug=True)
    return name, issues, runtime_localization_warnings


def _run_document(
    source: Path,
    doc: dict,
    args,
    output_dir: Path,
    label: str | None = None,
    translations: dict[str, str] | None = None,
) -> tuple[int, int, list[str]]:
    output_dir.mkdir(parents=True, exist_ok=True)

    extraction_warnings = (doc.get("_extraction") or {}).get("warnings") or []
    localization_warnings = (doc.get("_localization") or {}).get("warnings") or []
    prefix = f"[{label}] " if label else ""
    for warning in extraction_warnings:
        print(f"{prefix}[EXTRACT] {warning}")
    for warning in localization_warnings:
        print(f"{prefix}[LANG] {warning}")

    if args.all_presets:
        names = list((doc.get("presets") or {}).keys()) or [None]
    else:
        names = [args.preset]

    report: list[str] = []
    if label:
        report.append(f"LOCALE: {label}")
        report.append("")
    if extraction_warnings:
        report += ["=== extraction ===", *extraction_warnings, ""]
    if localization_warnings:
        report += ["=== localization ===", *localization_warnings, ""]

    total_errors = total_warnings = 0
    for preset in names:
        name, issues, preset_localization_warnings = run_one(
            source, doc, preset, output_dir, translations, label
        )
        dynamic_warnings = [
            warning
            for warning in preset_localization_warnings
            if warning not in localization_warnings
        ]
        for warning in dynamic_warnings:
            print(f"{prefix}[LANG] {name}: {warning}")
        errors = sum(i.severity == "ERROR" for i in issues)
        warnings = sum(i.severity == "WARNING" for i in issues)
        total_errors += errors
        total_warnings += warnings
        status = "OK" if errors == 0 else "FAIL"
        print(f"{prefix}[{status}] {name}: {errors} errors, {warnings} warnings")
        report.append(f"=== {name} ===")
        if dynamic_warnings:
            report.append("Localization warnings:")
            report.extend(f"  {warning}" for warning in dynamic_warnings)
        report.extend(issue.format(n) for n, issue in enumerate(issues, 1)) if issues else report.append("No issues.")
        report.append("")

    report.append(f"TOTAL: {total_errors} errors, {total_warnings} warnings")
    (output_dir / "report.txt").write_text("\n".join(report), encoding="utf-8")
    return total_errors, total_warnings, report


def _execute_once(args) -> int:
    """Generate all requested previews once and return the lint-style exit code."""

    base_doc = _load_source(args.source, args.menu, args.overlay, args.runtime_dump)

    variants: list[tuple[str | None, dict, dict[str, str] | None]] = []
    if args.lang:
        for lang_path in args.lang:
            locale = lang_path.stem
            translations = load_language(lang_path)
            variants.append(
                (locale, apply_language(base_doc, translations, locale), translations)
            )
    else:
        variants.append((None, base_doc, None))

    grand_errors = 0
    for locale, doc, translations in variants:
        output_dir = args.output / locale if locale else args.output

        if args.dump_ir:
            dump = args.dump_ir
            if locale:
                dump = dump.with_name(f"{dump.stem}.{locale}{dump.suffix or '.yaml'}")
            dump.parent.mkdir(parents=True, exist_ok=True)
            dump.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")

        errors, _, _ = _run_document(args.source, doc, args, output_dir, locale, translations)
        grand_errors += errors

    return 1 if grand_errors else 0


def _watch_input_paths(args) -> list[Path]:
    """Return only user inputs so generated PNG/report files never trigger a loop."""

    values: list[Path | None] = [
        args.source,
        args.menu,
        args.overlay,
        args.runtime_dump,
    ]
    values.extend(args.lang or [])
    return normalize_watch_paths(values)


def _format_changed(paths: list[Path], watched: list[Path]) -> str:
    labels: list[str] = []
    for path in paths:
        # Prefer short readable names; retain parent only when duplicate names exist.
        if sum(other.name == path.name for other in watched) == 1:
            labels.append(path.name)
        else:
            labels.append(str(path))
    return ", ".join(labels)


def _safe_watch_render(args) -> int | None:
    """Render one watch cycle without killing the watcher on a transient parse/save error."""

    try:
        return _execute_once(args)
    except Exception as exc:  # watch mode is intentionally resilient to half-written files
        print(f"[WATCH] render failed: {type(exc).__name__}: {exc}")
        print("[WATCH] waiting for the next input change...")
        return None


def _run_watch(args) -> int:
    watched = _watch_input_paths(args)
    if not watched:
        raise ValueError("watch mode requires at least one input file")

    watcher = FileWatcher(watched)

    print("[WATCH] initial render")
    _safe_watch_render(args)
    print(f"[WATCH] watching {len(watched)} input file(s); Ctrl+C to stop")
    for path in watched:
        print(f"[WATCH]   {path}")

    try:
        while True:
            changed = watcher.wait_for_change(args.watch_interval)
            # Editors often save via temp-file + rename or a small burst of writes.
            # Give the file a short settling window and combine those events.
            extra = watcher.settle(min(args.watch_interval, 0.15), rounds=1)
            for path in extra:
                if path not in changed:
                    changed.append(path)

            now = datetime.now().strftime("%H:%M:%S")
            print(f"\n[WATCH {now}] changed: {_format_changed(changed, watched)}")
            result = _safe_watch_render(args)
            if result is not None:
                status = "clean" if result == 0 else "lint errors"
                print(f"[WATCH {now}] updated PNG/report ({status})")
    except KeyboardInterrupt:
        print("\n[WATCH] stopped")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mc-gui-lint", description="Static Minecraft GUI preview + layout lint")
    parser.add_argument("source", type=Path, help="YAML/JSON preview spec, Screen.java, or Menu.java")
    parser.add_argument("--menu", type=Path, help="Menu.java when source is Screen.java")
    parser.add_argument("--overlay", type=Path, help="YAML/JSON overrides for extracted Java IR")
    parser.add_argument("--runtime-dump", type=Path, help="JSON dumped from a development Minecraft client")
    parser.add_argument("--lang", type=Path, action="append", help="Minecraft language JSON. Repeat for multi-locale audit.")
    parser.add_argument("--preset")
    parser.add_argument("--all-presets", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("build/gui-preview"))
    parser.add_argument("--dump-ir", type=Path, help="Write extracted/config IR as YAML. With multiple --lang, locale is appended.")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch input files and regenerate PNG/Lint output whenever they change.",
    )
    parser.add_argument(
        "--watch-interval",
        type=float,
        default=0.35,
        metavar="SECONDS",
        help="Polling interval for --watch (default: 0.35; minimum effective value: 0.05).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.watch:
        return _run_watch(args)
    return _execute_once(args)
