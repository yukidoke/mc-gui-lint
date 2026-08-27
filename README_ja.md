# mc-gui-lint

[English README](README.md)

`mc-gui-lint` は、Minecraft のコンテナGUI向けの**静的プレビュー + レイアウトLintツール**です。

主に `AbstractContainerScreen` / `AbstractContainerMenu` 系のGUIを対象としており、座標を少し変更するたびにMinecraftを起動して画面を確認する手間を減らすことを目的としています。

このツールの目的はMinecraft GUIを完全にエミュレートすることではありません。  
**実機確認の前にレイアウト不良をできるだけ検出すること**が目的です。

## 主な機能

- よくある `Screen.java` / `Menu.java` のレイアウトパターンを解析
- 通常PNG / debug PNGの生成
- Screen側の装飾slot枠と、Menu側の実slot座標を比較
- 文字切れ、重なり、GUI領域外へのはみ出しを検出
- ボタンラベルの幅超過を検出
- 単純な状態依存progress barを抽出
- empty / building / almost-finished などの状態presetを生成
- Minecraftのlanguage JSONから `Component.translatable(...)` を解決
- 複数localeを一括監査
- Java静的解析で足りない情報をYAML / JSON overlayで補完
- 開発用クライアントから取得したruntime dumpを適用
- 入力ファイルを監視し、PNG / Lint結果を自動更新
- `ERROR` がある場合は非0のexit codeを返す

## 必要環境

- Python 3.10+
- Pillow
- PyYAML

## インストール

リポジトリをcloneし、editable installします。

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

インストール後はCLIを直接呼べます。

```bash
mc-gui-lint --help
```

パッケージとして直接実行することもできます。

```bash
python -m mc_gui_lint --help
```

## Quick Start

汎用fixtureが以下に含まれています。

```text
examples/generic_machine/
```

これらのJavaファイルは**パーサ用fixture**です。importやMinecraft側の初期化コードは意図的に省略されており、単体のModとしてコンパイルすることは想定していません。

日本語・英語の両方でプレビューする例:

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

出力例:

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

## Watchモード

Screen / Menu / language JSON / overlay / runtime dumpを編集中に自動更新したい場合は `--watch` を使います。

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

最初に一度レンダリングした後、**入力ファイルだけ**を監視します。  
生成されたPNGやreportは再ビルドのトリガーになりません。

Lint ERRORが出てもwatchは停止しません。エディタの保存途中などで一時的にファイルが壊れた場合もエラーを表示して監視を継続し、次の変更で復帰できます。

監視間隔は変更できます。

```bash
--watch-interval 0.15
```

デフォルトは `0.35` 秒です。

## ScreenとMenuを別レイヤーとして扱う

`mc-gui-lint` では、見た目の装飾と実際のクリック領域を意図的に分けて扱います。

```text
Screenの装飾slot枠
        ↓ 比較
Menuの実クリック可能slot
        ↓
状態依存描画
```

これにより、

- 見た目は正しいがクリック位置だけずれている
- Menuのslotが1pxずれている
- inventory枠と実slotが一致していない

といった問題を検出できます。

一般的なslotの関係:

```text
Screen frame: 18x18
Menu slot:    16x16
Inset:        1px
```

## 現在のLint項目

| Code | 内容 |
|---|---|
| `SLOT_FRAME_MISMATCH` | 装飾slot枠と実Menu slotが一致しない |
| `SLOT_OVERLAP` | Menu slot同士が重なっている |
| `SLOT_OUTSIDE_IMAGE` | slotがGUI領域外へはみ出している |
| `TEXT_SLOT_OVERLAP` | 文字列とslot枠が重なっている |
| `TEXT_BUTTON_OVERLAP` | 文字列とボタンが重なっている |
| `TEXT_PROGRESS_OVERLAP` | 文字列と進捗バーが重なっている |
| `TEXT_RIGHT_CLIPPED` | 文字列がGUI右端を超えている |
| `OUT_OF_GUI_BOUNDS` | GUI要素が領域外へはみ出している |
| `CLICK_RENDER_MISMATCH` | click領域と描画位置が一致しない |
| `BUTTON_TEXT_OVERFLOW` | ボタン文字列が利用可能幅を超えている |
| `ELEMENT_TOUCHING` | 要素間隔が0px |

`BUTTON_TEXT_OVERFLOW` は現在 `ERROR` ではなく `WARNING` 扱いです。

## Debug PNGの色

- **緑**: Screen側slot枠とMenu slotが一致
- **赤**: slot位置またはサイズが不一致
- **黄**: Lint対象になった要素
- **青**: Menu slot / click領域
- **紫**: 状態依存領域

## 対応しているJavaパターン

`mc-gui-lint` はJavaコンパイラではありません。

静的に安全に評価できる、よくあるGUI座標式を対象にしています。

例:

```java
leftPos + 8
topPos + 17
8 + column * 18
97 + row * 18
```

一般的なMenu slot:

```java
addSlot(new Slot(container, 0, 44, 62));
```

単純なループ:

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

典型的なinventory配置であれば、波括弧なしループやnested loopにも対応しています。

Screen側では、以下のようなパターンに対応しています。

```java
graphics.fill(...);
graphics.drawString(...);

Button.builder(Component.translatable("gui.example.action"), ...)
    .bounds(leftPos + 106, topPos + 24, 63, 20);
```

また、典型的な `drawSlot(...)` などの単純な描画helperも展開します。

安全に解決できない式については、推測で処理せず、

```text
UNRESOLVED_...
APPROXIMATED_...
```

として報告します。

## Localization

Minecraftのlanguage JSONを1つ以上指定できます。

```bash
--lang ja_jp.json
--lang en_us.json
```

`Component.translatable(...)` を解決し、以下の一般的なplaceholderへ対応しています。

```text
%s
%1$s
%2$s
%%
```

これにより、**日本語では収まるが英語でははみ出す**といったlocale依存のレイアウト問題を検出できます。

## YAML / JSON入力

Java解析は必須ではありません。プレビュー定義を直接記述することもできます。

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

実行:

```bash
mc-gui-lint preview.yaml --output gui-preview
```

## Overlay

Java静的解析でほとんど取れているものの、一部だけ手動で補いたい場合は `--overlay` を使います。

```bash
mc-gui-lint \
  MachineScreen.java \
  --menu MachineMenu.java \
  --overlay preview-overrides.yaml \
  --output gui-preview
```

概念的な優先順位:

```text
Java extraction
      ↓
overlay YAML / JSON
      ↓
runtime dump
```

後から与えた情報ほど優先されます。

## Runtime Dump

静的解析だけでは、すべての実行時情報は取得できません。

たとえば:

- 同期されたMenu data
- 現在のItemStack
- 実行時生成slot
- 実際のGUI Scale
- 複雑な条件分岐の先にある値

などです。

開発専用helperとして以下を同梱しています。

```text
integration/GuiDebugDump.java
```

取得したJSONを指定します。

```bash
mc-gui-lint \
  MachineScreen.java \
  --menu MachineMenu.java \
  --runtime-dump machine-runtime.json \
  --output gui-preview
```

## GUI Scaleと解像度

プレビューでは物理解像度とGUI ScaleからGUI論理解像度を計算します。

```text
physical resolution
        ↓ GUI scale
logical GUI resolution
        ↓
Screen.width / Screen.height
        ↓
leftPos / topPos
```

配置は一般的な `AbstractContainerScreen` の関係に従います。

```java
leftPos = (width - imageWidth) / 2;
topPos  = (height - imageHeight) / 2;
```

## 抽出IRを確認する

`--dump-ir` を指定すると、Java抽出器がどのようにコードを解釈したかを確認できます。

```bash
mc-gui-lint \
  MachineScreen.java \
  --menu MachineMenu.java \
  --dump-ir gui-preview/extracted.yaml
```

未対応Javaパターンを調査するときに便利です。

## CIで使う

Lintで `ERROR` が1件以上ある場合、CLIは非0で終了します。  
`WARNING` だけの場合は現在成功扱いです。

```bash
mc-gui-lint \
  MachineScreen.java \
  --menu MachineMenu.java \
  --lang ja_jp.json \
  --lang en_us.json \
  --all-presets
```

GitHub Actionsなどへそのまま組み込めます。

## 現在の制約

Minecraftの完全再現は目的としていません。

現在の主な制約:

- フォント幅はMinecraft Fontのpixel-perfectな値ではなく概算
- texture atlasの描画は不完全
- `blit` は完全再現していない
- shaderは対象外
- 3D Entity描画は対象外
- 任意のJavaコードは評価できない
- server/client同期処理そのものは検証しない
- Minecraftの全Widgetには対応していない

想定ワークフロー:

```text
コード編集
   ↓
Preview + Lint
   ↓
状態 / locale別チェック
   ↓
明らかな配置不良を修正
   ↓
Minecraftで最終確認
```

このツールはMinecraftでの確認を完全になくすのではなく、**実機確認回数を減らすこと**を目的としています。

## 開発

テスト:

```bash
python -m unittest discover -s tests -v
```

構成:

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
├─ README_ja.md
└─ requirements.txt
```

## License

MIT Licenseです。詳細は [LICENSE](LICENSE) を参照してください。

`examples/generic_machine/` 以下のfixtureは、このリポジトリ向けに新規作成した汎用コードであり、外部Minecraft Modからコピーしたものではありません。
