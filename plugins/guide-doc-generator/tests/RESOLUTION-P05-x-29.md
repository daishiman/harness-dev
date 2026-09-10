# P05-x-29 裁定: AC-C11-19 の走査除外を「読まれないテキスト」へ厳密化する

- leaf: `P05-x-29` (depends_on: `P05-x-23`)
- write_scope: `plugins/guide-doc-generator/tests`
- 対象 AC: `AC-C11-19` (部品 id の第 2 の語彙をカタログ外に作らない)

## 1. 何が問題だったか

`P05-x-23` は「そのテキストを何かが読むか (実行される / 指示として読み込まれる)」という
**1 本の判断基準**を確立し、走査から外してよいものを 2 種類に限定した。

1. Python のコメントと docstring (実行されない)
2. `scripts/` 配下で**何にも読み込まれない**非実行ファイル (leaf の作業記録 `.md`)

ところが実装は `SCRIPT_EXECUTABLE_SUFFIXES = (".py",)` による **allowlist** で、
「`scripts/` 配下は `.py` 以外を走査しない」だった。基準は「読まれるか」なのに、
実装は「拡張子が `.py` か」を見ている。この差により `scripts/part-map.json` のような
**プログラムが読むデータファイル**が拡張子だけを理由に走査外へ落ちる。

これは P05-x-23 の worker 自身が「表を `config/` へ移して走査から外す Goodhart 的回避」
として明示的に退けた経路と、効果が同じである。発見時点で実害 (実ファイル) はゼロ。

## 2. 採った解

**allowlist を denylist へ反転し、除外条件を基準の文言そのものへ寄せた。**

| 観点 | 変更前 | 変更後 |
| --- | --- | --- |
| `scripts/` の扱い | `.py` **だけ**走査 (allowlist) | 「読まれない」と特定できるものだけ除外 (denylist) |
| 未知の拡張子 (`.yaml` `.toml` `.txt` …) | 素通り (走査されない) | 既定で走査対象 (fail-closed) |
| `scripts/*.json` | 素通り | 走査対象 |
| `scripts/*.md` | 拡張子で一律除外 | **どこからも参照されていない場合のみ**除外 |
| `.pyc` / `__pycache__` | decode 失敗で結果的に除外 | 生成物として明示除外 |

判断基準は増やしていない。増やしたのは「基準を実装へ写す精度」だけである。

### 2.1 `.md` の参照判定

除外条件の文言は「何にも読み込まれない」であって「`.md` である」ではない。よって
`scripts/*.md` も、走査対象のどれかがファイル名で参照していれば走査へ拾い直す。
判定材料は**散文マスク後**のテキストなので、Python のコメントが名前に言及しただけの
ものは「読んでいる」に数えない。

これを入れないと「参照付きの `.md` へ名簿を置く」が次の抜け道になる。現時点の
`scripts/RESOLUTION-P05-x-18.md` / `RESOLUTION-P05-x-19.md` はどこからも参照されて
いないため、この規則は現状 no-op で、将来に対してのみ fail-closed に効く。

### 2.2 生成物 (`.pyc` / `__pycache__`) の扱い

**走査しない。** 生成物は正本ではなく、正本を直せば必ず追随するので、走査しても
偽陽性を増やすだけである。従来も `UnicodeDecodeError` で結果的に落ちていたが、
「読めなかったから外れた」ではなく「生成物だから外す」と明示した。`__pycache__` 配下は
拡張子を問わず (誤って置かれた `.py` も含め) 除外する。

### 2.3 退けた案

- **`.json` だけを allowlist へ足す。** 今回の穴は塞がるが、次に `.yaml` を置かれたら
  また開く。allowlist である限り「まだ列挙していない拡張子」が常に抜け道になる。
- **`scripts/` を丸ごと走査対象へ戻す (P05-x-23 の narrowing を取り消す)。**
  基準を変えてしまう。leaf の作業記録が部品名に言及しただけで赤くなり、
  PAT-8 (常時発火による鈍麻) を招く。
- **検査を assert 側で緩める。** AC を弱めるだけで問題は解決しない。

## 3. 反例注入の実測 (両方向)

使い捨ての root へ反例を注入して実測した。**リポジトリ上の正本は一切変更していない。**
`scannable_sources(plugin_root=...)` / `enumerated_part_id_offenders(plugin_root=...)` へ
使い捨て root を渡す形にしたので、モジュールグローバルの書き換えも復元手順も存在しない
(復元手順が無ければ復元失敗も起きない)。root は `tempfile.TemporaryDirectory` で、
`with` を抜けると消える。

固定先: `tests/render-handout.py/test_scan_scope.py` (本 leaf で新規追加)。
部品 id はテスト内に書かず `H.catalog_parts()` から借りる。

### 3.1 RED を期待した反例

| # | 注入した反例 | 期待 | 実測 (修正後) | 実測 (P05-x-23 実装) |
| --- | --- | --- | --- | --- |
| R1 | `scripts/part-map.json` に部品 id の名簿 | RED | **RED** (`part-map.json` を指す offender) | GREEN (= 見逃し。塞いだ穴) |
| R2 | `scripts/part-map.yaml` / `part-map.txt` に名簿 | RED | **RED** (両方を検出) | GREEN (= 見逃し) |
| R3 | `scripts/gen.py` の実コード上に名簿 | RED | **RED** | RED (回帰なし) |
| R4 | `skills/run-x/SKILL.md` に名簿 | RED | **RED** | RED (回帰なし) |
| R5 | `scripts/part-roster.md` に名簿 + `loader.py` が名前で参照 | RED | **RED** | GREEN (= 見逃し) |

### 3.2 GREEN を期待した反例

| # | 注入した反例 | 期待 | 実測 (修正後) | 実測 (P05-x-23 実装) |
| --- | --- | --- | --- | --- |
| G1 | `scripts/RESOLUTION-P05-x-99.md` の散文 (参照なし) | GREEN | **GREEN** | GREEN |
| G2 | `scripts/render.py` の docstring / コメント内の散文 | GREEN | **GREEN** | GREEN |
| G3 | `scripts/part-roster.md` を `.py` の**コメント**だけが言及 | GREEN | **GREEN** | GREEN |
| G4 | `scripts/__pycache__/*.pyc` および `__pycache__/*.py` の名簿 | GREEN | **GREEN** | GREEN |
| G5 | R1 の名簿と G1/G2 の散文を**同時に**置く | 名簿だけ RED | **`part-map.json` のみ検出** | 検出ゼロ |

### 3.3 反例テスト自体の弁別力

反例テストが「本当に到達しているか」を確かめるため、P05-x-23 時点の allowlist 実装を
スクラッチへ複写して同じテストを実行した (リポジトリ側は read のみ)。

- P05-x-23 実装: **12 件中 5 件 FAIL** (R1 / R2 / R5 / G5 / 方針テスト)
- 本 leaf の実装: **12 件すべて OK**

GREEN 方向の 7 件はどちらの実装でも緑であり、narrowing の意図が保たれていることを示す。
片方向だけなら「直った」と「到達していない」を区別できないので、両方向を必須とした。

## 4. 4 スイートの失敗テスト名の集合 (着手前 / 着手後)

件数ではなく**名前の集合**で比較した (並行 build 下では件数比較が他 leaf の書込と交絡する)。
対象は AC-C11-19 とカタログを共有する 4 スイート。

| スイート | 着手前 | 着手後 | 差分 |
| --- | --- | --- | --- |
| `tests/render-handout.py` | `test_cross_component.GateHandoffTest.test_round_trip_equivalence` | 同左 | なし |
| `tests/extract-handout-config.py` | (なし) | (なし) | なし |
| `tests/verify-handout-a11y-print.py` | (なし) | (なし) | なし |
| `tests/validate-handout-config.py` | `test_document_fields.DocTypeVocabulary.test_unknown_doc_type_lists_vocabulary`, `test_normalize_date_determinism.FailClosed.test_no_temp_file_left_behind`, `test_normalize_date_determinism.NormalizeDefaults.test_provenance_shape`, `test_source_hygiene.SourceHygiene.test_no_purpose_vocabulary_literals` | 同左 | なし |

**追加 0 / 消失 0。** 上記の既存赤はいずれも本 leaf の対象外 (他 leaf 所有) であり、
本 leaf では触っていない。

## 5. 変更したファイル

| ファイル | 変更 |
| --- | --- |
| `tests/render-handout.py/_harness.py` | 走査除外を denylist 化 (`SCRIPT_UNREAD_SUFFIXES` / `GENERATED_*`)、`.md` の参照判定、`scannable_sources(plugin_root=...)`、`PART_ID_PATTERN` と `enumerated_part_id_offenders()` を追加 |
| `tests/render-handout.py/test_parts_catalog.py` | AC-C11-19 の検査を `H.enumerated_part_id_offenders()` 経由へ (assert の強さは不変)。未使用になった `import re` を削除 |
| `tests/render-handout.py/test_scan_scope.py` | 新規。両方向の反例注入 12 件 |

判定ロジックを `_harness` の 1 関数へ寄せたのは、**本番の検査と反例注入の検査が同じ経路を
通る**ようにするため。別実装のままだと「反例では鳴るが本番では鳴らない」を作り込める。

## 6. 未解決事項・追加タスク候補

1. **`references/` 配下の非テキスト資産。** 現状 decode 失敗で黙って落ちる。`.png` 等は
   語彙になり得ないので実害はないが、`GENERATED_SUFFIXES` と違い「意図した除外」として
   明示されていない。将来バイナリ形式の設定ファイル (`.msgpack` 等) が置かれると
   静かな穴になる。
2. **`config/` / `schemas/` / `genomes/` は `GREP_SCOPE_DIRS` に入っていない。**
   `config/handout-parts.json` が正本なので `config/` の除外は正当だが、
   「`config/` へ第 2 の表を置く」経路は依然として走査対象外。P05-x-23 が退けた
   Goodhart 的回避の本丸はここで、今回の denylist 化は `scripts/` 側しか塞いでいない。
   `config/` 内で「カタログ正本 1 ファイルだけを除外し、他は走査する」形へ絞る余地がある。
3. **参照判定はファイル名の substring 一致**であり、同名ファイルが複数階層にあると
   過剰に拾う (fail-closed 側なので安全側だが、偽陽性の芽ではある)。
4. 部品 id の正規表現 `\bB[01][0-9]\b` は `_harness.PART_ID_PATTERN` に置いたが、
   カタログの id 体系が `B20` 以降へ伸びると取りこぼす。カタログから id 集合を作って
   照合する形へ寄せられる (本 leaf の write_scope 内で可能だが、AC の意味を変えるため
   別 leaf の裁定に委ねる)。
