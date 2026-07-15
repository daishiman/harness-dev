---
id: IDX0
title: spec-drift-guardian 開発計画 index (main)
plugin_meta:
  manifest:
    required: true
    path: .claude-plugin/plugin.json
    name_matches_folder: true
    no_unresolved_placeholders: true
    validate_plugin: true
  marketplace:
    default_personal: true
    policy:
      installation: NOT_AVAILABLE
      authentication: ON_USE
      category: Developer Tools
    cachebuster_for_update: true
  distribution:
    distributable: false
    bundles: []
    marketplace: false
  pkg_contract:
    applicable: false
    reason: 既存の番号付き pkg 契約体系 (harness 側 002-008 等) には属さない新規単独 plugin であり本項は非該当
  governance:
    applicable: false
    reason: 単一リポジトリ内部で完結する plugin であり別建て runbook 契約は不要。close 前の規律は C07 (guard-spec-drift-close) が hook 契約として担保する
  ci:
    workflow: governance-check
  ssot_dedup:
    applicable: true
    read_only_source: plugins/harness-creator の rubric/schema/template (通常解析/proposeはread-only・複製しない)
    notes: C02 apply modeだけがC04 audit PASSとユーザー明示承認後にallowlist対象へEdit適用できる。commit/PR/issue closeは行わない
  feedback_deploy:
    enabled: false
    reason: 本 plugin は Notion 連携を持たない (フィードバックは GitHub issue コメント/close ゲートで完結する)
  harness_eval:
    evals_json: EVALS.json
    mechanical: required
    llm_eval: required
---

# spec-drift-guardian 開発計画 index (main)

> GitHub issue #17 系の spec-drift 対応で人手依存になっている影響判定 (step2) と rubric/schema/template 更新提案 (step3) を構造化・半自動化する plugin を、人間可読な 13 フェーズのライフサイクル (本 index + phase-01..13.md) と、機械可読な buildable component 目録 (`component-inventory.json`) の 2 軸直交で計画したもの。
> ライフサイクル軸 (フェーズ) は宣言型のタスク仕様 (`specfm.PHASE_BODY_SECTIONS` の 8 節) で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない (正規化)。

## 基本定義
- **プラグイン slug**: `spec-drift-guardian` (plan_dir=`plugin-plans/spec-drift-guardian/`・同一構想は常に同一出力先=再現性アンカー)。
- **最上位目的 (purpose)**: spec-drift issue の影響判定と rubric/schema/template 更新提案を構造化・半自動化し、対応漏れ・遅延・判断ブレを減らす。
- **仕様駆動 (大前提)**: 本計画は harness-creator 仕様を基に作成される (規律の焼き先=`harness-creator-spec-reflection.md` マトリクスの引用・独自流儀の発明禁止)。要件の正本は `goal-spec.json` の checklist (C1-C6)、仕様書 (本 index + 13 phase) はその被覆であり、実装との乖離が出たら**仕様を先に更新**してから build へ戻す (spec-first)。
- **スコープ (含む)**: index + 13フェーズ + inventory + handoffのL3契約。「完全diff再構成→4軸+semantics triage→独立verdict→提案→監査→明示承認→限定apply→post-image検証→ローカルclose gate」の設計。
- **スコープ (含まない)**: 検知 (fetch/diff/issue 起票、既存 `.github/workflows/update-yaml-spec.yml` + `ref-yaml-spec-fetcher` の責務)、実プラグイン/実コードの build (L4・後段 run-skill-create / run-build-skill / plugin-scaffold へ委譲)、PR 作成・リリース対応・marketplace 登録。

## ドメイン知識
- **2 軸直交**: ライフサイクル軸 (13 phase・人間可読) と成果物実体軸 (N=11 component・機械 SSOT) を二重に持たない。
- **component_kind (5 種)**: skill / sub-agent / slash-command / hook / script。同一 kind の複数実体はそれぞれ独立 component。
- **phase ≠ component**: 13 はフェーズ数の固定値、N=11 は buildable 実体数で独立に決まる。phase は `entities_covered: [C01, ...]` の id 参照のみで component に紐づく。
- **spec-drift 対応フロー**: 既存fetch/diff/issue→history eventとcache commit pair照合(C11)→完全diff parse(C08)→4軸+semantics triage(C09/C01)→独立verdict(C03)→propose(C02)→audit(C04)→明示承認→限定apply(C02)→post-image検証(C10)→ローカルclose gate(C07)。
- **完全性境界**: `spec-diff-history.md` は80行previewでありdiff正本ではない。C11はcommit pair/digest/complete=trueを証明できなければfail-closed。
- **書き込み境界**: 通常解析/proposeはread-only。C02 applyだけがC04 PASS・明示承認・allowlist・pre-image hash一致後に書ける。proposal-onlyではclose不可。
- **記号空間の分離 (曖昧性解消注記)**: goal-spec の checklist id `C1`-`C6` (要件 id・受入観点) と component id `C01`-`C11` (buildable 実体 id) は**別の記号空間**であり混同しない (前者は 1-2 桁の要件、後者はゼロ埋め 2 桁の実体)。checklist id の改称は RTM を破壊するため行わず本注記で曖昧性を解消する。
- **C01-C11 役割表 (index 単体可読性)**:

  | id | 名称 | 役割 (1 行) |
  |---|---|---|
  | C01 | run-spec-drift-triage (skill) | 完全diffを4軸+semanticsで判定しprovenance付きreportをemit |
  | C02 | run-rubric-sync (skill) | proposeと、監査PASS+明示承認後の限定applyを二段階実行 |
  | C03 | spec-impact-verifier (sub-agent) | 生diffから独立再導出しtriage-verdictをemit |
  | C04 | rubric-sync-auditor (sub-agent) | proposalの漏れ/過剰/allowlist/hashを監査しverdictをemit |
  | C05 | /spec-drift-triage (command) | トリアージを手動起動 |
  | C06 | /rubric-sync (command) | verdict→propose→audit→承認→apply→verifyを直列起動 |
  | C07 | guard-spec-drift-close (hook) | close 前 fail-closed ゲート (PreToolUse/Bash の gh issue close 捕捉) |
  | C08 | parse-spec-diff.py (script) | diff を hunk 単位へ構造化パース |
  | C09 | map-field-impact.py (script) | hunk→artifact pathとname/type/required/enum/semanticsを写像 |
  | C10 | check-triage-complete.py (script) | 4artifact+post-imageを突合しverified stateだけclose可 |
  | C11 | aggregate-issue-diffs.py (script) | history eventからcache commit pairの完全diffを再構成 |

## インフラ
- **実行環境**: スクリプトは Python 標準ライブラリのみ (.sh/.js 新規禁止)。lint/スクリプト起動は repo-root cwd 前提、skill 資産は self-relative 参照。パスは `$PROJECT_ROOT`/`$CLAUDE_PLUGIN_ROOT`/self-relative で表現し具体値を直書きしない。
- **同梱決定論ゲート (2 層命名・機械正本=`specfm.GATE_SCRIPTS`)**: core 5 scripts / 6 invocations = verify-index-topsort (§9 section 床+phase 完全性+DAG) / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張ゲート = check-requirements-coverage / check-surface-inventory / check-build-handoff / validate-task-graph (デフォルト成果物 task-graph.json の検査) / check-runtime-portability。
- **build の始め方**: handoff routesをtop-sortし、C11→C08→C09→C01→C03/C02→C04→C10→C05/C06/C07の依存を解決する。
- **コンポーネント目録の所在**: buildable な実体 (skill×2 / sub-agent×2 / slash-command×2 / hook×1 / script×4 = 計 11) は `component-inventory.json` が唯一の SSOT。build_target・依存 DAG・quality_gates・harness_coverage・feedback_contract を目録側が保持する。
- **envelope generator gap**: manifest/marketplace を自動生成する builder が現状存在しない。本 index の `plugin_meta.manifest`/`marketplace` を契約仕様として焼き込み、`envelope-draft/plugin.json` を手動適用前提の draft として emit する (gap は `handoff-run-plugin-dev-plan.json` の `open_issues` に記録)。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required | `plugin_meta.manifest` |
  | plugin-composition | required | `plugin-composition.yaml` |
  | harness/eval | required | `EVALS.json` + `plugin_meta.harness_eval` (C5) |
  | references/config/assets | required | `plugin_meta.ssot_dedup` (harness-creator read-only 参照先 + C09 写像表 references/field-impact-map の記録) |
  | schemas | required | triage-report / triage-verdict / sync-proposal / sync-audit-verdict の4artifact契約。handoff envelope owner割当済み |
  | vendor | omitted | component inventory の omitted_reason (vendoring 不要・read-only 参照のみ) |
  | MCP/app connector | omitted | component inventory の omitted_reason (gh CLI のみで完結) |
  | notion_config | omitted | component inventory の omitted_reason (Notion 連携なし) |

## 環境ポリシー
- **品質基準**: 全 buildable component が quality_gates (p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + harness_coverage(min≥80/kind_pass) を携帯する。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する (design-gate/final-gate)。C01/C02 の出力も独立 sub-agent (C03/C04) が別 context で再検査する。
- **現状値非焼込**: 「≥80% を満たす設計」を要件化し、harness 現状未達数値は component エントリへ焼かない (Goodhart 回避)。
- **書き込み境界の遵守**: C02 apply以外はread-only。C02もC04 PASS・明示承認・allowlist・hash guardなしでは変更0件。commit/PR/issue closeは行わない。
- **エスカレーション**: ゲート未達は最大 5 周 (goal-spec.max_loops) で findings を反映し再実行、超過時は `open_issues` に残し差し戻す。

## フェーズ一覧

1. P01 — requirements (要件定義) / 未実施
2. P02 — design (設計) / 未実施
3. P03 — design-review (設計レビューゲート) / 未実施
4. P04 — test-design (テスト設計) / 未実施
5. P05 — implementation (実装) / 未実施
6. P06 — test-run (テスト実行) / 未実施
7. P07 — acceptance-criteria (受入基準判定) / 未実施
8. P08 — refactoring (リファクタリング) / 未実施
9. P09 — quality-assurance (品質保証) / 未実施
10. P10 — final-review (最終レビューゲート) / 未実施
11. P11 — evidence (エビデンス集約) / 未実施
12. P12 — documentation (ドキュメント) / 未実施
13. P13 — release (完了/PR・リリース対応は責務外) / 未実施

## 完了チェックリスト
- [ ] 基本定義 (plugin slug / purpose / スコープ) が宣言されている。
- [ ] ドメイン知識 (2軸直交 / 5種kind / 完全diff / 4軸+semantics / 書き込み境界) が宣言されている。
- [ ] インフラ (実行環境 / core scripts / 目録所在 / envelope generator gap / surface 採否) が宣言されている。
- [ ] 環境ポリシー (品質基準 / proposer≠approver / 現状値非焼込 / 承認済み限定apply) が宣言されている。
- [ ] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (`specfm.PHASE_BODY_SECTIONS` の宣言型 8 節) を満たす。
- [ ] C1: C11がhistory previewを索引にcache commit pairの全未triage完全diffをdigest/completeness付きで再構成し、C08がhunk化する。
- [ ] C2: C09/C01がartifact pathとname/type/required/enum/semanticsをbefore/after/evidence付きで判定し、C03が独立verdictをemitする。
- [ ] C3: C02がproposeと承認済み限定applyを二段階で行い、C04 audit PASS・明示承認・allowlist・pre/post hash・validatorを必須とする。
- [ ] C4: C10/C07がapplied_verifiedまたはindependently_verified_no_changeだけをclose可としproposal-onlyを拒否する。
- [ ] C5: `EVALS.json` がIssue #17完全commit pairとsettings追加/doctor/MCP matcher/hook transcript/sub-agent/semantics-only/no-impactのfixture matrixを持つ。
- [ ] C6: C05 (`/spec-drift-triage`)・C06 (`/rubric-sync`) の手動起動 command が定義され、`handoff-run-plugin-dev-plan.json` で既存責務 (`ref-yaml-spec-fetcher`/`update-yaml-spec.yml`) との非重複が明示されている。
- [ ] 各 component が >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] 同梱決定論ゲート (core + 拡張・機械正本=`specfm.GATE_SCRIPTS`) が全 exit0。
- [ ] `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で builder/build_kind/build_args/build_target を持ち、各 component を後段 builder へルーティングする。
- [ ] `elegant-verification-30.json` が30思考法を省略なく記録し、4条件が全PASSである。

## 受入確認

> 計画 (上記) が満たすのは「各 component が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった実プラグインが当初 purpose を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (run-skill-create の harness criteria-test)。purpose の正本 = `goal-spec.purpose`「spec-drift issue の影響判定と rubric/schema/template 更新提案を構造化・半自動化し対応漏れ・遅延・判断ブレを減らす」。

| 受入観点 (purpose/checklist 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| C1: 完全diffがhunk化される | Issue #17 commit pairのdigest/completenessが一致し、truncated preview/missing commitはfail-closed | C11+C08 |
| C2: 4軸+semanticsが独立検証される | name/type/required/enum/semanticsの正解セットをC03が生diffから再導出し一致する | C09+C01+C03 |
| C3: 監査・承認後だけ限定適用される | 未承認系は差分0件、承認caseはallowlist対象だけ適用されpost hash/validator一致 | C02+C04+C06 |
| C4: verified stateだけcloseできる | proposal-only/不一致/未適用をC10/C07が拒否し、applied_verified/no-changeだけ許可 | C10+C07 |
| C5: Issue #17全カテゴリで測定される | 完全fixture matrixに対するprecision/recallとapply/close caseがthreshold以上 | EVALS+C01/C02 |
| C6: 手動起動 command が既存責務と重複しない | `/spec-drift-triage`・`/rubric-sync` の起動が fetch/diff/issue 起票を再実行しないことを `handoff-run-plugin-dev-plan.json` の記述で確認 | C05/C06 の description + handoff |

build 後、各 component の `feedback_contract.criteria` が criteria-test として実行され、上表の受入が PASS して初めて「purpose を満たすプラグインが出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入が評価系に配線されていることを宣言する。
