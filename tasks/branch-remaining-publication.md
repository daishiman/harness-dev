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
updated_at: "2026-11-02T03:21:23.487201Z"
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
implementation_readiness: {"checked_at": "2026-11-02T03:21:23.487201Z", "missing_sections": [], "status": "complete"}
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

[全件台帳](../docs/branch-publication/manifest.json) と [元worktree統合記録](../docs/branch-publication/worktree-integration.json) のsource SHA・元path・統合先を照合する。対象別の最小回帰、C02 preview/apply/C11、ファイルSHA、最終のroot statusとlocal/remote HEAD・追跡先を別々に記録する。initの有効PASSと、承認済み残り8対象（新実走2対象はfresh FAIL/DEGRADED、利用上限で停止2対象、未起動4対象）の未達およびCI失敗を分離して記録し、全30思考法は再走しない。

## リスクとロールバック

旧flyerのentrypointを現行1.3.2へ混在させず、旧版はraw保存とsource commitで辿れるようにする。他者の変更を撤回しない。公開後の修正は追加commit/revertで履歴を残す。古いreceiptや過去テストのSHAを現在版のPASSへ書き換えない。

## Handoff

親へC02 revision/immutable receipt/artifact SHAを渡す。最終commit・両branchのHEAD一致・両push・同名追跡先・root cleanの実測は親が統合記録へ追記する。本taskのdraft保持と既存harness-86khの追跡、未取得承認・promotion・CI PASSを作らない条件を維持する。

## 2026年11月2日のCI実走と再開条件

再開条件は新 source の独立コード追補 review と BASEci2 source freeze、新 source に対する8対象の実受入である。旧2件の BLOCKED と未起動6対象を分け、C03/sync は native hook user-hook-trust と正規 guard consumer の確認まで保留する。実走・採番・Beads・Git・PR は親の担当とし、この文書更新では実行しない。

利用者の「codexで進めて」に基づき、承認済みの残8対象を明示的な `--runtime codex` で検証するため、harness-creator の live-trial 契約を追加している。省略時は既存の Claude 経路を維持し、runtime をまたいだ PASS 再利用は禁止する。旧 runtime 未記録の証跡は Claude として保持する。正本は [live-trial Skill](../plugins/harness-creator/skills/run-skill-live-trial/SKILL.md) と [Codex native 契約](../plugins/harness-creator/skills/run-skill-live-trial/references/codex-live-trial.md)、今回の受領書は [Codex native 受入受領書](../system-spec/branch-publication/codex-native-acceptance-receipt.json) とする。

今回の仕様影響は製品契約への影響あり。native `exec` / 同一 session の `exec resume`、原 rollout parser、runtime 別の schema・挙動閉包・再利用・CLI 引数を追加する。native の実際の skill 注入と成功した全文 Read を source bytes に束縛し、実 model・親子 session・終了・累積 token・実 user turn を原ログから検査する。Claude の `Skill` / `Agent` / Stop / 権限 hook と同一のイベントや同一能力とは主張しない。

複数 operation は、宣言済みの順序付き native handoff と checkpoint を controller が照合し、各操作を実 user turn で渡す。入力回数・順序を記録し、単一入力による自走や救済 nudge と区別する。最小成果物の実 path・bytes SHA・開き方・深度四択を assistant 本文で提示し、実 user turn の standard 応答前に選択記録や Agent 評価へ進めない。native hook や正規 guard consumer の未到達を、generic resume や自作 receipt で承認済みに置き換えない。

書込み権限は fresh fixture と完了マーカー用の `workdir/out` に限定する。source provider・private control/raw・公開 workdir を actor workspace の外へ分離し、workspace・tmp・source・private の境界と書込み先の交差を検査する。HOME・CODEX_HOME・auth・利用者設定を転用せず、sandbox を無効化しない。既存 Claude の schema・digest・受入規則は維持する。

前 source `8c710295`（harness-creator 1.4.56 / dev-graph 0.1.29）では C05/render と C19/system-spec の2件を起動したが、native catalog の名前は `plugin:skill` である一方、producer が `$suffix` を送ったため自動 skill 注入は0件だった。両件は正規 `--blocked` finalizer で終了し、BLOCKED・goal_fit NOT_EVALUATED、残 actor process 0。旧 freeze の137ファイルは不変であり、旧 source の失敗状態や PASS を新 source へ付け替えない。その他6対象は未起動で、C03/sync は native hook `user-hook-trust` が必須のため保留、他5対象は候補である。

次 source は harness-creator 1.4.57 を正規採番済みで、dev-graph 0.1.29 を維持する（この文書同期時点では commit 前）。qualified name 全体と source の対応表を boot 時に固定し、移設後にも対応を検査する修正、原ログの streaming read・開始時刻 window と2日分探索・有限 cache、poll elapsed の切上げ整数化を追加した。旧 collector が1278履歴を全文 read していたことは親が sample 653 と lsof で確認した。関連合同回帰は親実行で275 passed、release は23 plugin PASS。独立コード追補 review は進行中であり、この文書担当が回帰や実走を再実行した結果ではない。

新 source の実受入 PASS は0件で、CI の残8対象は未解消。次の native 試行は新しい BASEci2 の source freeze 後に行う。今回は旧2 trace の停止確定と source 修正の記録であり、8対象の合格・native hook の成立・複数 operation の単一入力自走を認定しない。

再開時も同時上限2、scenario 全観測、時間/token 予算、goal-seek 実体、原 SHA と runtime 閉包、fixture-final/freeze、別 context の fresh goal 評価を維持する。作者・runner は goal PASS を作らない。過去の C14/decompose と C02/node の fresh FAIL・最終 DEGRADED、C19/system-spec と C05/render の利用上限 BLOCKED、未起動4対象、および private relocation の照合は [以前の CI 実走受領書](../system-spec/branch-publication/ci-exhaustive-attempt-receipt.json) に不変の履歴として残す。Codex への切替で上書きしない。

現行 criteria は親の前回確認で1 passed・8 failed、CI の残8対象は未達のまま。canonical criteria receipt は今回更新せず、古い PASS を現行の合格証拠に流用しない。CI 成功・全8対象完了・commit/push・PR 完了・feature/task の承認や promotion は主張しない。

