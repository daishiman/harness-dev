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
updated_at: "2026-11-02T03:21:23.487201Z"
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
implementation_readiness: {"checked_at": "2026-11-02T03:21:23.487201Z", "missing_sections": [], "status": "complete"}
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

feature の目的・受入・macro field は保持し、現在の実走契約と未達状態だけを更新する。draft / evaluation pending / tracker none を維持し、13計画生成や promotion へ進めない。

利用者の「codexで進めて」に基づき、承認済みの残8対象を明示的な `--runtime codex` で検証するため、harness-creator の live-trial 契約を追加している。省略時は既存の Claude 経路を維持し、runtime をまたいだ PASS 再利用は禁止する。旧 runtime 未記録の証跡は Claude として保持する。正本は [live-trial Skill](../plugins/harness-creator/skills/run-skill-live-trial/SKILL.md) と [Codex native 契約](../plugins/harness-creator/skills/run-skill-live-trial/references/codex-live-trial.md)、今回の受領書は [Codex native 受入受領書](../system-spec/branch-publication/codex-native-acceptance-receipt.json) とする。

今回の仕様影響は製品契約への影響あり。native `exec` / 同一 session の `exec resume`、原 rollout parser、runtime 別の schema・挙動閉包・再利用・CLI 引数を追加する。native の実際の skill 注入と成功した全文 Read を source bytes に束縛し、実 model・親子 session・終了・累積 token・実 user turn を原ログから検査する。Claude の `Skill` / `Agent` / Stop / 権限 hook と同一のイベントや同一能力とは主張しない。

複数 operation は、宣言済みの順序付き native handoff と checkpoint を controller が照合し、各操作を実 user turn で渡す。入力回数・順序を記録し、単一入力による自走や救済 nudge と区別する。最小成果物の実 path・bytes SHA・開き方・深度四択を assistant 本文で提示し、実 user turn の standard 応答前に選択記録や Agent 評価へ進めない。native hook や正規 guard consumer の未到達を、generic resume や自作 receipt で承認済みに置き換えない。

書込み権限は fresh fixture と完了マーカー用の `workdir/out` に限定する。source provider・private control/raw・公開 workdir を actor workspace の外へ分離し、workspace・tmp・source・private の境界と書込み先の交差を検査する。HOME・CODEX_HOME・auth・利用者設定を転用せず、sandbox を無効化しない。既存 Claude の schema・digest・受入規則は維持する。

前 source `8c710295`（harness-creator 1.4.56 / dev-graph 0.1.29）では C05/render と C19/system-spec の2件を起動したが、native catalog の名前は `plugin:skill` である一方、producer が `$suffix` を送ったため自動 skill 注入は0件だった。両件は正規 `--blocked` finalizer で終了し、BLOCKED・goal_fit NOT_EVALUATED、残 actor process 0。旧 freeze の137ファイルは不変であり、旧 source の失敗状態や PASS を新 source へ付け替えない。その他6対象は未起動で、C03/sync は native hook `user-hook-trust` が必須のため保留、他5対象は候補である。

次 source は harness-creator 1.4.57 を正規採番済みで、dev-graph 0.1.29 を維持する（この文書同期時点では commit 前）。qualified name 全体と source の対応表を boot 時に固定し、移設後にも対応を検査する修正、原ログの streaming read・開始時刻 window と2日分探索・有限 cache、poll elapsed の切上げ整数化を追加した。旧 collector が1278履歴を全文 read していたことは親が sample 653 と lsof で確認した。関連合同回帰は親実行で275 passed、release は23 plugin PASS。独立コード追補 review は進行中であり、この文書担当が回帰や実走を再実行した結果ではない。

新 source の実受入 PASS は0件で、CI の残8対象は未解消。次の native 試行は新しい BASEci2 の source freeze 後に行う。今回は旧2 trace の停止確定と source 修正の記録であり、8対象の合格・native hook の成立・複数 operation の単一入力自走を認定しない。

再開時も同時上限2、scenario 全観測、時間/token 予算、goal-seek 実体、原 SHA と runtime 閉包、fixture-final/freeze、別 context の fresh goal 評価を維持する。作者・runner は goal PASS を作らない。過去の C14/decompose と C02/node の fresh FAIL・最終 DEGRADED、C19/system-spec と C05/render の利用上限 BLOCKED、未起動4対象、および private relocation の照合は [以前の CI 実走受領書](../system-spec/branch-publication/ci-exhaustive-attempt-receipt.json) に不変の履歴として残す。Codex への切替で上書きしない。

現行 criteria は親の前回確認で1 passed・8 failed、CI の残8対象は未達のまま。canonical criteria receipt は今回更新せず、古い PASS を現行の合格証拠に流用しない。CI 成功・全8対象完了・commit/push・PR 完了・feature/task の承認や promotion は主張しない。

