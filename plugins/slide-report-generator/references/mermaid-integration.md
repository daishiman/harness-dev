# Mermaid 統合ガイド（report モード）

> 責務: output_mode=report のビジュアル三択（SVG図解 / Mermaid / Codex画像）のうち **Mermaid** 経路の統合仕様。対応図種・記法・`render-report.js` / `mermaid-render.js` との連携・フォールバックを定義する。
> 正本の役割分担: 意匠トークン（Kanagawa 配色・フォント）は vendor 共有 SSOT、三択の選択規準は [report-visual-strategy.md](report-visual-strategy.md)、Mermaid の schema 契約は `schemas/report-structure.schema.json` の `mermaidSpec`。本書は Mermaid 固有の記法と連携を担う。

---

## 1. Mermaid を使う場面

Mermaid は「関係・順序・状態遷移・割合が**定型記法で素直に書ける**」ときの第一候補である。SVG図解（`svg-builder.cjs` のインライン図解）と役割が重なるが、次の使い分けをする。

| 状況 | 選ぶ経路 |
|------|----------|
| ノード配置・意匠を細かく制御したい / 意匠トークンをフル活用したい | `svg`（インライン SVG2 図解） |
| フロー・シーケンス・状態・ガント・割合が定型で、記法で簡潔に書ける | `mermaid` |
| 情感・世界観・章扉的なコンセプト表現 | `codex-image` |
| 文章で足りる | `none` |

Mermaid の強みは**記述量の少なさと保守性**である。手順・状態遷移・ER・ガントのように構造が定型なものは、SVG のノード座標を手で置くより Mermaid 定義文字列のほうが誤りが少なく、後修正も容易い。

---

## 2. 対応図種（diagramType）

`mermaidSpec.diagramType` の enum と用途。

| diagramType | Mermaid キーワード | 用途 |
|-------------|-------------------|------|
| `flowchart` | `flowchart` / `graph` | 手順・分岐・依存フロー |
| `sequence` | `sequenceDiagram` | 主体間のやり取り・時系列メッセージ |
| `class` | `classDiagram` | クラス構造・データモデル |
| `state` | `stateDiagram-v2` | 状態遷移・ライフサイクル |
| `er` | `erDiagram` | エンティティ関係（DB スキーマ等） |
| `gantt` | `gantt` | スケジュール・工程表 |
| `pie` | `pie` | 割合・構成比 |
| `mindmap` | `mindmap` | 概念の発散・階層 |
| `timeline` | `timeline` | 時系列の出来事 |
| `journey` | `journey` | ユーザージャーニー・体験段階 |
| `gitgraph` | `gitGraph` | 分岐・マージの履歴 |
| `quadrant` | `quadrantChart` | 2軸マトリクス（優先度・ポジショニング） |
| `requirement` | `requirementDiagram` | 要件と検証の関係 |

---

## 3. 記法（definition）の書き方

`mermaidSpec.definition` に Mermaid 記法の本体を文字列で置く。

### 3.1 flowchart（手順・依存）

```
flowchart LR
  A[現状分析] --> B[目標設定]
  B --> C[ツール選定]
  C --> D[本格展開]
```

- 向きは `LR`（左→右）/ `TB`（上→下）/ `RL` / `BT`。`mermaidSpec.direction` に持たせても、definition に直書きしてもよい。
- report は縦スクロール読み物なので、横長になりすぎる場合は `TB` を選ぶと本文カラム幅に収まりやすい。

### 3.2 pie（割合）

```
pie title 削減時間内訳
  "定型作業" : 45
  "報告作成" : 25
  "情報収集" : 30
```

### 3.3 sequence（やり取り）

```
sequenceDiagram
  participant U as 利用者
  participant S as システム
  U->>S: 依頼を送信
  S-->>U: 結果を返却
```

### 3.4 gantt（工程）

```
gantt
  title 導入スケジュール
  dateFormat YYYY-MM-DD
  section 導入
  現状分析 :a1, 2026-01-01, 14d
  本格展開 :after a1, 30d
```

---

## 4. 配色・意匠の注入（テーマは render 側で）

**definition に配色を直書きしない。** Kanagawa（`kanagawa-lotus`）のアクセント色・背景・フォントは `render-report.js` / `mermaid-render.js` が Mermaid の `themeVariables`（init ディレクティブ）として注入する。これにより：

- 意匠トークンが slide/report で単一 SSOT に保たれる（build-contract §D 共有層）。
- 図種をまたいで配色が一貫する。
- レポート単位で色を変えても definition を触らずに済む。

したがって作図者は「構造（ノード・関係・値）」だけを記述し、色・フォントは意識しない。

---

## 5. render-report.js / mermaid-render.js との連携

決定論生成経路の呼び出し（詳細な実装は C19 owner の別担当が build-contract §F で作る。本書は契約の参照のみ）。

```bash
node "$CLAUDE_PLUGIN_ROOT/vendor/scripts/render-report.js" <report-structure.json> <out.html>
```

処理の流れ:

1. `render-report.js` が `report-structure.json` を読み、各 `sections[].visual` を走査する。
2. `visual.kind == "mermaid"` の節について、`mermaid-render.js` に `mermaidSpec.definition` と theme トークンを渡す。
3. `mermaid-render.js` は Mermaid CLI / lib があれば SVG（または HTML 片）へ変換し、無ければフォールバック（§6）を決定論生成する。
4. 変換結果を read-through レイアウトの該当セクションへ埋め込む。

依存（mermaid CLI/lib）は byte-copy 済み vendor ツリーへの **additive 追記**として `vendor/package.json` / `package-lock.json` に加える（build-contract §F・parity_scope.excluded_additive）。

---

## 6. フォールバック（描画不能時の可読性担保）

Mermaid CLI/lib が実行環境に無い、または definition が解釈不能な場合でも、レポートは読めなければならない。`mermaid-render.js` は次のフォールバックを決定論生成する。

1. **`<pre class="mermaid">` 埋め込み**: definition をそのまま `<pre class="mermaid">` に入れる。ブラウザ側で mermaid.js を読み込めばクライアントレンダリングされ、読めなくても定義文が可読テキストとして残る。
2. **`fallback` テキスト**: `mermaidSpec.fallback` があれば、図の要点を短い説明文として併記する（例: 「定型作業45% / 報告作成25% / 情報収集30%」）。read-through では図が出なくても要旨が読めることを最優先する。

フォールバックはエラーで停止せず、必ず何らかの可読要素を残す（fail-soft）。

---

## 7. チェックリスト

| 項目 | 基準 |
|------|------|
| diagramType が enum 内か | `mermaidSpec.diagramType` が 13 種のいずれか |
| definition が空でないか | 記法本体が 1 文字以上・6000 文字以内 |
| 配色を直書きしていないか | definition に HEX/色名を埋めず、テーマは render 側注入に委ねる |
| フォールバックがあるか | 描画不能時の `fallback` 説明文を用意（推奨） |
| 1項目1ビジュアルか | 同一セクションに Mermaid と他 kind を重ねていない |
