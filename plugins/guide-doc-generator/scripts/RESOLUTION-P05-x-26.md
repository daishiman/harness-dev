# P05-x-26 裁定: `prune_chrome` を `chrome_boundary.rule` の穴あき走査へ合わせる

対象: `plugins/guide-doc-generator/scripts/extract-handout-config.py`
write_scope: `plugins/guide-doc-generator/scripts` (この外へは 1 バイトも書いていない)

## 1. 何が乖離していたか

`script-brief-C20.json#renderer_marker_requirements.chrome_boundary.rule` は
読み飛ばしの単位をこう定めている。

> `data-hb-generated="true"` は『この要素とその子孫のうち、著者データマーカーを
> 持たないノード』が再生成可能であることの宣言である。したがって読み飛ばしの単位は
> 部分木そのものではなく『著者データマーカーを持つノードを抜いた部分木』である。

一方、実装は chrome の子に出会った時点で `continue` し、その部分木を丸ごと落として
いた。子を一切見ないため、chrome 部分木の内側に著者データマーカーが 1 つ置かれた
瞬間にその値が**診断も出さずに**消える。現状は C11 が hero 枠を空の生成要素として
分離しているため実害が観測されていなかっただけで、宣言と実装の乖離そのものである。

## 2. 採った実装

`prune_chrome(node, authored_markers)` を穴あき走査にした。chrome に出会っても走査を
止めず、`perforate_chrome()` が内側から「著者データマーカーを持つ最も外側のノード」だけを
文書順に拾い上げる。枠は捨てるので、拾ったノードは chrome があった位置 — 最も近い
非 chrome の祖先の直下 — へそのまま繰り上がる。

拾ったノードの内側は通常の走査 (`prune_chrome`) へ戻す。したがってそこへさらに
`data-hb-generated="true"` が現れれば再び読み飛ばし対象になり、`chrome_boundary.nesting`
の「判定は最も内側の宣言が勝つ」が別扱いを足さずに成立する。

クラス名による二重防御 (`.pop-header` / `.pop-bottom` / `.memo-*`) も同じ経路を通る。
`is_generated_chrome()` が宣言経路とクラス名経路を 1 つの判定にまとめているため、
`chrome_boundary.class_name_fallback` の「クラス名は宣言より弱い根拠であり、宣言を
覆さない」が自動的に満たされる。ここで経路を分けると規定が二重化する。

### 著者データマーカーの集合をどこから採るか (PAT-1)

`chrome_boundary.authored_data_markers` は「その集合は marker_source_of_truth の
裁定表から導出する」と定めている。したがって literal で列挙せず、
`schemas/ROUNDTRIP-CONTRACT.md` の fenced JSON から `decision == "marker"` の裁定を
取り、その `marker` 文字列から属性名を正規表現で機械抽出する
(`load_roundtrip_contract()` / `authored_data_markers()`)。

`data-hb-generated` 自身は読み飛ばしを宣言する側の属性であって著者記述を運ばないので
除く (`chrome_boundary`: 「除外されないのは data-hb-generated 自身と、純粋な提示属性のみ」)。

現時点の導出結果 (**この一覧は実測の記録であって正本ではない。正本は裁定表側**):

```
data-hb-attainment-step / data-hb-field / data-hb-key / data-hb-notes-enabled
data-hb-section-role / data-hb-src / data-hb-ties-to
```

列挙を script へ書き写すと裁定表と二名簿になり、裁定が増えたときに黙って取りこぼす。
そのため導出に失敗したら fail-closed で `LaunchAbort` (exit 2) にする。既定へ退避すると
「chrome 内側の著者記述が黙って消える」側へ倒れ、直そうとしている不具合そのものへ戻る。

## 3. 実測

### 3.1 受入基準の両方向

計測器は scratchpad に置き、成果物へは残していない。

| 条件 | chrome 内側の著者マーカー | マーカーを持たない chrome |
| --- | --- | --- |
| 旧実装 (部分木を丸ごと) | `/title` = `None`、exit 1 (`E-EXTRACT-UNRECOVERABLE`) | 捨てられる |
| 本実装 (穴あき走査) | `/title` = `'chrome の内側に置いた著者タイトル'`、exit 0 | 捨てられる (part ids は 6 件のまま) |

`data-hb-field="date"` の内側へ `data-hb-generated="true"` の装飾を置いた入れ子でも、
値は `2026/08/17` のみで装飾テキストが混ざらない (`nesting` が効いている)。

### 3.2 反例注入 (検査が働いていることの証拠)

| 注入 | 期待 | 実測 |
| --- | --- | --- |
| 穴あき走査を消して旧挙動へ戻す | chrome 内側のマーカーが到達不能になる | `/sections/0/goal` が chrome 内側の値ではなく元の値に戻る / `/title` は `None` + exit 1 |
| 導出集合から `data-hb-generated` を外さない | chrome 自身が著者データ扱いになり parts へ混入する | section 内 chrome の `B09` が 1 件混入し part 数 6 → 7 (AC-C20-07 が破れる) |
| 裁定表を読めなくする | fail-closed | exit 2 |

いずれも注入時のみ赤になり、復元後は再び緑に戻ることを実測した。

### 3.3 テストスイート

`extract-handout-config.py` / `render-handout.py` / `validate-handout-config.py` /
`handout-extract` の 4 スイートについて、着手前と着手後で**失敗テスト名の集合が同一**で
あることを確認した (件数ではなく名前集合の差分で判定)。assert を弱めた箇所は無い。

## 4. 未解決事項 (この write_scope では手を出していない)

1. **`tests/extract-handout-config.py/test_chrome_skip.py` の宣言が旧規約のまま。**
   docstring は「部分木を丸ごと切り落とすこと」、`test_chrome_lead_line_does_not_
   override_section_lead_line` の説明は「部分木ごと読み飛ばすため」と書いており、
   `chrome_boundary.rule` と食い違う。同ファイルの README 行も同じ。
   本実装で赤にはならない (fixture のダミー `data-hb-field="lead_line"` は section の
   外にあり、繰り上がっても section の lead_line にはならないため) が、
   **宣言としては誤り**であり、テスト側の write_scope を持つ担当が直す必要がある。
2. **既存スイートに chrome 内側の著者マーカーを覆う検査が無い。**
   反例注入 2 (chrome 自身を著者データ扱いにする) を入れても
   `tests/extract-handout-config.py` は 152 件緑のままだった。fixture の chrome が
   すべて section の外に置かれているため、混入が parts に現れない。
   AC-C20-07 の守りとしては穴である。section 内側へ chrome を置いた検査が要る。
