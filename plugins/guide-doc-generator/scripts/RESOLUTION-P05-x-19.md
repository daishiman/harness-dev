# RESOLUTION-P05-x-19 — C20 の照合表を brief の class_map へ追随させた記録

対象: `plugins/guide-doc-generator/scripts/extract-handout-config.py` (単一ファイル)
task-spec: `plugin-plans/guide-doc-generator/task-specs/P05-x-19.md`
受入基準: 完全マーカー付き HTML への正常系実行で `W-EXTRACT-CATALOG-DRIFT` が 0 行。
双方向の drift 検査 (`self_check_catalog`) は無改変。自スイート 152 件が緑。

---

## 1. 採った解 — 照合表へ 4 行を追加した

`PART_CLASS_MAP` へ、カタログの `section_scope=in-section` のうち行が無かった
4 部品の行を追加した。値はいずれも C11 `render-handout.py` の実出力から採った
クラス名で、当方が独立に確認した (行番号は実測):

| 部品 | 追加した根拠クラス名 | renderer の出所 |
|------|----------------------|-----------------|
| action-items 型 | `action-items` / `ai-row` | `render-handout.py:749` (`ul`) / `:744` (`li`) |
| handson 型 | `handson` / `hs-row` | `render-handout.py:765` (`ol`) / `:762` (`li`) |
| `DIAGRAM` | `diagram` | `render-handout.py:816` (`figure`) |
| `IMG` | `asset` / `asset-img` | `render-handout.py:785` (`figure`) / `:779` (`img`) |

(task-spec 手順 1 が挙げた行番号 745 / 750 / 763 / 766 / 813 / 817 / 780 は
現在の `render-handout.py` とは 1〜4 行ずれている。クラス名の綴りはすべて一致した。
`P05-x-18` が同ファイルへ加除を行ったための移動と見られる。)

追加後の該当行 (`PART_CLASS_MAP` は `:67-88`):

```python
    "B16": ("action-items", "ai-row"),
    "B17": ("handson", "hs-row"),
    "DIAGRAM": ("diagram",),
    "IMG": ("asset", "asset-img"),
    "TEXT": ("p", "div"),
```

`TEXT` は最後のままである。`FALLBACK_PART_ROW = "TEXT"` は本文の受け皿であり、
`guess_part` (`:689` 以降) がこの行だけ**タグ名照合**として扱う (他の行はクラス名照合)。
順序に意味があることを表直上のコメントへ明記した。

`self_check_catalog` (現 `:268-278`、変更前の `:261-267`) は **1 行も変更していない**
(コメント行の追加によって行番号だけが下へ移動した)。
本 leaf の変更は照合表のデータ行 4 行と、その直上の説明コメントだけである。

## 2. 裸 `<img>` を拾うかどうか — 拾わないと決めた

brief の `heuristic_fallback.class_map` は `IMG` の行へ
「`figure.asset / img.asset-img` (本文中の単独 `<img>` を含む)」と書いているが、
**本実装では「本文中の単独 `<img>`」を拾わない**。理由は 3 つで、いずれも実測に基づく。

1. **書いても効かない (無言の嘘になる)。** `guess_part` は表の値をクラス名として
   `node.classes()` と突き合わせる。タグ名照合は `FALLBACK_PART_ROW` の 1 行だけの
   特例である。ここへ `"img"` を足しても `class="img"` を持つ要素にしか当たらず、
   裸の `<img>` タグには当たらない。実際に効かせるには `guess_part` に
   「クラスでもタグでも当たる」第 2 の照合軸を足す必要があり、そうすると
   表のすべての値が「クラス名かタグ名か曖昧」になる (例えば `TEXT` の `"p"` が
   `class="p"` にも当たり始める)。表の意味を壊す変更であり、
   照合表の設計そのものへの変更は `P05-x-23` の裁定待ちの領域である。
2. **意味情報の捏造にあたる。** クラス名を持たない `<img>` は、手書き HTML では
   装飾アイコン・ロゴ・区切り線であることが多い。これを部品へ昇格させると、
   `asset_id` も `data-hb-src` も無いので `E-EXTRACT-UNRECOVERABLE` を伴う
   空の部品が量産される。brief の `never_guessed` が掲げる
   「位置や見た目から意味情報を当てにいかない」方針と正面から衝突する。
3. **受入基準に不要。** drift 検査はカタログ id と表の鍵の集合しか見ないため、
   `IMG` の行が存在すれば足りる。`P05-x-13` の shadow 検証も
   `("asset", "asset-img")` のみで 0 行・全緑を確認している。

**受け皿**: brief 側 (`script-brief-C20.json` の `class_map` の `IMG` 行の
括弧書き) は実装と食い違ったままである。brief は本 leaf の `write_scope` 外なので
触っていない。**`P05-x-21` (C20 brief の追随) へ、括弧書きを削るか
「クラス名を持つ画像に限る」へ改める修正として渡す。**

### 実測 (新 4 行が実際に部品を同定していること)

マーカー無しの手書き HTML (クラス名だけを持つ) に対する復元結果:

```
parts: ['B16', 'B17', 'DIAGRAM', 'IMG', 'TEXT', 'TEXT']
W-EXTRACT-HEURISTIC /sections/0/parts/0 B16 (根拠: action-items)
W-EXTRACT-HEURISTIC /sections/0/parts/1 B17 (根拠: handson)
W-EXTRACT-HEURISTIC /sections/0/parts/2 DIAGRAM (根拠: diagram)
W-EXTRACT-HEURISTIC /sections/0/parts/3 IMG (根拠: asset)
W-EXTRACT-HEURISTIC /sections/0/parts/4 TEXT (根拠: p)
W-EXTRACT-HEURISTIC /sections/0/parts/5 TEXT (根拠: p)
```

最後の `TEXT` は装飾用の裸 `<img>` を内包する段落である。**部品へ化けずに
本文のまま残る**ことを確認した (§2 の判断どおりの挙動)。
警告を黙らせただけでなく、図解・画像・実習手順が本文テキストへ化ける経路が
実際に塞がっていることの証拠でもある。

## 3. 正常系の `W-EXTRACT-CATALOG-DRIFT` — 4 行 → 0 行

`tests/extract-handout-config.py/_harness.py` の `full_html()` を入力に、
plugin root を temp へ複製して `--html` / `--out` で起動した (テストと同じ起動形)。

| | 行数 | 内容 |
|---|---|---|
| 着手前 | **4** | B16 / B17 / DIAGRAM / IMG が「カタログにあるが照合表に鍵が無い」 |
| 着手後 | **0** | stderr は空 (exit 0) |

## 4. 検査を殺していないことの反例 4 通り (双方向 × 各 2)

いずれも temp へ複製した plugin root のカタログだけを書き換えて実測した。

| # | 注入 | 向き | 結果 |
|---|------|------|------|
| (a) | カタログへ `B98` を追加 | カタログ→表 | `W-EXTRACT-CATALOG-DRIFT /parts B98 はカタログにあるが照合表に鍵が無い` 1 行 |
| (b) | カタログから `B11` を削除 | 表→カタログ | `W-EXTRACT-CATALOG-DRIFT /parts B11 は照合表の鍵にあるがカタログに無い` 1 行 + `E-EXTRACT-UNRECOVERABLE` / exit 1 |
| (c) | カタログから `IMG` を削除 | 表→カタログ | `W-EXTRACT-CATALOG-DRIFT /parts IMG は照合表の鍵にあるがカタログに無い` 1 行 |
| (d) | カタログから `DIAGRAM` を削除 | 表→カタログ | `W-EXTRACT-CATALOG-DRIFT /parts DIAGRAM は照合表の鍵にあるがカタログに無い` 1 行 |

(a)(b) は task-spec 手順 4 が挙げた 2 通りで、**どちらの向きでも発火する**ことを
自分で測り直した。(c)(d) は task-spec の要求を超えた追加で、
**本 leaf が新設した行そのものが監視下にある**ことを示すために入れた
(新行を足したせいで新行だけ検査から外れる、という失敗をしていない)。

「0 行だから直った」と「検査へ到達していないから 0 行」は出力では区別が付かないため、
正常系 0 行と反例 4 件の発火を同一の測定系で交互に測っている。

## 5. テスト結果 — 失敗テスト名の集合で比較

コマンド: 各テストディレクトリへ `cd` してから `python3 -m unittest discover -p 'test_*.py' -v`。

### `tests/extract-handout-config.py/`

| | 失敗テスト名の集合 | 総数 |
|---|---|---|
| 着手前 | `{}` (空) | Ran 152, OK |
| 着手後 | `{}` (空) | Ran 152, OK |

受入基準の「Ran 152 で緑」を満たす。既存の
`test_parts_catalog_ssot.CatalogIsTheOnlyVocabulary.test_self_check_is_quiet_when_catalog_and_table_agree`
(整合時に無言であること) と `test_class_map_keys_are_all_in_the_catalog` は
追加後も緑である。テストファイルは 1 バイトも書いていない。

### `tests/render-handout.py/` (照合表を grep する試験があるため確認した)

| | 失敗テスト名の集合 |
|---|---|
| 着手前 (P05-x-18 の報告値と一致) | `test_cross_component.GateHandoffTest.test_round_trip_equivalence`, `test_parts_catalog.SingleVocabularyTest.test_part_ids_are_not_enumerated_outside_the_catalog` |
| 着手後 | 同一 (Ran 195, failures=2) |

**集合は不変。新規に赤くなったテストは 0 件。**

ただし後者の失敗テストが数える offender **行数**は増えている (実測):

| ファイル | 着手前 | 着手後 |
|---|---|---|
| `scripts/extract-handout-config.py` | 13 | 15 (本 leaf の 2 行) |
| `scripts/RESOLUTION-P05-x-18.md` | 6 | 6 |
| `scripts/render-handout.py` | 2 | 2 |
| **合計** | **21** | **23** (+本ファイルの記載分) |

この試験は `plugins/guide-doc-generator/{scripts,skills,agents,commands,hooks,references}`
配下の**全ファイル** (`.md` を含む) を `\bB[01][0-9]\b` で走査するため、
`scripts/` 配下の RESOLUTION 文書も offender に数えられる。
本ファイルも同じ理由で数行を足す。**この試験は `P05-x-07` が blocked とし
`P05-x-23` が裁定する二重契約 (PAT-7) の当事者であり、本 leaf の担当外である。**
本 leaf は task-spec の指示どおり「表は今後も存在する」前提で行の中身だけを整えた。
`P05-x-23` が表をカタログへ畳み込む裁定を下す場合、offender は
`scripts/` 配下の RESOLUTION 文書の分だけ残るので、**裁定は走査対象から
`scripts/*.md` を外すか、文書での部品 id 言及を許す形にする必要がある**
(これは本 leaf の 2 行を消しても解決しない、という観測結果として渡す)。

## 6. 退けた解

- **`self_check_catalog` の警告条件を削る / `in_section - keys` の向きを落とす**:
  受入基準が明示的に禁じている「黙らせる解」。検査本体は無改変とした。
- **カタログの `section_scope` を `document` へ書き換えて `in_section` から外す**:
  drift は消えるが部品の分類を偽ることになり、C18 LANG-06 の「具体部品」述語
  (`in_section_parts()`) まで巻き添えで壊れる。退けた。
- **`DIAGRAM` の根拠に `svg[data-hb-kind=figure]` を入れる**: brief の
  `selector_class` はこう書いているが、照合表の値はクラス名であり属性セレクタを
  表現できない。`figure.diagram` が外側にあるので `diagram` 1 語で同定できる
  (実測: §2 の手書き HTML で `figure.diagram` が `DIAGRAM` として同定された)。
  属性照合の追加は `guess_part` の照合軸を増やす変更なので退けた (§2 の 1 と同じ理由)。
- **`IMG` の根拠を `asset-img` だけにする**: 外側の `figure.asset` が先に走査されるため
  `asset` が無いと `figure` 側で同定できず、内側の `img` へ降りる前に
  `collect_parts` の再帰へ落ちて `figcaption` を取り逃がす。両方を持たせた。

## 7. P05-x-18 §7 の申し送りの引き取り内訳

`RESOLUTION-P05-x-18.md` の §7.1 は `extract-handout-config.py` について 4 件を挙げている。
本 leaf の受入基準は「照合表の 4 行追加と drift の解消」に限定されているため、次のとおり切り分けた。

| §7.1 の項目 | 引き取り | 理由 |
|---|---|---|
| 3. 部品 id リテラル列挙 (`PART_CLASS_MAP`) をカタログ由来にする | **引き取らない** | task-spec が「本 leaf の担当外」と明記。`P05-x-23` (PAT-7 裁定) の担当。本 leaf はこの表が存続する前提で行の中身のみ整えた。§5 に offender 行数の実測と、裁定時に必要な追加観測を残した |
| 1. `CHROME_CLASSES` から `pop-header` を外す / 判定を `data-hb-generated` 保持要素へ限定する | **引き取らない** | 受入基準は drift 警告と自スイート緑のみを問う。この変更は `test_chrome_skip.UnmarkedChromeIsSkippedByClassName` (`test_pop_header_is_skipped` / `test_unmarked_chrome_is_not_reported_as_heuristic_part`) が固定する二重防御の契約 — マーカー無しの `.pop-header` をクラス名だけで捨てること — と正面から衝突し、テストの assert を弱めずには通せない。**契約の裁定が先に要る。受け皿が未割当なので dispatcher の割当を要する** |
| 2. `decision=marker` の 9 項目を読む (`DOC_FIELDS` / `SECTION_FIELDS` の拡張) | **引き取らない** | 受入基準の外。`ROUNDTRIP-CONTRACT.md` を正本とする round-trip 成立条件の実装であり、`test_cross_component.GateHandoffTest.test_round_trip_equivalence` の残る赤の原因はここにある。`P05-x-11` は同じ round-trip を扱うが `write_scope` が `schemas` のみで**実装へ書けない**。`extract-handout-config.py` へ書ける leaf は `P05-x-20` / `P05-x-23` だがどちらも別の裁定が主題である。**受け皿が実質未割当。dispatcher の割当を要する** |
| 4. `assets[]` の復元で `data_uri` を発明せず `src` へ格納する | **引き取らない** | 同上。項目 2 と同じ round-trip 実装の一部で、同じ受け皿へ渡すのが適切 |

引き取ったのは **4 行の追加と drift の解消のみ**である。§7.1 の 4 件はいずれも
「範囲を広げない」側の判断で見送り、上表で受け皿と未割当の所在を明示した。

## 8. 変更したファイル (write_scope 内)

- `plugins/guide-doc-generator/scripts/extract-handout-config.py` (照合表 4 行 + 直上コメント)
- `plugins/guide-doc-generator/scripts/RESOLUTION-P05-x-19.md` (本ファイル / produces)

`plugins/guide-doc-generator/scripts/` の外へは 1 バイトも書いていない
(`plugin-plans/` 配下、テスト、カタログ、brief はいずれも未変更)。
反例注入はすべて temp へ複製した plugin root 上で行い、repo のカタログは触っていない。
