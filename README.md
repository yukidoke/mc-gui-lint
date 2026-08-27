# mc-gui-lint

[日本語 README](README_ja.md)
`mc-gui-lint` is a static preview and layout linting tool for Minecraft container GUIs.

It targets `AbstractContainerScreen` / `AbstractContainerMenu` style UIs and helps catch coordinate mistakes before repeatedly launching Minecraft just to inspect the screen.

The goal is **not** to emulate Minecraft perfectly. The goal is to catch layout problems early and reduce in-game verification cycles.

## Features

- Parse common `Screen.java` and `Menu.java` layout patterns
- Render normal and debug PNG previews
- Compare decorative slot frames with actual Menu slot coordinates
- Detect text clipping, overlap, and out-of-bounds elements
- Detect button label overflow
- Extract simple state-driven progress bars
- Generate state presets such as empty / building / almost-finished cases
- Resolve `Component.translatable(...)` from Minecraft language JSON files
- Audit multiple locales in one run
- Apply YAML/JSON overlays when static extraction is incomplete
- Apply runtime dump data from a development client
- Watch input files and automatically regenerate PNG/Lint results
- Return a non-zero exit code when layout errors are found

## Requirements

- Python 3.10+
- Pillow
- PyYAML

## Installation

Clone the repository and install it in editable mode:

```bash
git clone https://github.com/YOUR_NAME/mc-gui-lint.git
cd mc-gui-lint
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -e .
```

Linux / macOS:

```bash
source .venv/bin/activate
pip install -e .
```

The CLI is then available as:

```bash
mc-gui-lint --help
```

You can also run the package directly:

```bash
python -m mc_gui_lint --help
```

## Quick start

A generic fixture is included under:

```text
examples/generic_machine/
```

These Java files are parser fixtures, so imports and Minecraft setup boilerplate are intentionally omitted; they are not intended to compile as a standalone mod.

Run the previewer against both Japanese and English:

```bash
mc-gui-lint \
  examples/generic_machine/MachineScreen.java \
  --menu examples/generic_machine/MachineMenu.java \
  --lang examples/generic_machine/ja_jp.json \
  --lang examples/generic_machine/en_us.json \
  --all-presets \
  --output gui-preview
```

PowerShell:

```powershell
mc-gui-lint `
  examples/generic_machine/MachineScreen.java `
  --menu examples/generic_machine/MachineMenu.java `
  --lang examples/generic_machine/ja_jp.json `
  --lang examples/generic_machine/en_us.json `
  --all-presets `
  --output gui-preview
```

Typical output:

```text
gui-preview/
├─ ja_jp/
│  ├─ empty.png
│  ├─ empty.debug.png
│  ├─ building.png
│  ├─ building.debug.png
│  └─ report.txt
└─ en_us/
   ├─ empty.png
   ├─ empty.debug.png
   ├─ building.png
   ├─ building.debug.png
   └─ report.txt
```

## Watch mode

Use `--watch` while editing your Screen, Menu, language files, overlay, or runtime dump:

```powershell
mc-gui-lint `
  examples/generic_machine/MachineScreen.java `
  --menu examples/generic_machine/MachineMenu.java `
  --lang examples/generic_machine/ja_jp.json `
  --lang examples/generic_machine/en_us.json `
  --all-presets `
  --output gui-preview `
  --watch
```

The command performs an initial render and then watches only the input files.
Generated PNGs and reports do not trigger another rebuild.

Lint errors do not stop the watcher. A temporarily half-written file caused by an editor save is reported, and the next change can recover normally.

Change the polling interval if needed:

```bash
--watch-interval 0.15
```

The default is `0.35` seconds.

## Screen and Menu are separate layers

The core model intentionally treats visible decoration and actual click targets separately:

```text
Screen decorative slot frame
            ↓ compare
Menu actual clickable slot
            ↓
state-dependent rendering
```

This catches problems where a slot looks correctly positioned but the real Menu slot is shifted.

A common relationship is:

```text
Screen frame: 18x18
Menu slot:    16x16
Inset:        1px
```

## Current lint checks

| Code | Meaning |
|---|---|
| `SLOT_FRAME_MISMATCH` | Decorative frame does not match the actual Menu slot |
| `SLOT_OVERLAP` | Menu slots overlap |
| `SLOT_OUTSIDE_IMAGE` | A slot extends outside the GUI |
| `TEXT_SLOT_OVERLAP` | Text overlaps a slot frame |
| `TEXT_BUTTON_OVERLAP` | Text overlaps a button |
| `TEXT_PROGRESS_OVERLAP` | Text overlaps a progress bar |
| `TEXT_RIGHT_CLIPPED` | Text extends beyond the right edge |
| `OUT_OF_GUI_BOUNDS` | An element extends outside the GUI |
| `CLICK_RENDER_MISMATCH` | Click bounds differ from rendered bounds |
| `BUTTON_TEXT_OVERFLOW` | Button text exceeds its usable width |
| `ELEMENT_TOUCHING` | Elements have zero spacing |

`BUTTON_TEXT_OVERFLOW` is currently a warning rather than an error.

## Debug PNG colors

- **Green**: Screen slot frame matches the Menu slot
- **Red**: slot position or size mismatch
- **Yellow**: element involved in a lint issue
- **Blue**: Menu slot or click bounds
- **Purple**: state-dependent region

## Supported Java patterns

`mc-gui-lint` is intentionally not a Java compiler.
It evaluates common layout expressions that can be resolved safely.

Examples:

```java
leftPos + 8
topPos + 17
8 + column * 18
97 + row * 18
```

Common Menu slots:

```java
addSlot(new Slot(container, 0, 44, 62));
```

Simple loops:

```java
for (int column = 0; column < 9; column++) {
    addSlot(new Slot(
        inventory,
        column,
        8 + column * 18,
        155
    ));
}
```

Typical unbraced and nested inventory loops are supported as well.

Common Screen patterns include:

```java
graphics.fill(...);
graphics.drawString(...);

Button.builder(Component.translatable("gui.example.action"), ...)
    .bounds(leftPos + 106, topPos + 24, 63, 20);
```

Simple drawing helpers such as `drawSlot(...)` are expanded for common layouts.

If the extractor cannot safely resolve an expression, it reports an `UNRESOLVED_...` or `APPROXIMATED_...` message instead of silently guessing.

## Localization

Pass one or more Minecraft language JSON files:

```bash
--lang ja_jp.json
--lang en_us.json
```

The tool resolves `Component.translatable(...)` and handles common placeholders:

```text
%s
%1$s
%2$s
%%
```

This makes it possible to detect layouts that fit in one language but overflow in another.

## YAML / JSON input

Java parsing is optional. You can describe a preview directly:

```yaml
screen:
  image_width: 176
  image_height: 179

viewport:
  width: 1920
  height: 1080
  gui_scale: 3

state:
  progress_ticks: 333
  duration_ticks: 1200
  power: 16000

elements:
  - type: text
    id: power
    x: 112
    y: 72
    text: "Power: {power}"

  - type: progress
    id: progress
    x: 8
    y: 78
    w: 88
    h: 4
    value: state.progress_ticks
    max: state.duration_ticks

menu_slots:
  - index: 0
    name: input
    x: 36
    y: 58
    w: 16
    h: 16
```

Run it with:

```bash
mc-gui-lint preview.yaml --output gui-preview
```

## Overlay files

Use `--overlay` when Java extraction gets most of the layout right but a small amount of information needs to be supplied manually:

```bash
mc-gui-lint \
  MachineScreen.java \
  --menu MachineMenu.java \
  --overlay preview-overrides.yaml \
  --output gui-preview
```

Conceptually:

```text
Java extraction
      ↓
overlay YAML / JSON
      ↓
runtime dump
```

Later sources take precedence.

## Runtime dump

Static parsing cannot know every runtime value, such as:

- synchronized Menu data
- current ItemStacks
- runtime-created slots
- effective GUI scale
- values behind complex branches

A development-only helper is included at:

```text
integration/GuiDebugDump.java
```

Then pass the generated JSON with:

```bash
mc-gui-lint \
  MachineScreen.java \
  --menu MachineMenu.java \
  --runtime-dump machine-runtime.json \
  --output gui-preview
```

## GUI scale and resolution

The preview derives logical GUI size from the physical resolution and GUI scale:

```text
physical resolution
        ↓ GUI scale
logical GUI resolution
        ↓
Screen.width / Screen.height
        ↓
leftPos / topPos
```

The positioning model follows the usual container-screen relationship:

```java
leftPos = (width - imageWidth) / 2;
topPos  = (height - imageHeight) / 2;
```

## Inspecting extracted IR

Use `--dump-ir` to see what the Java extractor understood:

```bash
mc-gui-lint \
  MachineScreen.java \
  --menu MachineMenu.java \
  --dump-ir gui-preview/extracted.yaml
```

This is useful when adding support for a new Java pattern.

## CI usage

The CLI exits with a non-zero status if at least one `ERROR` is found.
Warnings do not currently fail the command.

```bash
mc-gui-lint \
  MachineScreen.java \
  --menu MachineMenu.java \
  --lang ja_jp.json \
  --lang en_us.json \
  --all-presets
```

## Limitations

The project does not attempt to perfectly emulate Minecraft.
Current limitations include:

- font widths are approximate rather than pixel-perfect Minecraft metrics
- texture atlas rendering is incomplete
- `blit` is not fully reproduced
- shaders are out of scope
- 3D entity rendering is out of scope
- arbitrary Java cannot be evaluated
- server/client synchronization itself is not tested
- not every Minecraft widget is supported

The intended workflow is:

```text
edit code
   ↓
preview + lint
   ↓
check states and locales
   ↓
fix obvious layout issues
   ↓
verify in Minecraft
```

## Publishing this repository to GitHub

If you downloaded the prepared archive, extract it so that `README.md`, `pyproject.toml`, and `mc_gui_lint/` are at the repository root, then run:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_NAME/mc-gui-lint.git
git push -u origin main
```

The repository already contains `.gitignore`, an MIT `LICENSE`, packaging metadata, generic fixtures, and a GitHub Actions test workflow.

## Development

Run the tests:

```bash
python -m unittest discover -s tests -v
```

Repository layout:

```text
mc-gui-lint/
├─ mc_gui_lint/
├─ .github/workflows/tests.yml
├─ integration/
├─ examples/
│  └─ generic_machine/
├─ tests/
├─ .gitignore
├─ LICENSE
├─ pyproject.toml
├─ README.md
└─ requirements.txt
```

## License

MIT License. See [LICENSE](LICENSE).

The fixtures under `examples/generic_machine/` were written specifically for this repository and are not copied from an external Minecraft mod.
