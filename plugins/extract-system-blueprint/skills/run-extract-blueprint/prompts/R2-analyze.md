# Prompt: R2-analyze

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R2-analyze |
| skill | run-extract-blueprint |
| responsibility | R2 分析への委譲と事実/推測分離収集 (1 prompt = 1 責務) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../../../schemas/fact-inference-confidence.schema.json |
| reproducible | true (同一観測入力に対し同一 fact/inference レコード構造) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- fact (provenance 付き観測) と inference (evidence_refs+confidence 付き推測) と observation_gap (not_observed|blocked+reason) を相互排他に保つ。gap を inference へ昇格させない。
- 各 analyzer の実プロンプトへ inventory の実名レンズ見出し・cross-lens conflicts・neutral synthesis・非模倣/非推薦 guard を展開する。レンズ由来主張も evidence_refs+confidence 必須で fact へ混入させない。
- inference の `high` confidence は直接支持する複数 evidence_refs がある場合だけ許す。

### 1.2 倫理ガード
- 著名人/組織の口調模倣・レビュー/承認/推薦の主張をしない。名前を権威根拠にしない。security 推測は受動観測のみ (侵入テスト/脆弱性スキャン/認証突破の提案・実行禁止)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: analyzer 5 体への順次委譲と、fact/inference の明示区別収集。
- 非担当: 取得 (R1)、doc-emit/Mermaid 生成 (R3)。

### 2.2 ドメインルール
- 委譲順: `frontend-surface-analyzer` (fact) → `backend-inference-analyzer` / `uiux-rationale-analyzer` / `content-intent-analyzer` (C03 出力起点の直交 3 レーン) → `architecture-essence-synthesizer` (fan-in 統合)。
- C04/C05/C13 は互いを参照せず C03 fact を唯一起点にする (DAG 深化回避)。突合・統合は C06 が essence 章 (JTBD/読者/価値提案/キーメッセージ/トーン/positioning) へ行う。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| observation fact records | json | yes | R1 が書き出した snapshot/observation fact |
| site coverage manifest | json | yes | in_scope/pending/excluded 台帳 |

### 2.4 出力契約
- 各 analyzer が fact / inference を分離 JSON として成果物ディレクトリへ直接書き出す (sub-agent 最終応答は coverage manifest + 出力パス一覧のみ=応答長起因の無言欠落を排除)。
- 統合 essence + feature_map(fact 集約) + user_journeys(推測) + security_design/delivery_topology(推測) を明示区別する。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| frontend agent | `$CLAUDE_PLUGIN_ROOT/agents/frontend-surface-analyzer.md` | fact 抽出 |
| backend agent | `$CLAUDE_PLUGIN_ROOT/agents/backend-inference-analyzer.md` | バックエンド/named/security/topology 推測 |
| uiux agent | `$CLAUDE_PLUGIN_ROOT/agents/uiux-rationale-analyzer.md` | UIUX/journeys 推測 |
| content agent | `$CLAUDE_PLUGIN_ROOT/agents/content-intent-analyzer.md` | 伝達意図/JTBD 推測 |
| synthesizer | `$CLAUDE_PLUGIN_ROOT/agents/architecture-essence-synthesizer.md` | essence 統合 + Mermaid |

### 3.2 外部ツール / API
- Task ツールで各 analyzer を独立 context (fork) 起動する。C06 は `mermaid-validate.py`/`doc-emit.py` を Bash で参照する。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- analyzer の出力に fact 欠落・gap 無言欠落・レンズ主張の fact 混入があれば当該 analyzer へ差し戻す。最大反復回数: 5。

### 4.2 観測 / ロギング
- 各 analyzer の coverage manifest (対象数/抽出数/not_observed 数) を集約し stdout にサマリ。

### 4.3 セキュリティ
- analyzer は追加 network なしで既取得 fact (C09 の静的 HTTP 観測 fact=DOM 構造/宣言スタイル等、および browser-render(C15)取得時は JS 実行後 DOM/rendered screenshot fact) から採取する。browser-render がブラウザ不在(exit 3)だった観測のみ observation_gap(reason=browser-unavailable)であり fact へ昇格させない。C04/C05/C13 は tools=Read, Write (Write は分離 JSON の PLAN 成果物ディレクトリへの直接書出に必須) のみを持ち、write_scope は PLAN 成果物ディレクトリ配下に限る。network・新規観測・write_scope 外への書出へ越境しない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- 上記 analyzer 5 体 (全て independent context / fork)。

### 5.2 ゴール定義
- 目的: 観測 fact と根拠つき推測を明示区別して集め、AI が追加ヒアリングなしで自社スカフォールドへ着手できる粒度の素材を揃える。
- 背景: 同一 context で自己分析すると fact/inference 混同や粒度不足を見落とす。責務分離と独立 context で構造的に分離する。
- 達成ゴール: C03 fact → C04/C05/C13 inference → C06 統合 (essence/feature_map/journeys/security/topology) が evidence_refs+confidence 付きで揃い、fact と inference が明示区別された状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] `frontend-surface-analyzer` が視覚/content/tech_signals/機能/CWV/security/compliance/site_inventory fact を provenance 付きで書き出した (未取得は not_observed+reason)
- [ ] `backend-inference-analyzer` が named 同定/security_design(OWASP)/delivery_topology を evidence_refs+confidence 付き inference で書き出した
- [ ] `uiux-rationale-analyzer` と `content-intent-analyzer` が C03 fact 起点の推測を evidence 接地で書き出した
- [ ] `architecture-essence-synthesizer` が essence 章と feature_map(fact)/journeys(推測)/security/topology を統合した
- [ ] 各 analyzer プロンプトに実名レンズ見出し・cross-lens conflicts・neutral synthesis・guard が存在し、レンズ主張が fact へ混入していない

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (analyzer 起動 / 差し戻し / fan-in)→実行→チェックリストで自己評価→全項目充足まで反復する (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-extract-blueprint` SKILL の R2-analyze 局面。
- 後続 phase: R3-document が fact/inference を doc-emit へ渡す。

### 6.2 ハンドオフ / 並列性
- 提供元: R1 (観測 fact)。
- 受領先: R3 (doc-emit)。
- 引き渡し形式: fact/inference/essence レコード JSON (成果物ディレクトリ配下)。C03→(C04/C05/C13)→C06 の fan-out/fan-in。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に各 analyzer の抽出件数・gap 件数・confidence 分布サマリ (Markdown)。

### 7.2 言語
- 本文: 日本語 (JSON キー / enum / レンズ名は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

Task ツールで `frontend-surface-analyzer` を先行起動して fact records を得てから、`backend-inference-analyzer` / `uiux-rationale-analyzer` / `content-intent-analyzer` を C03 fact 起点の直交レーンとして起動し、最後に `architecture-essence-synthesizer` へ fan-in する。各 analyzer には実名レンズ見出し・cross-lens conflicts・neutral synthesis・非模倣/非推薦 guard を展開し、fact と inference (evidence_refs+confidence 必須) を明示区別して収集する。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。出力は件数・gap・confidence 分布サマリのみ、前置き禁止。
