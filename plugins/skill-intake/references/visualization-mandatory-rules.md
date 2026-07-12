---
name: visualization-mandatory-rules
description: 非エンジニア対応マスト 8 ルール (図解の機械検証規則)
type: reference
---

# 図解マスト 8 ルール

`scripts/enforce_visualization_rules.py` がこの 8 ルールを全図に対して機械検証する。1 つでも違反すれば PASS 不可。

## 8 ルール一覧

| # | ルール | 検証方法 |
|---|--------|----------|
| 1 | 1 図あたり 7±2 ノード上限 | ノード数カウント |
| 2 | ノードラベルは日本語 10 文字以内 | 文字数計測 |
| 3 | 色は意味付き（赤=注意／緑=完了／青=進行中）凡例必須 | 色コード抽出+凡例存在確認 |
| 4 | アイコンは FontAwesome（絵文字禁止） | Unicode ブロック検査 |
| 5 | 専門用語は non-tech-vocabulary.md で言い換え | 用語辞書突合 |
| 6 | 最終出力は SVG/PNG レンダリング済み（生 Mermaid 構文を見せない） | ファイル拡張子・MIME |
| 7 | 各図に「言いたい一言」を 1 行付記 | one_liner フィールド存在 |
| 8 | 視覚理解度 ★1 の図種は非エンジニア向けで自動代替 | type と user_profile の整合 |

---

## ルール 1: ノード数 7±2

| 範囲 | 判定 |
|------|------|
| 5〜9 個 | OK |
| 3〜4 個 | 警告（情報不足の可能性） |
| 10 個以上 | NG（分割せよ） |
| 2 個以下 | NG（図解不要） |

```javascript
const nodeCount = countNodes(diagram);
if (nodeCount < 3 || nodeCount > 9) return { pass: false, reason: 'node_count' };
```

## ルール 2: ラベル日本語 10 文字以内

| 例 | 判定 |
|----|------|
| 「ユーザー」(4 字) | OK |
| 「フォーム作成」(6 字) | OK |
| 「Google Forms 連携処理」(13 字) | NG → 「Forms 連携」(6 字) に短縮 |

英数字も日本語 1 字相当でカウント（厳しめ）。

## ルール 3: 意味付きカラー + 凡例

| 色 | 意味 |
|----|------|
| 赤 #E74C3C | 注意・エラー |
| 緑 #2ECC71 | 完了・成功 |
| 青 #3498DB | 進行中・中性 |
| 黄 #F1C40F | 警告 |
| 灰 #95A5A6 | 無効・スキップ |

凡例ブロックを SVG 右下または下部に必ず配置。

## ルール 4: FontAwesome のみ・絵文字禁止

```javascript
const hasEmoji = /[\u{1F300}-\u{1F6FF}\u{1F900}-\u{1F9FF}\u{2600}-\u{27BF}]/u.test(svg);
if (hasEmoji) return { pass: false, reason: 'emoji_detected' };
```

許可: `<i class="fa-solid fa-user"></i>` 等の FontAwesome アイコン。

## ルール 5: 専門用語の言い換え

`references/non-tech-vocabulary.md` の辞書で、図中の文字列を全件突合。未変換語があれば NG。`user_profile.technical_level === "上級"` の場合のみスキップ。

## ルール 6: SVG/PNG 出力必須

| 出力 | OK/NG |
|------|-------|
| `output/<hint>/diagrams/*.svg` | OK |
| `output/<hint>/diagrams/*.png` | OK |
| 本文中に Mermaid 生構文残存 | NG |

`scripts/render_to_svg.py` と `scripts/render_to_image.py` が最終レンダリングを実行。Notion 公開時は PNG 必須。

## ルール 7: one_liner 1 行付記

| 要件 | 値 |
|------|----|
| 文字数 | 60 字以内 |
| 文体 | 動詞または形容詞で結ぶ |
| 配置 | 図の直下 caption |

例: 「フォーム作成から集計までの 5 ステップを示す」

## ルール 8: ★1 図種の自動代替

| 元 | 代替先 | 条件 |
|----|--------|------|
| sequence | numbered-steps | technical_level != 上級 |
| class | comparison-table | technical_level != 上級 |
| er | icon-grid | technical_level != 上級 |

代替は `scripts/select_diagram_type.py` が自動実施。

## 検証フロー

```
[visualizer 出力]
  ↓
enforce_visualization_rules.py
  ├─ ルール 1〜8 を順次検証
  ├─ 全 PASS → 通過
  └─ 1 つでも NG → 修正指示返却
       ↓
visualizer 再生成（最大 3 回）
  ↓
3 回 NG → ★1 代替 or 図削除
```

## サンプル: google-forms-generator のフロー図検証結果

| ルール | 結果 |
|--------|------|
| 1 ノード数=5 | OK |
| 2 最長ラベル「Sheets 連携」(7 字) | OK |
| 3 進行中=青で凡例あり | OK |
| 4 絵文字検出ゼロ | OK |
| 5 「API」→「外部サービス連携」変換済 | OK |
| 6 SVG 出力済 | OK |
| 7 one_liner=「申込フォーム作成の 5 ステップ」 | OK |
| 8 type=numbered-steps（★3） | OK |

→ 全 PASS。
