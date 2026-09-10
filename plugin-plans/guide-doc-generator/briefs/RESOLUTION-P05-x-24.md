# RESOLUTION P05-x-24 — C17 / C22 brief を実装が獲得した実行時依存と失敗経路へ追随させる

leaf: `P05-x-24` / phase: P05 / entity: C17 (+C22)
write_scope: `plugin-plans/guide-doc-generator/briefs` — 実際に編集したのは
`script-brief-C17.json` / `script-brief-C22.json` / 本文書の 3 ファイルのみ。
`script-brief-C20.json` (P05-x-21 が編集) には触れていない。

---

## 1. 実装の実測 — `verify-handout-a11y-print.py` の exit 2

### 1.1 コード経路

- `PARTS_RELPATH = Path("config") / "handout-parts.json"` (:65)
- `ROOT_ENV_VARS = ("HB_ROOT", "CLAUDE_PLUGIN_ROOT")` (:64) → `resolve_root()` (:499)
  はこの順に env を見て、いずれも未設定なら `Path(__file__).resolve().parent.parent`
  (= plugin root) を root にする。カタログのパスは argv で差し替えられない。
- `class CatalogError(Exception)` (:495)、`load_part_ids_by_block_type()` (:507)
- 注入点 `ctx = Ctx(doc, css, load_part_ids_by_block_type())` (:1221)
- 捕捉点 `except CatalogError as exc: ... return 2` (:1314)

`load_part_ids_by_block_type()` が `CatalogError` を投げる条件は 4 つある。

1. カタログを読めない (`OSError`) — 不在・権限
2. カタログが JSON として不正 (`ValueError`)
3. `data_block_type` が一意でない (同じ block type に 2 部品)
4. 検査対象の block type (`map` / `chips` / `tabs`) がカタログに無い

### 1.2 再現手順

`git stash` は使わず、スクラッチへ `cp` して退避した。復元は `finally` で必ず実行する
スクリプトにした (scratchpad/`repro_exit2.py`)。呼び出しは黒箱ではなく
`build_parser()` の `add_argument` を先に読み、`--html` が必須・`--json-report` が任意で
あることを確認した上で組んだ。

```
cp plugins/guide-doc-generator/config/handout-parts.json <scratch>/handout-parts.json.bak
# 4 形へ差し替えて起動 → finally で cp 戻し
```

### 1.3 実測結果 (verbatim)

```
catalog sha256 (before) = 04580817c8ca5356f770d2b710225ca280cc858af6ac055d44e4c38f02e9b480
=== CASE 0: カタログ正常 (baseline) ===
exit=1
--- stderr ---
FAIL	A11Y-07	1:0	@media (prefers-reduced-motion: reduce)	prefers-reduced-motion と reduce の双方を含む @media ブロックが無い (scroll-behavior / animation / transition の抑制が宣言されていない)
FAIL	PRINT-01	1:0	@media print	@media print ブロックが 1 つも無い
FAIL	PRINT-04	1:0	@media print	セクションカードに対する break-inside / page-break-inside: avoid の宣言が無い
FAIL	PRINT-04	1:0	@media print	見出し要素 (h1..h6) に対する break-after: avoid 相当の宣言が無い
FAIL	STICKY-01	1:0	<style>	section 群へ到達するセレクタに対する正の scroll-margin-top / scroll-padding-top の宣言が無い
FAIL	STICKY-01	1:0	<script>	script に getBoundingClientRect による sticky 要素の実測 (該当 class/tag の取得との共起) が無い
--- stdout (先頭3行) ---
RESULT: FAIL /private/tmp/.../scratchpad/min.html
A11Y-01 PASS checked=0 violations=0
A11Y-02 PASS checked=0 violations=0

=== CASE A: カタログ不在 ===
exit=2
--- stderr ---
ERROR	部品カタログ正本を読めない: /Users/dm/orca/workspaces/harness/資料作成のプラグイン作成/plugins/guide-doc-generator/config/handout-parts.json ([Errno 2] No such file or directory: '/Users/dm/orca/workspaces/harness/資料作成のプラグイン作成/plugins/guide-doc-generator/config/handout-parts.json')
--- stdout (先頭3行) ---

=== CASE B: カタログが不正 JSON ===
exit=2
--- stderr ---
ERROR	部品カタログ正本を読めない: /Users/dm/orca/workspaces/harness/資料作成のプラグイン作成/plugins/guide-doc-generator/config/handout-parts.json (Expecting property name enclosed in double quotes: line 1 column 3 (char 2))
--- stdout (先頭3行) ---

=== CASE C: 検査対象の block.type が欠落 ===
exit=2
--- stderr ---
ERROR	部品カタログに検査対象の block.type が無い: chips, tabs
--- stdout (先頭3行) ---

=== CASE D: data_block_type が一意でない ===
exit=2
--- stderr ---
ERROR	部品カタログの data_block_type が一意でない: map
--- stdout (先頭3行) ---

catalog sha256 (after restore) = 04580817c8ca5356f770d2b710225ca280cc858af6ac055d44e4c38f02e9b480
RESTORED_OK = True
```

観測:

- 4 形すべてが exit 2 で、stdout は空、stderr は `ERROR<TAB>...` の 1 行。
- 4 形の ERROR 本文は互いに区別できる (読めない / block.type が無い / 一意でない)。
- baseline は exit 1 で、カタログ失敗 (2) と品質違反 (1) は明確に分離している。
- カタログ復元は sha256 一致で確認済み (`RESTORED_OK = True`)。
  加えて `git status --porcelain plugins/guide-doc-generator/config/` に差分が出ないことも
  確認した (当該ディレクトリは untracked ディレクトリ配下のため、sha256 一致が主証拠)。

**前提は崩れていない。dispatcher が未再現としていた exit 2 経路は実在する。**

## 2. C17 の exit code 棚卸し — 番号衝突は無い

task-spec の「既存に 2 が別の意味で使われていたら実装側が誤り」という警告に従い、
brief の宣言と実装の全 return 経路を突き合わせた (`re.finditer` で全 `return <数字>` /
`SystemExit` / `sys.exit` を列挙。`grep -oE '\b...'` は使っていない)。

実装 `verify-handout-a11y-print.py` の終了経路 (行番号は現行実装):

| 行 | code | 条件 |
|---|---|---|
| 1201 | argparse 由来 | `SystemExit(status)` (`--help` = 0)。usage エラーは `UsageError` 経由で 1294 の 2 へ回る |
| 1294 | 2 | 引数が不正 |
| 1299 | 2 | `--html` のファイルが存在しない |
| 1302 | 2 | `--html` がファイルではない |
| 1307 | 2 | `--html` を UTF-8 デコードできない |
| 1310 | 2 | `--html` を読み取れない (OSError) |
| **1316** | **2** | **`CatalogError` (今回の新経路)** |
| 1320 | 2 | 検査中の回復不能例外 |
| 1327 | 2 | `--json-report` の親ディレクトリが無い |
| 1335 | 2 | `--json-report` を書き込めない |
| 1339 | 0 / 1 | `report["result"] == "PASS"` なら 0、それ以外 1 |

**使われている code は 0 / 1 / 2 の 3 種類だけで、それ以外は無い。**
既存の 2 の意味は「検査そのものが成立しなかった」であり、カタログを解決できず
検査対象の器を同定できない状態はその一例に収まる。**番号衝突は無く、実装側の誤りも
無い。** 別番号 (3 等) を新設する必要も無い。

裁定: **カタログ失敗へ新番号を割かず、既存の 2 の定義文へ「部品カタログ正本を解決
できない場合」を明示的に足す。** 理由を brief 本文へ書いた — 呼び出し側 (C01) が
必要とする分岐は「品質が悪い (1)」と「検査が成立していない (2)」の 2 つであり、
2 をさらに細分しても呼び出し側の行動は変わらない。細分の情報は stderr 本文が担う。

同様の棚卸しを C22 (`verify-handout-narrative.py`) でも行った。終了経路は
1386 の `return 1 if verdict == "FAIL" else 0` と 1395 の `except GateError: return 2`
のみで、こちらも 0 / 1 / 2 の 3 種類。C22 は 4 種の同梱データ
(parts / sections / schema / theme tokens) を実行時に読み、いずれも失敗時は
`GateError` → 2 に落ちる。これも brief 未宣言だったので同時に宣言へ書き戻した。

## 3. C17 brief への書き戻し (編集内容)

1. `exit_codes["2"]` — カタログ解決失敗を追記し、「別番号を割かない」理由を明記。
2. `dependencies.reads` — `config/handout-parts.json` を実行時依存 (read-only) として追加。
3. `dependencies.runtime_catalog` (新設サブキー) — path / root_resolution
   (`HB_ROOT` → `CLAUDE_PLUGIN_ROOT` → script の 2 階層上) / why_runtime (P03 Y-05,
   AC-C11-19) / predicate (`data_block_type` 述語) / `catalog_invariants_required`
   (3 項) / on_failure。
4. `algorithm` — `1b.` としてカタログ解決段を検出評価より前に挿入。`9.` の文言を
   カタログ込みへ更新。
5. `failure_modes` — カタログ 4 形の失敗ケースを追加。1 でも 0 でもなく 2 に落とす
   理由を書いた。
6. `acceptance_checks` — `AC-C17-13` (カタログ退避 → exit 2 / stdout 空)、
   `AC-C17-14` (不正 JSON / block type 欠落 / 重複の 3 形を stderr 本文で区別) を追加。
   `catalog_invariants_required` の各項と 1 対 1 に対応させた。
7. `detections` A11Y-01 / A11Y-02 — 判定条件から部品 id の literal (`B08` / `B15` /
   `B13`) を外し、「トグル UI を持つ block type / タブの block type に対応する部品 id
   をカタログから引く」導出形へ書き換えた (PAT-1)。`violation_example` /
   `pass_example` / テスト fixture (`AC-C17-02`) の literal は残した — これらは
   説明用の実例であって判定条件ではないため、二名簿にはならない。

## 4. C22 brief への書き戻し — hero フィールドの解決規約

### 4.1 実測した事実

`plugins/guide-doc-generator/tests/render-handout.py/_harness.py` の `base_config()` を
使って実際に描画し (`render_html` は `(res, html, path)` の 3-tuple を返す —
戻り値の形を確かめずに使って一度 `TypeError` を踏んだ)、
`extract-handout-config.py` の `build_tree()` / `prune_chrome()` を適用して測った。

- `prune_chrome(node)` は **破壊的で戻り値を返さない (`None`)**。
  最初 `pruned = ex.prune_chrome(tree)` と書いたため `walk(None)` を測ってしまい、
  「枝刈りで全フィールドが消えた」という**逆の結論**が出かけた。木を 2 本作って
  測り直した。これは「検査対象へ到達していない結果と正しく測った結果は出力では
  区別が付かない」の実例なので記録しておく。

枝刈り**前**の祖先鎖 (実測):

```
date                 body.handout > header.doc-head > p.doc-date > span.date-pill num
title                body.handout > main.wrap > div.hero > h1
duration             main.wrap > div.hero > p.hero-meta > span.hero-duration num
purpose              main.wrap > div.hero > p.hero-purpose > span
background           main.wrap > div.hero > p.hero-background > span
goal                 main.wrap > div.hero > p.hero-goal > span
focus_theme          main.wrap > div.hero > ul.meta-list focus-theme > li   (×2)
target_task          main.wrap > div.hero > ul.meta-list target-tasks > li
attainment_level     main.wrap > div.hero > p.attainment > span
must_remember        main.wrap > div.hero > ul.meta-list must-remember > li
no_need_to_remember  main.wrap > div.hero > ul.meta-list no-need > li
```

枝刈り**後**に残存した `data-hb-field` の集合は枝刈り前と完全一致し、
**消えたフィールドは 0 件**だった。

決定的な事実 2 つ:

- **`data-hb-part`(hero 部品) は `.hero-frame` — 中身が空で `aria-hidden="true"` かつ
  `data-hb-generated="true"` の枠 — に付いている。** 著者記述 (`purpose` 等) は
  `.hero` の子であって、hero 部品マーカーの部分木の**外側**にある。
- **`date` は `<header class="doc-head">` にあり、hero 部品マーカーより文書順で前。**

したがって旧 NAR-01 の位置条件「3 要素すべてが hero 要素 (`data-hb-part="B02"`) の
内部、または hero の直後の兄弟ブロック内」は**現行の実描画に対して偽**である。
しかも偽り方が悪い: 枠の中身が空なので「対象 0 件」になり、静かに PASS へ畳まれる。

実装 `verify-handout-narrative.py` の `_is_in_hero_region()` は既に包含関係ではなく
**文書順の窓** (hero マーカーの seq 以降、最初の section の seq より前) で書かれており、
brief の側だけが古かった。実描画に対して `NAR-01 PASS checked=3` / `NAR-02 PASS checked=3`
を実測で確認した。

### 4.2 宣言した規約 (`canonical_rules.hero_field_resolution` = CR-HERO1)

「どの要素の中にあるか」ではなく「**どのマーカーで引くか**」で書いた。

- **statement**: 文書レベルのフィールドは `data-hb-field="<フィールド名>"` によって
  **のみ**同定する。器の包含関係 (hero 部品の部分木か、header か、直後の兄弟か) を
  同定条件に用いない。マーカーが一致すれば文書のどこにあってもそのフィールドであり、
  マーカーが無ければ hero の内側にあってもそのフィールドではない。
- **rationale**: P05-x-18 の実測 (§4.1) をそのまま根拠として書いた。
- **field_set**: **列挙しない (PAT-1)。** 「C20 の `required_markers` に現れる
  `data-hb-field` の値のうち、handout-config スキーマで document スコープ
  (`sections[]` の外) に属するもの」と定義し、正本は
  `schemas/ROUNDTRIP-CONTRACT.md` の adjudications であると明記した。
  C20 の `marker_source_of_truth` と二名簿にしないため。
- **cardinality**: 単数/複数もスキーマ型から導出する。スカラーは 1 個ちょうど、
  配列は要素 1 件につきマーカー 1 個。識別子を持つ配列要素は `data-hb-key` を併置。
- **value_extraction**: 可視テキストを algorithm 4 の正規化関数で正規化。
  装飾兄弟要素をマーカー要素の内側へ含めない。
- **position_conditions_allowed**: 位置条件を課してよいのは「冒頭に描画されている
  こと」自体が要件である場合 (NAR-01) に限り、その場合も**器の包含関係ではなく
  文書順の窓**として書く。**日付は hero マーカーより前に出るため、この窓を全フィールドへ
  広げてはならない**と明記した。
- **part_id_literals**: hero / nav 部品を `B01` / `B02` の literal で名指ししない。
  骨格部品の id は部品カタログの `section_scope=document` からカタログ順で導出する
  (実装は既にそうしている)。
- **implemented_by_detections**: NAR-01 / NAR-02。**新しい detection は足していない**
  — `detection_order_contract` により detections 配列が CLI 契約の件数の唯一の正本で
  あり、増やすと実装・stdout・テストが同時に動く。今回は宣言の追随であって
  検出の追加ではない。

受入基準が名指しする 8 フィールド (`title` / `date` / `duration` / `focus_theme` /
`target_task` / `attainment_level` / `must_remember` / `no_need_to_remember`) は、
**規約本文の名簿としてではなく acceptance check の被検インスタンス**として置いた
(`AC-C22-CR-HERO1-a`)。そこには「これは導出結果の実測スナップショットであり、
本 brief 側の名簿ではない」と明記してある。テスト fixture が具体値を持つのは
二名簿ではない (突合の被検側だから) という整理である。

### 4.3 併せて直した C22 の食い違い

- `NAR-01.rule` — 包含条件を撤去し、CR-HERO1 に従うマーカー同定 + 文書順の窓へ。
  hero 部品マーカーが見つからない文書では窓の下端を課さない (実装 `_is_in_hero_region`
  の `doc.hero is None` 経路と一致)。
- `NAR-01.pass_example` / `violation_example` — `.hero` / 空の `.hero-frame` の
  現行構造へ更新。
- `NAR-07.rule` — 走査起点の `hero (data-hb-part="B02")` を導出参照へ。
- `AC-C22-01.how` — 「hero 内にあり」を「冒頭の窓に描画され」へ。
- `exit_codes["2"]` — 同梱データ解決失敗を追記。
- `dependencies.runtime_data` (新設サブキー) — 実行時に read-only で引く 4 ファイル
  (parts / sections / schema / theme tokens) と `on_failure`。CR-HERO1 の
  `part_id_literals` がこの導出を前提にするため、依存を宣言しないと規約が宙に浮く。
- `acceptance_checks` — `AC-C22-CR-HERO1-a`..`-d` を追加 (8 フィールドのマーカー同定 /
  hero マーカー部分木が空でも PASS すること + date が窓の下端より前にあること /
  chrome 枝刈り後に 1 件も失われないこと / 骨格部品 id を差し替えても結果が変わらないこと)。

## 5. C20 `chrome_boundary` との整合の取り方

`script-brief-C20.json` の `renderer_marker_requirements.chrome_boundary` を読んだ上で、
**同じ立場を参照する形**にした (規定文を複製していない)。CR-HERO1 の
`chrome_boundary_alignment` に次を書いた。

- `data-hb-field` は chrome_boundary が言う「著者データマーカー」であり、
  `data-hb-generated="true"` の部分木の内側に現れても読み飛ばし対象から外れる
  (chrome_boundary の `rule` / `authored_data_markers` と同じ)。
- したがって CR-HERO1 は「著者記述が chrome の外に置かれていること」を**前提にしない**。
  現行 C11 は hero 枠を空の生成要素として分離することで条件を満たしているが、
  規約はその実装方式に依存しない — chrome_boundary の `not_specified_here`
  (枠分割にするか穴あき走査にするかは P05-x-18 / P05-x-19 の裁量) と整合する。
- chrome の存在・不在から値を推定しない (chrome_boundary の
  `no_inference_inside_chrome` と同じ立場)。

矛盾しないことの実測: 現行の `prune_chrome()` は部分木を丸ごと落とす実装だが、
C11 が枠を空にしているため 8 フィールドは 1 件も失われない (§4.1)。
`AC-C22-CR-HERO1-c` はこの相互検証を回帰として固定するために置いた。
なお `prune_chrome()` が chrome_boundary の言う「著者データマーカーを持つノードを
抜いた部分木」を実装していない点は C20 (P05-x-19) の領分であり、本 leaf では
手を出していない (§8)。

## 6. トップレベルキー集合の保存 (実測)

編集前にキー列を記録し、編集後に突き合わせた。

```
C17 keys equal(as list/order): True | set equal: True | n= 21
C22 keys equal(as list/order): True | set equal: True | n= 22
```

両ファイルとも `json.load` を通り、**順序も含めて一致**。追加はすべて既存
トップレベルキーの内側 (`dependencies` / `algorithm` / `detections` /
`acceptance_checks` / `failure_modes` / `canonical_rules`) に収めた。

`script-brief-C20.json` は読み取りのみで、`json.load` が通ることと
sha256 `f48131d5f9599bece61a7fc356dbfac820c4d42314315c68e981c1053433b3e7` を確認した
(編集していない)。

## 7. dispatcher 前提のうち外れていたもの

1. **「exit 2 経路は未再現」** → 再現した。前提は崩れていない (§1)。
2. **「task-spec の件数記述を信用するな」** → 今回は C17 の exit code に不揃いは
   **無かった** (0/1/2 の 3 種のみで衝突なし)。ただし警告に従って全経路を列挙して
   確認したこと自体は必要だった — 検査せずに「無い」とは言えなかったため。
   一方で **C22 側に未宣言の実行時依存が 4 件**あることが同じ棚卸しで見つかり、
   これは task-spec が言及していない追加の食い違いだった。
3. **「hero フィールドの解決規約が C22 に無い」** (task-spec の記述) → 正確には
   「無い」のではなく **NAR-01 に位置ベースの誤った規約があった**。無いものを足す
   のではなく、誤っているものを撤去してマーカーベースへ置き換える作業だった。
4. **`prune_chrome()` の戻り値** — dispatcher は「`build_tree()` + `prune_chrome()` を
   実際に適用して実測済み」としていたが、この関数は破壊的で `None` を返す。
   素直に `pruned = prune_chrome(tree)` と書くと全フィールドが消えたように見える。
   dispatcher の結論 (フィールドは残存する) 自体は当方の測り直しでも一致した。

## 8. write_scope 外として手を出さなかった事項

- **`script-brief-C20.json`** — P05-x-21 の担当。読むだけで編集していない。
- **`plugins/guide-doc-generator/scripts/*.py`** (実装) — 一切変更していない。
  以下は観測のみで報告に留める。
  - `extract-handout-config.py` の `prune_chrome()` は `data-hb-generated` の部分木を
    丸ごと落としており、C20 brief の `chrome_boundary.rule` が言う「著者データ
    マーカーを持つノードを抜いた部分木」を実装していない。現状は C11 が枠を空に
    しているため実害が出ていないが、chrome 部分木の内側へ著者マーカーが 1 つでも
    置かれた瞬間に値が消える。C20 (P05-x-19) の領分。
  - `verify-handout-narrative.py` は brief 未宣言の同梱データ 4 件を読む。brief 側は
    今回宣言へ書き戻したが、実装の変更は不要 (実装が正しく brief が古かった)。
  - C17 brief の A11Y-04 は `data-hb-part="B05" 配下の <table>` と書いているが、
    実装 `detect_a11y04()` は文書内の全 `<table>` を対象にしている。brief 本文自体が
    続けて「table が data-hb-part を持たない場合も検査対象に含める」と書いており
    最終的な判定条件は一致するため、今回の受入基準の範囲外として書き換えていない。
    冒頭句が誤読を招く点は後続 leaf の候補として記録する。
- **カタログ `config/handout-parts.json`** — 再現のため一時的に差し替えたが、
  sha256 一致で復元済み (§1.3)。`git stash` は使っていない。
- **git commit / push / 設定ファイル** — 行っていない。
