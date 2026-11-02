---
graph_node_id: "feature-branch-publication"
artifact_kind: "feature"
artifact_subtypes: []
title: "元ブランチの全残存を新版を保持してPRへまとめる"
project_id: "harness"
domain: "delivery"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["branch-publication", "source-preservation", "existing-contracts"]
file_path: "features/branch-publication.md"
template_id: "feature"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "generated", "source_digest": null, "source_path": null, "source_plugin": "dev-graph", "source_version": null}
created_at: "2026-11-01T21:51:01.228579Z"
updated_at: "2026-11-02T04:02:36.456667Z"
depends_on: []
related_nodes: []
resource_scope: []
purpose: "元rootの全1440差分そのものをcommit・統合し、mainの新版を保持した同一履歴をPRへ公開できるようにする。"
goal: "元1440件をsource commitと統合先で説明でき、元rootがclean、元/PRブランチが同一HEADで両push・同名追跡先を確認できる。"
scope_in: ["元1440差分の元ブランチ上commitと元HEAD先行11変更の統合", "最新mainと既存PRの元rootへの統合および競合解消", "raw eval-log1063件の元path保持と旧flyer165件のraw保存", "元rootのclean化・元/PR同一HEAD・両push・同名追跡先の確認"]
scope_out: ["新規HTTP・DB・認証基盤の追加", "新しい13フェーズ計画の生成・feature/taskの承認やpromotion", "現行flyer1.3.2を元1.3.1で上書きする変更"]
acceptance: ["元1440差分の元bytesがsource commitから辿れ、各統合先またはraw保存先を説明できる", "mainの先行修正を保ち旧flyer entrypointを現行1.3.2へ混在させない", "元rootの未commit/未追跡0件を最終commit後に確認する", "元ブランチとPRブランチの同一HEAD・両push・元の同名origin追跡先を確認する", "文書・feature・taskはdraft/pending・trackerなしで既存harness-86khの追跡を維持する"]
architecture_refs: ["arch-branch-publication"]
parent_feature: null
feature_package_id: null
phase_ref: null
classification_confidence: 1.0
classification_reason: "declared by the C14 macro contract (run-dev-graph-decompose)"
classification_candidates: [{"artifact_kind": "feature", "candidate_path": "features/branch-publication.md", "confidence": 1.0}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-02T04:02:36.456667Z", "missing_sections": [], "status": "complete"}
---

# 目的

元rootの全1440差分そのものをcommit・統合し、mainの新版を保持した同一履歴をPRへ公開できるようにする。

## 到達状態

元1440件をsource commitと統合先で説明でき、元rootがclean、元/PRブランチが同一HEADで両push・同名追跡先を確認できる。

## スコープ

- スコープ内: 元1440差分の元ブランチ上commitと元HEAD先行11変更の統合
- スコープ内: 最新mainと既存PRの元rootへの統合および競合解消
- スコープ内: raw eval-log1063件の元path保持と旧flyer165件のraw保存
- スコープ内: 元rootのclean化・元/PR同一HEAD・両push・同名追跡先の確認
- スコープ外: 新規HTTP・DB・認証基盤の追加
- スコープ外: 新しい13フェーズ計画の生成・feature/taskの承認やpromotion
- スコープ外: 現行flyer1.3.2を元1.3.1で上書きする変更

## 受入

- [ ] 元1440差分の元bytesがsource commitから辿れ、各統合先またはraw保存先を説明できる
- [ ] mainの先行修正を保ち旧flyer entrypointを現行1.3.2へ混在させない
- [ ] 元rootの未commit/未追跡0件を最終commit後に確認する
- [ ] 元ブランチとPRブランチの同一HEAD・両push・元の同名origin追跡先を確認する
- [ ] 文書・feature・taskはdraft/pending・trackerなしで既存harness-86khの追跡を維持する

## アーキテクチャ参照

- `arch-branch-publication`

## 機能間依存

- 先行 feature なし (`depends_on` は空)

## Handoff

元rootでの全1440差分のcommitとmain/PR統合を、親のworktree-integration.jsonへ接続する。親が最終commit・root clean・元/PR同一HEAD・両push・同名追跡先を実測しPR #87へ渡す。本featureは整理用draft、実行追跡は既存harness-86khとし、新13計画・promotion・未取得承認・CI PASSを生成しない。

## 2026年11月2日のCI実走と再開条件

提供機能はCodex nativeの実証拠を収集し、外部変更の確認を実runtimeへ束縛すること。今回はsource修復と再受入準備の記録であり、受入完了ではない。

利用者の「codexで進めて」に基づき、明示 `--runtime codex` の実受入を進める。省略時のClaude経路を保持し、runtime間のPASS再利用や原JSONLのClaude形式への変換はしない。正本は [live-trial Skill](../plugins/harness-creator/skills/run-skill-live-trial/SKILL.md)、[Codex native契約](../plugins/harness-creator/skills/run-skill-live-trial/references/codex-live-trial.md)、[外部変更guard契約](../plugins/skill-governance-adapters/references/external-mutation-guard-contract.md)。今回の影響と検証は [Codex native受入受領書](../system-spec/branch-publication/codex-native-acceptance-receipt.json) に追記する。

製品契約への追加影響あり。SGAの `hook-confirm` / `pretool` は信頼済みhook commandの `--runtime claude|codex` を受け、既定Claudeを保持する。確認・intent receiptのproducerを署名前にruntimeから選び、Codexは `codex-user-prompt-submit`、Claudeは既存値とする。payloadの自己申告をruntimeに使わず、生成後のreceipt・署名を書き換えない。Codexが実際に渡すcanonical `Bash` / `tool_input.command` と既存deny形式を利用し、架空のBash/UserPromptSubmitを注入しない。HCのtyped外部gate接続は実装・独立確認中で、深度選択とは別の契約として扱う。

正規 `build-artifact-delivery` writerによる23 pluginのprojection更新は共有runnerのSHA同期だけであり、他plugin全体への新機能・権限追加とは区別する。SGAの動作検査33件成功・projection検査1件成功は親担当の報告で、この文書担当が再実行した結果やnative hook実走の成功ではない。最終版番号・release整合・source SHAは採番とfreeze待ちとし、途中の値を確定値へ付け替えない。

共有SGA実装は全9対象のruntime閉包に含まれるため、今回の変更で旧init PASSも現行sourceの合格根拠ではなくなる。必要な新受入はinitを含む全9対象へ更新する。C01のCodex scenarioは旧args・required observations・時間/token予算を逐語保持し、native IDを付けた正本を親が追加済み。旧criteriaの1 passed・8 failedは当時のsourceの実測として保持し、新sourceでも同じ結果だったとは主張しない。canonical criteria receiptは未更新である。

旧source `8c710295` のC05/renderとC19/system-specはnamespace不一致によりnative skill注入0件、正規BLOCKED・goal_fit NOT_EVALUATED・残process 0の履歴を保持する。旧freezeの137ファイル、revision9/10のimmutable receipt、過去のClaude FAIL/DEGRADED/利用上限BLOCKEDと [以前の実走受領書](../system-spec/branch-publication/ci-exhaustive-attempt-receipt.json) の原SHAを書き換えない。続く旧 `43a` sourceのBASEci2はC19 fixture準備のみ・actor起動0件で、private原固定を保持する。これらを新sourceの実走やPASSに数えない。

C03/syncは、最終command/sourceをレビュー可能にしてから隔離fixtureの2handlerに限るnative `/hooks` の信頼許可を1回確認する予定で、現在は未提示・未承認。logging wrapperを含む最終定義を固定し、実native UserPromptSubmitと正規guard consumerの到達まで保留する。trust hash・確認receipt・署名を自作せず、generic resumeを外部変更の承認へ読み替えない。fake-ghによるfixture内の変更だけを許し、実GitHub/Beads/Projectsへの接続・一般trust/sandbox bypass・他ユーザー設定の変更を行わない。

新sourceの実受入PASSは0件、CIは未達である。新しい `/private/tmp/harness-codex-ci3-20261102` の試行は最終freeze後に行う。最大同時2と元の反復上限・予算を守り、全scenario、goal-seek実体、原SHA/runtime閉包、fixture-final/freeze、別contextのfresh goalを確認する。成果物の本文提示→実user選択→独立Agentの順と、typed native handoffの回数・順序を記録する。source/private control/raw/公開workdirはactor workspace外とし、書込先はfixtureと完了マーカー用outだけ。Claude固有のSkill/Agent/Stop/権限hookの成立や単一入力での無対話自走と同一視せず、旧PASSのSHA付替え、CI成功・全9対象完了・最終commit/push/PR完了・新promotionの認定を行わない。

