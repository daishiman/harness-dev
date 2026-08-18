# C14 `render-diagram-svg.py` 受入テスト (P04-C14-01 で赤に固定)

実装 (`plugins/guide-doc-generator/scripts/render-diagram-svg.py`) より先に判定基準をここで確定させた。
P05 の実装側がテストを自分に都合よく書き換えられないよう、**契約はすべて設計正本から起こしている**。

- 契約の正本: `plugin-plans/guide-doc-generator/briefs/script-brief-C14.json`
  (`argv` / `stdout` / `exit_codes` / `write_scope` / `single_writer` / `algorithm` /
  `failure_modes` / `acceptance_checks`)
- component 定義: `plugin-plans/guide-doc-generator/component-inventory.json` の C14
- 追加確定: `briefs/RESOLUTION-P03.md` (Y-02 = CR-EXT) / `briefs/RESOLUTION-R21.md` (C55 / C56)
- 外部参照の判定規則: `briefs/script-brief-C16.json` の `canonical_rules.external_reference_rule`
  と `goal-spec.json` の C60 (= SC-10、`data:` 以外を一律違反とする許可列挙)

C14 の責務 (R07) は「装飾でなく理解を助ける図解」。テストはその担保である
**意味フィールドの fail-closed 検査** (欠落・件数超過・折返し超過で exit 1) と
**決定論** (バイト一致・座標整数化・id 採番規則) を中心に固定してある。

## 実行

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/render-diagram-svg.py -p 'test_*.py'
```

実装が無いあいだは全件が赤 (**failure**) になるのが正しい状態。
`_harness.require_script()` が実体不在を `AssertionError` へ変換しているため、
「実装が無い」も「契約を満たさない」も同じ形の失敗として現れ、`errors` は 0 件になる。
`setUpClass` では一切例外を投げていない (unittest が errors へ分類してしまうため)。

**赤の記録 (実装前):** `Ran 166 tests` / `FAILED (failures=256)` / errors 0
(failures が test 数を上回るのは `subTest` がパターンごとに独立計上されるため)。

## ファイル構成

| ファイル | 固定した内容 |
| --- | --- |
| `_harness.py` | 共通土台 (実体解決・subprocess 起動・6 パターン fixture・SVG 走査)。テストは持たない |
| `test_argv_and_exit_codes.py` | argv と exit code の契約、stdout の断片としての形、write_scope=none |
| `test_input_violations.py` | 違反系入力で exit 1 になる系 (パターン語彙・必須フィールド・件数・座標範囲・折返し超過) |
| `test_determinism.py` | 同一入力の再現性、golden 比較、標準ライブラリのみ、id 採番、座標の整数化 |
| `test_svg_contract.py` | 外部参照ゼロ・絵文字ゼロ・色トークン間接化・a11y 属性・エスケープ |
| `test_patterns.py` | 6 パターンの描画責務、テキスト幅見積りと折返し、module API、C56 境界 |
| `record_goldens.py` | golden 記録用の補助 (テストではない)。実装後に 1 回だけ実行する |

## 契約 id ↔ テストの対応表

| 契約 id | 出所 | テスト |
| --- | --- | --- |
| AC-C14-1 | 6 パターンの最小 fixture が golden とバイト一致 | `test_determinism.GoldenSvgTest` 2 件 (+ `record_goldens.py`) |
| AC-C14-2 | 2 回実行の sha256 一致 (乱数・時刻・辞書順依存が無い) | `test_determinism.ByteReproducibilityTest` 6 件 + `NonDeterminismSourceTest.test_source_has_no_nondeterministic_calls` |
| AC-C14-3 | `http://` `https://` `//` `xlink:href` の外部参照 0 件 | `test_svg_contract.ExternalReferenceTest` 8 件 |
| AC-C14-4 | 絵文字レンジ (U+1F300-1FAFF / U+2600-27BF / U+FE0F) 0 件 | `test_svg_contract.EmojiTest` 2 件 |
| AC-C14-5 | `var()` フォールバック以外に 16 進カラーリテラル 0 件 (checklist C14) | `test_svg_contract.ColorTokenTest` 5 件 |
| AC-C14-6 | 未知パターン / pattern 不一致 / 件数超過 / 折返し 4 行で exit 1 + キーパス | `test_input_violations` の全 8 クラス 45 件 |
| AC-C14-7 | 不在パス / 壊れた JSON / `--width=0` で exit 2 | `test_argv_and_exit_codes.UnreadableInputTest` 4 件 + `WidthArgvTest` 4 件 + `MissingArgvTest` 5 件 |
| AC-C14-8 | 標準ライブラリのみ・yaml import 0 件 (checklist C27) | `test_determinism.StdlibOnlyTest` 4 件 |
| argv `--width` (既定 860) | brief `argv[2]` | `WidthArgvTest.test_default_width_is_860` ほか 4 件 |
| stdout 契約 (`<svg`…`</svg>` + 末尾改行 1 個 / XML 宣言なし) | brief `stdout` | `test_argv_and_exit_codes.StdoutShapeTest` 7 件 |
| 手順 4 (パターン別の必須フィールドと件数範囲) | brief `algorithm[4]` | `Flow/Compare/Hierarchy/Cycle/Matrix/VersusFieldTest` 33 件 |
| 手順 5 (east_asian_width W/F/A = 1.00em、他 0.55em) | brief `algorithm[5]` | `test_patterns.TextWrapTest.test_wide_characters_are_measured_wider_than_narrow_ones` / `test_ambiguous_width_characters_are_measured_as_wide` |
| 手順 6 (`<tspan x dy>` / dy = 0 → 1.45em / 上限行数で exit 1) | brief `algorithm[6]` | `TextWrapTest` 6 件 + `test_input_violations.TextOverflowTest` 7 件 |
| 手順 7 (パターン別座標・整数丸め) | brief `algorithm[7]` | `test_patterns.PatternRenderingTest` 14 件 + `test_determinism.CoordinateRoundingTest` 2 件 |
| 手順 8 (`viewBox="0 0 W H"` / width・height 属性を出さない) | brief `algorithm[8]` | `WidthArgvTest` 3 件 + `test_patterns.PatternRenderingTest.test_height_grows_with_content` |
| 手順 9 (色は `var(--token, #hex)`) | brief `algorithm[9]` | `ColorTokenTest` 5 件 |
| 手順 10 (`role="img"` / `<title>` / `<desc>` / 装飾の `aria-hidden`) | brief `algorithm[10]` | `test_svg_contract.AccessibilityTest` 7 件 |
| 手順 11 (id は `hbdg-{pattern|diagram.id}-{連番}`) | brief `algorithm[11]` | `test_determinism.NonDeterminismSourceTest` 5 件 |
| 手順 12 (`html.escape(quote=True)` / 2 スペース / `\n` / 末尾改行 1 個) | brief `algorithm[12]` | `test_svg_contract.EscapingTest` 4 件 + `StdoutShapeTest` 3 件 |
| `write_scope=none` | brief `write_scope` | `test_argv_and_exit_codes.WriteScopeTest` 2 件 |
| module API `render_diagram(spec, pattern, width) -> str` | brief `dependencies.invoked_by` | `test_patterns.ModuleApiTest` 5 件 |
| C55 / SC-09 (DIAGRAM は `<svg>` と描画要素を持つ) | `RESOLUTION-R21.md` / `script-brief-C16.json` SC-09 | `test_patterns.PatternRenderingTest.test_every_pattern_emits_drawing_elements` / `test_no_placeholder_text_is_emitted` |
| C56 (概念図は screenshot の代替にならない) | `RESOLUTION-R21.md` | `test_patterns.AssetRoleBoundaryTest` 2 件 |
| C60 / SC-10 (`data:` 以外を一律違反とする許可列挙) | `goal-spec.json` C60 / `task-specs/P04-x-02.md` | `ExternalReferenceTest` 8 件 (`_harness.external_reference_hits`) |

## gaps (ブリーフ未定義のため、テスト側で解釈を置いた点)

| what | why |
| --- | --- |
| `compare.cells` のデータ構造 | brief 手順 4 は「`cells` は items×axes の全マスが埋まっていること」としか書かず、2 次元配列なのかオブジェクトの配列なのかを定めていない。fixture は **行 = items / 列 = axes の 2 次元配列** と解釈した。実装が別形を採るなら `_harness.compare_spec` と `test_input_violations.CompareFieldTest` の期待値を先に P04 側で改訂する必要がある |
| ノード識別子のキー名 | brief の stderr 契約は「該当ノード id」と書くが、`steps[]` / `children[]` の必須フィールドは `label` だけで `id` は列挙されていない。fixture は各ノードへ `id` を持たせ、折返し超過の stderr が `id` 値を含むことを固定した。`id` を持たない入力での stderr の書式は未定義のまま残している |
| `hierarchy` の「深さ 2-3」の数え方 | root を第 1 層と数えるか子を第 1 層と数えるかが未定義。root を第 1 層と数え、root + 2 段のネスト (計 3 層) を上限、root + 3 段を exit 1 と解釈した |
| `versus` の bullets 最大行数 (2 行) と枠幅の関係 | brief 手順 6 は bullets の最大行数を 2 と定めるが、versus カラムの内寸 (枠幅・padding) は手順 7 に「左右 2 カラムの rect」としか書かれていない。折返し超過テストは 200 文字超の極端な入力でだけ判定し、境界値は固定していない |
| `xmlns` 属性の可否 | AC-C14-3 が `//` の検出 0 件を要求するため、`xmlns="http://www.w3.org/2000/svg"` を出すと AC に抵触する。HTML への inline 埋め込み前提 (brief `stdout`) では xmlns は不要なので **出さない**と解釈し、`test_no_protocol_relative_reference` で固定した |
| `url(#id)` (同一文書内 fragment) の扱い | C60 の文面は「`data:` 以外を一律違反」だが、`marker-end="url(#hbdg-…)"` のような fragment 参照は取得を発生させない。SC-02 が確立した「取得を発生させない参照は違反ではない」境界を優先し、**fragment は違反としない**と解釈した (`_harness.external_reference_hits`)。C60 の許可列挙を文字どおり適用すると marker が使えなくなるため、P04-x-02 側で SC-10 の文面に fragment の除外を明記することを推奨する |
| `flow` 版組の `gap` / `margin` の値 | 手順 7 は `(W - gap×(n-1) - margin×2)/n` とだけ書き、`gap` と `margin` の数値を定めていない。ノード幅の絶対値は検査せず、**全ノードの幅が等しいこと**と `--width` に応じて折返し上限が動くことだけを固定した |
| `title` / `description` の折返し上限 | 手順 6 が上限行数を定めるのはノード label (3) と bullets (2) だけ。`title` の上限は未定義だが、極端に長い `title` は figure として破綻するため exit 1 を期待するテストを 1 件置いた (`TextOverflowTest.test_overflowing_title_is_exit1`)。上限行数を brief 側で明記することを推奨する |
