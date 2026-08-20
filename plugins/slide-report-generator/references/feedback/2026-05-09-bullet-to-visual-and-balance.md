---
date: 2026-05-09
project: slide-2026-05-08-claudecode-concept-guide
severity: critical
status: must-apply-going-forward
---

# 文字列リスト禁止・図解優先・カード内バランス徹底

## 背景
非エンジニア向け 40 分プレゼン（38スライド）の改修中、複数の指摘が集中して上がった。
同じ指摘が今後も上がらないよう、スキル運用に恒久反映する。

## 指摘事項（2026-05-08〜09）

### 1. 文章羅列・bullet list は読まれない
- `<ul><li>` の箇条書き（`code-list`, `statement-sub` など）は「文章を読む」作業を要求してしまい、内容が頭に入らない
- スライドに残ったテキストは即座に直感把握できる視覚要素であるべき

### 2. カード内が文章だらけ
- カードを並べても、各カード内が「ターミナルで claude 実行。CLAUDE.md・スキルYAML・MCP定義が読み込まれる」のような長文だと結局読みづらい
- カード内も**さらに分解した可視要素**（chip / icon-label / mini-card）にする

### 3. 上下に巨大空白＋中央に小さな図
- SVG `viewBox` を小さく取って `max-height:160px` などで縛ると図が縮み、上下に巨大空白が生まれる
- カードの矢印が `align-items: stretch` のせいで「上揃え」になりカード中央と外れる

### 4. カード内文字が小さい
- `font-size: 1.3rem` 以下は遠目で読めない。カードの desc は最低 `1.45rem`
- カード見出しは `1.85rem〜2.0rem`、アイコンは `2.8rem〜3.2rem`

## 必須運用ルール（恒久）

### A. 「文字列リストを書きたくなったら止まる」
スライドに `<ul><li>...</li></ul>` を書こうとした瞬間に止まる。置換先を一律に名指しせず、次の分岐で決める。

| 条件 | 表現 |
|------|------|
| 並列する要素が 3 件以下・項目間に関係が無い | chip |
| 順序・因果・対比・包含のいずれかの関係を持つ要素が 3 件以上 | 図解 |
| 各項目が異種要素を束ね、その面でカードが担う役割が定義されている | カード（役割定義なしのカードは不可） |

分岐条件の逐語正本は `skills/run-slide-report-generate/references/visual-generation-rules.md` §4。

### B. カード内の構造ルール
1. **見出し**：18〜20px (`1.8rem〜2.0rem`) +アイコン
2. **本文**：1〜2行で、できれば chip 化（短語 + アイコン）
3. **長文 desc は禁止**。3行を超えるなら chip 群に分解
4. アイコンは必ず Font Awesome 6.5.1（絵文字禁止）
5. 1 つの情報が同時に持ってよい装飾は 1 つまで（囲み・塗り・角丸・影・色・アイコンのうち 1 つ。VGCONST_008）

### C. レイアウト・余白の鉄則
1. フローカードの容器は `align-items: center`（矢印を縦中央に）
2. カード内は `justify-content: center`（コンテンツを縦中央に）
3. SVG 図解は固定 `max-height: NNNpx` で縛らない。HTML カード+chip で代替
4. スライド本文に巨大な余白が出たときの直し方（2026-08-13 更新。旧記述「コンテンツが小さすぎるサイン → カード/フォント拡大」は現行方針と逆向きなので置き換えた）:
   余白率・充填率の正本は `assets/slide-templates/frame-contract.json` の `fill_policy` / `vertical_margin_policy`。
   `fill_policy.note_antipattern` により、**下限割れ（空白過多）は面の統合か項目の追加で直す**のであって、
   カードやフォントの拡大で埋めてはいけない（書体を `typography.min` 未満へ下げるのも同様に禁止）。
   スロットの伸長（`flex: 1 1 0` / `grid-auto-rows: 1fr` / `align-content: stretch`）も、
   内容量と無関係に面積比だけ稼ぐので禁止。残余高さは群の外側余白として上下へ均等に残す（CONST_008）。

### D. テキストサイズ最低基準（2026-05-09 改訂）
- カード本文：`1.45rem` 以上
- カード見出し：`1.85rem` 以上
- chip ラベル：`1.25rem` 以上（chip は短語のみ・複数並べる）
- subtitle-line：`1.5rem` 以上
- code 例（misfire-sample 等）：`1.6rem` 以上

### E. v8 検証で追加すべき自動チェック（提案）
- V-039: `slide-statement` 内の `statement-sub > ul > li` 数 → 0件であること
- V-040: `slide-diagram` 内の `code-list > li` 数 → 0件であること（A の分岐条件で置換済みか）
- V-041: フローカード／step ボックスの container に `align-items: center` が指定されていること
- V-042: SVG `max-height` 指定の禁止（HTML カードフローを推奨）

## 参考：今回適用したパターン名（CSS クラス）

- `access-trio` / `access-card` (3経路カード, N05 で採用)
- `feat-quad` / `feat-card` (2x2機能カード, N20 で採用)
- `keypoint-trio` / `kp-card` (3カード番号付, N17 で採用)
- `kp-quad` / `kp-mini` (2x2横ミニカード, N19/N26/N30/N31 で採用)
- `exec-v2` + `step-chip` (Before/After 工程ピル, N09 で採用)
- `flow4` + `f4-chip` (4ステップ大カード+chip, N16 で採用)
- `trigflow` + `desc-compare` (5ステップパイプライン+比較, N22 で採用)

これらは `references/composition-patterns.md` および `references/slide-design-patterns.md` に正式登録すること。

## 関連
- 過去フィードバック: `feedback_slides_no_emoji_use_fontawesome.md`
- 過去フィードバック: `feedback_no_unverified_metrics.md`
- ユーザー直接指摘: 「文章が羅列されていると、スライドの文章を読むのが大変で見にくい」「もっと直感的に分かるような図解を用いて表現するように」「カード内の文字がちっちゃくて見にくい」「結構隙間空いてたり」「全てのスライドで共通です」
