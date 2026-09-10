# RESOLUTION-P05-x-21 — C20 brief のマーカー語彙と chrome 境界規定を裁定結果へ追随させる

task: `P05-x-21` / consumes: `plugins/guide-doc-generator/schemas/ROUNDTRIP-CONTRACT.md`,
`briefs/RESOLUTION-P05-x-13.md` / write_scope: `plugin-plans/guide-doc-generator/briefs/`
(実際に書いたのは `script-brief-C20.json` と本ファイルの 2 ファイルのみ)

## 1. 裁定表からのマーカー集合の導出

件数も一覧も散文へ書き下さず、`ROUNDTRIP-CONTRACT.md` の fenced JSON から機械的に導出した。
使用したコード (再現可能):

```python
import json, re
src = open('plugins/guide-doc-generator/schemas/ROUNDTRIP-CONTRACT.md', encoding='utf-8').read()
contract = json.loads(re.findall(r"```json\n(.*?)\n```", src, re.S)[0])
attrs, fields = set(), set()
for a in contract['adjudications']:
    attrs  |= set(re.findall(r'data-hb-[a-z-]+', a['marker']))
    fields |= set(re.findall(r'data-hb-field="([^"]+)"', a['marker']))
```

`grep -oE '\b<pattern>'` は使っていない (進め方 7)。属性名も診断コードも Python の
`re.findall` で抽出している。

導出結果と、編集後の `script-brief-C20.json#renderer_marker_requirements` の記載集合
(属性は required_markers 全体、`data-hb-field` の値は同節の value 列挙を `|` で分解) の
包含関係は次のとおり。

```
contract attrs  : data-hb-attainment-step, data-hb-field, data-hb-key,
                  data-hb-notes-enabled, data-hb-section-role, data-hb-src, data-hb-ties-to
contract fields : attainment_level, date, focus_theme, heading,
                  must_remember, no_need_to_remember, target_task
attrs  ⊆ brief : True (差集合 空)
fields ⊆ brief : True (差集合 空)
```

編集前は次が欠けていた (同じコードで実測):

- 属性: `data-hb-ties-to` / `data-hb-notes-enabled` / `data-hb-section-role` /
  `data-hb-attainment-step` の 4 件が `required_markers` に不在。
- `data-hb-field` の値: `focus_theme` / `target_task` / `attainment_level` /
  `must_remember` / `no_need_to_remember` / `heading` の 6 件が value 列挙に不在。
- `data-hb-key` と `data-hb-src` は記載済みだったが、裁定が課している意味
  (`data-hb-key` = `target_tasks[].id`、`data-hb-src` = ペイロードの置き場は `src` であって
  `data_uri` キーを発明しない) が書かれていなかったため、当該行に追記した。

`data-hb-ties-to` には裁定表の `required_serialization` (半角スペース区切りトークン列、
空配列は空文字列) をそのまま宣言として写した。Python list repr / JSON 配列リテラルを
属性値へ入れることを明示的に禁止している。

## 2. chrome 境界としてどう規定したか

`renderer_marker_requirements.chrome_boundary` を新設した。規定の骨子:

- **chrome の範囲**は `roundtrip_granularity.not_preserved_by_design` の P1 免除と同一集合
  (nav / hero 枠そのもの / sprite / CSS / JS / footer / メモ UI / lightbox)。範囲は広げない。
- **読み飛ばしの単位を部分木から変えた。** `data-hb-generated="true"` は
  「この要素とその子孫のうち、著者データマーカーを持たないノード」が再生成可能である
  ことの宣言であり、読み飛ばしの単位は「著者データマーカーを持つノードを抜いた部分木」。
- **入れ子は最内の宣言が勝つ** (著者データ領域の内側にさらに `data-hb-generated` の子が
  現れたらそれは再び読み飛ばす)。
- **クラス名による二重防御にも同じ規定が及ぶ** (クラス名は宣言より弱い根拠なので宣言を覆さない)。
- **読み飛ばし領域からの推定を禁止** (メモ UI の描画有無から `notes_enabled` を決める等)。
- 実装方法は書いていない。`not_specified_here` に「renderer 側で枠を分割するか、抽出器側を
  穴あき走査にするか、両方かは P05-x-18 / P05-x-19 の裁量」と明記した。

あわせて、宣言の一貫性のために次を chrome 境界へ参照させた (規定の重複定義は作っていない):
`algorithm.A3`、`required_markers` の `data-hb-generated` 行、
`roundtrip_granularity.not_preserved_by_design` の chrome 行、`failure_modes` の chrome 項。
`failure_modes` には対称の失敗として「chrome 枠の内側にある著者記述を枠ごと捨ててしまう」を追加した。

### 判断が割れた点

1. **境界の置き方が 2 案あった。**
   (a) 抽出器側で「穴あき読み飛ばし」を宣言する (内側マーカー優先)。
   (b) renderer 側に「`data-hb-generated` 部分木の内側に著者データを置いてはならない」と
   構造制約を課し、読み飛ばしは丸ごとのまま残す。
   (b) の方が抽出器は単純になるが、hero 枠は「枠が生成物・中身が著者記述」という入れ子が
   本質的であり、(b) を採ると C11 に枠の分割方法まで事実上指定することになる — これは
   進め方 3 が禁じる実装指示への踏み込みである。よって**宣言としては (a) を正本にし、
   (b) を実装選択肢として `not_specified_here` に残した**。両者は observable には同値
   (どちらでも AC-C20-01 と AC-C20-07 が同時に成立する) であることを合格条件として書いた。
2. **「著者データマーカー」の集合を列挙するか導出させるか。** 列挙すると裁定表と brief の
   二名簿になる (PAT-1 の再発)。`authored_data_markers` は
   「required_markers のうち値を運ぶもの全て、集合は marker_source_of_truth の裁定表から導出」
   と書き、具体名の列挙を避けた。ただし hero 内の文書レベルフィールドだけは
   `what_is_not_chrome` に例示している (真因の説明としてどれが捨てられていたかを示す必要があるため)。
   これは規定ではなく事例であり、正本は裁定表側にある旨を `marker_source_of_truth.divergence_policy`
   で明示した。
3. **chrome_boundary を top-level に置くか。** 置くと top-level キー集合が変わり、
   受入基準の「既存キーを壊さない」の実測が濁る。`renderer_marker_requirements` 配下に入れた。
   chrome 境界は renderer と extractor の双方に効くため、抽出器側の義務は
   `extractor_obligation` として同じ節に併記した。

## 3. `data-hb-notes-enabled` の命名

**追認した (別名を採らない)。** 理由:

- 命名規約に合致している。既存の `<html>` 属性は `data-hb-schema-version` /
  `data-hb-doc-type` / `data-hb-subject-slug` のように「構成データのキーを kebab-case にした」
  形であり、`notes_enabled` → `data-hb-notes-enabled` は同じ規則の適用にすぎない。
- 別名を採ると裁定表 (`ROUNDTRIP-CONTRACT.md`、本 leaf の write_scope 外) との不整合が生じ、
  それを直せないまま残すことになる。追認すれば不整合は 0 になる。
- 衝突が無い。既存 brief の属性名集合に `data-hb-notes-enabled` は存在しなかった (実測)。

値の書式は brief 側で明確化した (`true|false` の文字列表現。省略・空文字は不可)。裁定表は
「`<html>` へ true/false を刻む」としか書いていないため、書式の宣言はここで補っている
(裁定と矛盾しない範囲の具体化)。

## 4. `exit_codes` の書式不揃いの棚卸し (進め方 6)

`re.findall(r'[EW]-[A-Z0-9-]+', ...)` による棚卸し結果 (編集前):

| キー | 記載されていたコード | 文言が言及する失敗事由 | 不揃い |
| --- | --- | --- | --- |
| `exit_codes["0"]` | (なし) | 必須の復元不能なし / compare 等価 / strict 下の任意欠落 0 件 | 3 事由すべてコード名なし |
| `exit_codes["1"]` | `E-EXTRACT-UNRECOVERABLE`, `E-ROUNDTRIP-DIFF`, `E-HTML-MALFORMED` | 上記 3 + 「strict 下での任意フィールドの復元不能」 | 起票時に指摘された 1 件 (`W-EXTRACT-OPTIONAL` 欠落) |
| `exit_codes["2"]` | (なし) | 起動引数の不正 5 種 | stderr 契約に対応コードが存在しない |

起票時の想定 (`exit_codes["1"]` の 1 件だけ) より不揃いは多かった。実測で追加検出したのは:

- `exit_codes["0"]` は成功条件を述べる節なのにコード名が 1 件も無く、`exit_codes["1"]` と
  対称に読めなかった。→ 各条件へ対応コードを併記し、あわせて
  「`W-EXTRACT-CATALOG-DRIFT` は出ていても exit 0 を妨げない」を追記した
  (stderr 契約が「exit code を変えない」と定めている内容の言い換えで、意味は変えていない)。
- `exit_codes["1"]` は `--strict-fidelity` 下の格上げについて **任意フィールドの復元不能しか
  挙げていなかった**。stderr 契約は `W-EXTRACT-OPTIONAL` と `W-EXTRACT-HEURISTIC` の 2 件が
  格上げ対象と定めているので、`W-EXTRACT-HEURISTIC` (heuristic 経路による部品同定) の
  事由も欠落していた。→ 2 件ともコード名つきで追記した。
- `exit_codes["2"]` の事由には対応する診断コードが stderr 契約に**存在しない**。ここへ
  コードを発明すると stderr 契約 (他 leaf が触る行) を書き換える必要が出るため、
  **コードを作らず「この経路にはコードを割り当てない」と明示する**方針を採った。
  下流が exit 2 をコード名で分岐する必要が生じたら stderr 契約へ先に追加すること、という
  順序も書いてある。

`stderr` キー自体は 1 バイトも編集していない (P05-x-16 の成果を保存。編集後に再抽出した
コード集合も 6 件で編集前と一致)。

## 5. 既存記述の非破壊の実測

編集前後の実測 (`json.load` → `sorted(dict)` の比較):

```
toplevel keys equal : True (26 キー、順序も不変)
heuristic_fallback  : class_map / class_map_completeness / never_guessed /
                      recovery_limits / reporting / when (6 キー、不変)
class_map rows      : 18 (末尾は TEXT — 順序制約を保持)
stderr codes        : E-EXTRACT-UNRECOVERABLE, E-HTML-MALFORMED, E-ROUNDTRIP-DIFF,
                      W-EXTRACT-CATALOG-DRIFT, W-EXTRACT-HEURISTIC, W-EXTRACT-OPTIONAL
```

`class_map` の 18 行は「task-spec 本文の記述」ではなく編集直前の実測値である
(dispatcher の指示どおり再測した。結果として task-spec の 18 行という記述と一致した)。
`class_map` / `class_map_completeness` / `recovery_limits` / `reporting` / `never_guessed` は
1 バイトも触っていない。

追加したキー (いずれも新設で、既存キーの上書きではない):

- `renderer_marker_requirements.marker_source_of_truth`
- `renderer_marker_requirements.chrome_boundary`
- `required_markers` の 4 行 (`data-hb-ties-to` / `data-hb-section-role` /
  `data-hb-attainment-step` / `data-hb-notes-enabled`)
- `data-hb-asset-*` 行の `payload_placement`
- `failure_modes` の 1 項

## 6. dispatcher / task-spec の前提のうち外れていたもの

- **外れていない**: fenced JSON がちょうど 1 個で `json.loads` が通ること、両ファイルの
  トップレベルキー構成、`class_map` が 18 行であること — いずれも実測で一致した。
- **task-spec 進め方 6 の「この 1 件だけ書式が揃っていない」は不正確**だった。実測では
  `exit_codes["0"]` にコード名が 1 件も無く、`exit_codes["1"]` の strict 格上げ事由も
  `W-EXTRACT-HEURISTIC` が欠落しており、`exit_codes["2"]` には対応コードが存在しない。
  不揃いは 1 件ではない (§4)。
- 「`required_markers` 相当の節がどれか」は `renderer_marker_requirements.required_markers`
  で正しかった (`ROUNDTRIP-CONTRACT.md` 冒頭の正本関係の記述も
  `script-brief-C20.json#renderer_marker_requirements` をマーカー契約の正本と名指ししている)。

## 7. write_scope 外として手を出さなかった事項

いずれも 1 バイトも書いていない。必要な作業だけを記す。

1. `plugins/guide-doc-generator/scripts/render-handout.py` (P05-x-18 / C11)
   - hero 枠 (`:1386-1391`) と header (`:1411`) の `data-hb-generated="true"` と、その内側の
     `data-hb-field` の関係を chrome_boundary の規定に合わせる。
   - `:1511` の `<h2 class="section-label">` へ `data-hb-field="heading"` を付ける
     (連番 `<span class="section-num">` を含まない要素へ)。
   - `:1536` の `data-hb-ties-to` を Python list repr ではなく半角スペース区切りで直列化する。
   - `<html>` へ `data-hb-notes-enabled` を刻む。
2. `plugins/guide-doc-generator/scripts/extract-handout-config.py` (P05-x-19 / C20)
   - `:422` 付近の `prune_chrome` / `is_generated_chrome` を chrome_boundary の規定に合わせる。
   - `data-hb-section-role` / `data-hb-attainment-step` / `data-hb-ties-to` /
     `data-hb-notes-enabled` を読む。
   - `:822` の `data_uri` キー新設をやめ `src` へ格納する。
3. `plugins/guide-doc-generator/schemas/ROUNDTRIP-CONTRACT.md`
   - 修正不要 (本 leaf は裁定表へ合わせる側であり、別名も採らなかったため不整合は無い)。
4. `plugin-plans/guide-doc-generator/briefs/script-brief-C17.json` / `script-brief-C22.json`
   - 同ディレクトリだが P05-x-24 の担当。参照も編集もしていない。
5. `blocking_contract_divergences` の `c11-c12-input-shape-divergence`
   (`normalized:true` / `nav` / `sections[].blocks` vs `parts`) は本 leaf の宣言では解けない。
   C11 / C12 側の別タスクが要る。chrome 境界を直しても、これが残る限り
   AC-C20-01 / AC-C20-02 / AC-C11-15 は緑にならない。
