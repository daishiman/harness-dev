---
name: run-skill-iter-improve
description: 既存skillの品質を実走eval駆動で反復改善したいとき、run-skill-live-trialの受け入れFAILやgoal-proxy乖離を改善に引き継ぐときに、PASS詐欺・context汚染・評価縮退を構造的に防ぐeval帰属改善ループとして起動する。
disable-model-invocation: false
user-invocable: true
argument-hint: "<plugin>/<skill> <task-args> [--goal \"真のgoalを1文\"] [--n N] [--max-iter M] [--threshold T]"
arguments: [target, task_args, goal, parallel_agents, max_iter, threshold]
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash(python3 *)
  - Bash(git diff *)
  - Skill
  - Agent
kind: run
prefix: run
effect: local-artifact
goal_seek:
  activation_state: semantic_evaluator_started
  engine: task-graph
  engine_profile: checklist-graph
  full_task_spec_graph: false
  progress: eval-log/{{plugin}}/{{skill}}/iter-improve/{{run_id}}/progress.json
  intermediate: eval-log/{{plugin}}/{{skill}}/iter-improve/{{run_id}}/intermediate.jsonl
  fork: agent-team
owner: team-platform
since: 2026-07-02
version: 0.1.0
role_suffix: orchestrator
source: plugins/harness-creator/ROADMAP.md
source-tier: internal
last-audited: 2026-07-02
audit-trigger: quarterly
schema_refs:
  - schemas/interrogation-log.schema.json
  - ../run-goal-elicit/schemas/goal-spec.schema.json
script_refs:
  - scripts/extract-ready-set-from-checklist.py
  - scripts/build-self-reflection-entry.py
  - scripts/extract-capability-dependency-graph.py
  - scripts/build-capability-graph-knowledge-entry.py
  - ../run-build-skill/scripts/plan-verification-obligations.py
  - ../run-build-skill/scripts/record-verification-evidence.py
  - ../run-skill-live-trial/scripts/plan-live-trials.py
reference_refs:
  - references/goal-declaration.md
  - ../run-elegant-review/references/convergence-policy.json
  - ../run-build-skill/references/goal-seek-paradigm.md
  - ../run-build-skill/references/verification-obligation-protocol.md
  - ../run-build-skill/references/content-review-protocol.md
  - ../run-build-skill/references/feedback-loop-deployment.md
  - ../../references/orchestrate-gate-pattern.md
completeness_exempt:
  - "prompts: ゴールシーク形 orchestrator。手順は局面カタログから都度選択し、fan-out agent prompt 核は fresh-context 前提宣言が本体のため本文に 1 個だけ持つ。prompt-creator の R-id 単位 7 層プロンプトは適用外 (run-goal-seek と同型の skip)。"
  - "manifest: 局面はゴールシークループで都度選択するため phase/gate 固定の workflow-manifest は適用外 (run-goal-seek と同型)。"
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 毎 iter の審問ログが schemas/interrogation-log.schema.json を通過し score 急変または評価経路接触の iter は independent_check.required true かつ verdict 非 null で記録される
      verify_by: script
      derived_from: [CL-2, CL-4]
    - id: IN2
      loop_scope: inner
      text: 各 iter の改善投入件数が convergence-policy loop_bounds.iter_improve.batch_per_iter_max 以下で commit は全て eval 集計取得後に 1 commit 1 ロジックで行われる
      verify_by: script
      derived_from: [CL-3, CL-5]
    - id: IN3
      loop_scope: inner
      text: 各 iter の evaluator 起動前に current contract があれば exact obligation fingerprint と current PASS receipt を機械計画し contract 不在時は reuse 0として全件未解決へ倒し新規判定は同じ fingerprint へ記録して reuse 対象では Agent を起動しない
      verify_by: verification-obligation
      derived_from: [CL-10]
    - id: OUT1
      loop_scope: outer
      text: 収束停止前に GOAL VERIFICATION が current observational receipt または新規の実走成果物と行動ログ実体だけを根拠に PASS を返し静的レビューを行動 claim の収束根拠に一切含めない
      verify_by: live-trial
      derived_from: [CL-6]
    - id: OUT2
      loop_scope: outer
      text: 審問独立判定 agent と fresh GOAL VERIFICATION agent を同じ iter で起動する場合は別個体かつ履歴非共有で score と改善履歴を渡されずに判定する
      verify_by: evaluator
      derived_from: [CL-4, CL-6]
artifact_delivery:
  contract: artifact-delivery-v1
  state_machine:
    initial: artifact_created
    states: [artifact_created, minimal_guard_passed, artifact_presented, user_choice_recorded, semantic_evaluator_started, handoff_complete]
    transitions:
      - {from: artifact_created, event: minimum_guard_pass, to: minimal_guard_passed}
      - {from: minimal_guard_passed, event: present_actual_artifact, to: artifact_presented}
      - {from: artifact_presented, event: record_user_choice, to: user_choice_recorded}
      - {from: user_choice_recorded, event: accept-as-is, to: handoff_complete}
      - {from: user_choice_recorded, event: "light|standard|detailed", to: semantic_evaluator_started}
      - {from: semantic_evaluator_started, event: improvement_complete, to: handoff_complete}
    pre_choice_forbidden: [semantic-evaluator, task-fork, subagent, multi-worker, revise-loop]
    accept_contexts: {evaluator: 0, improver: 0}
  release: explicit-only
  exhaustive: explicit-only
---

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# run-skill-iter-improve

> **配布注記**: cross-skill refs (`../run-goal-elicit/`, `../run-build-skill/`, `../run-elegant-review/`) は repo-bundled 前提 (単独配布非対応)。本 skill と `run-skill-live-trial` は実行 acceptance 系として**ローカル開発環境限定**であり、量産先 plugin へは配備しない (正本: `../run-build-skill/references/feedback-loop-deployment.md` の配備境界)。CI でも実行しない。

## Purpose & Output Contract

target skill の品質を「current proof の機械再利用判定 → 未解決分だけ fresh-context 並列実走 eval → 弱点 diagnose + PASS 詐欺審問 → skill 層を少数件 Edit → commit → GOAL VERIFICATION」で反復改善する **eval 帰属のメタ改善ループ** (skill が skill を改善する)。

score を上げる方法は 2 つある — generator (成果物を作る側) を本当に良くするか、evaluator を緩めて score を通すか。後者の方が速く score が上がるので、規律が無いと必ずそちらへ流れる (Goodhart の法則)。本 skill は skill 改善ループで起きやすいこの事故を 8 INVARIANTS で構造的に防ぐ。**INVARIANTS を破る改善ループは、score がいくら上がっても失敗である。**

- **入力**: target (`<plugin>/<skill>`) + task args + `--goal` (goal 正本へのエイリアス、後述) + ループパラメータ (既定値の正本は後述 `loop_bounds.iter_improve`) + 任意の current build handoff (`verification contract` / `evidence dir` / `stage`。不在は未解決扱いであり再利用扱いにしない)
- **出力**:
  - 改善 commit 群 — 1 commit 1 ロジック、`wrap-git-commit-safe` 経由
  - `eval-log/<plugin>/<skill>/iter-improve/<run-id>/interrogation-log.jsonl` — 毎 iter の PASS 詐欺自己審問ログ (`schemas/interrogation-log.schema.json` 準拠の**必須 artifact**)
  - 同 run dir の `<date>-score.jsonl` — 既存の `**/*-score.jsonl` 合流規約 (run-skill-rubric-governance の aggregate-evals.py が収集)。採点行は evaluator id / mode / rubric hash / 前提を携帯する。**独自 sink 新設禁止**
  - 同 run dir の `intermediate.jsonl` — obligation id / fingerprint / `reuse|observe|adjudicate` / evidence path を各 iter の task-graph trace と同じ行へ記録。証拠再利用専用の別 sink は作らない
  - GOAL VERIFICATION 判定 (PASS|FAIL + blocker 列挙) + iter summary (score 推移 / goal 達成度推移 / 破棄した改善案 / 最終 score がどの mode・rubric・前提で出たかの明記)
- **起動導線 (正規経路)**: `run-skill-live-trial` の受け入れ verdict FAIL、または goal 達成度と score の乖離 ⚠️ からの handoff を受けて起動する。plateau 突破を狙う単独起動も可。issue 更新 / close / push は呼び元責務
- **Codex 配布の再同期**: 改善対象がClaude plugin envelope配下なら、収束後に `run-codex-plugin-package <plugin>` の冪等upsertを実行し `--all --check` exit 0 を完了条件に追加する。

## 境界 (どの改善はどの機構か)

| 改善の性質 | 担当 | 規律 |
|---|---|---|
| 1 回のレビューの findings 一括改善 (eval 非帰属) | `run-elegant-review` Phase 3 (`elegant-improvement-executor`) | severity high 放置 0・DAG 全件消化 |
| **実走 eval 帰属の反復改善** | **本 skill** | **1 iter 少数件 (INVARIANT 5) で効果帰属を保つ** |
| artifact (生成物 1 個) の改善 | 量産 skill 側の feedback_contract 評価ループ | 本 skill の対象は skill 層 (SKILL.md / writer-prompt / scripts / schema) そのもの |
| evaluator 自体の盲点 | 本 skill の target を当該 evaluator skill に切替 | 「緩める」でなく「goal に寄せて作り直す」 |

eval 帰属反復と一括改善の 2 エンジンは編集エンジン・収束判定を共有しない (相互参照: `agents/elegant-improvement-executor.md`「適用層境界」)。

## ゴールシーク実行

固定手順は書かず、ゴール+チェックリストへ向け局面を都度選択・反復する。正本: `../run-build-skill/references/goal-seek-paradigm.md`。

### ゴール (Goal)

target skill が `goal-spec.json.goal` を実走で達成する状態に改善され、その過程の全 iter が審問ログ・score jsonl・commit として eval-log に帰属記録され、収束宣言が GOAL VERIFICATION (実走成果物ベース・PASS|FAIL+blocker) で独立確認されている。

### 目的・背景 (Why)

artifact 単体の改善は LLM 主観評価 ±3-5pt のブレに律速され plateau に張り付く。skill 層の構造改善 (prompt rules / script logic / schema 制約) だけが plateau を破り、並列衝突・orchestrator stall 等の実 bug を E2E で発見できる。だが skill 改善ループは generator でなく **evaluator から腐る** — INVARIANTS はこの構造事故への防御である。

### 完了チェックリスト (Checklist)

- [ ] iter 0 GOAL DECLARATION 完了 (goal 正本読取 / proxy 妥当性審問 Yes|No+根拠 / forbidden_loosening 宣言。手順: `references/goal-declaration.md`) <!-- CL-1 -->
- [ ] 毎 iter の審問ログが `interrogation-log.jsonl` へ 1 行 append され `schemas/interrogation-log.schema.json` を通過する <!-- CL-2 -->
- [ ] 各 iter の改善投入件数が `loop_bounds.iter_improve.batch_per_iter_max` 以下 <!-- CL-3 -->
- [ ] score 急変または評価経路接触の iter は別個体 fresh agent の独立判定 verdict が記録済 (発火条件は同 schema の allOf が機械強制) <!-- CL-4 -->
- [ ] commit は全て eval 集計後・1 commit 1 ロジック (`wrap-git-commit-safe` 経由) <!-- CL-5 -->
- [ ] 収束宣言前に GOAL VERIFICATION を実施し PASS、または max_iter 到達時に「score X / goal FAIL / 残 blocker」を隠さず報告した <!-- CL-6 -->
- [ ] 全 artifact が `eval-log/<plugin>/<skill>/iter-improve/<run-id>/` に保存済 (score は `*-score.jsonl` 合流規約) <!-- CL-7 -->
- [ ] Claude plugin envelope配下なら `sync-plugin-platforms.py --all --check` が exit 0 <!-- CL-8 -->
- [ ] plugin公開面・Codex代替・依存を変更した場合、repo rootで `python3 plugins/harness-creator/scripts/audit-capability-parity.py --repo-root . --all` と `python3 plugins/skill-governance-lint/scripts/lint-plugin-composition.py plugins/*/plugin-composition.yaml` がともに exit 0。静的契約PASSをinstall/enabled/trust/new-session/runtime実証と混同しない <!-- CL-9 -->
- [ ] 各 iter の Agent 起動前に verification obligation を計画し、current PASS receipt は再利用、入力 slice / checker・scenario 契約 / 上流 proof が変わった claim と未解決 claim だけを再評価し、新規 evidence を同じ fingerprint へ記録した。`intermediate.jsonl` に action と evidence path がある <!-- CL-10 -->

### ゴールシークループ

正本 6 ステップ (現状評価→手順生成→実行→検証→Anchor Step→反復) に従い、下記**局面カタログ**から未達チェックリスト項目を埋める局面を都度選ぶ。ループパラメータ (反復上限 / iter あたり投入件数 / 並列 agent 数 / score 閾値) の生値は本文に書かず、`../run-elegant-review/references/convergence-policy.json` の `loop_bounds.iter_improve` (`max_iter` / `batch_per_iter_max` / `parallel_agents_default` / `score_threshold_default`) を唯一の正本とする (二重宣言禁止)。

### ゴールシーク配線（task-graph 変種）

`semantic_evaluator_started` 後、iter 0 は `GOAL DECLARATION → proof plan → unresolved eval → 集計+審問 → edit → 独立判定 → commit → GOAL VERIFICATION`、後続 iter は GOAL DECLARATION を再生成せず `proof plan` から始める checklist として同 run dir の `progress.json` へ保持する。実際の進行は `depends_on` が全て done の item に限定し、別状態は作らない。

- 各周回冒頭で `scripts/extract-ready-set-from-checklist.py <run-dir>/progress.json` を実行し、ready 集合の最小 id だけを選ぶ。unresolved eval item は tier を保ち、`live` は `run-skill-live-trial` の `live_batches`、`fork` は Agent Team、`static` は決定論 check へ送る。fork は未解決 obligation 数と N の小さい方だけを並列実行し、個別 run dir のみを write scope として全結果の fan-in 後に done にする。reuse だけなら Agent 0 体で evidence path を記録して done にする。edit / commit は単一 writer で直列実行する。
- GOAL VERIFICATION FAIL かつ正本の max_iter 未満の場合だけ、`scripts/build-self-reflection-entry.py` で次 iter chain を直前 verification 依存の sink として追記する。独立判定不要時も「発火条件非該当」証跡を残して done にし、依存を飛ばさない。追記 item を全て done にするまで self-reflect 完了 gate を閉じる。
- `<run-dir>/intermediate.jsonl` の各周回に `ready_set` / `selected_item` / `original_goal` / `merged_directive_for_next` と obligation の `fingerprint` / `action` / `evidence_path` を追記する。`selected_item` は `ready_set` 最小 id、その依存は過去に全て done であることを検証し、トレース不在を依存順消費や proof 再利用の成功に畳まない。
- アンカー検証は `required_keys` と `original_goal_hash` を読み、`hashlib.sha256` で不変性を確認する。着手前に `scripts/extract-capability-dependency-graph.py` を実行し、再利用価値のある依存判断だけを `scripts/build-capability-graph-knowledge-entry.py` で dependency graph knowledge へ記録する。

## 8 INVARIANTS (破ったら即停止・巻き戻し)

| # | 不変条件 | 実体 |
|---|---|---|
| 1 | PASS 詐欺禁止 | 本文 (下記) |
| 2 | context 汚染回避 | 正本: `goal-seek-paradigm.md`「コンテキスト分離」節。改善の正否は改善履歴を知らない fresh-context agent にのみ判定させ、orchestrator の「良くなった」体感を証拠にしない |
| 3 | goal ≠ proxy | 正本: `goal-seek-paradigm.md`「達成判定 (GOAL VERIFICATION)」節。goal アンカー正本は `goal-spec.json.goal` / `original_goal` 単一系、`--goal` は正規化書込/読取エイリアス (二重宣言禁止) |
| 4 | 構造改善 > 対症療法 | 本文 (下記) |
| 5 | 1 iter 少数件 | 本文 (下記) |
| 6 | eval-driven commit | 正本: `run-elegant-review`「副作用境界 / ロールバック (B7)」+ `wrap-git-commit-safe`。commit は eval data 取得後のみ、speculative な先回りは regression の温床 |
| 7 | 自己適用安全 | 正本: `scripts/feedback_contract_ssot.py` の `requires_subject_copy` 述語。エンジン閉包 (`ENGINE_SKILLS`) と交差する時のみ被験体を scratch copy して編集し、通常 skill は直接編集を維持 |
| 8 | 評価縮退禁止 | 本文 (下記) |

2 / 3 / 6 / 7 は正本の**再実装禁止** — 本表の 1 行相互参照のみを持つ。

### INVARIANT 1: PASS 詐欺禁止

score を上げる手段に「evaluator を緩める / 採点 mode を易しく倒す / threshold を下げる / 採点対象を goal から外す / 評価方法を差し替える」が含まれたら、それは改善でなく詐欺。手段 (target ファイル編集 / spec・入力編集 / 引数 / 環境変数 / 評価手順の差し替え) を問わず**効果**で判定する。構造防御は 3 点:

1. **iter 0 で緩め禁止リスト宣言** — `references/goal-declaration.md` の手順で goal-spec の `forbidden_loosening[]` へ格納する。一般形は convergence-policy の `anti_patterns` が正本 (target 固有の具体形のみ宣言、再掲禁止)
2. **毎 iter 自己審問** — 改善案ごとに「generator を良くするか / 評価を緩めるか」を Yes/No + 根拠で `interrogation-log.jsonl` に記録する (schema 準拠。**保存は必須成果物** — 記録の無い iter は INVARIANT 1 違反とみなす)
3. **score 急変は別個体独立判定** — 急変閾値と発火条件 (評価経路接触を含む) は `schemas/interrogation-log.schema.json` の allOf が機械正本。独立判定が「緩め (loosening)」なら自己審問より外部判定を優先して破棄する

### INVARIANT 4: 構造改善 > 対症療法

弱点を観測したら「1 入力固有か / 複数 sample で再現するか」を必ず判定する。複数 sample で再現した弱点を入力側で手直しするのは敗北 — skill 層 (SKILL.md / writer-prompt / scripts / schema 制約) に safety net を入れる。1 箇所の skill 改修が全入力に波及する改善だけが plateau を破る。

### INVARIANT 5: 1 iter 少数件 (eval 帰属の境界宣言)

1 iter の改善投入は `loop_bounds.iter_improve.batch_per_iter_max` 件以下。一括投入は消化不良で後退する (実証根拠: 一括投入時に平均 88→72)。この上限は **eval 帰属** (どの編集がどの score 変化を起こしたか) を保つためのものであり、eval 非帰属のレビュー一括改善 (elegant-review Phase 3 の DAG 全件消化) とは適用層が異なる (境界の相互参照: `agents/elegant-improvement-executor.md`「適用層境界」)。

### INVARIANT 8: 評価縮退禁止 (Gate D 限定スコープ)

「実走が重い」を理由に実評価を SKILL.md 静的レビューへ置換するのは evaluator 緩和と同型の PASS 詐欺 (INVARIANT 1 の特殊形)。本 INVARIANT の輸入スコープは behavioral claim (自走完遂 / goal 達成などの実挙動) 限定で、design claim (設計 adequacy) は従来通り content-review / elegant-review / rubric が正本 — Gate 帰属は `../../references/orchestrate-gate-pattern.md`「Gate D」を参照。

- **収束判定への寄与重み: 実走の行動ログ / 成果物 = 100%、静的レビュー = 0%**。静的レビューは弱点の当たり付け専用で、収束 PASS|FAIL の根拠に 1 文字も使わない (「補助として薄く添える」グレー運用も禁止)
- **自己適用時も縮退禁止**: 二重メタが重い場合は被験体を軽量 target で 1-fold だけ実走してよいが、**対照群 (エンジン版に同一シナリオを実走) 必須**。INVARIANT 発火の有無は行動差分でのみ客観判定でき、対照無し単発実走の自己申告は違反
- 軽量実走の合否も orchestrator が自己判定せず、GOAL VERIFICATION 契約 (独立 fresh agent + PASS|FAIL + blocker 列挙) で独立判定する

## 局面カタログ (順序固定でない。未達項目を埋める局面を都度選ぶ)

### 局面: GOAL DECLARATION (iter 0、必須経由)

`references/goal-declaration.md` の 3 ステップ (goal 正本読取 / proxy 妥当性審問 Yes|No+根拠 / 緩め禁止リスト宣言→goal-spec 拡張 field 格納)。これを飛ばしたループは INVARIANT 3 違反。

### 局面: proof plan (毎 iter、Agent 起動前)

差分再評価・証拠再利用の正本は `../run-build-skill/references/verification-obligation-protocol.md`。claim / 対象 input slice digest / checker または scenario 契約 / upstream fingerprint が同じ current PASS receipt だけを `reuse` し、どれかが変わった claim と未解決 claim だけを `observe|adjudicate` へ送る。`changed_paths[]` や「影響なし」という自然文自己申告で省略しない。

- design claim は current content-review receipt だけを再利用できる。legacy `{elegance,rubric}-verdict.json` の SHA 一致だけは高速 pre-filter であり、再利用の十分条件にしない (`content-review-protocol.md`)。
- behavioral claim は `run-skill-live-trial` の incremental planner が `reuse` とした schema-valid PASS verdict + behavior closure digest + stable scenario id + transcript digest、または同じ情報へ束縛された current observational receipt だけを再利用できる。content-review / 静的 rubric は behavioral claim を閉じない。
- target edit 後は変更した input slice とその downstream obligation だけを無効化する。無関係な sibling claim の current receipt は維持する。矛盾証拠・低 confidence・予算超過は Agent を追加せず `escalate|defer` として停止理由へ残す。
- planner / receipt が無い、または evidence file の digest が一致しない場合は fail-closed で未解決とする。`reuse|observe|adjudicate`、fingerprint、evidence path を `<run-dir>/intermediate.jsonl` に記録する。

build handoff に verification contract / evidence dir / stage がある場合は、Agent 起動前に正本 planner を同じ stage で再実行する。`$PLUGIN/$SKILL` は target、`$RUN_ID/$RUN_DIR` は本実行の固定 id / canonical run dir、`$CONTRACT/$EVIDENCE_DIR/$STAGE` は handoff から設定する。iter-improve 側から `draft` を `release` へ自動昇格しない。`llm_batches[]` / `observational_queue[]` のうち target claim だけが未解決 work で、`reuse` は起動対象でない。

```bash
python3 plugins/harness-creator/skills/run-build-skill/scripts/plan-verification-obligations.py \
  --contract "$CONTRACT" --repo-root . --evidence-dir "$EVIDENCE_DIR" \
  --profile incremental --stage "$STAGE" --run-id "$RUN_ID" --out "$RUN_DIR/verification-plan.json"
```

live tier の再利用可否は専用 planner に委ねる。`action=reuse` だけを閉じた behavioral claim とし、`run` は `run-skill-live-trial` へ、`fork|static` は対応する軽量評価へ送る。

```bash
python3 plugins/harness-creator/skills/run-skill-live-trial/scripts/plan-live-trials.py \
  --plugin-dir "plugins/$PLUGIN" --eval-root eval-log --profile incremental \
  --skill "$SKILL" --out "$RUN_DIR/live-plan.json"
```

verification plan から実行した新規判定は、将来の再利用前に同じ fingerprint へ束縛する。evidence file が無い判定や plan 外の obligation は receipt 化せず、未解決のまま残す。

```bash
python3 plugins/harness-creator/skills/run-build-skill/scripts/record-verification-evidence.py \
  --plan "$RUN_DIR/verification-plan.json" --obligation-id "$OBLIGATION_ID" \
  --status "$STATUS" --verifier-kind "$VERIFIER_KIND" --verifier-id "$VERIFIER_ID" \
  --evidence-path "$EVIDENCE_PATH" --repo-root . --evidence-dir "$EVIDENCE_DIR" \
  --run-id "$RUN_ID" --model-action-id "$MODEL_ACTION_ID"
```

### 局面: unresolved eval (tier 一致、fork は最大 N 並列)

main orchestrator は proof plan の未解決 obligation だけを実行する。`action=run` の live tier は `run-skill-live-trial` の `live_batches` どおり本物の session へ送り、Agent fork へ格下げしない。fork tier だけを `parallel_agents_default` を上限として同一メッセージ内に並列発火し、static tier は対応する決定論 check だけを実行する。同じ fingerprint の current PASS receipt を「念のため」再採点する Agent は起動しない。fork agent prompt の核:

```
あなたは context-fresh agent。この skill の改善履歴・前回 score・改善意図を一切知らない前提で作業する。
Skill({skill: "<target>", args: "<task args>"}) を起動し、完走後 <run-dir>/eval-output.json を Read。
goal-spec.json.goal の 1 文が達成されているかを score と別立てで採点し、根拠を 3 行で書く。
target skill のファイル編集は絶対禁止 (改善は呼び元の責務)。
報告: overall_score / breakdown / 弱点 top3 / goal 達成度 (score と別立て)。
```

plateau が 2 iter 続いたら、未解決 obligation の範囲内で prompt を model swap / persona / source 深度に variant 化して再 iter する。current PASS の sibling claim を variant 数合わせのため再実走しない。

### 局面: 集計 (file polling)

`Bash(run_in_background=true)` の polling ループで今回 `observe` した eval の完了を待つ (`eval-output.json` の個数 or deadline 到達)。current fingerprint の reuse receipt と新規結果を区別して overall_score / breakdown / goal 達成度を集計し、run dir の `<date>-score.jsonl` へ append する。異なる fingerprint / evaluator 契約の score は同じ平均へ混ぜない。score 平均と goal 達成度平均の乖離が iter を追って開く場合、generator でなく評価が壊れている兆候 (INVARIANT 3 の警告 signal)。

### 局面: diagnose + 審問

1. current receipt と今回の runs に共通する弱点を `batch_per_iter_max` 件以下に絞る
2. 構造改善判定 (INVARIANT 4): 1 入力固有か / 複数 sample 再現か
3. rubric 起因の疑い: 同一弱点が 3 iter 連続 + 直接修正で +0pt なら rubric bug を 8 割疑い、target を当該 evaluator skill に切替
4. **PASS 詐欺自己審問 + 緩め禁止リスト照合** → `interrogation-log.jsonl` へ 1 行 append (schema 必須)。独立判定の発火条件該当時は**別個体 fresh agent** に改善 diff だけを渡し「generator 改善か / 緩め操作か」を判定させる (期待する答え・改善履歴・score は渡さない)

### 局面: edit

skill 層を `batch_per_iter_max` 件以下 Edit する (writer-prompt の rule 追加 / SKILL.md の手順明文化 / scripts の bug fix と defensive guard 注入 / schema 制約強化)。**禁止**: evaluator / rubric / 採点 mode を「score を通すため」に緩める編集。rubric が goal の悪い代理と判明したら、それは「緩める」のではなく target を evaluator skill に切り替えて「goal に寄せて作り直す」別ループで行う。

### 局面: commit

eval data 確認後に 1 ロジック 1 commit (`wrap-git-commit-safe` 経由、INVARIANT 6)。message に iter 番号 / 観測根拠 (どの run のどの弱点) / 期待効果を書き、複数ロジックを 1 commit に混ぜない (revert 可能性を保つ)。

### 局面: GOAL VERIFICATION + 収束判定

成功停止は 1 つだけ。**score は診断信号であり、成功条件でも周回継続条件でもない (INVARIANT 3)**:

1. **GOAL VERIFICATION**: 契約の正本は `goal-seek-paradigm.md`「達成判定 (GOAL VERIFICATION)」節。final goal の exact fingerprint に束縛された current observational PASS receipt があれば `reuse` し、なければ fresh agent が実走成果物 / 行動ログ実体を入力に **PASS|FAIL + blocker 列挙のみ**を返す (点数出力禁止・SKILL.md 静的レビューでの代替禁止)。edit / scenario・checker 契約 / upstream proof の変更で当該 fingerprint が変われば必ず再観測する
2. **PASS**: score にかかわらず目的達成として即停止し、残 task-graph 予算を消費しない。**FAIL**: avg overall ≥ `score_threshold_default` なら PASS 詐欺疑いとして扱い、blocker が改善可能かつ `max_iter` 未満の場合だけ次 iter へ進む。連続 2 iter +0 または `max_iter` 到達時も成功へ丸めず「score X / goal FAIL / 残 blocker」の `INCOMPLETE` として停止する

停止時の最終報告に必ず含める:

- 全 iter の score summary (iter / new・reused samples / fingerprint / avg / range) + **goal 達成度の推移** (乖離監視の証跡)
- 全 commit 一覧 (hash + 1 行要約) と **審問ログで破棄した改善案の一覧** (何を PASS 詐欺と判定したか)
- 残課題 (plateau 突破に必要な structural change 候補)
- **評価の前提明示**: 最終 score がどの evaluator / mode / rubric hash / 前提で出たか (同一成果物が文脈で点数割れするのを防ぐ)

## 判定者独立性 (3 役は別個体・履歴非共有)

| 役割 | 受け取る入力 | 禁止事項 |
|---|---|---|
| unresolved eval agent (最大 N 体) | target + task args + 割当 obligation のみ | 改善履歴・前回 score の知悉 / target skill ファイルの編集 / reuse claim の再採点 |
| 審問独立判定 agent | 改善 diff のみ | GOAL VERIFICATION agent との兼任 / 期待する答え・改善履歴・score の受領 |
| GOAL VERIFICATION agent (observe 時のみ) | 実走成果物・行動ログ実体のみ | 審問独立判定 agent との兼任 / score・breakdown・改善履歴の受領 / 点数出力 |

## Gotchas

- **`context: main` 必須** — Skill → Agent 不可制約により、本 skill を Skill 経由で起動すると fan-out 用の Agent ツールが使えない。常に main 直下から起動する
- **TaskOutput 多重 block 禁止** — 複数 BG task の同時 block wait は orchestrator を stall させる。file polling (集計局面) が正
- **同題材並列実行は collision** — target 側 init に mktemp -d (random suffix) が無ければ最初の iter で必ず fix する
- **±3-5pt は noise** — 1-2pt の上下で判断しない。3pt 以上の連続変化 or breakdown の structural 変化を真の signal とする
- **score 急上昇を疑え** — 急上昇は generator 改善より evaluator 緩和の方が起こしやすい。発火条件・独立判定強制は `schemas/interrogation-log.schema.json` が機械正本
- **rubric bug を疑う閾値** — 3 iter 連続同一弱点 + 直接修正 +0pt で rubric 側を 8 割疑う (diagnose 局面参照)
- **ローカル開発環境限定** — 量産先 plugin へ本 skill を配備しない。CI でも実行しない (配備境界は配布注記参照)
- **再帰遮断** — 本 skill / `run-skill-live-trial` / `run-elegant-review` (エンジン閉包) を target にする場合は INVARIANT 7 の scratch copy 必須。判定は `requires_subject_copy` 述語に委ね、閉包リストをここへ再掲しない

## Additional resources

- `references/goal-declaration.md` — iter 0 GOAL DECLARATION 手順書
- `schemas/interrogation-log.schema.json` — 審問ログ契約 (独立判定発火条件の機械正本)
- `run-skill-live-trial` — 前段の実走受け入れ (Gate D)。FAIL / 乖離 handoff の供給元
- `../run-elegant-review/references/convergence-policy.json` — `loop_bounds.iter_improve` / `anti_patterns` の正本
- `../run-build-skill/references/goal-seek-paradigm.md` — コンテキスト分離 / 達成判定 (GOAL VERIFICATION) の正本
- `../run-build-skill/references/verification-obligation-protocol.md` — fingerprint / receipt / machine-first 差分再評価の正本
- `../run-build-skill/references/content-review-protocol.md` — design claim と legacy content-review verdict 投影の境界
