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
updated_at: "2026-11-02T05:20:06.808023Z"
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
implementation_readiness: {"checked_at": "2026-11-02T05:20:06.808023Z", "missing_sections": [], "status": "complete"}
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

最新main26cc8692はローカルmain経由で統合済みで、6競合を解消したmerge commit9d981850を両branchへ公開し、GitHubのMERGEABLEを確認した。上流cache/historyの原bytesと今回runtime対応を両方保持している。

現行業務sourceに対する初期化・描画・構想分解・状態照会の4試行はfresh独立goalと共通verdictでPASS。C01/C05/C14/C18のcanonical受入testも計4件PASS。描画の判定CLIが4番目の証拠指定を漏らした記録は旧DEGRADEDのまま保持し、同じ実行の全原bytes/SID/token/clock/sourceを残した別judgmentで回収指定だけ訂正した。追加actor起動0であり、新実走を装わない。

source照合は、controllerのstate SHAに束縛した対応表の正確なprovider正本pathとproject aliasを、同namespace・現repo本文SHA・実Readと突合する。private元実体が残る場合の本文改変も拒否し、suffix一致では受理しない。native58件と現物C05受入を確認した。harness-creatorは1.4.60へ正規採番した。

scheduleの既存read-only契約に反してlistがlockをwrite-openしていた不具合を修復した。既存lockをread-onlyで開き共有lockで2ledgerを取得し、context/listでディレクトリや空ファイルを作らない。mutation側の排他lockは維持し、部分store/破損/読取中変更を拒否する。18製品検査と、旧fixtureを同native sandboxで参照する非LLM smokeが成功、旧109entryは全状態不変。変更される被験閉包はschedule/syncだけで、他7対象と既存成功は不変。dev-graphは0.1.31へ正規採番した。

残る再試行はC19の成果物全件提示、nodeの元5Mtoken予算内でのfresh独立監査、requirementsの準備担当所有lockの正規release後入力、scheduleの修復済み参照処理である。元観測・引数・予算を省略/拡張せず、新run/newFXで実施し旧FAIL/BLOCKED/DEGRADEDと原freezeは保持する。C03は同じfixtureと2hookへの信頼許可が質問済み・未回答で、勝手に信頼を有効化しない。最大同時2、原source/goal-seek/実transcript/独立goalを維持し、全CI成功はまだ未確認。

