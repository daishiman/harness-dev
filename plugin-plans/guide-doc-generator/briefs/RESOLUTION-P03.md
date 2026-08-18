# P03 evidence Y-01〜Y-09 の解消記録

本ファイルは `evidence/P03.json` の findings Y-01〜Y-09 に対して、**どの記述を単一正本に確定したか**を 1 箇所に記録するものである。
各項目は「指摘 / 採用した単一正本 / 変更したファイルと箇所 / 降格させた側に残した参照記述」の 4 節で書く。
以後この plan を読む者は、同じ規則が 2 箇所に書かれているのを見つけたら、ここに記録された正本側が正しいと判断してよい。

対象ディレクトリ: `plugin-plans/guide-doc-generator/`
未着手 (書き換え禁止) : `task-graph.json` / `task-specs/` / `evidence/` / `goal-spec.json` / `handoff-run-plugin-dev-plan.json`

---

## Y-01 (info) — C21 の network 宣言と冪等再利用の位置づけ

**指摘**
C21 (`invoke-srg-image-pipeline.py`) は `network: false` と宣言されていたが、委譲先の `generate-images-codex.js` が codex CLI を起動し、codex がモデル API へ通信する。また「既存 PNG があれば再生成しない」という冪等動作が `failure_modes` に書かれており、正常系の挙動が異常系の記述に紛れていた。

**採用した単一正本**
- network の真偽: `component-inventory.json` の C21 `network: true`。「自分で socket を開くか」ではなく「この component を実行すると外部通信が起きるか」で判定する。
- 冪等スキップ: `briefs/script-brief-C21.json` の `algorithm` 手順 12 (通常の正規ステップ)。

**変更したファイルと箇所**
- `component-inventory.json` — C21 `network` を `false` → `true`、`purpose` 末尾に理由を追記。
- `briefs/script-brief-C21.json` — `algorithm` に手順 12 (既存 PNG の署名検査つき回収 / 全 slug 充足時は委譲先を起動せず exit0) を挿入し以降を繰り下げ。`network` ブロック (value/rationale/inventory_sync) を新設。受け入れ検査 `AC-C21-11` を追加。

**降格させた側に残した参照記述**
`failure_modes` の非決定論の項に「既存 PNG の再利用による冪等化は algorithm 12 の正規ステップで行う (ここでは定義しない)」と残した。

---

## Y-02 (blocking) — 外部参照チェックの三重実装

**指摘**
「何を外部参照とみなすか」の判定規則が C16 (`verify-handout-selfcontained.py`)・C11 手順 23・C10 hook D1 の 3 箇所にそれぞれ書かれていた。特に「本文テキスト中の URL 文字列」の扱いが揃っておらず、片方だけ改訂されれば恒久的に食い違う。

**採用した単一正本**
`briefs/script-brief-C16.json` の `canonical_rules.external_reference_rule` (id: **CR-EXT**)。
規則本文はここにだけ書く: **fetch を起こす参照 (`src` / `href` / `url()` / `@import` / `srcset` 等の属性および CSS 値) だけが違反であり、テキストノード中の URL 文字列は違反ではない**。根拠は R01「オフラインで同一挙動」— 取得が起きなければ挙動は変わらない。例外は `<script>` / `<style>` 内のリテラルで、これらは実行時に fetch を起こしうるため対象に含む。

**変更したファイルと箇所**
- `briefs/script-brief-C16.json` — `canonical_rules` ブロック新設 (CR-EXT: statement / implemented_by_detections SC-01〜SC-04 / delegated_consumers)。`module_api` を新設し `scan_external_references(html_text) -> list[Violation]` を公開 (`importlib.util.spec_from_file_location('hb_selfcontained', ...)` で読み込む)。`AC-C16-11` / `AC-C16-12` を追加。
- `briefs/script-brief-C11.json` — 手順 23 を「自前判定をやめ CR-EXT の実装 (`scan_external_references`) を呼ぶ」に書き換え。`failure_modes` の「三重防御」を「同一規則の三重適用」へ修正。
- `briefs/hook-brief-C10.json` — D1 の rule を委譲記述に置換し `rule_source: "C16 canonical_rules.external_reference_rule (CR-EXT)"` を明記。`rule_delegation` ブロック (読み込み方法・import 失敗時は exit0 + systemMessage) を新設。

**降格させた側に残した参照記述**
- C11 手順 23: 「何が違反かの列挙 (スキーム・属性名) は CR-EXT の定義であり、本 script のソースへ複製しない」。
- C10 D1: `rule_source` による正本ポインタと、`boundary_with_C16` の「D1/D2 が hook と C16 の両方から報告されるのは『二重実装』ではなく『同一規則の二重適用』である」。

---

## Y-03 (high) — 絵文字チェックの二重実装

**指摘**
C16 SC-05 は「二層の明示集合」で絵文字を判定し ★ (U+2605) や ✔ (U+2714, VS16 なし) を通すのに対し、C10 hook D2 は U+2600–U+27BF などの Unicode ブロック丸ごと denylist を持っていた。同じ入力に対し hook だけが落とす偽陽性が構造的に発生する。

**採用した単一正本**
`briefs/script-brief-C16.json` の `canonical_rules.emoji_rule` (id: **CR-EMOJI**) = SC-05 の二層規則。ブロック単位の denylist は用いない。

**変更したファイルと箇所**
- `briefs/script-brief-C16.json` — `canonical_rules.emoji_rule` を新設 (statement / 層 1・層 2 の SC-05 参照 / delegated_consumers)。`module_api` に `scan_emoji(text) -> list[Violation]` を公開。
- `briefs/hook-brief-C10.json` — D2 のブロック denylist を削除し委譲記述へ置換。`pass_example` に `<h2>★ ポイント 3 つ</h2>` を追加。「★ ✔ © が通る」回帰検査を含む受け入れ検査 3 件を追加。

**降格させた側に残した参照記述**
C10 D2 に「Unicode ブロック丸ごとの denylist (旧記述の U+2600-U+27BF / U+2B00-U+2BFF 等) は廃止した」と経緯を残し、両ブリーフへ不変条件「**C10 と C16 は同一入力に対し必ず同一判定を返す**」を明記した。差異が出た場合はそれを実装バグとみなし、P06 が同一 fixture で突き合わせる (`AC-C16-11`)。

---

## Y-04 (blocking) — 同梱物の writer が不在

**指摘**
出力ディレクトリの同梱 4 点のうち、`handout-config.json` の配置と `assets/` 原本の複製について writer を名乗る component が無かった (C19 は「mkdir と存在検査のみ」、C13 は「配置しない」、C11 は `--out` と同じディレクトリへ書くと読める記述)。存在検査だけがあって書き手がいないため、正しく運用しても検査に落ちる。

**採用した単一正本**
出力ディレクトリの owner である **C19** (`route-handout-output.py`) を配置の writer に確定。同梱物ごとの writer 割り当ての正本は `briefs/script-brief-C19.json` の **`bundle_writers`** 表とする。

| 同梱物 | writer |
| --- | --- |
| `handout.html` | C11 (C19 が返したディレクトリへ 1 ファイルだけ書く) |
| `handout-config.json` | **C19** (`--place-config` で `--config` をバイト無加工で複製) |
| `assets/` | **C19** (mkdir と `--assets-src` からの再帰複製) |
| `README.md` | C01 (文言生成を伴うため決定論 script の責務ではない = X-08 の決着) |

**変更したファイルと箇所**
- `briefs/script-brief-C19.json` — `purpose` を「置いたうえで検査する」へ変更。argv に `--assets-src DIR` と `--place-config` を追加。`write_scope` を 5 項へ拡張し `single_writer` を書き換え、`bundle_writers` 表を新設。`algorithm` に手順 **9b** (assets 再帰複製・冪等・symlink や `..` での脱出は exit2) と **9c** (`--config` をバイト複製) を追加。手順 10 を「4 点それぞれに writer id を注記」+「`--check-only` のときだけ欠落を exit1、通常実行では present/absent 一覧を出して exit0」に書き換え (writer が書く前に自分で失敗する順序矛盾を避けるため)。受け入れ検査 7 件を追加。
- `briefs/script-brief-C11.json` — `--config-out FILE` を新設し、テーマ書き戻し先を出力ディレクトリ外の明示パスへ移動。`--theme` 単独指定は `--out` ではなく `--config-out` 未指定で exit2。`write_scope` 第 2 項・`single_writer`・手順 1/4/25・`AC-C11-12` / `AC-C11-13` を追随。
- `briefs/script-brief-C13.json` — `purpose` に「ファイルの配置には一切関与しない。素材原本を出力先 `assets/` へ複製するのは C19」を明記。
- `briefs/skill-brief-C01.json` — R4-verify に「`handout-config.json` と `assets/` の配置は C19 に `--place-config` / `--assets-src` を渡して行わせ、自分では置かない」を明記。
- `component-inventory.json` — C19 の purpose / inputs / outputs、C11 の inputs / outputs / purpose、C13 の purpose を上記へ整合。

**降格させた側に残した参照記述**
- C11 `single_writer`: 「同梱 4 点のうち本 script が writer であるのは `handout.html` 1 点だけである」。
- C11 `open_questions`: 旧案 (`--out` と同一ディレクトリへ `handout-config.json` を書く) を「同梱物の writer が 2 つになるため破棄した」と記録。
- C19 `open_questions` の X-08 記録は「README.md 1 点についての決着であり、Y-04 で確定した `handout-config.json` / `assets/` の配置 (writer = C19) とは対象が異なるため両立する」と限定し、矛盾しないようにした。

---

## Y-05 (high) — 部品 id 語彙に owner がいない

**指摘**
部品 id が `index.md` (B01-B15)・C04 の output_contract (B01-B15)・C12 の part_catalog (B01-B16 相当)・C18 LANG-06 (B03..B15)・C23 の recommended_parts (B16 を含む) に別々の版で散在し、B16 が存在するのかどうかすら文書ごとに違っていた。

**採用した単一正本**
データファイル **`config/handout-parts.json`** (plan 上の表現: `briefs/config/handout-parts.json`)。**owner / 唯一の writer は C11**。C23 の `config/handout-purposes.json` と同じ形 (語彙とその属性を宣言データで持つ) を踏襲した。
各エントリは `kind` / `section_scope` / `data_block_type` / `since` / `source` を持ち、C18 LANG-06 の「具体部品」述語は **`section_scope == "in-section"`** で判定する (id の範囲指定を使わない)。

**B16 の存在判定 (事実確認の結果)**
`analysis/guide-doc-generator/reference-analysis.md` を read-only で確認した。判定は **「B16 は存在する。ただし参照資料由来ではなく、本 plugin plan で新設した部品である」**。根拠は 3 点:
1. reference-analysis.md §2 の部品カタログは B01-B15 の 15 行のみで B16 は無い。
2. 同ファイル末尾が「骨格・部品カタログ・添付埋め込み (B01〜B15, §2) は v1 を正本とする」と書いており、参照資料側の語彙は B15 で閉じている。
3. `component-inventory.json` の `preset_addon_decisions` で「アクションアイテム要件」が verdict=`new` と判断され、C12 の部品表と C23 の agenda プリセットは既に B16 を前提にしている。

したがってカタログは B01-B16 + メディア 3 種 (IMG / DIAGRAM / TEXT) を持ち、B01-B15 は `since: "v1"`、B16 と メディア 3 種は `since: "plan"` とする。

**変更したファイルと箇所**
- `briefs/config/handout-parts.json` — **新規作成** (19 エントリ + `non_part_structure_markers`)。
- `briefs/script-brief-C11.json` — `parts_catalog_ssot` ブロック新設 (catalog_path / ownership / why_data_file / schema / `b16_determination` / consumer_contract: `load_parts_catalog()` / `is_known_part(id)` / `in_section_parts()`)。`purpose` の「部品 B01-B15」をカタログ参照へ置換。`AC-C11-5` をカタログ駆動へ、`AC-C11-19` (id 列挙が catalog 外に無いことの grep) / `AC-C11-20` を追加。
- `briefs/script-brief-C12.json` — `part_catalog` を **`part_data_schema`** へ改称し、各エントリの `name` を削除 (名前の正本を持たせない)。起動時にカタログと突き合わせ、不一致は `E-PARTS-CATALOG-MISMATCH` exit 2。
- `briefs/script-brief-C18.json` — LANG-06 の「B03..B15」を `section_scope == "in-section"` 述語へ置換。`AC-C18-06` を追随、`AC-C18-LANG06-CAT` (カタログに部品を足せば script 無改修で認識される) を追加。
- `briefs/skill-brief-C04.json` / `component-inventory.json` C04 — output_contract と boundary をカタログ参照へ。
- `briefs/agent-brief-C05.json` — 参照先を `references/` の散文から `config/handout-parts.json` へ。
- `briefs/script-brief-C23.json` — 手順 4(h) の recommended_parts 検査をカタログ + `section_scope=in-section` で行う形へ。
- `briefs/script-brief-C20.json` — 部品→クラス名の照合表の説明にあった「B01-B16 の id 自体は C12 のスキーマ正本と同期させる」を削除し、`config/handout-parts.json` (owner: C11) を id 集合の正本として参照する形へ置換。**C20 が保持してよいのは「部品 id → クラス名」の対応だけで、「どの部品 id が存在するか」は保持しない**という切り分けを明記し、照合表とカタログの過不足を起動時の自己整合検査で列挙する旨を追記した (C12 を id 語彙の出所として指す第二正本の解消)。
- `index.md` L65 / 要件被覆表の C12 行、`component-inventory.json` の responsibility_decisions・envelope_design — id 列挙を削除しカタログ参照へ。

**降格させた側に残した参照記述**
各所に「部品 id をこのファイル以外へ列挙しない」という規則と `config/handout-parts.json` へのポインタを残した。C12 側には `part_data_schema_note` として「id 語彙は C11 のカタログが正本であり、ここが持つのは部品ごとのデータ形だけ」と明記。

---

## Y-06 (medium) — 用途語彙の食い違い

**指摘**
`index.md` が用途語彙を独自に列挙し、しかも C23 の正本と食い違っていた (`一般配布資料=report` / `onboarding`・`guide` を同一視)。

**採用した単一正本**
**`config/handout-purposes.json`** (owner: C23)。正しい対応は **`guide` = 一般配布資料 / `report` = 報告資料** であり、`onboarding` は別語彙 (オンボーディング・導入ガイド)。

**変更したファイルと箇所**
`index.md` L66 — 語彙の列挙を削除し `config/handout-purposes.json` を指すポインタへ置換。旧記述が誤っていた点 (`一般配布資料=report` / `onboarding`・`guide` の同一視) を明記して削除理由を残した。

**降格させた側に残した参照記述**
「この index も含めて語彙をここへ列挙しない (P03 Y-06)」を本文に残した。C04 の boundary にも同じポインタを置いた。

---

## Y-07 (medium) — ゲート結果集約の二重実装

**指摘**
4 状態 (pass/fail/error/not-run) 分類と「not-run を pass に畳まない」規則が、C09 `/handout-verify` と C01 R4-verify の両方に書かれていた。また inventory の C09 description が 3 面しか列挙しておらず、depends_on の 4 件 (C16/C17/C18/C22) と食い違っていた。

**採用した単一正本**
`briefs/command-brief-C09.json` の **`canonical_aggregation` (id: CR-GATE-AGG)** = behavior 手順 4〜6。集約するゲート面は **C16 / C17 / C18 / C22 の 4 面**。

**変更したファイルと箇所**
- `briefs/command-brief-C09.json` — `description` を 4 面へ修正。`canonical_aggregation` ブロック新設 (gate_faces / delegated_consumers / invariant / rationale)。`open_questions` の 2 件 (3 面 vs 4 面 / C01 との突き合わせ) を「P03 Y-07 で決着」として閉じた。`AC-C09-AGG-1` (同一入力に対し直叩き経路と C01 経路が同一 verdict) を追加。
- `briefs/skill-brief-C01.json` および `component-inventory.json` の C01 responsibilities — R4-verify を「C09 を起動してその集約結果を受け取る。4 状態分類と全体 verdict の規則は再実装しない」に書き換え。
- `component-inventory.json` — C09 description を 4 面 (C16/C17/C18/C22) へ修正。

**降格させた側に残した参照記述**
C01 R4-verify に「規則は C09 の `canonical_aggregation` (CR-GATE-AGG) が単一正本であり、not-run を『通った』と読み替える判断をこちら側で持たない」を明記。

---

## Y-08 (blocking) — section_kind enum の循環参照

**指摘**
`section_kind` の enum は C12 のスキーマ散文が正本で、C23 がそれを参照し、同時に C12 が C23 のプリセットを参照していたため、C12 ⇄ C23 の相互依存になっていた。

**採用した単一正本**
中立なデータファイル **`config/handout-sections.json`** (plan 上の表現: `briefs/config/handout-sections.json`) に物理正本を移し、**writer は C12** の 1 つだけ。**C23 はこのファイルを読むだけで C12 を import しない**。これにより残る依存は **C12 → C23 (プリセット解決) の一方向**のみになる。

**変更したファイルと箇所**
- `briefs/config/handout-sections.json` — **新規作成** (`default: "standard"` と 6 種: standard / agenda-timebox / decisions / action-items / sources / known-unknown-next)。`_meta.cycle_note` に循環を断った経緯を記載。
- `briefs/script-brief-C12.json` — `section_kind` フィールド制約の enum 列挙を削除しファイル参照へ。`section_kind_ssot` ブロック新設 (ownership / why_neutral_file / read_access に「C23 は C12 を import しない (してはならない)」/ 検査規則自体は C12 に残る旨)。`dependencies.reads` に追加。
- `briefs/script-brief-C23.json` — 手順 4(h) を「データファイルを読んで照合する (C12 を import しない)」へ。`addon_requirements_as_common_schema.section_kind_enum` を列挙からポインタへ置換。`ownership` を「物理正本は中立データファイル、writer は C12、C23 は read-only」に書き換え。`dependencies.reads` に追加。
- `component-inventory.json` — C12 / C23 の purpose に依存の向きを明記。

**降格させた側に残した参照記述**
C23 の `ownership` に「section_kind の正本はこの component ではない」と残し、C12 側には「enum の値そのものはこのファイルに書かず、検査規則だけを持つ」と残した。

---

## Y-09 (medium) — 宣言エッジの食い違い 6 件

**指摘**
ブリーフ側の `dependencies` と `component-inventory.json` の `depends_on` が 6 箇所で一致していなかった。

**採用した単一正本**
依存グラフの正本は **`component-inventory.json`**。ブリーフ側は inventory と一致する形へ直し、消したエッジは `not_invoked_by` として理由つきで残す (再発時に「書き忘れ」と誤読されないため)。

| エッジ | 判定 | 対応 |
| --- | --- | --- |
| C11 → C07 | 誤り | C07 → C01 → C11 の 1 ホップ経由を直接呼び出しと誤記していた。C11 の `invoked_by` から削除し `not_invoked_by` に理由を記載 |
| C12 → C04 | 誤り | 括弧書きの読み違い。C12 の `invoked_by` から削除 |
| C12 → C07 | 誤り | C11 と同じ 1 ホップ誤記。削除 |
| C12 → C05 / C23 → C05 | 誤り | C05 の tools は Read / Write のみで script を起動できない。C12 の `invoked_by`、C23 の `invoked_by` と `consumer_contract` から削除し、「C05 が必要とするプリセットは C01 が取得して prompt へ渡す」を明記 |
| C16 → C21 | 誤り | C16 を呼ぶのは C21 相当の pre-write hook 経路ではなく **C10 の PostToolUse** (および 4 面ゲートの 1 面としての C09)。`invoked_by` を差し替え |
| C19 → C18 | 誤り | C18 は C19 を呼ばない。C18 は既存のディレクトリ名を `--out-dir` 文字列として受け取るだけ。inventory の `couples_with: C18` は「同じ命名規則を見る」関係であって呼び出し関係ではない旨を `not_invoked_by` に記載 |
| C01 depends_on に C03 が無い | 欠落 | inventory の C01 `depends_on` に `C03` を追加 |

**変更したファイルと箇所**
`briefs/script-brief-C11.json` / `briefs/script-brief-C12.json` / `briefs/script-brief-C16.json` / `briefs/script-brief-C19.json` / `briefs/script-brief-C23.json` の `dependencies` と新設 `not_invoked_by`、`component-inventory.json` の C01 `depends_on`。

**降格させた側に残した参照記述**
削除した各エッジは `not_invoked_by` に「なぜ呼び出し関係ではないのか」を 1 文で残した (1 ホップ経由 / tools 制約 / couples_with の意味)。

---

## 付記: 正本の一覧 (P03 時点)

| 語彙・規則 | 単一正本 | owner |
| --- | --- | --- |
| 外部参照の判定 (CR-EXT) | `briefs/script-brief-C16.json` `canonical_rules.external_reference_rule` | C16 |
| 絵文字の判定 (CR-EMOJI) | `briefs/script-brief-C16.json` `canonical_rules.emoji_rule` (SC-05) | C16 |
| ゲート結果の集約 (CR-GATE-AGG) | `briefs/command-brief-C09.json` `canonical_aggregation` | C09 |
| 部品 id 語彙 | `config/handout-parts.json` | C11 |
| section_kind enum | `config/handout-sections.json` | C12 (writer) |
| 用途語彙とプリセット | `config/handout-purposes.json` | C23 |
| 同梱物ごとの writer | `briefs/script-brief-C19.json` `bundle_writers` | C19 |
| `data-hb-*` 属性語彙 | `briefs/script-brief-C11.json` `html_attribute_contract` | C11 |
| 依存グラフ | `component-inventory.json` | — |
