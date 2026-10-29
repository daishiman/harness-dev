<!--
正本: system-dev-planner (生成器) 側テンプレート。
template_version: 1.2.0
`plugin-plans/dev-graph/templates/system-task-spec.md` (draft) は現状独立ファイルであり、
P08/P12 で本正本への pointer 化予定。それまでフィールド名・節構成は非後退とし
draft の既存参照を壊さない。P08 で正本化・P12 で最終確定 (goal-spec C5)。
-->

# System task overlay: <task title>

## Machine-readable registration fields

- feature_package_id: <feature-package/<stable-id>; 13 taskで共有>
- owners / tags / related_nodes: <values or empty arrays>
- parent_feature: <起動元 dev-graph feature ノードの graph_node_id。自動起動はfeature文脈から、手動起動は解決済みfeature参照から充填し、1 runが生む全task specで共有する>
- phase_ref: <P01..P13。1 package内で各値ちょうど1件>
- classification: <confidence + reason + task candidate paths>
- tracker_binding_intent: <auto|beads|github|none; execution_tracker.mode=both では auto 禁止>
- github_publication: <mode + project_aliases + labels + milestone>
- pr_completion_policy: <linked_pr_merged_all|linked_pr_merged_any>
- branch_policy: <one-task-one-branch + worktree lease required + default-branch reconciliation + assignment_owner=dev-graph-scheduler>

## 目的

<単一責務の実装完了時に成立するシステム状態。task.mdの全必須sectionも併用する>

## 背景

<system-spec/architecture/phase docの根拠ノードとユーザー価値>

## 前提条件

- Required spec/architecture/phase/task nodes: <graph_node_id>
- Entry gate: <machine-verifiable condition>
- P01 upstream entry gate: <P01は `parent_feature.depends_on all done|closed`。P02..P13は `N/A: intra-feature depends_on gate`>
- Source pin: system-spec-harness v0.1.0 / run-system-spec-compile / assign-system-spec-completeness-evaluator
- Repository context: <repo_identity + root_resolution_source + .dev-graph/config.json; absolute path禁止>

## Workstream applicability

- Frontend: <applicable + change | N/A: reason>
- Backend: <applicable + change | N/A: reason>
- API: <applicable + contract | N/A: reason>
- Data: <applicable + migration | N/A: reason>
- Infrastructure: <applicable + IaC/deploy | N/A: reason>
- Security: <applicable + control | N/A: reason>
- Quality: <applicable + tests/gates | N/A: reason>
- Documentation: <applicable + docs | N/A: reason>
- Operations: <applicable + runbook/monitoring | N/A: reason>

## Architecture and deploy unit

- Architecture decisions: <graph_node_id>
- Deploy unit/environment: <unit or N/A: reason>
- Compatibility/migration/backfill: <contract or N/A: reason>

## 成果物

- Produced artifacts: <paths and graph nodes>
- Consumed artifacts: <paths and graph nodes>
- Write scope/touches: <paths>

## Tracker publication and completion

> 本specは`tracker_binding_intent`とGitHub公開intentだけを宣言し、永続bindingの解決・起票・完了収束はdev-graphが所有する。`auto`はrepo-configで解決するが、`execution_tracker.mode=both`では曖昧なため禁止する。Beads束縛時のGitHub viewer mirrorは`bd github sync --push-only`だけをauthorityとし、gh-bridgeによる二重起票とProjects custom-field同期を行わない。

- Tracker binding intent: <auto|beads|github|none>
- Publication mode: <local_only|issue|issue_and_projects>
- Project aliases / labels / milestone: <values or N/A: reason>
- PR completion policy: <linked_pr_merged_all|linked_pr_merged_any>
- PR body contract: <Closes #issue + dev-graph graph_node_id; default branch target>
- Ownership boundary: <system-dev-planner declares intent; dev-graph performs mutations/reconciliation>

## Branch and worktree execution

- Branch: <assigned after dev-graph registration by C15 as devgraph/<graph_node_id>; system-dev-planner does not preassign>
- Worktree lease: <claim graph_node_id before implementation; heartbeat/release>
- Parallel safety: <depends_on complete + resource_scope and active lease do not overlap>
- Completion projection: <feature branch records pending event only; clean default branch writes durable done>

## スコープ外

- <explicit non-goal>

## テスト戦略

> 4 項目はこの順序・このラベルで固定する。契約 version が `1.2.0` 以上に解決される package では
> 本 section の欠落・順序入替・空本文を `validate-system-plan.py` (C12) が fail-closed で拒否する。
> 契約 version は package の canonical digest から `assets/validation-contract-baseline.json` を
> 引いて決まり、未登録 digest は最新契約へ倒れる。`1.1.0` 以前で登録された legacy 世代でも、
> 本 section を書いた場合は同じ厳格さで検査される。

- テストレベル選定: <単体・結合・境界値・回帰の4レベルすべてに言及し、当該taskでの適用可否を示す。適用外は `N/A: reason` で明示する>
- カバレッジ目標: <既定80%を数値で明示。層別に上書きする場合は上書き値と理由を併記する>
- 層別方針: <`Workstream applicability` で applicable な層の方針。フロント=behaviorベース / バックエンド=API 契約+ロジック単体+DB 結合 / インフラ=IaC 静的検証+smoke。該当層が無い場合は `N/A: reason`>
- 保守性制約: <pixel位置依存とDOM構造依存を禁止する旨、および実装詳細へ密結合した過剰テストを作らない線引き>

## Verification and evidence

- Automated commands: <commands>
- Required evidence: <paths>

`Automated commands` は promotion 後 (content-addressed generation へ atomic rename された後) も
そのまま再実行できる形だけを書く。`--repo-root . --staging .` のように repository root 起点で
解決できない形と、generation id の直書き (再計画で stale になる) は禁止する。plan validator の
再実行は世代非依存の `validate-system-plan.py --repo-root <root> --feature-package <feature_package_id>`
を使う (`references/feature-execution-package-contract.md` §2.3)。`<feature_package_id>` は自 package の
値であること。契約 version が `1.3.0` 以上に解決される package では、`--staging` の使用・
`--feature-package` の欠落・他 package の id を `validate-system-plan.py` (C12) が fail-closed で
拒否する。検査対象は fenced block と inline code span が提示するコマンドだけで、散文中の
script 名への言及は対象外。

## Inner goal-seek execution loop

- Methodology contract: `system-task-goal-seek/v1`
- Goal: <このtask単体で達成する検証可能な状態>
- Generic execution prompt: <実装手段を固定せず、目的・背景・制約・成果物を渡すprompt>
- Rubric: <PASS条件を列挙。最低限、受け入れ条件・カバレッジ閾値 green・既存テストの回帰 0 件・証跡・scopeを含む>
- Feedback loop: <実装→独立評価→findingをpromptへ反映→再実行し、rubric verdict=PASSまで反復。上限到達時はfail-closed>
- P13 spec/architecture writeback: <P13はrequired: execution results, decisions, and improvement findingsをsystem specとarchitectureへ反映。P01..P12はN/A: P13 owns writeback>

## Rollout and rollback

- Rollout: <steps/flags>
- Rollback trigger and steps: <contract>

## Handoff

- Executor: <system build route>
- Ready when: <confirmed + evaluation pass + readiness complete + promoted digest + dev-graph registration complete>

## 参照情報

- System specification: <system-spec-harness output node>
- Architecture: <system-spec-harness output node>
- Feature: <起動元 dev-graph feature ノードの graph_node_id (parent_feature)。architecture_refs 先は system-spec-harness 引用のlineage参照であり本節のArchitectureと重複記載しない>
- Phase doc: <system-phase-spec node>
- Dependencies: <task graph node>

## task-spec validation (正本追記)

- runtime outputは本テンプレートを使う実行task spec 13件だけで構成し、別の13 lifecycle文書や14件目のcanonical taskを生成しない。正本=`references/feature-execution-package-contract.md`。
- 上記全 section が placeholder (`<...>`) のまま残っていないこと。
- 標準15 section (最低限 `Machine-readable registration fields`/`前提条件`/`成果物`/`Tracker publication and completion`/`Branch and worktree execution`/`Verification and evidence`/`Inner goal-seek execution loop`/`Handoff` の8 sectionを含む) は必須充足とし、空・重複・TODO・未解決 `<...>` を禁止する。1件でも残る場合、`validate-system-plan.py` (system-dev-planner C12) が promotion 前に fail-closed で拒否する。C08 は upstream の confirmed system-spec と completeness evaluation を検査し、task spec 本文の検査は C12 が所有する。
- `テスト戦略` は 16 番目の section であり、適用は package の canonical digest から解決される契約 version で段階化する (解決正本: `assets/validation-contract-baseline.json`)。`1.2.0` 以上に解決される package (= 台帳未登録の現行世代) では 13 件すべてに必須で、欠落・重複・空本文・4 項目の欠落/順序入替/空本文・必須語 (4レベル語・`80%`・`pixel`・`DOM`) の欠落・applicable な層の方針欠落を C12 が非0終了で拒否する。`1.1.0` 以前で台帳登録済みの legacy 世代では section の**不在だけ**を許し、書かれている場合は同じ厳格さで検査する (strict-if-present)。既存 promoted 世代の再検証結果は変わらない。
- `Workstream applicability` は該当しない workstream を `N/A: reason` で明示し、空欄のまま省略しない (適用外の理由を機械可読に残す)。
- 全pathはcaller repository相対でC09 containment済みであること。`/absolute`、drive-letter、`..`、root外symlinkはincomplete。
- task spec本文かruntime時に読むgoal/manifest/validator/evidenceはpackage-relative pathまたはcanonical published pathで参照する。C11のatomic rename後に消滅する`.dev-graph/staging`参照は禁止し、C12がpromotion前にfail-closedで拒否する。
- 同じ理由で、本文が提示する`validate-system-plan.py`再実行コマンドは`--staging`ではなく自packageの`--feature-package <feature_package_id>`を使う。契約`1.3.0`以上に解決されるpackageではC12が`task-spec-rerun-staging-path`/`task-spec-rerun-package-missing`/`task-spec-rerun-package-mismatch`で拒否する。
- P01は`parent_feature.depends_on all done|closed`を機械判定可能なentry gateとして明記する。upstream feature IDはtask `depends_on`へ複製せず、schedulerがcanonical parent featureの現行edgeを都度評価する。
- staging/evaluator/published digestが一致しC11 promotion receiptが存在するまでL4 handoffを出さない。
