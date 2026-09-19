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
| `TEXT_REGION_OVERFLOW` | Legacy `text_regions` text does not fit its declared rectangle |
| `ELEMENT_OUT_OF_REGION` | An element does not fit its `constraints.<id>.inside` rectangle |
| `ELEMENT_ALIGNMENT_MISMATCH` | An element is not left/center/right aligned within its declared region |
| `GAP_TOO_SMALL` | A relative `right_of` / `left_of` / `below` / `above` spacing constraint is violated |
| `CONSTRAINT_TARGET_NOT_FOUND` | A relative constraint references an unknown element ID |
| `UNKNOWN_ALIGNMENT` | A constraint uses an alignment other than `left`, `center`, or `right` |
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
- **Cyan**: expected rectangle declared by `constraints.<id>.inside` or legacy `text_regions`

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

## Dynamic translation keys

A common Minecraft pattern such as:

```java
Component.translatable("gui.example.formation." + menu.formation())
```

is supported when the Menu accessor resolves to an **integer state value** supplied by a preset, overlay, or runtime dump. The extractor stores a safe template such as:

```text
gui.example.formation.{formation}
```

and resolves the final key only after the selected preset has been applied.

Only top-level concatenation of Java string literals and no-argument `menu.foo()` / `menu.getFoo()` accessors is accepted. More complex Java expressions remain unresolved and keep the normal placeholder warning behavior.

A six-state, Japanese/English regression fixture is included under `examples/dynamic_translation_key/`.

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


### Numeric constants and simple PoseStack transforms

Coordinate expressions support primitive `static final` integer/float constants, simple arithmetic, and `Math.round(...)`. The extractor also follows linear `pushPose / translate / scale / popPose` sequences inside the same method.

```java
private static final float LABEL_SCALE = 0.8F;
private static final int LABEL_X = Math.round(120 * LABEL_SCALE);

graphics.pose().pushPose();
graphics.pose().translate(10, 4, 0);
graphics.pose().scale(LABEL_SCALE, LABEL_SCALE, 1.0F);
graphics.drawCenteredString(font, title, LABEL_X, 18, 0xFFFFFF);
graphics.pose().popPose();
```

Transforms hidden behind helpers/lambdas or complex control flow are intentionally left to overlay hints.

### Simple conditional rendering

v0.1.8 tracks straightforward `if / else if / else` blocks in the same Java method and turns common Menu state checks into visibility conditions. This lets presets change which elements are actually rendered instead of only changing their text/value.

```java
if (menu.isWorking()) {
    graphics.drawString(font, "Working", 8, 8, 0xFFFFFF);
} else {
    graphics.drawString(font, "Idle", 8, 8, 0xFFFFFF);
}

if (menu.getPower() > 0 && !menu.isBroken()) {
    graphics.fill(8, 24, 40, 28, 0xFF00FF00);
}
```

Supported condition syntax is intentionally small: no-argument Menu getters/methods, simple fields, `!`, `&&`, `||`, numeric/boolean literals, arithmetic, and comparison operators. The extracted IR records `visibility_conditions`, and `state`/preset values are applied before elements are parsed, linted, and rendered.

```yaml
presets:
  idle:
    state:
      is_working: false
  working:
    state:
      is_working: true
```

Unsupported conditions emit `UNRESOLVED_IF_CONDITION`. The affected element is kept visible rather than being hidden on an unsafe guess. Conditions propagated through helper/lambda calls are still out of scope.

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

### Layout constraints and scale hints

Overlay-only hints are keyed by extracted element ID, so you do not need to replace the whole `elements` list:

```yaml
screen_scale: 0.9

element_overrides:
  power_text:
    scale: 0.8

constraints:
  title:
    inside: [8, 6, 160, 12]
    align: center

  power_text:
    right_of: power_icon
    gap: 4

  start_button:
    below: progress
    gap: 6
```

`inside` accepts either `[x, y, w, h]` or a mapping with `x`, `y`, `w`, and `h`. Coordinates and `gap` values are GUI-local values before `screen_scale` is applied. An element outside its declared region emits `ELEMENT_OUT_OF_REGION`. The debug PNG draws declared regions in cyan.

`align` with an `inside` region checks horizontal `left`, `center`, or `right` alignment. For text elements it also defines how the element's `x` coordinate is interpreted as a text anchor, so `align: center` matches `drawCenteredString(...)`.

Relative constraints use resolved element bounds after PoseStack/overlay transforms. `right_of`, `left_of`, `below`, and `above` accept another element ID, while `gap` defines the minimum required spacing. A violated spacing emits `GAP_TOO_SMALL`; an unknown target emits `CONSTRAINT_TARGET_NOT_FOUND`. Negative actual gaps therefore catch overlap for relationships that you explicitly declare without enabling a noisy all-elements overlap check.

The v0.1.5 `text_regions` syntax remains supported for compatibility and still reports `TEXT_REGION_OVERFLOW`:

```yaml
text_regions:
  text_1:
    x: 80
    y: 18
    w: 88
    h: 10
    align: center
```

`screen_scale` scales Screen-side rendered elements but intentionally leaves Menu slot coordinates unchanged, so render/click mismatches remain visible. `element_overrides.<id>.scale` acts like an otherwise-unseen `PoseStack.scale(...)`: it scales that element's coordinates and rendered extent about the GUI origin. These hints are intended for transforms hidden behind helpers such as `scaled(graphics, .8F, () -> ...)`.

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
- arbitrary Java cannot be evaluated; conditional rendering only follows simple same-method `if / else` expressions
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

Screen-side support includes common patterns such as:

```java
graphics.fill(...);
graphics.drawString(...);

Button.builder(Component.translatable("gui.example.action"), ...)
    .bounds(leftPos + 106, topPos + 24, 63, 20);
```

### Button helpers

Small button helper chains declared in the same Screen class are expanded from `init()`.
This lets application code keep reusable helpers instead of duplicating button rectangles just for the linter.

```java
@Override
protected void init() {
    addActionButton(
        leftPos + 8,
        topPos + 20,
        Component.translatable("gui.example.action")
    );
}

private void addActionButton(int x, int y, Component label) {
    addRenderableWidget(
        Button.builder(label, button -> {})
            .bounds(x, y, 44, 20)
            .build()
    );
}
```

Supported helper behavior is intentionally limited:

- integer helper arguments must be statically evaluable;
- whole-expression values such as a `Component label` can be forwarded into the helper;
- nested button helpers are expanded up to a small fixed depth;
- arbitrary Java execution is not attempted.

If a numeric helper argument cannot be resolved, extraction falls back to `UNRESOLVED_BUTTON_HELPER_ARGUMENT` / `UNRESOLVED_BUTTON_BOUNDS` warnings instead of inventing coordinates.
