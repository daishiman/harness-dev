---
graph_node_id: "spec-branch-publication"
artifact_kind: "specification"
artifact_subtypes: []
title: "元ブランチ全残存の統合と保存の仕様"
project_id: "harness"
domain: "delivery"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["branch-publication", "source-preservation", "existing-contracts"]
file_path: "specs/branch-publication.md"
template_id: "specification"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-01T21:51:01.228579Z"
updated_at: "2026-11-02T04:02:36.456667Z"
depends_on: []
related_nodes: ["task-branch-remaining-publication"]
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
classification_reason: "元ブランチ全残存の統合を、既存責務契約への参照と実パスの対応で記録する正規specification。"
classification_candidates: [{"artifact_kind": "specification", "candidate_path": "specs/branch-publication.md", "confidence": 0.99}, {"artifact_kind": "document", "candidate_path": "docs/branch-publication.md", "confidence": 0.01}]
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

# 目的と成功状態

元rootに残っていた全1440差分そのものを元ブランチ上でcommitし、最新mainと既存PRの修正を統合した履歴をPR #87へ公開する。成功条件は元差分の対応先不明0件に加え、元rootの未commit/未追跡0件、元ブランチとPRブランチの同一HEAD・両push・同名追跡先の確認である。[全件台帳](../docs/branch-publication/manifest.json)、[統合記録](../docs/branch-publication/worktree-integration.json)、[タスク](../tasks/branch-remaining-publication.md) を参照する。

## スコープ

元HEAD 8c1eb6c8の先行11変更と元rootの1440 status entriesを対象にする。source commit d71ac0a6に元path全体を保存し、元ブランチでmain 76abc53dとレビュー済みPR 86adf784を統合する。raw eval-log1063件は元pathを保持し、flyer旧追加165件はdocs/branch-publication/source-files/plugins/flyer-studio/へraw保存する。既存のdev-graph/UBM/composition/SBB/guideの製品責務は変更せず、新HTTP・DB・認証基盤・13計画は追加しない。

## 用語と主体

C02はgraphと正規文書の単一writer、C14はmacro feature契約の宣言者、C28はBeads投影、C16はready推薦を所有する。既存Beads harness-86khのscope拡張を実行追跡とし、新しいdraft taskや本資料を起票済み・承認済みとは扱わない。

## ユースケースとユーザーフロー

元1440差分をsource commitへ記録する。元ブランチへ最新mainと既存PRを順に取り込み、mainの新修正を保持して競合を解消する。原pathの証跡と旧flyer raw保存先を照合し、正規文書を更新して最小検証を集約する。最後に元rootの変更をcommitしてcleanにし、PRブランチを同じHEADへ揃えて両方pushし、追跡先を確認する。実施済みと未実施は [統合記録](../docs/branch-publication/worktree-integration.json) で区別する。

## 機能要件

- dev-graphのmaterialize・confirm-feature・link-beads・planned_featuresは [C02](../plugins/dev-graph/skills/run-dev-graph-node/SKILL.md) と [C16](../plugins/dev-graph/skills/run-dev-graph-schedule/SKILL.md) の契約を正本とする。parity生成規則は [execution-tracker §10](../plugins/dev-graph/references/execution-tracker-contract.md) の単一builderを維持する。
- UBMの3チェックシートとCodexのskills領域限定許可は [journal](../plugins/ubm-goal-setting/skills/run-ubm-journal/SKILL.md) と [書込guard](../plugins/ubm-goal-setting/hooks/ubm-write-path-guard.py) に従う。
- JSON compositionは [lint](../plugins/skill-governance-lint/scripts/lint-plugin-composition.py) と [release writer](../scripts/build-plugin-release.py) の既存入口で扱う。
- SBBの番号クリックは [book生成](../plugins/system-briefing-book/scripts/build-briefing-book.mjs) と [座標取得](../plugins/system-briefing-book/scripts/render-board-png.mjs) の契約に従う。

## 非機能要件

元rootを変更しないという旧制約は撤回し、元ブランチでのcommit・統合・clean化を必須にする。他者の変更とmainの新修正を戻さず、元bytesはsource commitとraw/ZIP保存から辿れるようにする。Gitのclean・branchの同一HEAD・push・CI・mergeを互いの代替証拠にしない。

## UI・状態遷移

SBBは文中の番号と画像上の測定済み枠から対応画面・説明へ移動する。リンク先がない番号、自己参照、検査後に変わったボードの古い枠は既存生成器の規則で扱う。本資料とfeatureはdraft/pendingのまま、文書骨格のreadiness completeだけで実装着手・tracker投影へ昇格しない。

## ビジネスルールと検証

flyer-studioの現行1.3.2へ旧1.3.1のentrypointやmanifestを混在させない。旧追加165ファイルはraw保存、元path全体はsource commitで保持し、従来の素材42・verification85・development-plan25を含む362ファイルの保存証拠も残す。元1440件の対応付けだけでroot cleanやpush済みを推測しない。

## API契約

N/A: 新規または変更する公開HTTP endpointはない。影響する内部CLI・JSON receipt・構成入力は上の正本リンクと [影響受領書](../system-spec/branch-publication/spec-impact-receipt.json) へ接続し、この文書で引数やschemaを二重定義しない。

## データモデル

新DB・新製品データモデルはない。source commitは元pathとbytes、raw eval-logは元path、旧flyerはsource-files配下、manifest/worktree-integrationは元pathと統合先の対応を保持する。C02 graphとimmutable receiptは既存形式を使い、以前のreceiptのSHAを新内容へ置換せずfollowupを追記する。

## 認証・認可

新しい認証機構はない。ユーザーのgs明示は元rootを含むscopeとcommit/pushの作業指示の根拠であり、未取得のguard承認receiptやtask promotionの証拠を作るものではない。本資料登録はdraftを維持し、実行追跡は既存harness-86khに集約する。

## エラー・例外・回復

C02 previewとapplyのrevisionがずれればCAS拒否から再previewする。normal taskのpromotion writer不在はdraftを手編集で昇格させず既存harness-86khで追跡する。parityのstaleはcanonical builderで再生成しdigestだけを書き換えない。元版保存はmainのファイルを旧版へ置換する回復策にしない。

## イベント・非同期処理

新しいqueueやschedulerは作らない。PR merge後の完了収束は [GitHub lifecycle契約](../plugins/dev-graph/references/github-lifecycle-contract.md) のC26→C02 consumerへ委譲する。PR close未mergeやfeature/dirty worktreeをdoneにしない。本登録ではlifecycleや外部投影を起動しない。

## 可観測性

[全件台帳](../docs/branch-publication/manifest.json) と [統合記録](../docs/branch-publication/worktree-integration.json) にsource commit、元pathのSHA、統合先、競合解消、raw保存、最終branch/remote/追跡先/root statusの結果を記録する。C02 receiptは本scope修正のrevisionとartifact SHAを記録する。当時のtask契約評価は当時SHAのdesign評価として保持し、今回のscope修正やCI PASSへ流用しない。

## 互換性・移行・リリース

既存製品仕様を変えず、元rootをPRから除外していた古い作業scopeを更新する。元source commit d71ac0a6とmain/PRの統合履歴を保持し、現行runtimeの巻き戻しを避ける。最終commit後は元/PR両ブランチを同一HEADへ進めて両方pushし、元ブランチの追跡先を同名origin branchへ変更する。版採番は今回の文書変更では行わない。

## テストと受入条件

元1440差分のsource保存と現行/保存先の説明、main修正保持、raw eval-log1063件と旧flyer165件の所在、C02更新5文書のfinding0・draft保持を確認する。最終のroot未commit/未追跡0件、両branch同一HEAD、両push、同名追跡先を親が実測する。旧init PASSと残8対象の結果は当時の履歴として保持する。共有SGA変更後の現行受入には全9対象の再実走が必要であり、新PASS0件・CI未達を明記する。過去テスト写し188件のdiscovery対応は別担当の既存記録を参照する。

## 未決事項

親担当の最終commit・元root clean・両ブランチの同一HEADとpush・追跡先の実測、および別担当の過去テスト写し188件のdiscovery lint対応を集約する。CI PASSとPR mergeは実結果が得られるまで主張しない。通常taskのpromotion writer不在によるdraft保持は継続する。

## 2026年11月2日のCI実走と再開条件

明示runtime producerとtyped外部gateは製品契約に影響する。共有SGA変更後の受入はinitを含む全9対象に必要である。

利用者の「codexで進めて」に基づき、明示 `--runtime codex` の実受入を進める。省略時のClaude経路を保持し、runtime間のPASS再利用や原JSONLのClaude形式への変換はしない。正本は [live-trial Skill](../plugins/harness-creator/skills/run-skill-live-trial/SKILL.md)、[Codex native契約](../plugins/harness-creator/skills/run-skill-live-trial/references/codex-live-trial.md)、[外部変更guard契約](../plugins/skill-governance-adapters/references/external-mutation-guard-contract.md)。今回の影響と検証は [Codex native受入受領書](../system-spec/branch-publication/codex-native-acceptance-receipt.json) に追記する。

製品契約への追加影響あり。SGAの `hook-confirm` / `pretool` は信頼済みhook commandの `--runtime claude|codex` を受け、既定Claudeを保持する。確認・intent receiptのproducerを署名前にruntimeから選び、Codexは `codex-user-prompt-submit`、Claudeは既存値とする。payloadの自己申告をruntimeに使わず、生成後のreceipt・署名を書き換えない。Codexが実際に渡すcanonical `Bash` / `tool_input.command` と既存deny形式を利用し、架空のBash/UserPromptSubmitを注入しない。HCのtyped外部gate接続は実装・独立確認中で、深度選択とは別の契約として扱う。

正規 `build-artifact-delivery` writerによる23 pluginのprojection更新は共有runnerのSHA同期だけであり、他plugin全体への新機能・権限追加とは区別する。SGAの動作検査33件成功・projection検査1件成功は親担当の報告で、この文書担当が再実行した結果やnative hook実走の成功ではない。最終版番号・release整合・source SHAは採番とfreeze待ちとし、途中の値を確定値へ付け替えない。

共有SGA実装は全9対象のruntime閉包に含まれるため、今回の変更で旧init PASSも現行sourceの合格根拠ではなくなる。必要な新受入はinitを含む全9対象へ更新する。C01のCodex scenarioは旧args・required observations・時間/token予算を逐語保持し、native IDを付けた正本を親が追加済み。旧criteriaの1 passed・8 failedは当時のsourceの実測として保持し、新sourceでも同じ結果だったとは主張しない。canonical criteria receiptは未更新である。

旧source `8c710295` のC05/renderとC19/system-specはnamespace不一致によりnative skill注入0件、正規BLOCKED・goal_fit NOT_EVALUATED・残process 0の履歴を保持する。旧freezeの137ファイル、revision9/10のimmutable receipt、過去のClaude FAIL/DEGRADED/利用上限BLOCKEDと [以前の実走受領書](../system-spec/branch-publication/ci-exhaustive-attempt-receipt.json) の原SHAを書き換えない。続く旧 `43a` sourceのBASEci2はC19 fixture準備のみ・actor起動0件で、private原固定を保持する。これらを新sourceの実走やPASSに数えない。

C03/syncは、最終command/sourceをレビュー可能にしてから隔離fixtureの2handlerに限るnative `/hooks` の信頼許可を1回確認する予定で、現在は未提示・未承認。logging wrapperを含む最終定義を固定し、実native UserPromptSubmitと正規guard consumerの到達まで保留する。trust hash・確認receipt・署名を自作せず、generic resumeを外部変更の承認へ読み替えない。fake-ghによるfixture内の変更だけを許し、実GitHub/Beads/Projectsへの接続・一般trust/sandbox bypass・他ユーザー設定の変更を行わない。

新sourceの実受入PASSは0件、CIは未達である。新しい `/private/tmp/harness-codex-ci3-20261102` の試行は最終freeze後に行う。最大同時2と元の反復上限・予算を守り、全scenario、goal-seek実体、原SHA/runtime閉包、fixture-final/freeze、別contextのfresh goalを確認する。成果物の本文提示→実user選択→独立Agentの順と、typed native handoffの回数・順序を記録する。source/private control/raw/公開workdirはactor workspace外とし、書込先はfixtureと完了マーカー用outだけ。Claude固有のSkill/Agent/Stop/権限hookの成立や単一入力での無対話自走と同一視せず、旧PASSのSHA付替え、CI成功・全9対象完了・最終commit/push/PR完了・新promotionの認定を行わない。

