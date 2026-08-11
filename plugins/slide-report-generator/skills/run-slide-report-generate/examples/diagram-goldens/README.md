# 図解ゴールデン実例（入力 → 完成 HTML のペア）

> **手書き経路 <!-- count: diagramGoldenHand -->53 組 + 決定論ビルダー経路 <!-- count: diagramGoldenBuilder -->10 組（`builders/`）は「正解の見本」であり、同時に**回帰の基準線**である。**
> 同じ `<type>-input.json` を与えて図解を書かせたら、出来上がりは
> `<type>-golden.html` と**視覚的に同一**になるべきである。
> ずれたら、ずれた側（生成物か、正本の契約か）のどちらが動いたのかを先に決める。

## 0. なぜ実例が要るか

図解の契約（`references/diagram-layout-contract.md`）と色の索引
（`references/diagram-style-tokens.md`）と骨格
（`assets/diagram-templates/`）は揃っているが、**「この入力からこの HTML が出る」
という完成した対**がどこにも無かった。条文だけでは、

- 条文どうしがぶつかったとき（例: §11.34 のコード例の線幅と D9 の下限）
  どちらへ寄せるのが正解かが読めない
- 骨格のどこまでを書き換えてよいのかが、読む人によってぶれる
- 「契約を全部満たした図」が具体的にどのくらいの密度なのかが伝わらない

本ディレクトリはその 3 つを、**動く 1 枚**で答える。

## 1. ファイル一覧

命名は全ペア共通: `<型>-input.json` → `<型>-golden.html`。diagram id は
`d-<型>`（report 骨格）/ `f-<型>`（slide 骨格）の slug 形式で、複数枚を
同一ページへ埋め込んでも marker id が衝突しない。
**「何を見せたいか → 型」の選定と「型 → 参照節」の対応の正本は
`references/diagram-type-crosswalk.md`**（この README は索引を重複して持たない）。

| グループ | 参照節 | ペア数 |
|---|---|---|
| 循環・フロー系 | `diagram-cycle-flow.md` §11.1-11.5, §11.30 | 6 |
| 比較・対立系（ガントを含む） | `diagram-comparison.md` §11.6-11.10, §11.31-11.32 | 7 |
| ビジネスフレーム系 | `diagram-business.md` §11.11-11.20（FABE 詳細は `diagram-fabe.md`） | 10 |
| 視覚・構造系 | `diagram-visual.md` §11.21-11.29, §11.33-11.34 | 11 |
| 技術系（ER・シーケンス・状態遷移ほか） | `diagram-technical.md` §11.35-11.40 | 6 |
| 運用・体験・増減系 | `diagram-extended.md` §11.41-11.44 | 4 |
| チャート 9 種 | `chart-types.md` §13.1-13.9 | 9 |
| 決定論ビルダー経路 | `builders/README.md`（spec → `render-diagram-golden.cjs` → HTML） | 10 |

骨格の正本は `assets/diagram-templates/diagram-skeleton-slide.html` と
`diagram-skeleton-report.html`。全枚が `<defs>` の marker 3 種・`role` /
`aria-labelledby`・`figure` の class をそのまま引き継ぎ、
書き換えたのは `data-diagram-id`（と marker の id 接頭辞）・図解本体・
`figcaption` だけである。

## 2. 入力 JSON の読み方

全ファイルとも同じ最小構造を持つ。**図解の「意味内容」だけを書き、
座標も色も持たない**（座標と色は契約側が決める、というのがこの分離の主張である）。

| キー | 意味 |
|---|---|
| `diagramId` / `surface` / `skeleton` | どちらの骨格へ差し込むか。`surface` が `report` なら `figureWidth` も持つ |
| `reference` | この型の正本節。golden HTML の幾何はここから取っている |
| `canvas.viewBox` | 参照節が定める寸法。自分で決めた値ではない |
| `title` / `message` | 図の主題と、1 枚で言い切る主張（slide なら 1 スライド 1 メッセージ） |
| `nodes[]` | ノードの `label` / `sub` / `style`（`plain` / `focal` / `external` …。`diagram-style-tokens.md` §4 の 7 種） |
| `relations[]` | 関係。`kind` で語彙を分ける（`flow` / `feedback` / `ring` / `writeback` / `contains`） |
| `emphasis.focal[]` + `reason` | 焦点。**なぜそこか**を書かせるのが要点で、書けないなら焦点ではない |
| `annotations[]` | 注釈（最大 2・§D-5） |
| `geometry` | 参照節が特殊な幾何を定める型だけが持つ（ピラミッド・包含・フライホイール） |
| `caption` | `figcaption` の本文。図のラベルを含めない（R9-10） |

型固有のキーは最小限に留めてある（象限の `axes` / `quadrantTags`、
対比の `criteria` と `nodes[].values`）。

## 3. 初期 6 枚（flow / quadrant / pyramid / nested / flywheel / comparison）が実演している契約

| 契約 | どの実例で見えるか |
|---|---|
| D-1 4px グリッド | 全 6 枚。座標・寸法・間隔・角丸がすべて 4 の倍数（`--check-grid` 付きで検証済み） |
| D-2 #1/#2 複雑度 | フローは 4 ノード + 4 コネクタ。「技術的に載る量より少し足りないくらいで止める」 |
| D-2 #3 accent | 全 6 枚が焦点 1-2 件。フライホイールだけがハブ + 1 工程の 2 件 |
| D-2 #17 段数 | ピラミッドが上限の 5 段。段ごとに色を変えず、序列は位置と幅だけが語る |
| D-2 #21 フォント階層 | 最大 3 段（16 / 14 / 12）。4 段目を作っていない |
| D-3 原則 1 直交 | フローの戻り線が `M 804 288 V 356 H 372 V 292`。斜めのセグメントが 1 本も無い |
| D-3 原則 1 例外 (a) | フライホイールのリング円弧（`A` コマンド）。放射状型の語彙なので斜線禁止の対象外 |
| D-3 原則 2 マスク | フローの「差し戻し」ラベルが線を跨ぐので `paper` のマスク矩形を下に敷いている |
| D-5 annotation | フロー・ピラミッド・包含・対比の 4 枚。イタリック + 破線リーダー + 半径 2 のドット・矢じり無し |
| R9-9 / R9-10 キャプション | report 3 枚の `figcaption` が 40-120 字で、図のラベルを 1 つも含まない |
| R9-14 影 | 全 6 枚。`drop-shadow` / `box-shadow` を持たない |
| R9-15 書体 | 全 6 枚が `font-family` を 1 箇所も書かない。成果物の `:root` が解決する |

### 参照節から意図的にずらした点（2 件）

正本の節をそのまま写すと契約に落ちる箇所がある。**golden 側が正しい。**

1. **ピラミッド（§11.34）**: 節のコード例は段の区切りの線幅が D9 の下限を
   下回っているので、`STROKE.hairline`（値の正本は `svg-kit.cjs` の `STROKE`）へ寄せた。
2. **対比（§11.6）**: 節のコード例は `box-shadow`・`hover` の変形・
   `rgba(0,0,0,0.4)` の影を持つ。R9-14（影は常に 0）と D10（純黒禁止）に触れるので
   すべて落とした。骨格 README §4「移植するのは作図文法であって配色ではない」の実例である。

また 6 枚とも、参照節が CSS class で当てていた塗り・線を
**presentation 属性へ展開**してある。断片を単体で開いても同じ見た目になる
（＝自己完結・外部依存ゼロ）ことを優先したためで、色のロールは変えていない。

## 4. 検証（全ペアが指摘ゼロ）

```bash
cd plugins/slide-report-generator
python3 scripts/validate-svg-diagram.py --check-grid --strict \
  skills/run-slide-report-generate/examples/diagram-goldens/*-golden.html \
  skills/run-slide-report-generate/examples/diagram-goldens/builders/*-golden.html
```

`--check-grid`（既定オフの D6）と `--strict`（warning も失格扱い）を付けて
**errors=0 warnings=0**。D14-D17 まで含めて指摘は 1 件も出ない。

report 系 3 枚の R9 溶け込み契約（`validate-report-visual.py` の C25 (p) 重複 /
(q) 占有）は、断片のままでは節が無くて測れない。最小の report へ差し込んでから測る:

```bash
# 各 golden を <section class="report-section"> の中へ、直前に本文 1 段落を置いて差し込み、
# h1.report-title を持つ 1 枚の HTML にしてから:
python3 scripts/validate-report-visual.py <組み立てた report.html>
```

この手順で 3 枚とも fail=0 warn=0（キャプション字数・キャプションとラベルの重複・
ラベルと本文の n-gram 重複・図版の占有のいずれも指摘なし）である。

## 5. 使い方

- **few-shot として**: 新しい図解を書く前に、同じ `surface` の golden を 1 枚読む。
  条文を 20 個思い出すより、契約を全部満たした 1 枚を見る方が速い。
- **回帰基準線として**: 契約・骨格・vendor のどれかを触ったら、
  §4 のコマンドを流す。golden が落ちたら、落ちたのは golden ではなく**変更の側**かもしれない。
  正本を意図して動かしたのなら golden も同じコミットで直す
  （`diagram-style-tokens.md` §7 と同じ同期義務）。
- **契約の解釈が割れたとき**: §3 の「意図的にずらした点」に前例がある。
  意味の正本はspec/contractであり、validatorはその実行可能な射影である。節と検査がぶつかったら、
  どちらかへ無条件追従せず、正本の意図を確認してvalidatorとgoldenを同時に同期する。

## 6. 関連

- 図解 1 枚の契約 → `references/diagram-layout-contract.md`
- 色ロールの索引 → `references/diagram-style-tokens.md`
- 型と経路の対応 → `references/diagram-type-crosswalk.md`
- 骨格と埋め込み契約 → `assets/diagram-templates/README.md`
