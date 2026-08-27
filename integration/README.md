# Runtime dump integration

静的解析では解けないMenuの実slot座標・同期値・ItemStackを、開発用MinecraftからJSONへdumpして上書きできます。

`GuiDebugDump.java` を開発用ソースへ置き、`AbstractContainerScreen` サブクラスから一時的に呼びます。

```java
int guiScale = (int) this.minecraft.getWindow().getGuiScale();

GuiDebugDump.dump(
    Path.of("run/gui-dump/machine.json"),
    getClass().getName(),
    this.minecraft.getWindow().getWidth(),
    this.minecraft.getWindow().getHeight(),
    guiScale,
    this.width,
    this.height,
    this.leftPos,
    this.topPos,
    this.imageWidth,
    this.imageHeight,
    this.menu.slots,
    Map.of(
        "power", this.menu.getPower(),
        "progress_ticks", this.menu.getProgressTicks(),
        "duration_ticks", this.menu.getDurationTicks()
    )
);
```

生成JSONを重ねてプレビューします。

```bash
python -m mc_gui_lint MachineScreen.java \
  --menu MachineMenu.java \
  --runtime-dump run/gui-dump/machine.json \
  --output build/gui-preview
```

優先順位は概ね、

```text
Java静的抽出 < overlay YAML < runtime dump
```

です。runtime dump側のMenu slot、state、ItemStack、viewportを優先します。
