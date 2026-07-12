# スライドタイプ概要

**責務**: スライドタイプの一覧と選択ガイド

---

## スライドタイプ一覧

### 基本スライド（9種）

| タイプ | クラス名 | 用途 | 詳細 |
|--------|---------|------|------|
| タイトル | `slide-title` | 表紙・セクション見出し | [slide-types-basic.md](slide-types-basic.md#タイトルスライド) |
| メッセージ | `slide-message` | 1メッセージを強調 | [slide-types-basic.md](slide-types-basic.md#メッセージスライド) |
| リスト | `slide-list` | 並列要素の列挙 | [slide-types-basic.md](slide-types-basic.md#リストスライド) |
| 比較 | `slide-compare` | Before/After・対比 | [slide-types-basic.md](slide-types-basic.md#比較スライド) |
| フロー | `slide-flow` | 横方向プロセス | [slide-types-basic.md](slide-types-basic.md#フロースライド) |
| タイムライン | `slide-timeline` | 時系列・履歴 | [slide-types-basic.md](slide-types-basic.md#タイムラインスライド) |
| テーブル | `slide-table` | 詳細情報の表 | [slide-types-basic.md](slide-types-basic.md#テーブルスライド) |
| コード | `slide-code` | プロンプト・コード表示 | [slide-types-basic.md](slide-types-basic.md#コードブロックスライド) |
| コード比較 | `slide-code-compare` | Before/Afterコード比較 | [slide-types-basic.md](slide-types-basic.md#コード比較スライドBeforeAfter) |

### 拡張スライド（8種）

| タイプ | クラス名 | 用途 | 詳細 |
|--------|---------|------|------|
| ピラミッド | `slide-pyramid` | 階層構造・優先度 | [slide-types-extended.md](slide-types-extended.md#ピラミッドスライド) |
| サークル | `slide-circle` | 中心と周辺の関係 | [slide-types-extended.md](slide-types-extended.md#サークルスライド) |
| グリッド | `slide-grid` | カード形式の一覧 | [slide-types-extended.md](slide-types-extended.md#グリッドスライド) |
| ハイライト | `slide-highlight` | 重要な数値/メッセージ | [slide-types-extended.md](slide-types-extended.md#ハイライトスライド) |
| アイコングリッド | `slide-icon-grid` | アイコン主体の一覧 | [slide-types-extended.md](slide-types-extended.md#アイコングリッドスライド) |
| プロセス | `slide-process` | 縦方向ステップ | [slide-types-extended.md](slide-types-extended.md#プロセススライド) |
| 引用 | `slide-quote` | 引用文・権威付け | [slide-types-extended.md](slide-types-extended.md#引用スライド) |
| ヒーロー | `slide-hero` | インパクト見出し | [slide-types-extended.md](slide-types-extended.md#ヒーロースライド) |

### 図解タイプ（29種）

| カテゴリ | タイプ数 | 詳細 |
|----------|---------|------|
| サイクル・フロー系 | 5種 (11.1-11.5) | [diagram-cycle-flow.md](diagram-cycle-flow.md) |
| 比較・マトリックス系 | 5種 (11.6-11.10) | [diagram-comparison.md](diagram-comparison.md) |
| ビジネス系 | 9種 (11.11-11.19) | [diagram-business.md](diagram-business.md) ※PREP型・STAR型含む |
| FABE型 | 1種 (11.20) | [diagram-fabe.md](diagram-fabe.md) ※5バリエーション |
| ビジュアル系 | 9種 (11.21-11.29) | [diagram-visual.md](diagram-visual.md) |

### グラフタイプ（9種）

| タイプ | 用途 | 詳細 |
|--------|------|------|
| 棒グラフ | 数値比較 | [chart-types.md](chart-types.md#棒グラフ) |
| 折れ線 | 推移・トレンド | [chart-types.md](chart-types.md#折れ線グラフ) |
| 円グラフ | 構成比 | [chart-types.md](chart-types.md#円グラフ) |
| レーダー | 多軸評価 | [chart-types.md](chart-types.md#レーダーチャート) |

### D3インタラクティブ図解（24種）

| カテゴリ | タイプ数 | 詳細 |
|----------|---------|------|
| 循環系 (cycle.js) | 4種 | サイクル, PDCA, 三角サイクル, 回転フロー |
| 階層系 (hierarchy.js) | 6種 | ツリー, 組織図, ピラミッド, サンバースト, ツリーマップ, パックドサークル |
| フロー系 (flow.js) | 5種 | サンキー, シェブロン, ロードマップ, ファネル, 縦タイムライン |
| グラフ系 (charts.js) | 6種 | 棒, 円, 折れ線, レーダー, ゲージ, バブル |
| 高度系 (advanced.js) | 6種 | フォース, コード, ヒートマップ, 放射状棒, ワードクラウド, アーク |
| 拡張系 (extended.js) | 10種 | ウォーターフォール, ドーナツ, ブレット, スロープ, バタフライ等 |

**詳細**: [d3-integration.md](d3-integration.md)

---

## 関連リソース

| リソース | 読み込み条件 |
|----------|-------------|
| [slide-types-basic.md](slide-types-basic.md) | 基本スライド作成時 |
| [slide-types-extended.md](slide-types-extended.md) | 拡張スライド作成時 |
| [slide-interactions.md](slide-interactions.md) | ホバー・アニメーション実装時 |
| [slide-text-guidelines.md](slide-text-guidelines.md) | テキスト調整時 |
| [diagram-*.md](.) | 図解スライド作成時 |
| [diagram-fabe.md](diagram-fabe.md) | FABE型（5バリエーション）作成時 |
| [chart-types.md](chart-types.md) | グラフスライド作成時 |
