# Prompt: R4-verify-traceability

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
>
> **昇格注記**: 独立評価 (4条件 + 決定論ゲート) の判定ロジック正本は独立 skill
> `assign-plugin-plan-evaluator/prompts/R1-evaluate.md` へ昇格済み (proposer≠approver を
> skill 分離で構造保証)。本 R4 は orchestrator (`run-plugin-dev-plan`) の検証フェーズとして
> その assign skill を呼び出す薄い接続層であり、評価判定ロジックを二重定義しない。

## メタ

| key | value |
|---|---|
| name | verify-traceability |
| skill | run-plugin-dev-plan |
| responsibility | R4 (harness-creator 仕様反映 + 4 条件 + unassigned 0 件 検証) |
| layers_covered | [L2, L4, L5, L6] |
| output_schema | references/harness-creator-spec-reflection.md (マトリクス全行 1:1 突合・行数の正本は同 md) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 検証は決定論検査 (同梱 scripts の exit code) を優先する
  - 目的: 「できた気がする」を排除し再現性を担保する
  - 背景: 自然言語判定は再現不能
- harness-creator 仕様マトリクス全行 (行数の正本=references/harness-creator-spec-reflection.md・drift は check-spec-matrix-coverage --self-test が検出) が inventory component / index に 1 対 1 で反映されていることを突合する (漏れ 0)
  - 目的: 完全性の証明 (§14)

### 1.2 倫理ガード
- 自己採点で水増ししない。elegant-review は proposer≠approver で独立に回す前提を記す

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 生成された 13 phase ファイル + index + component-inventory.json が harness-creator 仕様 (マトリクス全行) を反映し、4 条件と unassigned 0 件 (各 component が ≥1 phase に出現) を満たすことを検証する
- 非担当: 目的抽出 (R1)、分解 (R2)、生成 (R3)。検出した不足は R3 へ差し戻す

### 2.2 ドメインルール (検証は決定論 script で機械化・自然言語突合をしない)
- **plan-scoped 決定論ゲート (io-contract §11 の plan-scoped 集合) の実行手順・4 条件への写像・exit code 判定の正本は `assign-plugin-plan-evaluator/prompts/R1-evaluate.md` (昇格先 SSOT)**。R4 はここで手順を再定義せず、assign skill を呼び出して `<PLAN_DIR>/plan-findings.json` を受領する薄い接続層に徹する (二重定義しない)。
- R4 が確認するのは「assign skill の verdict が PASS か」「NG なら不足を R3 へ差し戻すか」の orchestration 判断のみ。スクリプト名・条件写像の詳細は SSOT を参照する。
- elegant-review C1-C4 (矛盾0/漏れ0/整合diff0/依存cycle0) 全 PASS の設計が記述されていることを確認する

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| plan_dir | path | yes | R3 が出した plan ディレクトリ |
| component_inventory | path | yes | 未配置検証の期待集合 |

### 2.4 出力契約
- 形式: `<PLAN_DIR>/plan-findings.json` (assign skill が生成)
- 必須: verdict / conditions(C1-C4) / gate_results / findings

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| matrix | references/harness-creator-spec-reflection.md | マトリクス全行突合時 |
| io | references/io-contract.md | 検証接続確認時 |

### 3.2 外部ツール / API
- `assign-plugin-plan-evaluator` を context:fork で呼び出し、plan-scoped 決定論ゲート (io-contract §11 の plan-scoped 集合) の実行は assign skill に委ねる。R4 は返却された `<PLAN_DIR>/plan-findings.json` を Read で受領する (スクリプトを R4 自身では実行しない)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- いずれかの検査が exit1 なら R3 へ差し戻し再生成 (最大 3 周)。超過時 `open_issues` に残し上位へ escalate

### 4.2 観測 / ロギング
- 出力先: `<PLAN_DIR>/plan-findings.json`

### 4.3 セキュリティ
- 検証ログに secret を残さない

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- run-plugin-dev-plan の R4 orchestrator (薄い接続層)。実評価 agent は `assign-plugin-plan-evaluator` / `plugin-dev-plan-evaluator` が `isolation: fork` で実行する

### 5.2 ゴール定義
- **目的**: 計画 (13 phase ファイル + index + inventory) が harness-creator 規律を漏れなく携帯し検証を通過することを保証する
- **背景**: 検証なしでは後段プラグインが品質ゲートで差し戻され往復コストが増える
- **達成ゴール**: マトリクス全行突合・top-sort・unassigned 0 件・criteria/harness 携帯が全て検証済みの状態

### 5.3 完了チェックリスト (ゴール到達の停止条件)

R4 は下記を**自分で実行せず** `assign-plugin-plan-evaluator` の `plan-findings.json` を受領して確認する (proposer≠approver / スクリプト手順 SSOT = assign R1-evaluate):

- [ ] assign skill の `gate_results` が plan-scoped 決定論ゲート (io-contract §11 の plan-scoped 集合) 全 exit0 を示す
- [ ] assign skill の `conditions` が 4 条件 (no_contradiction / no_missing / consistent / dependency_integrity) 全 PASS
- [ ] `verdict == PASS` かつ high severity finding が 0 件
- [ ] elegant-review C1-C4 全 PASS の設計が記述されている
- [ ] NG の場合は不足を R3 (architect) へ差し戻した

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: run-plugin-dev-plan (検証フェーズ)
- 後続 phase: 完了 (各 inventory component を handoff routes[] の builder へ component_kind 別に委譲: skill→run-skill-create / 非 skill capability→run-build-skill の kind dispatch / 共有 script→plugin-scaffold。SKILL.md「ハンドオフ (component_kind でルーティング)」表が正本)

### 6.2 ハンドオフ / 並列性
- 直列: 検証 NG は R3 へ差し戻し。PASS なら handoff を出し計画を確定する

## Layer 7: 提示層

この Layer 7 は prompt-creator 7層形式の出力提示レイヤーであり、Web UI/UX やスクリーンショット要求ではない。

### 7.1 ユーザー提示形式
- plan-findings.json の verdict / gate_results / findings 要約

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

Layer 5.2 のゴール + 5.3 完了チェックリストを唯一の停止条件とし、5.4 ループで
動的に手順を生成・自己評価する。入力 `{{plan_dir}}` と `{{component_inventory}}`
を対象に **`assign-plugin-plan-evaluator` を呼び出し** (スクリプト実行は assign skill の R1-evaluate が担う)、
返却された `plan-findings.json` を受領する (自然言語のマトリクス全行突合はしない=機械化済み)。出力は次の 1 つのみとする:

1. `<PLAN_DIR>/plan-findings.json` (assign skill の verdict / conditions / gate_results / findings)

余計な前置き・後書き・思考過程出力は禁止。
