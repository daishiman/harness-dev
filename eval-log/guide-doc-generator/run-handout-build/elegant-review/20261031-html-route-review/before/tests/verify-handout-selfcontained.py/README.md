# C16 `verify-handout-selfcontained.py` 受入テスト (P04-C16-01)

実装 (`plugins/guide-doc-generator/scripts/verify-handout-selfcontained.py`) より先に
判定基準を確定させ、赤で固定したテスト群。**P05 の実装側がここを自分に都合よく
書き換えて緑にすることは許されない**。契約を変えるときは先に
`plugin-plans/guide-doc-generator/briefs/script-brief-C16.json` を直す。

## 実行

repo ルートから:

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/verify-handout-selfcontained.py -p 'test_*.py'
```

Python 3.10+ の標準ライブラリのみ。現状は **354 tests / 354 failures (赤)** で、
すべて「未実装: … が存在しない」で落ちる。実装が現れた時点で個々の assert が
本来の契約を検査しはじめる。

## ファイル構成

| ファイル | 役割 |
| --- | --- |
| `hb_c16.py` | 共通ハーネス (テストではない)。CLI 起動・stdout/stderr のパース・共通 fixture `good_html()` |
| `test_cli_contract.py` | argv / exit code / stdout / stderr / json-report / write_scope / 冪等性 / failure_modes |
| `test_external_refs.py` | SC-01..SC-04 と **CR-EXT の境界** (text node の URL は違反にしない) |
| `test_emoji.py` | SC-05 と **CR-EMOJI の二層規則** (★ ☆ ✔ ♪ ■ © を殺さない) |
| `test_icons_symbols_anchors.py` | SC-06 / SC-07 / SC-08 |
| `test_figures_sc09.py` | SC-09 (R21 goal-spec C55) |
| `test_sc10_bundle_closure.py` | **SC-10 (同梱閉包の包括規則)**。script@src / iframe / link / CSS url() の残余を塞ぐ |
| `test_module_api.py` | module_api / **AC-C16-11 (C10 との判定一致)** / AC-C16-12 (規則本文の非複製) |

### 共通 fixture の考え方

検出ごとの入力は、`good_html()` (AC-C16-01 が要求する参照 v2 相当の自己完結 HTML)
へ snippet を差し込んで作る。単体の最小 HTML を渡すと
`failure_modes`「nav も section も存在しなければ exit 1」に巻き込まれて
目的の detection を切り分けられないため。

## 契約 id とテストの対応

### detections

| 契約 | 固定した内容 | テスト |
| --- | --- | --- |
| SC-01 | URL を取り得る 12 属性 / 6 スキーム / srcset の候補単位判定 / 大小文字・前後空白の正規化 | `test_external_refs.TestSC01Attributes` |
| SC-01 (除外) | 名前空間 URI 3 値の **完全一致のみ** 除外。`xml:base` は除外しない。`…/2000/svg/evil.js` は通さない | `TestSC01NamespaceWhitelist` |
| SC-02 | `<script>`/`<style>` 本文の http(s) リテラルはコメントでも違反。text node は対象外 | `TestSC02ScriptAndStyleLiterals` |
| SC-03 | img/source/video/object/embed は `data:` 必須。a@href は `#`/`data:`/`mailto:`/`tel:` のみ | `TestSC03AssetClosure` |
| SC-04 | rel 6 種は href の値によらず違反 / `@import` は値によらず違反 / `@font-face` の url()・local() / url() の引用 3 形 / font-family 列挙は通す | `TestSC04FontsAndStylesheets` |
| SC-05 | 層 1 (単独違反) / 層 2 (VS16 併用時のみ違反) / ZWJ / VS / 明示的に非検出の記号群 | `test_emoji.TestSC05*` |
| SC-06 | `data-hb-kind="icon"` の 5 属性 + stroke-width 2.2〜2.6。mascot / decor は対象外。**属性なしは「分類不能」で違反** | `test_icons_symbols_anchors.TestSC06IconStyle` / `TestSC06Unclassified` |
| SC-07 | D−U (未使用) / U−D (未定義) / id 重複。`#` なし use@href は SC-07 の対象外 | `TestSC07SymbolUse` |
| SC-08 | nav↔section の 1:1 / nav 内 href 重複 / 文書内 id 重複 / `href="#"` | `TestSC08NavAnchors` |
| SC-09 | DIAGRAM の描画要素 9 種 / IMG の data URI 実体長 64 バイト境界 / 枠だけの figure / 未解決 placeholder 5 種 | `test_figures_sc09.*` |
| SC-10 | (a) `<script src>` は値によらず違反・インライン本文は pass / (b) `iframe`・`frame`・`portal` は存在自体が違反 / (c) `<link>` は rel によらず href が `data:` 以外なら違反 / (d) CSS `url()` は `@font-face` 外も対象 / (e) **スキームの有無ではなく `data:` か否かで判定** | `test_sc10_bundle_closure.*` (54 件) |
| SC-10 (境界) | SC-02 が確定させた境界を壊さない — text node の URL・相対パス文字列・コード例は違反にしない。`<figure>` を `<frame>` の前方一致で拾わない | `TestSC10TextNodeBoundaryPreserved` / `TestSC10Frames.test_figure_element_is_not_a_frame` |

### canonical_rules (単一正本)

| 契約 | 固定した境界 | テスト |
| --- | --- | --- |
| CR-EXT | **text node の URL 文字列は違反にしない**。リンク化した瞬間 SC-01 が捕える。alt/title の URL も違反にしない | `test_external_refs.TestTextNodeUrlBoundary` (8 件) / `test_sc10_bundle_closure.TestSC10TextNodeBoundaryPreserved` |
| CR-EXT (実装 detection) | `SC-01 / SC-02 / SC-03 / SC-04 / SC-10` の 5 つ。SC-10 も `scan_external_references` が返す (C10 / C11 へ届く) | `hb_c16.EXTERNAL_REF_DETECTIONS` / `test_sc10_bundle_closure.TestSC10ModuleApi` |
| CR-EMOJI | ★U+2605 / ☆U+2606 / ✔U+2714 / ♪U+266A / ■U+25A0 / ©U+00A9 / ®/™/▶/⚙ (いずれも VS16 なし) は **pass**。ブロック denylist を使っていないことをソース検査でも確認 | `test_emoji.TestSC05PassesJapaneseSymbols` / `test_module_api.TestScanEmoji.test_no_block_denylist_in_source` |
| invariant | C10 と C16 が同一入力に同一判定 | `test_module_api.TestAcC16_11` (16 件) |

### acceptance_checks

| AC | テスト |
| --- | --- |
| AC-C16-01 | `test_cli_contract.TestPassPath` (SC-09 が実際に評価されることも含む) |
| AC-C16-02 | `test_external_refs.TestAcC16_02` |
| AC-C16-03 | `test_emoji.TestAcC16_03` |
| AC-C16-04 | `test_emoji.TestAcC16_04` |
| AC-C16-05 | `test_icons_symbols_anchors.TestSC06Unclassified` |
| AC-C16-06 | `test_icons_symbols_anchors.TestAcC16_06` |
| AC-C16-07 | `test_icons_symbols_anchors.TestAcC16_07` |
| AC-C16-08 | `test_cli_contract.TestUsageErrors` |
| AC-C16-09 | `test_cli_contract.TestWriteScope` |
| AC-C16-10 | `test_cli_contract.TestDeterminism` |
| AC-C16-11 | `test_module_api.TestAcC16_11` (違反有無 15 fixture + 違反コードポイント 4 fixture)。相対 script@src / インライン script / iframe も C10 と一致させる |
| AC-C16-12 | `test_module_api.TestAcC16_12` |
| AC-C16-R21-55a | `test_figures_sc09.TestAcC16_R21_55a` (SC-01..SC-04 が同時に PASS することも検査) |
| AC-C16-R21-55b | `test_figures_sc09.TestAcC16_R21_55b` |
| AC-C16-R21-55c | `test_figures_sc09.TestAcC16_R21_55c` |

### module_api / failure_modes

| 契約 | テスト |
| --- | --- |
| `scan_external_references(html_text)` / `scan_emoji(text)` / Violation の形 | `test_module_api.TestScanExternalReferences` / `TestScanEmoji` |
| CLI 側にだけ存在する判定分岐を作らない | `TestCliAndModuleShareTheSameJudgement` |
| 崩れた HTML で exit 2 にしない・SC-00 相当を報告 | `test_cli_contract.TestStructuralFailureModes` |
| nav も section も無い HTML は PASS へ畳まず exit 1 | 同上 |
| base64 本体を走査対象から除外しても検出漏れしない | `test_emoji.TestSC05ScanScope.test_base64_payload_is_excluded_from_scan` |
| network:false / stdlib_only | `test_cli_contract.TestBuildTarget.test_script_is_stdlib_only_no_network` |

## テスト側で置いた解釈 (ブリーフに明文が無い箇所)

実装がここと違う解釈を採るなら、テストではなく **ブリーフを先に直す**こと。

1. **SC-09 の checked の数え方** — `<figure data-hb-part="DIAGRAM">` のように figure と
   data-hb-part が同一要素に付く場合、対象要素の集合として **1 件**と数える。
2. **64 バイト閾値** — base64 を**デコードした後の**バイト長で判定する。境界は
   64 バイト = pass / 63 バイト = 違反 (「64 バイト以上」の素直な読み)。
3. **SC-09 (c) の可視テキスト** — `<figcaption>` を含む (AC-C16-R21-55c がキャプションを例示)。
4. **`<a href="">`** — SC-03 の許可接頭辞 (`#`/`data:`/`mailto:`/`tel:`) のいずれでもないので違反。
5. **fixture の図表 SVG の `data-hb-kind`** — `decor` を使う (下記 gap 1 を踏まないため)。
6. **SC-10 はサマリの固定順の末尾に付く** — stdout / json-report の detection 行は
   9 行ではなく **10 行 (SC-01..SC-10)** になる。
7. **CSS `url()` の担当 detection は SC-04 と SC-10 のどちらでもよい** — `@font-face` 外の
   `background:url(./bg.png)` を SC-04 と SC-10 のどちらが報告するかは決めず、
   「どちらかが必ず捕える」だけを固定した (`assertAnyDetectionFails`)。
8. **`<frameset>` 単体は SC-10 の対象にしない** — `frame` の前方一致で `<frameset>` や
   `<figure>` を拾う実装ミスを防ぐための断言であり、`<frameset>` の是非の判断ではない。

## gaps (P05 実装前に決着が要るもの)

1. **`data-hb-kind="figure"` の SC-06 上の扱いが未定義。** SC-06 の rule は
   「icon のみ検査、mascot と decor は対象外」としか書いておらず、
   open_questions X-03 が語彙として挙げる `figure` がどちらなのか決まっていない。
   本テストは図表 SVG に `decor` を使って回避した。C11 の
   `html_attribute_contract` が図表 SVG へ `figure` を付ける契約なら、SC-06 は
   `figure` を「対象外」として明記する必要がある (でないと全図表が分類不能で FAIL する)。
2. **SC-08 の逃げ道 `data-hb-nav="exclude"` が未決。** SC-08 の
   `false_positive_risk` は導入前提で書かれ、open_questions は未決としている。
   相反するため、この 1 点だけテスト化していない。決着後に
   「exclude 付き section は未リンク違反にしない」「json-report に列挙する」の 2 件を足す。
3. **json-report の info 表現が未定義。** 層 2 の VS16 なし出現・孤立 ZWJ・VS1-VS15・
   パーサ警告 (SC-00 相当) を「json-report に残す」とだけ書かれ、キー名も構造も無い。
   本テストは「シリアライズ結果に `U+2699` / `U+200D` / `U+FE0E` / `SC-00` が現れる」
   という最弱の形でしか固定していない。スキーマが決まったら強めること。
4. **`ERROR<TAB><reason>` の reason 語彙が未定義。** 1 行であることと exit 2 であること
   しか固定していない。
5. **SC-09 の対象に `data-hb-part` の他の値 (TEXT 等) があるかが C11 側未確定。**
   IMG / DIAGRAM 以外は対象外という前提でテストしている。
6. **SC-10 がブリーフに未反映。** 利用者要件の明確化で追加された新設判定であり、
   `script-brief-C16.json` の `detections` / `stdout` (「SC-01..SC-09 の固定順」を
   SC-10 まで拡張) / `canonical_rules.external_reference_rule.implemented_by_detections`
   (SC-10 を追加) / `acceptance_checks` を **実装より先に**改訂する必要がある。
   ブリーフを直さないと AC-C16-12 の「規則本文の非複製」も SC-10 を含まないままになる。
7. **`<iframe srcdoc="...">` のみを持つ場合の扱いが未定義。** srcdoc は取得を発生させない
   インライン文書だが、SC-10 (b) は「要素が存在すれば違反」と定めている。
   本テストは srcdoc 単独のケースを assert していない。ブリーフで
   「例外なく違反」か「srcdoc のみは許可」かを決めること。
8. **`<script src>` と SC-01 の二重報告を許すか。** `<script src="https://…">` は SC-01 と
   SC-10 の両方に該当する。本テストは両方が FAIL することを固定したが、
   1 違反を 1 detection にまとめる方針ならブリーフで明示すること。
