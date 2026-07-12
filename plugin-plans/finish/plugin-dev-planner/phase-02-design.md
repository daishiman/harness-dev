---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
5 種の component_kind を検討したうえで C1-C3 の変更対象を単一の既存 skill component (C01=run-plugin-dev-plan, mode=update) へ収束させ、各残債の具体的な機械検証ロジックの置き場所を確定する。特に C3 (harness-coverage 12 軸自己適用) の配線先を、両候補を現物比較したうえで確定する。加えて層A (C6-C9)・層B (C10-C12) の機械層/意味層の具体的な設計 (denylist 語彙集合・一致判定厳密度・埋め込み形式・適用強度分類) を確定し、C8/C12 の意味評価を担う既存 assign-plugin-plan-evaluator skill を C02 として inventory へ追加する根拠を固める。

## 背景
P01 で固定した goal-spec の 3 残債は、いずれも「新しい判断面・新しい操作面・新しい書き込み時不変条件」を追加するものではなく、既存の決定論ゲート (check-runtime-portability.py / check-build-handoff.py) の検査範囲を狭く拡張する改修である。この性質が component_kind 選定 (sub-agent/slash-command/hook を不要と判断する根拠) と builder 選定 (既存 skill の build へ Edit として畳む) の両方を決定づける。層A/層B の追加指示についても同じ判断軸を適用するが、C8/C12 (意味層の genuine 判定) は C01 とは別の物理 skill 実体 (assign-plugin-plan-evaluator) の責務拡張であるため、component_kind 選定の帰結が C1-C3 とは異なる (単一 skill 収束ではなく 2 skill component 収束になる)。

## 前提条件
- P01 の goal-spec.json (C1-C12・constraints・open_questions 込み) が確定している。
- `references/component-domain.md` (5 kind 写像規約 + script 畳み込み no-split threshold) と `references/plugin-creator-contract.md` (envelope 物理契約) を参照できる。
- 対象の現状コード (check-runtime-portability.py 188 行・check-build-handoff.py 395 行・governance-check.yml の plugin-dev-planner conformance block・scripts/validate-harness-coverage.py・plugins/harness-creator/scripts/compute-dogfooding-metrics.py・specfm.py の `_PHASE_SECTION_HINT`/`render_minimal_phase`) を Read 済みで、それぞれの現状の欠落点を把握している。
- `assign-plugin-plan-evaluator` の `prompts/R1-evaluate.md`・`schemas/plan-findings.schema.json`・`tests/test_evaluate_plan.py`・`tests/test_gate_parity.py`・`references/resource-map.yaml` を Read 済みで、conditions (C1-C4) が additionalProperties:false + required 固定であり変更しない設計であることを把握している。

## ドメイン知識
- **component_kind 選定根拠 (5 種全検討・C1-C5 範囲)**: sub-agent は不要 (独立文脈での新規判断面が無く、計画全体の最終評価は既存 plugin-dev-plan-evaluator agent が既に担っている)。slash-command は不要 (ユーザー向け新規操作面を追加しない・既存 /plugin-dev-plan 導線で足りる)。hook は不要 (書き込み時に強制すべき新しい不変条件を持たない・既存 PostToolUse hook の検査対象拡張ではない)。script の独立 component 昇格は不要 (no-split threshold のいずれも満たさない・詳細は component-inventory.json の derivation)。この範囲では buildable 実体は C01 (skill, mode=update) の 1 件のみに収束する。
- **C1 の設計**: check-runtime-portability.py は現状 `run(plan_dir, inventory_path)` が既に plan_dir を受け取っている (`check-runtime-portability.py <PLAN_DIR>` の 1 引数起動)。target_plugin_slug は新規 CLI 引数を追加せず、`<plan_dir>/goal-spec.json` から間接的に読む (`_target_plugin_slug(plan_dir)` ヘルパーを新設し、ファイル不在/キー欠落時は None を返し既存呼び出し元との後方互換を保つ)。`check_inventory(data, target_plugin_slug=None)` へシグネチャを拡張し、target_plugin_slug が非 None のときのみ (R) build_target の `plugins/<slug>/...` セグメントと target_plugin_slug の不一致を検出する新チェックを追加する (既存の (P) 共有 script hoist 検証・(Q) 自己完結検証とは独立した第 3 の検査)。
- **C2 の設計**: check-build-handoff.py の `_check_manifest_draft(path, target_plugin_slug, prefix)` は現状 name 一致と TODO placeholder のみを検査し、entry_points と inventory component 集合の突合を持たない。新規ヘルパー `_load_inventory_components(plan_dir)` (既存 `_check_inventory_provenance` とは意図的に独立実装し、既存関数への副作用リスクを避ける) と `_check_manifest_entry_points_coverage(entry_points, comps, prefix)` を追加する。突合対象は component_kind ∈ {skill, sub-agent, slash-command} のみ (`ENTRY_POINT_KEY_BY_KIND = {"skill": "skills", "sub-agent": "agents", "slash-command": "commands"}`)。hook/script は plugin.json の entry_points に現れない構造のため対象外とする。`_check_manifest_draft()` のシグネチャに `comps`引数を追加し、`_check_envelope()` から component-inventory.json 読み込み結果を渡す。
- **C3 の設計 (配線先の確定)**: open_questions で保留されていた配線先を、両候補の現物比較により確定する。
  - **候補 A: scripts/validate-harness-coverage.py への roster/filter 追加**。この script は `_real_dirs(PLUGINS_DIR)` でリポジトリ全 plugin を無条件横断する共有ダッシュボードで、per-plugin filter や roster の仕組みを意図的に持たない。plugin-dev-planner はこの無条件走査に既に暗黙的に含まれているため、この script 自体の改修は影響範囲がリポジトリ全体に及び、F8 (install-portability・plugin 内自己完結) の制約にも反する。既存 CI 配線は `--self-test` (fixture 内部ロジックテスト) のみで `--gate`/`--ratchet` の実データ実行は未配線であり、これを新設する変更は本 goal のスコープ (plugin-dev-planner 自身の残債解消) を超える。
  - **候補 B: governance-check.yml の既存 plugin-dev-planner conformance block への 1 ステップ追加**。この block には既に同種の dogfooding 検証 (validate-frontmatter/lint-skill-name/lint-skill-description/lint-skill-completeness/live-surface-audit) が 5 ステップ配線済みで、`test_ci_integration.py` の `test_governance_check_has_plugin_dev_planner_conformance` がその存在を固定する先例パターン (文字列存在チェック + subprocess 実行による green 実証) を持つ。harness-creator の `compute-dogfooding-metrics.py` (plugin 自身が `--plugin-root` 引数付きの自己測定 script を内部に持ち、結果を EVALS.json へ upsert する設計) が同型の先例となる。
  - **確定**: 候補 B を採用する。新規 script `scripts/check-harness-coverage-selfcheck.py` を run-plugin-dev-plan skill 内部 (plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/) に自己完結させ、`scripts/validate-harness-coverage.py --json` (既存共有インフラ) を subprocess で呼び出してレポートを取得し、plugin-dev-planner の行のみを抽出して 6 種別 × mechanical/llm_eval = 12 軸のうち EVALS.json.threshold_note の哲学 (現状値非焼込み・存在検証のみ) と矛盾しない形で構造的カバレッジ (各軸が測定/宣言されているか) を検証する。governance-check.yml の既存 block へこの script の呼び出しを 1 ステップ追記する (repo-level 編集のため plugins/ 外・component 化せず handoff.open_issues に gap として起票する)。`test_ci_integration.py` へ新規テスト関数を追加し、追記されたステップの存在を固定する。
- **C6/C7 の設計 (denylist 語彙集合・一致判定厳密度)**: 新規 script `scripts/check-generative-fidelity.py` を C01 の scripts/ 配下に追加する (単一 skill scope・no-split threshold 未達のため独立 component 化しない)。**denylist 語彙集合**: 「適切に」「しっかり」「うまく」「品質を高める」「なるべく」「できるだけ」「効果的に」「柔軟に」「十分に」「必要に応じて」の 10 語 (判定不能な効果性・程度のみを主張し観測可能な基準を伴わない語彙。将来拡張は `references/ambiguous-vocabulary-denylist.md` へ切り出しコード変更なしで追加可能にする)。走査対象は phase 本文の宣言型 8 節と inventory component の goal/checklist/criterion 文字列。**一致判定は部分文字列一致 (substring match)** を採用する (理由: 日本語は分かち書きされず厳密なトークン境界一致は困難。denylist の各語は単独で確定的な意味を持つ熟語であり、他語彙への偶発的部分一致リスクは低い)。ただし denylist 定義そのもの、コード/定数名、`満たさない例` の否定例本文は自己説明・fixture 説明として `ignored_context` に分類し、violation にはしない。C7 は `_PHASE_SECTION_HINT` (specfm.py の 8 節分フォールバック辞書) と生成された phase 本文の対応節本文を**完全一致 (前後空白 strip 後の exact string equality)** で比較する (部分一致にしない理由: フォールバック文言は完結文であり、節全体が一字一句同一になるのは未カスタマイズの場合のみであるため、完全一致が Goodhart 耐性を最大化する)。両者とも検出結果は WARN/FAIL の構造化結果 (該当箇所・該当語/該当節・ignored_context 件数を含む) として出力し、意味の正否 (具体性が真に課題解決に資するか) の最終判定は行わない (C8 へ委譲)。
- **C8/C12 の設計 (意味層・findings 記録)**: 新規 script は追加しない。既存 `assign-plugin-plan-evaluator/prompts/R1-evaluate.md` の既存 step 4 パターン (「C1 と C2-004 を LLM 意味判定し、必要なら high finding を追加」) を踏襲し、C8 (phase 本文の下流実行着手可能な具体度) と C12 (C10/C11 受入例・事前解決済み判断の実効性) の新規意味判定ステップを追加する。`plan-findings.schema.json` の `conditions` は additionalProperties:false + required:["C1","C2","C3","C4"] 固定であり (`test_evaluate_plan.py` がこの集合を固定アサーション)、C8/C12 は conditions を増やさず `findings[].bucket` (自由文字列・enum 制約なし) の新規 bucket として記録する。`plan-rubric.json` の `semantic_checks` (既存 S1/S2 と同型) へ新規エントリ (runner: llm-only) を追加する設計とし、`deterministic_gates`/`conditions` 自体は変更しない (`test_gate_parity.py` の 9 parity テストに影響しない設計)。
- **C10/C11 の設計 (埋め込み形式・適用強度分類)**: 埋め込み形式は golden example (`examples/sample-plan/phase-05-implementation.md`) の `## 完了チェックリスト` を拡張する形とし、新設 9 節目は追加しない (`specfm.PHASE_BODY_SECTIONS` SSOT を変更しない軽量な設計選択)。具体的には `## 完了チェックリスト` 直下に `### 受入例 (満たす例 / 満たさない例)` と `### 事前解決済み判断` のサブ見出しを設ける。新規 script `scripts/check-downstream-harness.py` (C01 の scripts/ 配下・単一 skill scope) がこの 2 サブ見出しの存在を機械検出する。**適用強度分類**: goal-spec の open_questions が名指しした「成果物より判定行為が中心の phase」を P03 (design-gate)・P07 (acceptance-criteria)・P09 (qa)・P10 (final-gate) の 4 phase と確定し、これらは縮小要件 (判定行為そのものが受入例的性質を持つため簡略形で可) とする。残り 9 phase (P01/P02/P04/P05/P06/P08/P11/P12/P13) はフル要件とする。
- **C02 追加の設計判断**: C8/C12 は既存の assign-plugin-plan-evaluator skill (物理ディレクトリが C01 と別) の責務拡張であるため、「同一 component_kind の複数実体はそれぞれ独立 component」の原則により C02 として inventory へ追加する。C02 は skill_kind=assign であり、io-contract.md §11 の条件表に従い feedback_contract.criteria (B1) と goal_seek は skill_kind∈{run,wrap,delegate} 限定のため N/A (skip_reason で明示)、prompt_layer:7layer は skill_kind∈{run,assign} 限定のため必須、combinators は全 skill 必須のため空配列で明示する。depends_on:[C01] とする (C02 が C01 の生成物である phase 本文を評価対象とするため)。
- **C02 自己更新の bootstrap-trust**: C02 (assign-plugin-plan-evaluator) 自身の build/改訂時、その評価ロジック (R1-evaluate.md) の改変品質を「改変前の evaluator 自身」に見させると自己言及的循環になる懸念がある。本設計はこれを、proposer≠approver の環境ポリシーを C02 の build にもそのまま適用すること (改変差分は独立した approver = run-elegant-review 系の別 context レビューが担い、改変版 evaluator 自身を承認者にしない) と、C02.boundary が定める加算的限定 (conditions C1-C4 の意味を変えない findings[] 新規 bucket 追加に限る) の 2 点で解消する。本 plan における C02 の評価実行 (P07/P10 等の fork evaluator 実行) はいずれも未改変版 R1-evaluate.md によるものであり、bootstrap 循環は発生しない。

## 成果物
- `component-inventory.json` (C01/C02 の 2 skill component + 5 kind 検討証跡 + plugin_level_surfaces 採否)。
- `envelope-draft/plugin.json` (既存 plugin.json を Read した現状値ベースの整合ドラフト。entry_points に run-plugin-dev-plan/assign-plugin-plan-evaluator 両方が既存のため変更不要)。
- 本ファイルに記録した C1/C2/C3/C6/C7/C8/C10/C11/C12 の設計判断 (特に C3 の配線先確定・C6/C7 の denylist 語彙集合と一致判定厳密度・C10/C11 の埋め込み形式と適用強度分類・C02 追加根拠)。

## スコープ外
- 設計の合否判定 (P03 design-gate へ委譲・自己承認しない)。
- 受入 criteria の導出 (P04 へ委譲)。
- 実コードの生成 (P05・実 `plugins/` へは書かない。本 plan は L3 計画であり L4 build を実行しない)。
- 曖昧語彙 denylist の意味的正否判定・受入例の実効性判定 (機械層に留め、意味層は C8/C12 = assign-plugin-plan-evaluator の genuine 判定に委ねる)。

## 完了チェックリスト
- [ ] C01/C02 component が build_target 非空・builder/build_kind 整合・depends_on 非循環 (C02→[C01]) で inventory に載っている。
- [ ] considered_component_kinds が 5 種全列挙され、sub-agent/slash-command/hook/script (独立昇格) が不要である根拠が derivation に明示されている。
- [ ] C3 の配線先 (governance-check.yml block への追記 + 新規 self-check script) が候補 A との比較根拠込みで確定している。
- [ ] `envelope-draft/plugin.json` が既存 plugin.json の entry_points/hooks/depends_on と整合し TODO placeholder を含まない。
- [ ] C6/C7 の denylist 語彙集合 (10 語) と一致判定厳密度 (部分一致/完全一致) が明示されている。
- [ ] C6 の自己説明・否定例が violation にならない ignored_context 境界が明示されている。
- [ ] C10/C11 の埋め込み形式 (完了チェックリスト直下のサブ見出し) と適用強度分類 (P03/P07/P09/P10 縮小・他 9 phase フル) が明示されている。
- [ ] C8/C12 の意味層設計 (findings 新規 bucket・conditions/schema 構造不変) が明示されている。
- [ ] C02 自己改訂時の bootstrap-trust (改変版 evaluator でなく独立 approver = run-elegant-review 系が評価する設計) が明示されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: C01/C02 の 2 component が inventory に load-bearing フィールド (build_target/builder/build_kind/depends_on/quality_gates/harness_coverage) を漏れなく携帯し、C3 配線先確定と C6/C7/C10/C11 の設計判断がいずれも本ファイルに具体的根拠込みで記録されている。
- 満たさない例: component 分解が C01 の 1 件のみに留まり C8/C12 の意味層拡張先 (C02) が inventory に反映されていない、または denylist 語彙集合や適用強度分類が「後で決める」のまま未確定である。

### 事前解決済み判断
- 分岐点: C6/C7 の新規 script を C01 と C02 のどちらへ畳み込むか → 判断: C01 (run-plugin-dev-plan・生成時に実行する検出ロジックのため、生成主体である C01 の scripts/ に配置する)。
- 分岐点: C10/C11 を新設 9 節目にするか既存 `## 完了チェックリスト` 拡張にするか → 判断: 既存節の拡張 (specfm.PHASE_BODY_SECTIONS という SSOT の変更を避け、既存 8 節契約を壊さない軽量な設計)。

## 参照情報
- `references/component-domain.md` / `references/phase-lifecycle.md` / `references/plugin-creator-contract.md` / `references/io-contract.md` §11。
- 対象 component C01/C02 (`component-inventory.json`)。
- 比較対象: `scripts/validate-harness-coverage.py` / `.github/workflows/governance-check.yml` / `plugins/harness-creator/scripts/compute-dogfooding-metrics.py` / `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/tests/test_ci_integration.py`。
- `assign-plugin-plan-evaluator/prompts/R1-evaluate.md` / `schemas/plan-findings.schema.json` / `tests/test_evaluate_plan.py` / `tests/test_gate_parity.py`。
- golden example: `examples/sample-plan/phase-05-implementation.md`。
- 後続 P03 (design-review)。
