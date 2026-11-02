---
graph_node_id: "doc-branch-publication"
artifact_kind: "document"
artifact_subtypes: []
title: "元ブランチ全残存の統合・保存先の案内"
project_id: "harness"
domain: "delivery"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["branch-publication", "source-preservation", "existing-contracts"]
file_path: "docs/branch-publication.md"
template_id: "document"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-01T21:51:01.228579Z"
updated_at: "2026-11-02T04:02:36.456667Z"
depends_on: []
related_nodes: ["spec-branch-publication", "arch-branch-publication", "feature-branch-publication", "task-branch-remaining-publication"]
resource_scope: []
purpose: null
goal: null
scope_in: []
scope_out: []
acceptance: []
architecture_refs: []
parent_feature: null
feature_package_id: null
phase_ref: null
classification_confidence: 0.99
classification_reason: "元ブランチ全残存の統合を、既存責務契約への参照と実パスの対応で記録する正規document。"
classification_candidates: [{"artifact_kind": "document", "candidate_path": "docs/branch-publication.md", "confidence": 0.99}, {"artifact_kind": "specification", "candidate_path": "specs/branch-publication.md", "confidence": 0.01}]
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

元rootの全残存を実際にcommitし、最新main・既存PRを統合した同一履歴を公開してrootをcleanにする作業の参照先をまとめる。

## 対象読者

統合を担当するmaintainer、PR reviewer、元版や素材の保存先を確かめる利用者。

## 要約

元の1440差分はsource commit d71ac0a6へ記録し、mainとレビュー済みPRを元ブランチで統合する。raw eval-log1063件を元pathで保持し、flyer旧追加165件はdocs/branch-publication/source-files/plugins/flyer-studio/にraw保存して現行1.3.2を戻さない。最後に元ブランチとPRブランチを同一HEADへ揃えて両方をpushし、元rootのcleanを確認する。

## 本文

[全件台帳](branch-publication/manifest.json) と [worktree統合記録](branch-publication/worktree-integration.json) が、元rootの1440 status entries・元HEADの先行11変更・source commitのbytes・現行の統合先を対応付ける。source commitは元pathの正確な版を保持する。raw eval-logは元path、旧flyer165ファイルは [raw保存先](branch-publication/source-files/plugins/flyer-studio/) に置く。従来の元版362ファイルのZIP保存と [復元script](branch-publication/restore-source.py) も過去の保存証拠として残す。

正規の説明は [仕様](../specs/branch-publication.md)、[責務設計](../architecture/branch-publication.md)、[macro feature](../features/branch-publication.md) を参照する。既存製品のCLI・描画・文書契約は各pluginの正本に残し、今回のscope修正で新しいHTTP/DB/製品仕様は追加しない。

## 決定事項

「PR作業ツリーだけ」「元worktreeを変更しない」という旧条件を、元rootで全残存をcommit・統合・clean化する確定scopeへ置き換える。文書/feature/taskはdraft/pending・tracker_binding noneを維持し、新しい13計画へ昇格しない。[draft task](../tasks/branch-remaining-publication.md) は既存harness-86khの拡張scopeで追跡する。未取得の承認、promotion、CI PASSは作らない。

## 運用・更新方法

親が最終commit後に元ブランチ devgraph/package-artifacts-and-feature-promotion とPRブランチ devgraph/task-gdg-reviewを同一HEADへ揃え、両remote branchへpushし、元ブランチの同名origin追跡先とroot cleanを実測する。対応先不明0件と、commit/push/CI/mergeの達成は別々に記録する。C02文書を直接編集せずpreview/applyを通し、古いreceiptの当時SHAは書き換えずfollowupを追記する。

## 関連資料

- [確定scopeの統合タスク](../tasks/branch-remaining-publication.md)
- [元worktree統合記録](branch-publication/worktree-integration.json)
- [全残存の案内](branch-publication/README.md)
- [当時のtask契約評価](branch-publication/task-contract-review.json)：当時SHAの評価であり、今回修正したscopeへ自動流用しない。
- [system-spec影響索引](../system-spec/branch-publication/README.md)
- [仕様影響受領書と追記](../system-spec/branch-publication/spec-impact-receipt.json)
- [既存guide資料](../system-spec/guide-doc-generator/README.md)

## 変更履歴

2026-11-02: C02で4資料を初回draft登録。その後、利用者のgs明示により元1440差分そのもののcommit、元rootの統合・clean化、2ブランチの同一HEADと両pushを受入へ追加。過去receiptの当時SHAは保持し、新しいC02 updateの証拠をfollowupへ追記する。

## 2026年11月2日のCI実走と再開条件

共有runtime guardの修復と全9対象の再受入へ運用状態を同期する。過去の失敗・承認・原SHAと当時の受領書は履歴として保持する。

利用者の「codexで進めて」に基づき、明示 `--runtime codex` の実受入を進める。省略時のClaude経路を保持し、runtime間のPASS再利用や原JSONLのClaude形式への変換はしない。正本は [live-trial Skill](../plugins/harness-creator/skills/run-skill-live-trial/SKILL.md)、[Codex native契約](../plugins/harness-creator/skills/run-skill-live-trial/references/codex-live-trial.md)、[外部変更guard契約](../plugins/skill-governance-adapters/references/external-mutation-guard-contract.md)。今回の影響と検証は [Codex native受入受領書](../system-spec/branch-publication/codex-native-acceptance-receipt.json) に追記する。

製品契約への追加影響あり。SGAの `hook-confirm` / `pretool` は信頼済みhook commandの `--runtime claude|codex` を受け、既定Claudeを保持する。確認・intent receiptのproducerを署名前にruntimeから選び、Codexは `codex-user-prompt-submit`、Claudeは既存値とする。payloadの自己申告をruntimeに使わず、生成後のreceipt・署名を書き換えない。Codexが実際に渡すcanonical `Bash` / `tool_input.command` と既存deny形式を利用し、架空のBash/UserPromptSubmitを注入しない。HCのtyped外部gate接続は実装・独立確認中で、深度選択とは別の契約として扱う。

正規 `build-artifact-delivery` writerによる23 pluginのprojection更新は共有runnerのSHA同期だけであり、他plugin全体への新機能・権限追加とは区別する。SGAの動作検査33件成功・projection検査1件成功は親担当の報告で、この文書担当が再実行した結果やnative hook実走の成功ではない。最終版番号・release整合・source SHAは採番とfreeze待ちとし、途中の値を確定値へ付け替えない。

共有SGA実装は全9対象のruntime閉包に含まれるため、今回の変更で旧init PASSも現行sourceの合格根拠ではなくなる。必要な新受入はinitを含む全9対象へ更新する。C01のCodex scenarioは旧args・required observations・時間/token予算を逐語保持し、native IDを付けた正本を親が追加済み。旧criteriaの1 passed・8 failedは当時のsourceの実測として保持し、新sourceでも同じ結果だったとは主張しない。canonical criteria receiptは未更新である。

旧source `8c710295` のC05/renderとC19/system-specはnamespace不一致によりnative skill注入0件、正規BLOCKED・goal_fit NOT_EVALUATED・残process 0の履歴を保持する。旧freezeの137ファイル、revision9/10のimmutable receipt、過去のClaude FAIL/DEGRADED/利用上限BLOCKEDと [以前の実走受領書](../system-spec/branch-publication/ci-exhaustive-attempt-receipt.json) の原SHAを書き換えない。続く旧 `43a` sourceのBASEci2はC19 fixture準備のみ・actor起動0件で、private原固定を保持する。これらを新sourceの実走やPASSに数えない。

C03/syncは、最終command/sourceをレビュー可能にしてから隔離fixtureの2handlerに限るnative `/hooks` の信頼許可を1回確認する予定で、現在は未提示・未承認。logging wrapperを含む最終定義を固定し、実native UserPromptSubmitと正規guard consumerの到達まで保留する。trust hash・確認receipt・署名を自作せず、generic resumeを外部変更の承認へ読み替えない。fake-ghによるfixture内の変更だけを許し、実GitHub/Beads/Projectsへの接続・一般trust/sandbox bypass・他ユーザー設定の変更を行わない。

新sourceの実受入PASSは0件、CIは未達である。新しい `/private/tmp/harness-codex-ci3-20261102` の試行は最終freeze後に行う。最大同時2と元の反復上限・予算を守り、全scenario、goal-seek実体、原SHA/runtime閉包、fixture-final/freeze、別contextのfresh goalを確認する。成果物の本文提示→実user選択→独立Agentの順と、typed native handoffの回数・順序を記録する。source/private control/raw/公開workdirはactor workspace外とし、書込先はfixtureと完了マーカー用outだけ。Claude固有のSkill/Agent/Stop/権限hookの成立や単一入力での無対話自走と同一視せず、旧PASSのSHA付替え、CI成功・全9対象完了・最終commit/push/PR完了・新promotionの認定を行わない。

