# 部品 id ↔ CSS クラス名 写像の owner 裁定 (P05-x-23)

`AC-C11-19` (カタログ外に部品 id リテラルを置かない) と
`tests/extract-handout-config.py/test_parts_catalog_ssot.py` (C20 に部品 id を鍵とする
照合表が 1 個存在すること) が両立しない、という報告 (PAT-7) への裁定。

## 1. 真因

対立していたのは「テストどうし」ではなく、**『部品 id → CSS クラス名』という写像の
owner が未決定であること**。写像を部品 id で鍵付けする限り、写像を持つ側は必然的に
部品 id を列挙する。「id を列挙してよい唯一の場所」(カタログ) と「写像を持つ場所」
(C20) が別々に決まっている以上、片方が必ず違反する。

## 2. 裁定

**写像の owner はカタログである。ただしカタログへクラス名の列を足すのではなく、
`data_block_type` を join 鍵にして写像を 2 つの表の合成へ分解する。**

| 表 | owner | 鍵 | 値 |
|---|---|---|---|
| `config/handout-parts.json#parts` | C11 (カタログ) | 部品 id | `data_block_type` ほか |
| `BLOCK_TYPE_CLASS_MAP` (`extract-handout-config.py`) | C20 | `data_block_type` | 同定の根拠クラス名 |

「部品 id → クラス名」は両者の join (`build_part_class_map()`) で**導出**する。
結果として C20 は部品 id を 1 つも列挙しない。

この形にすると各側が持つ知識が責務どおりに分かれる。

- カタログ = 「どの部品が存在し、それがどの block type か」(語彙)
- C20 = 「その block type を HTML のクラス名からどう見分けるか」(抽出の手口)

C20 が持っていた「B03 はステップ行である」という知識は、もともとカタログの知識の
複製だった。これが複製でなくなったので、`AC-C11-19` を弱めずに満たせる。

### 先例との整合

同じ方向が既に 2 箇所で選ばれており、本裁定はそれを 3 箇所目へ揃えるもの。

- `render-handout.py` の `PART_DATA_PROJECTIONS` (鍵 = `data_block_type`, P05-x-20)
- `verify-handout-a11y-print.py` の `load_part_ids_by_block_type()` (P05-x-07)

## 3. 退けた案

### (却下) カタログへ `selector_class` 列を足す

task-spec の本命案。部品 id のリテラルは確かに消えるが、次の 2 点で退けた。

1. **owner が逆になる。** クラス名は C20 が HTML を見分けるための手口であって、
   部品語彙の属性ではない。カタログ (C11 所有・C04/C12/C18/C23 が読む) へ
   C20 の抽出戦略を書き込むと、抽出器の都合で語彙正本が動くようになる。
2. **drift 検査が完全に死ぬ。** 両側が 1 ファイルへ畳まれるため、食い違いが
   原理上起きなくなり `W-EXTRACT-CATALOG-DRIFT` が永久に沈黙する (PAT-8)。
   加えて `_meta.source_of_truth` が指す plan 側カタログへの追随が必要になる
   (write_scope 外)。

`data_block_type` 鍵なら列の追加が要らず、plan 側への追随も発生しない。

### (却下) テストの assert を弱める / 表を `config/` へ移して走査から外す

P05-x-07 の worker が退けたとおり。前者は契約の放棄、後者は走査範囲を回避する
だけで第 2 の語彙は残るため Goodhart 的回避。

### (却下) `_class_map()` を「導出であること」の検査へ全面的に書き換える

task-spec の代替案 (b)。`_class_map()` は `dir(module)` で**形**を見ており、
dict の由来 (リテラルか導出か) を縛っていない。よって導出値でもそのまま通る。
書き換える必要が無かったので、変更を 1 メソッドに留めた。

## 4. `W-EXTRACT-CATALOG-DRIFT` の扱い — 死なせていない

写像が導出値になっても、**両側は依然として独立に書かれている**ので drift は起きる。
起きる場所が部品 id 空間から block type 空間へ移っただけである。

| 向き | 事象 | 報告する識別子 |
|---|---|---|
| カタログ → 照合表 | カタログの in-section 部品の block type に行が無い | 部品 id (実在する) |
| 照合表 → カタログ | 照合表の行をどのカタログ部品も要求していない | block type (実在する) |

後者で部品 id を名指さないのは、その部品がカタログから消えた時点で id がどこにも
残っていないため。**消えた id を名指せるのは C20 が id を覚えている場合だけで、
それはまさに本裁定が禁じた第 2 の名簿である。**

### 検査が生きていることの実測 (変異テスト)

`self_check_catalog()` の 2 つの向きを 1 つずつ削除し、対応するテストが赤くなることを
確認した (潰しても緑なら、その検査は何にも固定されていない = 死んだ検査)。

| 変異 | `test_class_map_row_without_catalog_entry_is_reported` | `test_catalog_entry_without_class_map_row_is_reported` |
|---|---|---|
| なし | GREEN | GREEN |
| 照合表 → カタログ の向きを削除 | **RED** | GREEN |
| カタログ → 照合表 の向きを削除 | GREEN | **RED** |

正常系では `W-EXTRACT-CATALOG-DRIFT` は 0 行 (stderr 全体が空・exit 0)。

### 途中で見つけた、検査を鈍らせていた点

`test_class_map_row_without_catalog_entry_is_reported` は元々
`assertIn(removed_part_id, res.stderr)` だった。しかし fixture HTML には当の部品が
含まれるため、カタログから消すと `E-EXTRACT-UNRECOVERABLE` が**別件として**その id を
stderr へ出す。本裁定後はこの経路だけでもテストが通ってしまい、drift 検査を丸ごと
削除しても緑のままになる状態だった。診断コードまで見る `assert_diag()` へ**強化**し、
対になる `test_catalog_entry_without_class_map_row_is_reported` も同様に強化した。

## 5. `AC-C11-19` の走査範囲についての裁定

`data_block_type` 鍵にしても `test_part_ids_are_not_enumerated_outside_the_catalog` は
緑にならなかった。実測した offender 30 件の内訳は 3 系統。

| 系統 | 件数 | 例 |
|---|---|---|
| C20 の照合表リテラル | 15 | `extract-handout-config.py:68-82` |
| `scripts/` 配下の leaf 作業記録 `.md` | 13 | `scripts/RESOLUTION-P05-x-18.md` |
| Python の docstring 内の散文 | 2 | `render-handout.py` の `flow()` / `build_doc_head()` |

走査は `rglob("*")` でファイル種別を絞らず、正規表現もコメント・散文を区別していな
かった。**leaf が RESOLUTION 文書を書いて部品 id に言及するたび offender が増える**
ため、作業するほど赤が深まる状態だった。

### 適用した規則

`AC-C11-19` が禁じているのは「第 2 の部品 id **語彙**」である。語彙になり得るのは、
**システムが実行するテキストか、エージェントが指示として読み込むテキスト**だけで、
何にも読み込まれない散文は語彙になり得ない。この 1 本の基準で 2 点だけ外した。

1. **Python のコメントと docstring** を空白へマスクしてから走査する
   (`_mask_python_prose()`)。文字列リテラル一般は潰さない — 照合表の鍵のような
   「データとしての文字列」はまさに検出したい対象で、潰すと assert が弱くなる。
   潰すのは文としての文字列 (docstring) とコメントのみ。
2. **`scripts/` 配下の非実行ファイル** (`.py` 以外) を対象外にする。`scripts/` は
   プログラムの置き場であり、そこへ置かれる `.md` は誰にも読み込まれない。

`skills` / `agents` / `commands` / `hooks` / `references` は**拡張子を問わず全て対象の
まま**。frontmatter を持たない `prompts/*.md` や `references/*.md` も指示として
読み込まれるので、ここを外すと本当に検出したい列挙を見逃す。

### 弱めていないことの実測 (反例注入 8 通り)

| # | 注入先 | 期待 | 実測 |
|---|---|---|---|
| a | `scripts/*.py` の実行されるコード | RED | RED |
| b | `skills/*/SKILL.md` (frontmatter あり) | RED | RED |
| c | `skills/*/prompts/*.md` (frontmatter なし) | RED | RED |
| d | `skills/*/references/*.md` | RED | RED |
| e | `commands/*.md` | RED | RED |
| f | `scripts/*.py` の docstring 内の散文 | GREEN | GREEN |
| g | `scripts/*.py` のコメント内の散文 | GREEN | GREEN |
| h | `scripts/*.md` の作業記録 | GREEN | GREEN |

a-e が本来検出すべき列挙、f-h が意図的な対象外。**実行に効くコード上の列挙は
依然として検出される**ことを a で確認している。

### 検討して採らなかった代替

`scripts/RESOLUTION-P05-x-*.md` を `schemas/` へ移す案 (既存の
`schemas/INPUT-CONTRACT-RESOLUTION.md` に倣う) を検討したが、**plan 側 task-spec の
`produces:` が `plugins/guide-doc-generator/scripts/RESOLUTION-P05-x-18.md` を指しており**
(`task-graph.json` の辺も同様)、plan は write_scope 外なので採らなかった。
→ 下記 7 章の申し送り事項。

## 6. 変更したファイル

| ファイル | 変更 |
|---|---|
| `scripts/extract-handout-config.py` | `PART_CLASS_MAP` リテラル → `BLOCK_TYPE_CLASS_MAP` + join 導出。`self_check_catalog()` を block type 空間へ。`Extractor` が起動時カタログから照合表を組む |
| `tests/extract-handout-config.py/test_parts_catalog_ssot.py` | drift 検査の 2 テストを `assert_diag()` で強化。1 件は報告識別子を block type へ |
| `tests/render-handout.py/_harness.py` | `scannable_sources()` / `_mask_python_prose()` を追加 |
| `tests/render-handout.py/test_parts_catalog.py` | 走査を `H.scannable_sources()` 経由へ |
| `schemas/PART-CLASS-MAP-RESOLUTION.md` | 本文書 (新規) |

`config/handout-parts.json` は**変更していない** (列の追加が不要な解を採ったため)。
`verify-handout-a11y-print.py` も無変更で成立している。

## 7. 申し送り (write_scope 外)

1. **leaf 作業記録の置き場が 2 系統に割れている。** 既存の慣行は
   `schemas/INPUT-CONTRACT-RESOLUTION.md` と `tests/*-ALIGNMENT.md` (どちらも
   `GREP_SCOPE_DIRS` の外) だが、P05-x-18 / P05-x-19 の task-spec は `produces:` を
   `scripts/` 配下にしている。`scripts/` は AC-C11-19 の走査対象なので、置き場を
   `schemas/` へ揃えるのが plan 側の一貫した扱いになる。
2. `plugin-plans/guide-doc-generator/briefs/script-brief-C20.json#heuristic_fallback.class_map`
   は部品 id 鍵の表として書かれているはずで、本裁定に合わせて `data_block_type` 鍵へ
   追随させる必要がある (contract 正本なので実装側からは触っていない)。
