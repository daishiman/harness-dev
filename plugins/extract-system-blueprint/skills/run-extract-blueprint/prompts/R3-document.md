# Prompt: R3-document

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R3-document |
| skill | run-extract-blueprint |
| responsibility | R3 章別 draft と 5 種 Mermaid の確定・自己検証 (1 prompt = 1 責務) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../../../schemas/system-blueprint.schema.json |
| reproducible | true (同一 fact/inference から同一 draft_hash) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 章別 draft (md/json) は同一 shape・同一 draft_hash から導出する。
- screenshot/rendered DOM は R1 の browser-render(C15)が取得し C03 が fact 化する。C11(doc-emit)自身は raster を撮らず md/json/SVG/manifest/検査のテキスト演算に責務を限定する (stdlib_only)。browser-render がブラウザ不在だった観測は observation_gap として記録され、その場合 screens[] は空になる。
- text 系 (layout.json/verbatim 等) の PII・認証後情報・機微は emit 時に redact し redaction_applied を記録する。

### 1.2 倫理ガード
- 各正本 (スクリーンショット含む) へ参考/学習目的限定注記を焼く。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: `doc-emit.py` で章別 draft + 5 種 Mermaid + 画面別 layout.json + 合成 design-tokens.json + site coverage manifest を確定し、completeness/構文を自己検証する。screenshot/rendered DOM は R1 の browser-render(C15)が取得済みで、C11 は raster を撮らずその参照整合を検査する (取得できなかった観測は observation_gap)。
- 非担当: 観測 (R1)、分析 (R2)。

### 2.2 ドメインルール
- 5 種 Mermaid 必須図種: 全体構成/事実↔推測区別レイヤ/画面遷移/データフロー sequence/データモデル。harness-meta 図は製品出力契約から除外。
- `doc-emit.py --check-screens` は screenshot が存在する場合の screenshot/layout 参照整合・観測色の palette 孤児 0・site coverage manifest の pending 無言欠落なしを検査する (screens が空なら check-screens はスキップ)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| extraction | json | yes | R2 の fact/inference/essence 統合レコード |
| request ledger | json | yes | R1 の load-policy 計上 |

### 2.4 出力契約
- schema: `system-blueprint.schema.json` 準拠の md + json。screens[] がある場合は各 screenshot_ref がローカル実在 (screens が空なら任意)。
- 出力: 章別 draft + 5 種 Mermaid + 画面別 layout.json + design-tokens.json + site coverage manifest + draft_hash (screenshot/rendered DOM は browser-render 取得時に screens へ、ブラウザ不在時は observation_gap)。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| doc emitter | `$CLAUDE_PLUGIN_ROOT/scripts/doc-emit.py` | draft/manifest 生成 + completeness 検査 |
| mermaid gate | `$CLAUDE_PLUGIN_ROOT/scripts/mermaid-validate.py` | 5 種図種網羅 + 構文検証 |
| blueprint schema | `$CLAUDE_PLUGIN_ROOT/schemas/system-blueprint.schema.json` | top-level shape 正本 |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/doc-emit.py" --extraction <json> --out-dir <dir> --request-ledger <f> [--check-screens]`
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/mermaid-validate.py" --docs-dir <dir>`
- network なし (C11 は書き込みのみ)。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- schema violation / provenance 欠落 / screenshot-layout completeness violation は exit1。R2 (fact 補完) または R1 (再観測) へ差し戻す。最大反復回数: 5。

### 4.2 観測 / ロギング
- stdout に生成パス一覧 + draft_hash + check-screens/mermaid-validate 結果。

### 4.3 セキュリティ
- emit 時 text redact-on-emit。C11(doc-emit) 自身は画像実体を取得せず (screenshot/rendered DOM は R1 browser-render(C15) が取得・ブラウザ不在時のみ observation_gap)、画像側 redaction は対象外で C11 は text 系 emit の redaction_applied のみ記録する。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- 決定論 script (`doc-emit.py`/`mermaid-validate.py`) 主体。統合 draft は `architecture-essence-synthesizer` 出力を入力にする。

### 5.2 ゴール定義
- 目的: fact/inference/gap 区別済み抽出結果を schema 準拠 md/json + 5 種 Mermaid + 画面別 layout として確定し、draft_hash を固定する。
- 背景: 生成側 (C01) と承認側 (C02) が同一決定論ゲート (C10/C11) を共有することで基準乖離を防ぐ。
- 達成ゴール: `doc-emit.py --check-screens` と `mermaid-validate.py` が exit0 で、screenshot/layout 参照整合・観測色 palette 孤児 0・5 種図種網羅が満たされ、draft_hash が固定された状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] `doc-emit.py` で章別 draft (md/json) + 5 種 Mermaid + 画面別 layout.json + design-tokens.json + site coverage manifest を生成した (screenshot/annotated/overlay は browser-render(C15) 取得時に screens[] へ・ブラウザ不在時のみ observation_gap)
- [ ] `doc-emit.py --check-screens` が exit0 (参照整合・観測色 palette 孤児 0・pending 無言欠落なし。screens が空なら check-screens はスキップ)
- [ ] `mermaid-validate.py` が exit0 (5 種図種網羅 + 構文妥当)
- [ ] text 系 PII/認証後情報を redact し redaction_applied を記録した

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (doc-emit 実行 / check-screens / mermaid-validate / 差し戻し)→実行→チェックリストで自己評価→全項目充足まで反復する (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-extract-blueprint` SKILL の R3-document 局面。
- 後続 phase: C02 が draft_hash に束縛した独立品質 verdict (PASS/FAIL) を発行する。

### 6.2 ハンドオフ / 並列性
- 提供元: R2 (fact/inference/essence 統合)。
- 受領先: C02 (独立品質評価)。
- 引き渡し形式: 章別 draft + draft_hash (成果物ディレクトリ配下)。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に生成パス一覧・draft_hash・check-screens/mermaid-validate の結果サマリ (Markdown)。

### 7.2 言語
- 本文: 日本語 (schema キー / enum / Mermaid 記法は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`doc-emit.py` で fact/inference/gap 区別済み抽出結果を `system-blueprint.schema.json` 準拠の章別 md/json + 5 種 Mermaid + 画面別 layout.json + 合成 design-tokens.json + site coverage manifest へ確定する (screenshot/annotated/overlay/computed-style は R1 browser-render(C15) 取得時に screens[] へ、ブラウザ不在時のみ observation_gap として記録)。`doc-emit.py [--check-screens]` (screens が空なら check-screens はスキップ) と `mermaid-validate.py --docs-dir` を exit0 まで通し、draft_hash を固定する。text 系 PII/認証後情報は redact する。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。出力は生成パス一覧・draft_hash・検査結果サマリのみ、前置き禁止。
