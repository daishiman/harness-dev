# C17 `verify-handout-a11y-print.py` 受入テスト (P04-C17-01 で赤に固定)

実装 (`plugins/guide-doc-generator/scripts/verify-handout-a11y-print.py`) より先に判定基準を確定させるためのテスト群。
**契約の正本は `plugin-plans/guide-doc-generator/briefs/script-brief-C17.json` であり、ここには判定規則を複製しない。**
テストは「契約をどう観測するか」だけを持ち、規則そのものを再定義しない。

## 実行

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/verify-handout-a11y-print.py -p 'test_*.py'
```

Python 3.10+ の標準ライブラリのみ。ブラウザ・外部ツール・ネットワークは使わない。
判定はすべて **生成 HTML 文字列に対する静的検査** を CLI 経由で観測する形で行う。

## 赤の状態 (P04 時点)

実装が存在しないため 187 件すべてが **failure** として落ちる (errors ではない)。
`hb_c17.require_script()` が `AssertionError` を投げる設計にしてあるので、
「import 例外で落ちているだけ」の空テストにはなっていない。

```
Ran 187 tests
FAILED (failures=187)
```

## ファイル構成

| ファイル | 件数 | 固定している範囲 |
| --- | --- | --- |
| `hb_c17.py` | (テストではない) | 共通ハーネス。stdout/stderr のパーサ、12 detection の固定順、PASS 土台 fixture と `mutate()` |
| `test_cli_contract.py` | 49 | argv / exit code / stdout / stderr / OUT-OF-SCOPE 節 / write_scope / json-report / 冪等性 |
| `test_a11y_aria.py` | 37 | A11Y-01 aria-pressed / A11Y-02 aria-selected / A11Y-03 アクセシブル名 |
| `test_a11y_table_svg.py` | 19 | A11Y-04 th の scope / A11Y-05 装飾 SVG と意味を持つ SVG |
| `test_a11y_css.py` | 25 | A11Y-06 `:focus-visible` / A11Y-07 `prefers-reduced-motion` |
| `test_print.py` | 29 | PRINT-01..04 と、@media print / `<style>` の分割統合 |
| `test_sticky_offset.py` | 11 | STICKY-01 アンカーオフセット補正 (CSS と JS の両系) |
| `test_anchor_and_failure_modes.py` | 17 | 検査アンカー不在 (data-hb-part ゼロ) / 未解析 CSS / 非資料 HTML |

## 契約 id との対応表

### 受入検査 (`acceptance_checks`)

| 契約 id | 固定した内容 | テスト |
| --- | --- | --- |
| AC-C17-01 | 完備 HTML で exit 0・`RESULT: PASS`・12 detection 行・stderr 空 | `test_cli_contract.TestPassPath` (7) |
| AC-C17-02 | `aria-pressed` の文字列がコメントにあるだけでは PASS にしない | `TestA11y01AriaPressed.test_string_presence_elsewhere_does_not_pass` |
| AC-C17-03 | `data-hb-part` ゼロで exit 1。A11Y-01/02/05 は FAIL 計上 (保留にしない) | `TestMissingAnchor` (7) |
| AC-C17-04 | `aria-selected="true"` が 2 個 → A11Y-02 に違反 1 件 | `TestA11y02AriaSelected.test_two_selected_tabs` |
| AC-C17-05 | `:focus-visible` 規則が無く `outline:none` だけ → A11Y-06 違反 | `TestA11y06FocusVisible.test_no_focus_visible_rule_with_outline_none` |
| AC-C17-06 | reduce ブロックで animation だけ無効化 → scroll-behavior と transition の欠落が出る | `TestA11y07ReducedMotion.test_animation_only_is_violation` / `test_violation_message_names_the_missing_properties` |
| AC-C17-07 | sticky セレクタに print 側の指定が無い → PRINT-02 違反 1 件 | `TestPrint02StickyNeutralized.test_sticky_selector_without_print_override` |
| AC-C17-08 | `@media print` 不在 → PRINT-01 違反、PRINT-02..04 も未充足として計上 | `TestPrint01MediaPrintExists.test_no_media_print_block` / `test_print_02_to_04_also_counted_when_media_print_missing` |
| AC-C17-09 | `scroll-margin-top` はあるが JS に `getBoundingClientRect` が無い → STICKY-01 違反 1 件 | `TestSticky01AnchorOffset.test_css_only_without_js_measurement` |
| AC-C17-10 | OUT-OF-SCOPE 節に 5 事項 (A4 実版面 / 改ページ実位置 / 実フォーカスリング / JS 実行後 DOM / CSS カスケード) を毎回出す | `TestOutOfScopeSection` (5) |
| AC-C17-11 | `--html` 不在・書き込み不可などは exit 2 + `ERROR` 1 行。品質 FAIL (1) と混ざらない | `TestUsageErrors` (12) |
| AC-C17-12 | 同一入力の 2 回実行で stdout / stderr / json-report がバイト一致 | `TestDeterminism` (6) |

### detection

| detection | 固定した境界 | テストクラス |
| --- | --- | --- |
| A11Y-01 | 欠落 / 不正値 / 大文字 / 空値 / `[role="button"]` も対象 / `data-hb-single` で true は高々 1 個 (0 個は可) / `data-hb-part-role="aux"` が唯一の除外口 / B08・B15 外のボタンは対象外 / 複数欠落は個別計上 | `TestA11y01AriaPressed` |
| A11Y-02 | true が 2 個・0 個 / `role="tablist"` 欠落 / `aria-selected` 欠落・不正値 / `aria-controls` の不在・未指定・参照先が tabpanel でない / 非選択 panel の `hidden` 欠落 / 選択 panel の `hidden` 余分 | `TestA11y02AriaSelected` |
| A11Y-03 | アイコンのみのボタン / 空・空白のみの `aria-label` / テキストの無い `<a href>` `<summary>` / label の無い checkbox / `aria-labelledby`・`title` は可 / href の無いアンカーは対象外 / hidden 要素も検査する | `TestA11y03AccessibleName` |
| A11Y-04 | scope 欠落 / thead の th が row / 行頭 th が col / 不正値・空値 / `data-hb-part` 非依存で `<table>` は必ず対象 / 個別計上 | `TestA11y04TableScope` |
| A11Y-05 | (a) テキストを持つ親の中の icon・decor に aria-hidden 必須 / (b) aria-hidden + `<title>` の矛盾 / (c) 名前の供給源が aria-hidden / `data-hb-kind="figure"` は (a) 対象外だが title か aria-label 必須 / `aria-hidden="false"` は非該当 | `TestA11y05Svg` |
| A11Y-06 | 規則不在 / `outline:none`・`0` / `box-shadow` は可 (`none` は不可) / コメントだけでは PASS にしない / (c) の同一セレクタ突合・`*` による充足・カンマ区切りの分割・空白正規化 | `TestA11y06FocusVisible` |
| A11Y-07 | ブロック不在 / scroll-behavior・transition・animation の各欠落 / reduce ブロック内の `scroll-behavior:smooth` / `no-preference` prelude は不可 / (c) JS の `behavior:'smooth'` と `matchMedia`+`prefers-reduced-motion` の共起 (単引用・二重引用の両方) | `TestA11y07ReducedMotion` |
| PRINT-01 | ブロック不在 / 空ブロック / A4 の無い `@page` かつ版面幅の再指定も無い / 版面幅再指定は `@page` の代替になる | `TestPrint01MediaPrintExists` |
| PRINT-02 | sticky・fixed の両方を収集 / print 側の指定なし / `display:none`・`position:relative` は充足 / print 側も sticky なら違反 / 部分列一致の緩和 (`header.pop-header`) / 個別計上 | `TestPrint02StickyNeutralized` |
| PRINT-03 | `display:none` なし / 属性セレクタ形だけ・class 形だけでも充足 / class に memo を含む要素は `data-hb-part` 無しでも対象 / `@media print` 外の `display:none` は不可 / `visibility:hidden` は不可 | `TestPrint03ScreenOnlyUiHidden` |
| PRINT-04 | `break-inside` 欠落 / 見出しの `break-after` 欠落 / 旧 `page-break-inside` 単独は可 / 値 `auto` は不可 / print 外の宣言は数えない | `TestPrint04PageBreaks` |
| STICKY-01 | CSS 単独 / JS 単独 / `scroll-margin-top` が 0・負 / `scroll-padding-top` は可 / JS が sticky 要素を参照していない / script 不在 / section へ到達しないセレクタは不可 | `TestSticky01AnchorOffset` |

### failure_modes

| failure_mode | 固定した内容 | テスト |
| --- | --- | --- |
| 解けない CSS | CSS ネスト・ネストされた `@supports` で exit 1、`unparsed_css_blocks` に位置つき列挙、解ける CSS では空 | `TestUnparsableCss` (6) |
| `data-hb-part` 契約が未実装 | exit 1 + stderr に属性名 | `TestMissingAnchor` |
| `@media print` の分割 | 3 ブロック分割・`<style>` 2 個分割でも単一ブロックと同一 verdict | `TestMultipleMediaPrintBlocks` (3) |
| 資料 HTML でない | `<style>` も `data-hb-part` も無ければ exit 1 (2 ではない) / 空文書 / 未閉じタグで exit 2 に倒れない / `</style>` 欠落を PASS にしない | `TestNonHandoutDocument` (4) |

## fixture の作り方 (実装者向け)

`hb_c17.good_html()` が **12 detection をすべて PASS する土台**を返す。
各テストは `mutate(html, old, new)` で規則を 1 つだけ壊す。差し替え対象が見つからなければ
`mutate` が即座に落ちるので、fixture の文言を変えたときに検査が空振りしたまま緑になることはない。

土台を差し替える引数: `base_css` / `focus_css` / `rm_css` / `page_css` / `print_css` / `script` / `body`、
追記する引数: `css_extra` / `head_extra` / `body_extra`。

`assertOnlyThisDetectionFails()` は「狙った detection だけが落ちる」ことも固定する。
これは実装が 1 つの違反を複数 detection へ二重計上する退化を防ぐためのもの。

## 本テストが意図的に固定していないこと

- **A4 実版面への収まり・改ページの実位置・実フォーカスリングの描画・JS 実行後の DOM・CSS カスケードの実効性**。
  これらは C17 の範囲外であり、テストも「範囲外だと stdout に毎回明示すること」だけを固定している (AC-C17-10)。
  範囲外項目を PASS へ畳まないことが本ゲートの契約。
- **ライトボックス (R04) のキーボード操作・フォーカストラップ・ESC/背景クリックでの閉止**。
  `script-brief-C17.json` の detections にこの契約が無いため、テストを起こしていない (下記 gap を参照)。
  PRINT-03 の対象としての lightbox (印刷時の非表示) だけは固定してある。
