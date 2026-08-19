# RESOLUTION-P05-x-13 — C20 の常時発火する catalog-drift 警告

task: `P05-x-13` / consumes: `briefs/script-brief-C20.json` / write_scope: `plugin-plans/guide-doc-generator/briefs/`

## 1. 現象の実測

完全マーカー付き HTML (`tests/extract-handout-config.py/_harness.py` の `full_html()`
— これは `renderer_marker_requirements.required_markers` に列挙されたマーカーだけで
組んだ「C11 が出したはずの HTML」) を `extract-handout-config.py --html ... --out ...`
へ与えた。exit code は 0 (正常系) で、stderr は次の全文だった。

```
W-EXTRACT-CATALOG-DRIFT /parts B16 はカタログにあるが照合表に鍵が無い (heuristic 経路なし)
W-EXTRACT-CATALOG-DRIFT /parts B17 はカタログにあるが照合表に鍵が無い (heuristic 経路なし)
W-EXTRACT-CATALOG-DRIFT /parts DIAGRAM はカタログにあるが照合表に鍵が無い (heuristic 経路なし)
W-EXTRACT-CATALOG-DRIFT /parts IMG はカタログにあるが照合表に鍵が無い (heuristic 経路なし)
```

対象部品は `B16` / `B17` / `DIAGRAM` / `IMG`。起票時の前提と一致した。
diagnostic の向きは片側のみ (「カタログにあって照合表に鍵が無い」) で、
逆向き (「照合表の鍵にあるがカタログに無い」) は正常系では発火していない。

原因は `heuristic_fallback.class_map` が `B03`..`B15` と `TEXT` の行しか持たず、
カタログ (`config/handout-parts.json`) の `section_scope = in-section` 部品のうち
上記が漏れていること。自己整合検査 (RESOLUTION-P03.md Y-05) は対象 HTML と無関係に
起動時へ走るため、この差は毎回・全実行で報告される。

## 2. 採った解: class_map への行追加

`script-brief-C20.json` の `heuristic_fallback.class_map` へ、漏れていた
`B16` / `B17` / `DIAGRAM` / `IMG` の行を追加した。根拠になるクラス名は推測ではなく、
C11 レンダラ (`plugins/guide-doc-generator/scripts/render-handout.py`) が実際に出力する
マークアップから採った。

| part | 追加した selector | C11 側の出力箇所 |
| --- | --- | --- |
| B16 | `ul.action-items / .ai-row` | `action_items()` が `ul.action-items` と `li.ai-row` を出す |
| B17 | `ol.handson / .hs-row` | `handson()` が `ol.handson` と `li.hs-row` を出す |
| DIAGRAM | `figure.diagram / svg[data-hb-kind=figure]` | `diagram()` が `figure.diagram` と `<svg data-hb-kind="figure">` を出す |
| IMG | `figure.asset / img.asset-img` | `image()` が `figure.asset` と `img.asset-img` を出す |

あわせて 2 つの契約文を追記した。

- `class_map_completeness`: カタログの in-section 部品は全件この表に行を持つこと、
  整合していれば自己整合検査は 1 行も出さないこと、カタログ追加のたびに追従させること。
- `recovery_limits`: class_map は「部品種別の同定」までしか担わない。DIAGRAM は
  生成 SVG から構造データへ戻せず、IMG は原本相対パスと asset_id を、B16 は
  owner / due を、属性なしでは持てない。同定を諦めて TEXT にするのではなく、
  同定したうえで欠けた値を `E-EXTRACT-UNRECOVERABLE` として報告する。

## 3. 検査の片方向化を採らなかった理由

「カタログにあって class_map に鍵が無い場合を drift として扱わない」という片方向化も
許された解として提示されていたが、採らなかった。理由は 3 つ。

1. **警告は事実として正しかった。** これらの部品には本当に heuristic 経路が無い。
   報告を止めても事実は変わらない。直すべきは原因であって報告ではない。
2. **止める向きが、この検査の主目的そのものだった。** 自己整合検査が守っているのは
   「カタログへ部品を足したのに heuristic 経路を足し忘れた」という drift の検出で、
   それはまさに片方向化で消える側の向きである。既存テスト
   `test_parts_catalog_ssot.py::test_catalog_entry_without_class_map_row_is_reported`
   がこの向きの発火を assert しており、片方向化はこの assert を弱めることになる
   (task-spec の「緑にするために既存 assert を弱めない」に抵触する)。
3. **黙らせると実害が残る。** class_map に行の無い部品は、マーカー無し HTML で
   最終行の受け皿 `TEXT` へ落ちる。すなわち図解や画像やアクション行が本文テキストへ
   化けたまま復元される。警告を消すとこの静かな劣化だけが残る。行を足す解は
   この実害も同時に消す。

## 4. 追随後の実測

`class_map` へ上記の行を持つ状態の抽出器 (repo 外の shadow コピーで brief に追随させた
もの。詳細は §5) に、同じ完全マーカー付き HTML を与えた結果:

```
exit 0
stderr: (空)
```

`W-EXTRACT-CATALOG-DRIFT` は 1 行も出なくなった。

### 本物の drift では依然発火することの確認

検査を殺していないことを、両方向について実測で確かめた。

- カタログへ heuristic 経路を持たない部品 `B98` を追加 → exit 0 のまま
  `W-EXTRACT-CATALOG-DRIFT /parts B98 はカタログにあるが照合表に鍵が無い (heuristic 経路なし)`
  が出る。
- カタログから `B15` を削除 (照合表には鍵が残る) → 逆向きの
  `W-EXTRACT-CATALOG-DRIFT /parts B15 は照合表の鍵にあるがカタログに無い` が出る
  (同時に当該部品が `E-EXTRACT-UNRECOVERABLE` になり exit 1)。

すなわち「正常系では黙り、実際の drift では両方向とも鳴る」状態になっている。

## 5. write_scope による未完了部分 (要フォロー)

`W-EXTRACT-CATALOG-DRIFT` の発火判定は、brief ではなく実装
`plugins/guide-doc-generator/scripts/extract-handout-config.py` の モジュール定数
`PART_CLASS_MAP` とカタログの突き合わせで行われる。抽出器は実行時に brief を読まない。
本タスクの write_scope は `plugin-plans/guide-doc-generator/briefs/` に限られるため、
**repo 内の実装は未変更であり、repo 現状の stderr は §1 のまま**である。
§4 の実測は、repo 外 (scratchpad) の shadow コピーへ brief 追随の変更を当てて取った。

実装側に必要な追随は `PART_CLASS_MAP` への行追加のみ:

```python
    "B15": ("pop-chips",),
    "B16": ("action-items", "ai-row"),
    "B17": ("handson", "hs-row"),
    "DIAGRAM": ("diagram",),
    "IMG": ("asset", "asset-img"),
    "TEXT": ("p", "div"),
```

この変更を当てた shadow に対して C20 の受入スイートを全件実行し、回帰が無いことを
確認済み (Ran 152 / failures 0 / errors 0)。`TEXT` は「どの型にも当たらない本文」の
受け皿なので、追加行は必ずその手前へ置く必要がある。

## 6. 本タスクで触れていない隣接事項

- `W-EXTRACT-OPTIONAL` の stderr 契約への追記は `P05-x-16` の担当。同じ
  `script-brief-C20.json` を触るため、競合回避のため本タスクでは一切触れていない。
- `script-brief-C20.json` の `stderr` 契約行には `W-EXTRACT-CATALOG-DRIFT` 自体も
  未記載である (実装と RESOLUTION-P03.md Y-05 にしか無い)。ただしその行は
  `P05-x-16` が編集する同一文字列であり、競合を避けるため本タスクでは変更しなかった。
  診断コードの stderr 契約への記載は `P05-x-16` 側か、別タスクで扱うのが安全である。
