# RESOLUTION-P05-x-18 — render-handout.py の実装欠陥 5 件の是正記録

対象: `plugins/guide-doc-generator/scripts/render-handout.py` (単一ファイル)
task-spec: `plugin-plans/guide-doc-generator/task-specs/P05-x-18.md`
裁定の正本: `plugins/guide-doc-generator/schemas/ROUNDTRIP-CONTRACT.md`

本書は 5 欠陥それぞれについて **採った解 / 退けた解とその理由 / 実測結果** を記録する。

---

## 0. 着手前後の失敗テスト名の集合 (件数ではなく名前集合で比較)

コマンド (両者とも `plugins/guide-doc-generator/tests/render-handout.py/` を cwd とする):

```
python3 -m unittest discover -p 'test_*.py' -v
```

### 着手前 (6 件)

```
test_determinism.TokenIndirectionTest.test_accent_token_change_only_diffs_root_block
test_parts_catalog_coverage.FlowRenderingTest.test_diagram_pattern_is_exposed
test_parts_catalog_coverage.FlowRenderingTest.test_flow_is_delegated_to_inline_svg
test_cross_component.GateHandoffTest.test_language_gate_passes
test_cross_component.GateHandoffTest.test_round_trip_equivalence
test_parts_catalog.SingleVocabularyTest.test_part_ids_are_not_enumerated_outside_the_catalog
```

### 着手後 (2 件)

```
test_cross_component.GateHandoffTest.test_round_trip_equivalence
test_parts_catalog.SingleVocabularyTest.test_part_ids_are_not_enumerated_outside_the_catalog
```

差分は **消えた 4 件のみ**。新規に赤くなったテストは 0 件 (集合の増分が空)。
残る 2 件はいずれも本 leaf の write_scope 外 (`extract-handout-config.py`) が原因である (§7)。
テストの assert は 1 箇所も変更していない (テストファイルは 1 バイトも書いていない)。

---

## 1. 欠陥 (1) トークン間接参照 — 達成

### 採った解

`build_css` の前段に `css_variables_of(tokens)` を新設し、`css_variables` の写しに対して
**トークンのトップレベルにある `--` 始まりキーを上書き適用**する。`:root` の行順は
`css_variables` のキー順を保つ (同名キーは値だけ差し替わるため行が移動しない)。

`CSS_VARIABLES_KEY` 不在時の `LaunchError` は `css_variables_of` の中へそのまま移設して残した
(トークンファイルの構造契約を弱めない)。

上書き方向を「トップレベルが正本」としたのは、トークン側の
`accent_top_level_note` が「トップレベルのこのキーがアクセントの入口であり、
accent.scale と css_variables の側を書き換えるときは同時にここも動かす」と
自ら宣言しているため。入口が正本であるという宣言に実装を合わせた。

### 退けた解

- **`css_variables` 側を正本にしてトップレベルを無視する**: 受入テストが
  トップレベルのキーを書き換えて差分を求めるため原理的に緑にならない。かつ
  トークン側の note の宣言と実装が食い違ったままになる。
- **`accent.scale[].css_var` から `:root` を組み立てる**: `css_variables` を
  経由しない第 3 の経路を増やすことになり、名簿が 1 本増える。退けた。

### 実測結果

`pop.json` のトップレベル `--pop-primary` だけを `#123456` へ書き換えた
clone に対する前後の HTML の unified diff (n=0):

```
['-  --pop-primary: #43a4f5;', '+  --pop-primary: #123456;']
```

差分は `:root` のアクセント定義 1 行のみ。dispatcher が「未検証」と注記していた
P05-x-08 の worker の予測値と一致した。

### アクセント実値の重複 — 増やしていない

`assets/tokens/` へは 1 バイトも書いていないため重複箇所は不変。実測:

```
$ python3 -c "import re,io; print(len(re.findall('#43a4f5', io.open('plugins/guide-doc-generator/assets/tokens/pop.json',encoding='utf-8').read(), re.I)))"
5
```

内訳 (行番号は実測):

| 行 | 位置 | 種別 |
|----|------|------|
| 8  | トップレベル `--pop-primary` | アクセント変数 (入口 = 正本) |
| 12 | `accent.base` | アクセント変数 |
| 14 | `accent.scale[step=bright].value` | アクセント変数 |
| 21 | `css_variables["--pop-primary"]` | アクセント変数 |
| 59 | `mascot_css_variables["--body-main"]` | **別変数** (マスコット本体色。同じ値だがアクセント変数ではない) |

task-spec が言う「アクセント実値の重複 4 箇所」は上表の上 4 行を指す。**4 のまま**。
削減 (冗長になった `accent.base` / `accent.scale[bright].value` / `css_variables` 側の
いずれかを参照へ置き換える等) は `assets/tokens/` が write_scope 外のため実施していない (§7)。

---

## 2. 欠陥 (2) B14 の C14 委譲 — 達成

### 採った解

`Renderer.flow` の自前 `<ol class="flow">` 描画を削除し、`self.diagram(...)` への
1 行の委譲にした。`Renderer.diagram` に `default_pattern` 引数を足し、
`pattern = block.get("pattern") or default_pattern` とした。

`flow` が渡す既定値は **`block.get("type")`** である。`block.type` の値 `"flow"` は
そのまま C14 の pattern 語彙の 1 語であるため、レンダラのソースへ pattern の
リテラルを新しく書き足さずに済む (語彙の二重名簿を作らない)。

DIAGRAM 経路と同一の関数を通るため、`data-hb-part` / `data-hb-part-id` /
`data-hb-key` / `data-hb-kind` の属性契約と `data-hb-diagram-*` は自動的に揃う。

併せて、部品が消えたことで死んだ CSS 規則 (`.flow` / `.flow-node` のセレクタ 2 箇所) を
外した。フロー表現がレンダラ側に残らないことを CSS の面でも成立させるため。

### 退けた解

- **`flow` 内で `render_diagram` を直接呼ぶ**: `diagram` が持つ spec 組み立て・
  `title` フォールバック・`data-hb-kind="figure"` の注入・`DiagramError` → `DataError`
  変換を写経することになり、二重実装を別の形で温存する。退けた。
- **`pattern` の既定値としてソースへ `"flow"` を直書きする**: 語彙のリテラルを
  レンダラへ増やす。`block.get("type")` で同じ語が取れるので不要。退けた。

### 実測結果

```
$ python3 (BLOCK_FIXTURES['flow'] を 1 個だけ持つ構成データを描画)
<figure data-hb-part="B14" data-hb-part-id="blk-flow" class="diagram"
        data-hb-diagram-id="blk-flow" data-hb-diagram-pattern="flow"
        data-hb-diagram-data="{...&quot;steps&quot;: [{...&quot;label&quot;: &quot;受付&quot;}, ...]}">
  <svg data-hb-kind="figure" id="hbdg-blk-flow-1" role="img" ...>…</svg>
</figure>
```

- `FlowRenderingTest.test_flow_is_delegated_to_inline_svg` → 緑 (部品内に inline SVG)
- `FlowRenderingTest.test_diagram_pattern_is_exposed` → 緑 (`data-hb-diagram-pattern="flow"` が素値)
- 既存の `test_root_uses_the_catalog_part_id` / `test_every_step_label_is_rendered` /
  `test_inline_svg_is_classified` も緑のまま (回帰なし)。
- 姉妹スイート `tests/render-diagram-svg.py/` は 166 tests OK。

---

## 3. 欠陥 (3) chrome 境界 と 5. 欠陥 (5) 日付ピルの配置 — 同時設計・達成

この 2 件は task-spec の指示どおり **同時に設計した**。以下はその設計判断の記録である。

### 制約の実測 (ここが設計を決めた)

抽出器の読み飛ばし述語は `data-hb-generated` だけではない。実測:

```
plugins/guide-doc-generator/scripts/extract-handout-config.py:90
    CHROME_CLASSES = ("pop-header", "pop-bottom")
plugins/guide-doc-generator/scripts/extract-handout-config.py:91
    CHROME_CLASS_PREFIXES = ("memo",)
plugins/guide-doc-generator/scripts/extract-handout-config.py:421-430  is_generated_chrome()
plugins/guide-doc-generator/scripts/extract-handout-config.py:433-442  prune_chrome()
```

`is_generated_chrome` は `data-hb-generated == "true"` **または** class が
`pop-header` / `pop-bottom` / `memo*` のいずれかで真になり、`prune_chrome` は
その部分木を丸ごと捨てる。したがって:

> **`.date-pill` を `header.pop-header` の内側へ移すと、`data-hb-generated` と
> `pop-header` class の二重の理由で `date` が読み飛ばされる。**

一方、受入基準は `date` を含む 12 項目が「読み飛ばし規則の下でも到達可能」であることを
要求している。よって「header.pop-header の中へ入れる」という task-spec 手順の字義は
受入基準と両立しない。**受入基準を優先し、DATE-01 の判定条件を実測してから配置を決めた。**

C18 の DATE-01 の冒頭判定は次のとおり (実測):

```
plugins/guide-doc-generator/scripts/verify-handout-language.py:709-722
    anchor_order = 最初に data-hb-part ∈ document_part_ids を持つ要素の order
    in_lead_position(node) := node.has_ancestor_tag("header")
                              or node.order < anchor_order
```

**`<header>` タグの内側であればよく、`.pop-header` である必要はない。**

### 採った解

1. **日付**: `build_doc_head()` を新設し、`<header class="doc-head">` の中へ
   `.date-pill` を **1 個だけ** 出す。文書順は sprite の直後・sticky ナビの直前。
   `<header>` タグの内側なので DATE-01 の第 1 条件を満たし、かつ B01 アンカーより
   前なので第 2 条件も満たす (二重に成立)。chrome class を持たないので到達可能。
   hero からは日付を撤去したので総数は 1 個のまま。
2. **hero**: 読み飛ばし境界を「枠」へ限定した。`.hero` 外側 div から
   `data-hb-part` / `data-hb-part-id` / `data-hb-generated` を外し、
   内側に空の `<div class="hero-frame" data-hb-part="B02" data-hb-part-id="b02-1"
   data-hb-generated="true" aria-hidden="true">` を置いた。
   背景・枠線・角丸をこの `.hero-frame` へ移し (`position:absolute; inset:0;
   pointer-events:none`)、著者記述は `.hero` 直下に残して
   `.hero > *:not(.hero-frame) { position: relative; }` で枠の上へ重ねる。
   **ROUNDTRIP-CONTRACT が「B02 hero 枠が P1 の生成 chrome であること自体は正しい」と
   述べたとおり、chrome なのは枠 (frame) であって中身ではない**という区別を
   DOM の形として実現したもの。

### 退けた解

- **hero から `data-hb-generated` を単に外す**: `test_html_attributes.
  GeneratedChromeTest.test_generated_chrome_is_marked` が
  `marked_parts` に `"B02"` を要求する (実測: 同ファイル 97-107 行)。
  外すとこのテストが赤になる。assert を弱めないという規律に反するので退けた。
- **hero の中身を hero の外 (main 直下の兄弟) へ全部出す**: hero の視覚的まとまりが
  壊れ、`.hero` が空の帯になる。枠の中に著者記述が見える状態を保てないため退けた。
- **著者記述側へ `data-hb-generated="false"` の打ち消しマーカーを付ける**:
  `prune_chrome` は親を捨てた時点で子を一切見ない (実測: 433-442 行の再帰は
  `is_generated_chrome(child)` が真なら `continue` する) ため、打ち消しは効かない。
  退けた。
- **`.date-pill` を `header.pop-header` の中へ入れる (task-spec の字義)**:
  上記のとおり `pop-header` class 自体が読み飛ばし対象であり、`date` が到達不能なままになる。
  受入基準の到達可能性要求と両立しないため退けた (§7 に brief 側の要修正として記載)。
- **外側 `<header>` を `.doc-head` にして `.pop-header` を内側の `<nav>` へ移す**:
  `position:sticky` の粘着範囲は包含ブロックの範囲に限られるため、短い `<header>` の
  中に sticky nav を入れるとスクロールで nav が流れて sticky が実質死ぬ。
  視覚的な回帰を招くので退けた。header は 2 本 (`.doc-head` と `.pop-header`) に分けた。

### 実測結果 (到達性)

`extract-handout-config.py` の `build_tree` + `prune_chrome` を実際に呼び、
枝刈り後に残った `data-hb-field` の集合を採取した:

```
reachable after prune: ['attainment_level', 'background', 'date', 'duration',
 'focus_theme', 'goal', 'heading', 'judgment_axis', 'lead_line', 'must_remember',
 'no_need_to_remember', 'purpose', 'section_duration', 'section_goal',
 'target_task', 'title']
MISSING: []
```

受入基準が挙げる 12 項目 (title / date / purpose / background / goal / duration /
focus_theme / target_task / attainment_level / must_remember / no_need_to_remember /
sections[].heading) は **すべて到達可能**。

C18 ゲートの実測 (`test_language_gate_passes`): 着手前は
`FAIL DATE-01 213:171 2026/01/05 日付表記が冒頭 … に無い` の 1 件で exit 1。
着手後は exit 0 で緑。**DATE-01 以外の隠れた原因は無かった**ことを実測で確認した
(着手前の出力でも他 8 detection はすべて PASS / NOT-REQUESTED であり、
DATE-01 だけが FAIL だった)。

---

## 4. 欠陥 (4) heading マーカーと ties_to の直列化 — 達成

### 採った解

- **heading**: `<h2 class="section-label">` の中で、連番 `<span class="section-num num">`
  と見出し本文を分離し、本文側を `field_span("heading", …, klass="section-heading")` に
  した。連番は復元対象の要素の外側に出たので、`data-hb-field="heading"` の
  テキストは素値そのものになる。連番自体は `index` から再生成できる派生物なので
  マーカーを与えない。
- **ties_to**: `serialize_token_list()` を新設し、`ROUNDTRIP-CONTRACT.md` の
  `required_serialization` (「半角スペース区切りのトークン列。空配列は空文字列」) に
  従って直列化する。裁定文書を正本として採用し、逸脱していない。
- **notes_enabled**: 裁定文書が割り当てた新設マーカー名 `data-hb-notes-enabled` を
  そのまま `<html>` へ実装した。値は `false` を選んだときだけ `"false"`、
  それ以外 (未指定を含む) は `"true"`。未指定を `"true"` にするのは
  normalize の既定と一致させるためで、`false` の消失 (裁定が禁じた失敗) を起こさない。

### 退けた解

- **`<h2>` 自体に `data-hb-field="heading"` を付ける**: `text_value()` は
  子孫テキストを連結するので `1全体の流れ` になり、素値へ戻せない
  (裁定文書 2.3 が実測で挙げた症状そのもの)。退けた。
- **連番を CSS カウンタで描く**: 見出しから連番を DOM ごと消せるが、
  `test_html_structure` の固定順序検査や既存の `.section-num` を前提にした
  版面 (`num` クラスの字送り) に波及する。マーカーの分離だけで復元は成立するので
  変更範囲を広げないほうを採った。
- **ties_to を JSON 配列文字列で埋める**: 裁定文書がスペース区切りと明記しており、
  裁定文書が正本である。従わない理由が無いので退けた。

### 実測結果

```
ties_to attr (rendered): ['data-hb-ties-to="goal target_task:t1"', 'data-hb-ties-to="goal"']
ties_to attr (prune_chrome 後も同値で到達可能)
notes_enabled=false のとき:  data-hb-notes-enabled="false"
heading:  <h2 class="section-label"><span class="section-num num">1</span>
          <span class="section-heading" data-hb-field="heading">セクション1</span></h2>
```

着手前の実測値 `data-hb-ties-to="[&#x27;goal&#x27;, &#x27;target_task:monthly-check&#x27;]"`
(Python の list repr) は解消した。

round-trip テストの前進も実測できている。着手前は
`E-EXTRACT-UNRECOVERABLE` が 8 件出て抽出器が exit 1 で落ちていたが、
着手後は **診断 0 件で抽出器が exit 0** になり、テストの失敗地点が
`assertEqual(0, proc.returncode, …)` (97 行手前) から
`assertEqual(source["sections"], got["sections"])` (97 行) へ進んだ。
残差は抽出器側の parts 形状の問題であり本 leaf の範囲外 (§7)。

---

## 5. 受入基準に挙がった 4 テストの結果

| テスト | 着手前 | 着手後 |
|--------|--------|--------|
| `test_determinism.TokenIndirectionTest.test_accent_token_change_only_diffs_root_block` | 赤 | **緑** |
| `test_parts_catalog_coverage.FlowRenderingTest.test_flow_is_delegated_to_inline_svg` | 赤 | **緑** |
| `test_parts_catalog_coverage.FlowRenderingTest.test_diagram_pattern_is_exposed` | 赤 | **緑** |
| `test_cross_component.GateHandoffTest.test_language_gate_passes` | 赤 | **緑** |

---

## 6. 姉妹スイートの回帰確認 (実測)

| スイート | 結果 |
|----------|------|
| `tests/verify-handout-language.py/` | 248 tests OK |
| `tests/verify-handout-a11y-print.py/` | 187 tests OK |
| `tests/verify-handout-selfcontained.py/` | 354 tests OK |
| `tests/extract-handout-config.py/` | 152 tests OK |
| `tests/render-diagram-svg.py/` | 166 tests OK |
| `tests/verify-handout-narrative.py/` | 217 tests, 1 failure (本 leaf と無関係) |
| `tests/validate-handout-config.py/` | 278 tests, 2 failures + 2 errors (本 leaf と無関係) |

無関係と判断した根拠 (すべて実測):

- `verify-handout-narrative.py` の
  `test_scope_and_determinism.TestMultiViolationAccounting.test_all_detections_reported_even_when_first_fails`
  は「detection 行が 8 行」を期待するが実装は NAR-09 / NAR-10 を含む 10 行を出す。
  当該テストは同スイート内の `build_html()` で HTML を自作しており
  `render-handout.py` を一切呼ばない (`grep -rln "render-handout" .` の結果に
  当該ファイルは含まれない)。C22 側の R22 追加分と試験の乖離。
- `validate-handout-config.py` の 4 件は
  `test_document_fields.DocTypeVocabulary.test_unknown_doc_type_lists_vocabulary` /
  `test_source_hygiene.SourceHygiene.test_no_purpose_vocabulary_literals` /
  `test_normalize_date_determinism.FailClosed.test_no_temp_file_left_behind` /
  `test_normalize_date_determinism.NormalizeDefaults.test_provenance_shape`。
  同スイートで `render-handout.py` を参照するのは `test_r22_detail_budget.py` のみで、
  失敗はそこに 1 件も無い。C12 側の課題。

---

## 7. write_scope 外として手を出さなかった作業 (受け皿つき)

`plugins/guide-doc-generator/scripts/` の外へは 1 バイトも書いていない。同ディレクトリ内でも
`render-handout.py` と本ファイル以外は書いていない (`extract-handout-config.py` は
読んだだけ)。以下は他 leaf へ渡す。

### 7.1 `scripts/extract-handout-config.py` (受け皿: P05-x-19 / P05-x-23)

1. **`CHROME_CLASSES` から `pop-header` を外すか、判定を「data-hb-generated を持つ要素の
   class」に限定する** (90 行)。現状は class 名だけで部分木を捨てるため、レンダラが
   マーカーを正しく置いても `.pop-header` の内側は原理的に読めない。本 leaf は
   日付をこの class の外へ出すことで回避したが、判定そのものは脆い
   (テーマが class 名を変えたら読み飛ばしが外れる／別の著者記述を巻き込む)。
2. **裁定で `decision=marker` とされたのに抽出器が読んでいない項目を読む**:
   `focus_theme` / `target_tasks` (+`data-hb-key`) / `attainment_level` /
   `must_remember` / `no_need_to_remember` / `sections[].ties_to` (スペース区切りを
   split する) / `sections[].role` / `sections[].attainment_step` /
   `notes_enabled` (`data-hb-notes-enabled` を boolean へ戻し、`null` を書かない)。
   現状 `DOC_FIELDS` (129-136 行) と `SECTION_FIELDS` (137-143 行) にこれらが無く、
   `UNMARKED_DOCUMENT_KEYS` (146 行) が `notes_enabled` に `null` を書いている。
   **本 leaf の変更で HTML 側の到達性は満たしたので、残りは読み取りだけである。**
3. **part id のリテラル列挙 (62-74 行付近の `PART_CLASS_MAP`) をカタログ由来にする**。
   `test_parts_catalog.SingleVocabularyTest.test_part_ids_are_not_enumerated_outside_the_catalog`
   の赤はこの 13 行が全原因であり、`render-handout.py` 側の違反は 0 件である
   (実測: 失敗メッセージの offender は全行が `extract-handout-config.py`)。
4. `assets[]` の復元で schema に無い `data_uri` キーを発明せず `src` へ格納する
   (裁定 `/assets/*/data_uri`)。

### 7.2 `plugin-plans/guide-doc-generator/briefs/script-brief-C11.json` (受け皿: P05-x-21)

1. `theme_token_schema_ownership` に **「アクセント色の入口はトークンのトップレベルの
   `--pop-primary` であり、`css_variables` の同名キーはこれで上書きされる」** を追記する。
   現状この節は `text_limits` の話しかしておらず、トップレベルの `--` キーの
   存在も上書き規則も未記載 (矛盾ではなく欠落)。
2. **手順 13 の「値をそのまま header の `.date-pill` として 1 個だけ出す」を
   「文書冒頭の `<header>` 要素の中に 1 個だけ出す (`.pop-header` の内側は不可)」へ
   改める。** 理由は §3 のとおりで、`.pop-header` は抽出器の chrome class であり
   その内側へ置くと `date` が round-trip で復元不能になる。C18 の DATE-01 は
   `<header>` タグの内側であれば通る (`has_ancestor_tag("header")`) ので、
   ゲートを緩めずに両立できる。**「1 個だけ」は維持している。**
3. `html_attribute_contract` へ新設マーカー `data-hb-notes-enabled` を追記する
   (裁定 `/notes_enabled` に基づき本 leaf が実装済み)。
4. `renderer_marker_requirements` (C20 brief) の `data-hb-field` 値の列挙へ
   `heading` を追加する (裁定 `/sections/*/heading`。現状 brief 側に欠落)。
   併せて `data-hb-generated="true"` の説明の「hero 枠」が **枠要素そのもの**を
   指し、枠の内側の著者記述を含まないことを明記する。

### 7.3 `plugins/guide-doc-generator/assets/tokens/*.json` (受け皿: 未割当。要 dispatcher 判断)

アクセント実値の 4 重化 (§1) は本 leaf では**増やしていないが減らしてもいない**。
削るなら `accent.base` と `accent.scale[step=bright].value` を
「トップレベル `--pop-primary` を指す参照」に変える案が考えられるが、
JSON に参照機構が無いためキーを消して読み手 (C15 / mascot 系) を直す必要があり、
影響範囲がトークンファイル単独では閉じない。**本 leaf では実施していない。**

---

## 8. 変更したファイル

- `plugins/guide-doc-generator/scripts/render-handout.py` (唯一の実装変更)
- `plugins/guide-doc-generator/scripts/RESOLUTION-P05-x-18.md` (本ファイル / produces)

`render-handout.py` の変更点の一覧:

| 箇所 | 変更 |
|------|------|
| `CSS_VARIABLE_PREFIX` / `css_variables_of()` 新設 | 欠陥 (1) |
| `build_css()` が `css_variables_of()` を使う | 欠陥 (1) |
| `Renderer.flow()` を `self.diagram()` への委譲 1 行にした | 欠陥 (2) |
| `Renderer.diagram()` に `default_pattern` 引数 | 欠陥 (2) |
| CSS から `.flow` / `.flow-node` セレクタを除去 (死んだ規則) | 欠陥 (2) |
| `build_doc_head()` 新設・`render_document` の body へ挿入 | 欠陥 (5) |
| `build_hero()` から日付を撤去 | 欠陥 (5) |
| `build_hero()` を `.hero` (著者記述) + `.hero-frame` (chrome) の 2 層へ | 欠陥 (3) |
| CSS に `.doc-head` / `.doc-date` / `.hero-frame` / `.hero > *:not(.hero-frame)` | 欠陥 (3)(5) |
| `build_section()` の `<h2>` を連番 span と `data-hb-field="heading"` span に分離 | 欠陥 (4) |
| `TOKEN_LIST_SEPARATOR` / `serialize_token_list()` 新設、`data-hb-ties-to` に適用 | 欠陥 (4) |
| `<html>` へ `data-hb-notes-enabled` | 欠陥 (4) |
