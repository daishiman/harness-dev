# Prompt: R3-emit

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R3-emit |
| skill | run-blueprint-apply |
| responsibility | R3 apply-recommendations の emit と決定論自己検証 (1 prompt = 1 責務) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../../../schemas/system-blueprint.schema.json |
| reproducible | true (同一 recommendations から同一 md/json + 同一検査結果) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 出力はローカル `apply-recommendations.json` + `.md` のみ。blueprint 本体 (`blueprint.json`) を書き換えない・対象 origin へアクセスしない (network 0)。
- `doc-emit.py --check-apply` が exit0 になるまで確定しない (schema 適合・evidence anchor 解決率 100%・kind=fact 新規レコード 0・分類 adopt|avoid|differentiate のみ)。
- md と json は同一 recommendations から導出する (内容乖離を作らない)。

### 1.2 倫理ガード
- `apply-recommendations.md` 冒頭へ参考/学習目的限定注記を付す (blueprint 由来の記述を自社適用文脈で扱う旨)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: recommendations の md/json emit、`doc-emit.py --check-apply` による決定論自己検証。
- 非担当: 受理検証 (R1)、推奨導出 (R2)。

### 2.2 ドメインルール
- json ルート形状は `{"recommendations": [...]}`。各項目は `kind:"inference"` / `category ∈ {adopt,avoid,differentiate}` / `claim` / `own_context_ref` / `evidence_refs:[...]` (全て blueprint 実在 anchor) / `confidence:{level,rationale}` を持つ。
- md は 3 分類ごとに節を分け、各推奨の claim / 根拠 anchor (evidence_refs) / 確度 (confidence.level+rationale) / 自社接地先 (own_context_ref) を提示する読み物にする。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| recommendations | json | yes | R2 が導出した 3 分類 recommendations |
| blueprint | json | yes | anchor 解決の参照元 (`<blueprint_dir>/blueprint.json`) |
| out_dir | path | no | 出力先。既定 `apply-recommendations/` |

### 2.4 出力契約
- `<out_dir>/apply-recommendations.json` (`{"recommendations":[...]}`) + `<out_dir>/apply-recommendations.md`。
- `doc-emit.py --check-apply <out_dir>/apply-recommendations.json --blueprint <blueprint_dir>/blueprint.json` が exit0 (`{"check":"apply","status":"pass"}`)。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| apply 検査 | `$CLAUDE_PLUGIN_ROOT/scripts/doc-emit.py` (--check-apply) | schema/anchor/fact/分類の決定論自己検証 |
| blueprint 正本 | `<blueprint_dir>/blueprint.json` | evidence anchor 解決の参照元 |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/doc-emit.py" --check-apply <out_dir>/apply-recommendations.json --blueprint <blueprint_dir>/blueprint.json`
- Write (apply-recommendations.md/json のローカル出力) のみ。network なし・blueprint 非書込。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `--check-apply` が exit1 なら violations を読み、該当項目 (無効 anchor/kind=fact 混入/分類逸脱/confidence 欠落/own_context_ref 欠落) を R2 へ差し戻して再導出する。最大反復回数: 3。

### 4.2 観測 / ロギング
- stdout に生成パス・3 分類件数・`--check-apply` の pass/fail サマリ。周回状態は `eval-log/run-blueprint-apply-intermediate.jsonl` へ追記する。

### 4.3 セキュリティ
- blueprint.json を read-only で扱う。自社コンテキストの機微を md へ生露出せず own_context_ref で参照する。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- 決定論 script (`doc-emit.py --check-apply`) 主体。emit は LLM が recommendations を md/json へ整形する。

### 5.2 ゴール定義
- 目的: recommendations を schema 準拠の md/json へ確定し、共有決定論ゲートで自己検証する。
- 背景: 生成側 (本 skill) が C01/C02 と同一の `--check-apply` を共有することで、apply shape の基準乖離と無根拠主張の混入を機構的に防ぐ。
- 達成ゴール: `apply-recommendations.json/.md` が emit され、`doc-emit.py --check-apply` が exit0 (schema 適合・evidence anchor 解決率 100%・fact 新規 0・3 分類のみ) で、blueprint 本体へ書き込んでいない状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] `apply-recommendations.json` (`{"recommendations":[...]}`) を emit した
- [ ] `apply-recommendations.md` を 3 分類ごとに claim/根拠 anchor/確度/自社接地先を提示する読み物として emit した
- [ ] `doc-emit.py --check-apply` が exit0 (schema 適合・anchor 解決率 100%・fact 新規 0・3 分類のみ)
- [ ] md 冒頭へ参考/学習目的限定注記を付した
- [ ] blueprint 本体を書き換えず・対象 origin へアクセスしていない (network 0)

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (md/json emit / check-apply / 差し戻し)→実行→チェックリストで自己評価→全項目充足まで反復する (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-blueprint-apply` SKILL の R3-emit 局面。
- 後続 phase: なし (本 skill の最終成果物)。apply-recommendations は自社版スカフォールド/設計判断の入力としてローカル利用する。

### 6.2 ハンドオフ / 並列性
- 提供元: R2 (recommendations JSON)。
- 受領先: ユーザー (ローカル apply-recommendations)。
- 引き渡し形式: `<out_dir>/apply-recommendations.json` + `.md` + `--check-apply` pass サマリ。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に生成パス・3 分類件数・`--check-apply` 結果サマリ (Markdown)。

### 7.2 言語
- 本文: 日本語 (JSON キー / enum / anchor は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

R2 が導出した recommendations を `<out_dir>/apply-recommendations.json` (`{"recommendations":[...]}`) と `<out_dir>/apply-recommendations.md` (3 分類ごとに claim/根拠 anchor/確度/自社接地先を提示する読み物・冒頭へ参考/学習目的限定注記) へ emit する。`python3 "$CLAUDE_PLUGIN_ROOT/scripts/doc-emit.py" --check-apply <out_dir>/apply-recommendations.json --blueprint <blueprint_dir>/blueprint.json` を exit0 (`status:pass`) まで通す。exit1 の violations は該当項目 (無効 anchor/kind=fact 混入/分類逸脱/confidence・own_context_ref 欠落) を R2 へ差し戻して再導出する。blueprint 本体へ書き込まず対象 origin へアクセスしない。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。出力は生成パス・3 分類件数・check-apply サマリのみ、前置き禁止。
