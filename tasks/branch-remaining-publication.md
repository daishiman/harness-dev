---
graph_node_id: "task-branch-remaining-publication"
artifact_kind: "task"
artifact_subtypes: []
title: "元ブランチの残存全変更を最新mainへ統合してPR化する"
project_id: "harness"
domain: "delivery"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: []
file_path: "tasks/branch-remaining-publication.md"
template_id: "task"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-01T21:31:31.563501Z"
updated_at: "2026-11-02T04:02:36.456667Z"
depends_on: []
related_nodes: ["task-gdg-review"]
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
classification_confidence: 1.0
classification_reason: "既存機能の残存差分全体の公開統合を追跡する通常task"
classification_candidates: [{"artifact_kind": "task", "candidate_path": "tasks/branch-remaining-publication.md", "confidence": 1.0}, {"artifact_kind": "document", "candidate_path": "docs/branch-remaining-publication.md", "confidence": 0.0}]
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

元rootの全1440差分そのものを元ブランチ上でcommitし、最新mainと既存PRの修正を統合した同一HEADを元ブランチとPR #87のブランチへ公開して、元rootをcleanにする。

## 背景

利用者がgsで確定したscopeは、保存用コピーをPRへ載せるだけでなく、元の作業場所の全残存をcommitして公開することまで含む。以前の「PR作業ツリーだけ」「元worktreeを変更しない」という制約は、この確定scopeに置き換える。

## 入力と前提条件

元HEAD 8c1eb6c8の全1440差分を記録したsource commit d71ac0a6、最新main 76abc53d、既存PRの86adf784、統合時HEAD a4bc8d14を入力にする。67件と10件の競合解消およびsource bytesの照合は [統合記録](../docs/branch-publication/worktree-integration.json) に接続する。古い元版でmainの修正を戻さない。

## 出力と成果物

全元差分を保持するsource commitと統合履歴、元path/統合先の全件対応表、raw eval-logの元path保持、flyer旧追加165件のraw保存、C02正規文書と追記の影響受領書、元rootのclean確認、同一HEADの2ブランチと各push/追跡先の記録。

## 依存関係

[guideタスク](gdg-review.md) と関連するが、他者のBeadsを無断で完了にしない。通常taskのpromotion writer不在により本taskはdraftを維持し、実行追跡は既存harness-86khの拡張scopeに集約する。過去テスト写し188件のdiscovery lint対応は別担当の変更を待ち、ここで編集しない。

## 実装対象

dev-graph、UBM、harness-creator、governance lint、release writer、flyer、SBB、guide関連と過去証跡を含む全残存。raw eval-log1063件は元pathを保持し、flyer旧追加165件はdocs/branch-publication/source-files/plugins/flyer-studio/へraw保存する。元path全体の正確な版はsource commitにも保持する。

## Write scope と競合制約

元root /Users/dm/dev/dev/個人開発/harness を統合・commit・clean化の対象にする。元ブランチへ最新mainとレビュー済みPRを統合し、最後にPRブランチを同じHEADへ揃える。他の実行担当と所有を分担し、mainの新版と他者の変更を戻さない。C02文書/graph/receiptは単一writerで更新する。

## GitHub publication

PR #87はhead devgraph/task-gdg-review、base mainを維持する。元ブランチ devgraph/package-artifacts-and-feature-promotion とPRブランチを同一HEADへ揃え、両方をpushする。元ブランチの追跡先は同名のoriginブランチへ設定する。完了は実際のHEAD・remote到達・追跡先・元rootのgit statusで確認し、CI PASSやmergeは未確認なら主張しない。

## 実行手順

1. 元の1440差分と先行11変更を棚卸しする。2. 元ブランチで1440件をsource commitとして記録する。3. 最新remote mainと既存PRを元ブランチへ取り込み、mainの新修正を保って競合を解消する。4. raw証跡とflyer旧版の保存先を照合する。5. C02で確定scopeへ文書を更新し、最小検証と別担当のlint対応を集約する。6. 最終変更をcommitしてrootをcleanにする。7. PRブランチを同一HEADへ進めて両方pushし、元ブランチの追跡先と公開結果を記録する。既に実施済みの段階は統合記録を参照し、未実施を成功扱いにしない。

## 受入条件

元1440差分全件の元bytesがsource commitに保存され、各項目の現行統合先またはraw保存先を説明できる。mainの新修正を保持し、元rootの未commit/未追跡が0件となる。元ブランチとPRブランチが同一HEADで、両remote branchへのpushと元ブランチの同名追跡先を確認できる。文書/feature/taskはdraft・trackerなしを維持し、既存harness-86khで追跡する。

## 検証方法

[全件台帳](../docs/branch-publication/manifest.json) と [元worktree統合記録](../docs/branch-publication/worktree-integration.json) のsource SHA・元path・統合先を照合する。対象別の最小回帰、C02 preview/apply/C11、ファイルSHA、最終のroot statusとlocal/remote HEAD・追跡先を別々に記録する。旧sourceでのinit PASSと残8対象の履歴は保持する。共有SGA実装変更後はinitを含む全9対象の新受入が必要であり、現行PASSやCI成功へ読み替えず、全30思考法は再走しない。

## リスクとロールバック

旧flyerのentrypointを現行1.3.2へ混在させず、旧版はraw保存とsource commitで辿れるようにする。他者の変更を撤回しない。公開後の修正は追加commit/revertで履歴を残す。古いreceiptや過去テストのSHAを現在版のPASSへ書き換えない。

## Handoff

親へC02 revision/immutable receipt/artifact SHAを渡す。最終commit・両branchのHEAD一致・両push・同名追跡先・root cleanの実測は親が統合記録へ追記する。本taskのdraft保持と既存harness-86khの追跡、未取得承認・promotion・CI PASSを作らない条件を維持する。

## 2026年11月2日のCI実走と再開条件

再開条件は共有guard/typed gateの修復・独立確認、正規採番・source freeze、新sourceに対する全9対象の実受入である。実走・採番・Beads・Git・PRと利用者への確認は親担当とし、この文書更新では実行しない。

利用者の「codexで進めて」に基づき、明示 `--runtime codex` の実受入を進める。省略時のClaude経路を保持し、runtime間のPASS再利用や原JSONLのClaude形式への変換はしない。正本は [live-trial Skill](../plugins/harness-creator/skills/run-skill-live-trial/SKILL.md)、[Codex native契約](../plugins/harness-creator/skills/run-skill-live-trial/references/codex-live-trial.md)、[外部変更guard契約](../plugins/skill-governance-adapters/references/external-mutation-guard-contract.md)。今回の影響と検証は [Codex native受入受領書](../system-spec/branch-publication/codex-native-acceptance-receipt.json) に追記する。

製品契約への追加影響あり。SGAの `hook-confirm` / `pretool` は信頼済みhook commandの `--runtime claude|codex` を受け、既定Claudeを保持する。確認・intent receiptのproducerを署名前にruntimeから選び、Codexは `codex-user-prompt-submit`、Claudeは既存値とする。payloadの自己申告をruntimeに使わず、生成後のreceipt・署名を書き換えない。Codexが実際に渡すcanonical `Bash` / `tool_input.command` と既存deny形式を利用し、架空のBash/UserPromptSubmitを注入しない。HCのtyped外部gate接続は実装・独立確認中で、深度選択とは別の契約として扱う。

正規 `build-artifact-delivery` writerによる23 pluginのprojection更新は共有runnerのSHA同期だけであり、他plugin全体への新機能・権限追加とは区別する。SGAの動作検査33件成功・projection検査1件成功は親担当の報告で、この文書担当が再実行した結果やnative hook実走の成功ではない。最終版番号・release整合・source SHAは採番とfreeze待ちとし、途中の値を確定値へ付け替えない。

共有SGA実装は全9対象のruntime閉包に含まれるため、今回の変更で旧init PASSも現行sourceの合格根拠ではなくなる。必要な新受入はinitを含む全9対象へ更新する。C01のCodex scenarioは旧args・required observations・時間/token予算を逐語保持し、native IDを付けた正本を親が追加済み。旧criteriaの1 passed・8 failedは当時のsourceの実測として保持し、新sourceでも同じ結果だったとは主張しない。canonical criteria receiptは未更新である。

旧source `8c710295` のC05/renderとC19/system-specはnamespace不一致によりnative skill注入0件、正規BLOCKED・goal_fit NOT_EVALUATED・残process 0の履歴を保持する。旧freezeの137ファイル、revision9/10のimmutable receipt、過去のClaude FAIL/DEGRADED/利用上限BLOCKEDと [以前の実走受領書](../system-spec/branch-publication/ci-exhaustive-attempt-receipt.json) の原SHAを書き換えない。続く旧 `43a` sourceのBASEci2はC19 fixture準備のみ・actor起動0件で、private原固定を保持する。これらを新sourceの実走やPASSに数えない。

C03/syncは、最終command/sourceをレビュー可能にしてから隔離fixtureの2handlerに限るnative `/hooks` の信頼許可を1回確認する予定で、現在は未提示・未承認。logging wrapperを含む最終定義を固定し、実native UserPromptSubmitと正規guard consumerの到達まで保留する。trust hash・確認receipt・署名を自作せず、generic resumeを外部変更の承認へ読み替えない。fake-ghによるfixture内の変更だけを許し、実GitHub/Beads/Projectsへの接続・一般trust/sandbox bypass・他ユーザー設定の変更を行わない。

新sourceの実受入PASSは0件、CIは未達である。新しい `/private/tmp/harness-codex-ci3-20261102` の試行は最終freeze後に行う。最大同時2と元の反復上限・予算を守り、全scenario、goal-seek実体、原SHA/runtime閉包、fixture-final/freeze、別contextのfresh goalを確認する。成果物の本文提示→実user選択→独立Agentの順と、typed native handoffの回数・順序を記録する。source/private control/raw/公開workdirはactor workspace外とし、書込先はfixtureと完了マーカー用outだけ。Claude固有のSkill/Agent/Stop/権限hookの成立や単一入力での無対話自走と同一視せず、旧PASSのSHA付替え、CI成功・全9対象完了・最終commit/push/PR完了・新promotionの認定を行わない。

