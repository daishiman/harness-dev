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
updated_at: "2026-11-02T03:21:23.487201Z"
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
implementation_readiness: {"checked_at": "2026-11-02T03:21:23.487201Z", "missing_sections": [], "status": "complete"}
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

元1440差分のsource保存と現行/保存先の説明、main修正保持、raw eval-log1063件と旧flyer165件の所在、C02更新5文書のfinding0・draft保持を確認する。最終のroot未commit/未追跡0件、両branch同一HEAD、両push、同名追跡先を親が実測する。dev-graphはinitの有効PASSを維持し、利用者が承認した残り8対象の未達（fresh FAIL/DEGRADEDが2、利用上限で停止2、未起動4）とCI失敗を隠さず、過去テスト写し188件のdiscovery対応は別担当に委譲する。

## 未決事項

親担当の最終commit・元root clean・両ブランチの同一HEADとpush・追跡先の実測、および別担当の過去テスト写し188件のdiscovery lint対応を集約する。CI PASSとPR mergeは実結果が得られるまで主張しない。通常taskのpromotion writer不在によるdraft保持は継続する。

## 2026年11月2日のCI実走と再開条件

前回の実走結果追加は製品影響なしだったが、今回の Codex native 経路追加は CLI・schema・実行と証跡・権限境界に製品契約の影響がある。既存 owner の正本を参照して以下の受入契約を追加し、過去の影響判断は当時の記録として保持する。

利用者の「codexで進めて」に基づき、承認済みの残8対象を明示的な `--runtime codex` で検証するため、harness-creator の live-trial 契約を追加している。省略時は既存の Claude 経路を維持し、runtime をまたいだ PASS 再利用は禁止する。旧 runtime 未記録の証跡は Claude として保持する。正本は [live-trial Skill](../plugins/harness-creator/skills/run-skill-live-trial/SKILL.md) と [Codex native 契約](../plugins/harness-creator/skills/run-skill-live-trial/references/codex-live-trial.md)、今回の受領書は [Codex native 受入受領書](../system-spec/branch-publication/codex-native-acceptance-receipt.json) とする。

今回の仕様影響は製品契約への影響あり。native `exec` / 同一 session の `exec resume`、原 rollout parser、runtime 別の schema・挙動閉包・再利用・CLI 引数を追加する。native の実際の skill 注入と成功した全文 Read を source bytes に束縛し、実 model・親子 session・終了・累積 token・実 user turn を原ログから検査する。Claude の `Skill` / `Agent` / Stop / 権限 hook と同一のイベントや同一能力とは主張しない。

複数 operation は、宣言済みの順序付き native handoff と checkpoint を controller が照合し、各操作を実 user turn で渡す。入力回数・順序を記録し、単一入力による自走や救済 nudge と区別する。最小成果物の実 path・bytes SHA・開き方・深度四択を assistant 本文で提示し、実 user turn の standard 応答前に選択記録や Agent 評価へ進めない。native hook や正規 guard consumer の未到達を、generic resume や自作 receipt で承認済みに置き換えない。

書込み権限は fresh fixture と完了マーカー用の `workdir/out` に限定する。source provider・private control/raw・公開 workdir を actor workspace の外へ分離し、workspace・tmp・source・private の境界と書込み先の交差を検査する。HOME・CODEX_HOME・auth・利用者設定を転用せず、sandbox を無効化しない。既存 Claude の schema・digest・受入規則は維持する。

前 source `8c710295`（harness-creator 1.4.56 / dev-graph 0.1.29）では C05/render と C19/system-spec の2件を起動したが、native catalog の名前は `plugin:skill` である一方、producer が `$suffix` を送ったため自動 skill 注入は0件だった。両件は正規 `--blocked` finalizer で終了し、BLOCKED・goal_fit NOT_EVALUATED、残 actor process 0。旧 freeze の137ファイルは不変であり、旧 source の失敗状態や PASS を新 source へ付け替えない。その他6対象は未起動で、C03/sync は native hook `user-hook-trust` が必須のため保留、他5対象は候補である。

次 source は harness-creator 1.4.57 を正規採番済みで、dev-graph 0.1.29 を維持する（この文書同期時点では commit 前）。qualified name 全体と source の対応表を boot 時に固定し、移設後にも対応を検査する修正、原ログの streaming read・開始時刻 window と2日分探索・有限 cache、poll elapsed の切上げ整数化を追加した。旧 collector が1278履歴を全文 read していたことは親が sample 653 と lsof で確認した。関連合同回帰は親実行で275 passed、release は23 plugin PASS。独立コード追補 review は進行中であり、この文書担当が回帰や実走を再実行した結果ではない。

新 source の実受入 PASS は0件で、CI の残8対象は未解消。次の native 試行は新しい BASEci2 の source freeze 後に行う。今回は旧2 trace の停止確定と source 修正の記録であり、8対象の合格・native hook の成立・複数 operation の単一入力自走を認定しない。

再開時も同時上限2、scenario 全観測、時間/token 予算、goal-seek 実体、原 SHA と runtime 閉包、fixture-final/freeze、別 context の fresh goal 評価を維持する。作者・runner は goal PASS を作らない。過去の C14/decompose と C02/node の fresh FAIL・最終 DEGRADED、C19/system-spec と C05/render の利用上限 BLOCKED、未起動4対象、および private relocation の照合は [以前の CI 実走受領書](../system-spec/branch-publication/ci-exhaustive-attempt-receipt.json) に不変の履歴として残す。Codex への切替で上書きしない。

現行 criteria は親の前回確認で1 passed・8 failed、CI の残8対象は未達のまま。canonical criteria receipt は今回更新せず、古い PASS を現行の合格証拠に流用しない。CI 成功・全8対象完了・commit/push・PR 完了・feature/task の承認や promotion は主張しない。

