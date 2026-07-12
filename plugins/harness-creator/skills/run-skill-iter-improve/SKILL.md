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
owner: team-platform
since: 2026-07-02
version: 0.1.0
role_suffix: orchestrator
source: eval-log/harness-creator/_plugin/elegant-review/20260702T160010-anti-goodhart/design-decisions.md
source-tier: internal
last-audited: 2026-07-02
audit-trigger: quarterly
schema_refs:
  - schemas/interrogation-log.schema.json
  - ../run-goal-elicit/schemas/goal-spec.schema.json
reference_refs:
  - references/goal-declaration.md
  - ../run-elegant-review/references/convergence-policy.json
  - ../run-build-skill/references/goal-seek-paradigm.md
  - ../run-build-skill/references/feedback-loop-deployment.md
  - ../../references/orchestrate-gate-pattern.md
completeness_exempt:
  - "prompts: ゴールシーク形 orchestrator。手順は局面カタログから都度選択し、fan-out agent prompt 核は fresh-context 前提宣言が本体のため本文に 1 個だけ持つ。prompt-creator の R-id 単位 7 層プロンプトは適用外 (run-goal-seek と同型の skip)。"
  - "manifest: 局面はゴールシークループで都度選択するため phase/gate 固定の workflow-manifest は適用外 (run-goal-seek と同型)。"
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 毎 iter の審問ログが schemas/interrogation-log.schema.json を通過し score 急変または評価経路接触の iter は independent_check.required true かつ verdict 非 null で記録される
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: 各 iter の改善投入件数が convergence-policy loop_bounds.iter_improve.batch_per_iter_max 以下で commit は全て eval 集計取得後に 1 commit 1 ロジックで行われる
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 収束停止前に GOAL VERIFICATION が実走成果物と行動ログ実体を入力に PASS を返し静的レビューを収束根拠に一切含めない
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: 審問独立判定 agent と GOAL VERIFICATION agent が別個体かつ履歴非共有で score と改善履歴を渡されずに判定する
      verify_by: evaluator
---

# run-skill-iter-improve

> **配布注記**: cross-skill refs (`../run-goal-elicit/`, `../run-build-skill/`, `../run-elegant-review/`) は repo-bundled 前提 (単独配布非対応)。本 skill と `run-skill-live-trial` は実行 acceptance 系として**ローカル開発環境限定**であり、量産先 plugin へは配備しない (正本: `../run-build-skill/references/feedback-loop-deployment.md` の配備境界)。CI でも実行しない。

## 目的と出力契約

target skill の品質を「fresh-context Agent N 体並列実走 eval → 弱点 diagnose + PASS 詐欺審問 → skill 層を少数件 Edit → commit → GOAL VERIFICATION」で反復改善する **eval 帰属のメタ改善ループ** (skill が skill を改善する)。

score を上げる方法は 2 つある — generator (成果物を作る側) を本当に良くするか、evaluator を緩めて score を通すか。後者の方が速く score が上がるので、規律が無いと必ずそちらへ流れる (Goodhart の法則)。本 skill は skill 改善ループで起きやすいこの事故を 8 INVARIANTS で構造的に防ぐ。**INVARIANTS を破る改善ループは、score がいくら上がっても失敗である。**

- **入力**: target (`<plugin>/<skill>`) + task args + `--goal` (goal 正本へのエイリアス、後述) + ループパラメータ (既定値の正本は後述 `loop_bounds.iter_improve`)
- **出力**:
  - 改善 commit 群 — 1 commit 1 ロジック、`wrap-git-commit-safe` 経由
  - `eval-log/<plugin>/<skill>/iter-improve/<run-id>/interrogation-log.jsonl` — 毎 iter の PASS 詐欺自己審問ログ (`schemas/interrogation-log.schema.json` 準拠の**必須 artifact**)
  - 同 run dir の `<date>-score.jsonl` — 既存の `**/*-score.jsonl` 合流規約 (run-skill-rubric-governance の aggregate-evals.py が収集)。**独自 sink 新設禁止**
  - GOAL VERIFICATION 判定 (PASS|FAIL + blocker 列挙) + iter summary (score 推移 / goal 達成度推移 / 破棄した改善案 / 最終 score がどの mode・rubric・前提で出たかの明記)
- **起動導線 (正規経路)**: `run-skill-live-trial` の受け入れ verdict FAIL、または goal 達成度と score の乖離 ⚠️ からの handoff を受けて起動する。plateau 突破を狙う単独起動も可。issue 更新 / close / push は呼び元責務

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

- [ ] iter 0 GOAL DECLARATION 完了 (goal 正本読取 / proxy 妥当性審問 Yes|No+根拠 / forbidden_loosening 宣言。手順: `references/goal-declaration.md`)
- [ ] 毎 iter の審問ログが `interrogation-log.jsonl` へ 1 行 append され `schemas/interrogation-log.schema.json` を通過する
- [ ] 各 iter の改善投入件数が `loop_bounds.iter_improve.batch_per_iter_max` 以下
- [ ] score 急変または評価経路接触の iter は別個体 fresh agent の独立判定 verdict が記録済 (発火条件は同 schema の allOf が機械強制)
- [ ] commit は全て eval 集計後・1 commit 1 ロジック (`wrap-git-commit-safe` 経由)
- [ ] 収束宣言前に GOAL VERIFICATION を実施し PASS、または max_iter 到達時に「score X / goal FAIL / 残 blocker」を隠さず報告した
- [ ] 全 artifact が `eval-log/<plugin>/<skill>/iter-improve/<run-id>/` に保存済 (score は `*-score.jsonl` 合流規約)

### ゴールシークループ

正本 6 ステップ (現状評価→手順生成→実行→検証→Anchor Step→反復) に従い、下記**局面カタログ**から未達チェックリスト項目を埋める局面を都度選ぶ。ループパラメータ (反復上限 / iter あたり投入件数 / 並列 agent 数 / score 閾値) の生値は本文に書かず、`../run-elegant-review/references/convergence-policy.json` の `loop_bounds.iter_improve` (`max_iter` / `batch_per_iter_max` / `parallel_agents_default` / `score_threshold_default`) を唯一の正本とする (二重宣言禁止)。

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

### 局面: fan-out (N 並列 fresh agent)

main orchestrator が**同一メッセージ内に N 個** (既定 `parallel_agents_default`) の Agent 呼出を並列発火する。各 agent prompt の核:

```
あなたは context-fresh agent。この skill の改善履歴・前回 score・改善意図を一切知らない前提で作業する。
Skill({skill: "<target>", args: "<task args>"}) を起動し、完走後 <run-dir>/eval-output.json を Read。
goal-spec.json.goal の 1 文が達成されているかを score と別立てで採点し、根拠を 3 行で書く。
target skill のファイル編集は絶対禁止 (改善は呼び元の責務)。
報告: overall_score / breakdown / 弱点 top3 / goal 達成度 (score と別立て)。
```

plateau が 2 iter 続いたら N agents を同一 prompt でなく model swap / persona / source 深度で variant 化して再 iter。

### 局面: 集計 (file polling)

`Bash(run_in_background=true)` の polling ループで N evals の完了を待つ (`eval-output.json` の個数 or deadline 到達)。完了後 overall_score / breakdown / goal 達成度を集計し、run dir の `<date>-score.jsonl` へ append する。score 平均と goal 達成度平均の乖離が iter を追って開く場合、generator でなく評価が壊れている兆候 (INVARIANT 3 の警告 signal)。

### 局面: diagnose + 審問

1. N runs 共通の弱点を `batch_per_iter_max` 件以下に絞る
2. 構造改善判定 (INVARIANT 4): 1 入力固有か / 複数 sample 再現か
3. rubric 起因の疑い: 同一弱点が 3 iter 連続 + 直接修正で +0pt なら rubric bug を 8 割疑い、target を当該 evaluator skill に切替
4. **PASS 詐欺自己審問 + 緩め禁止リスト照合** → `interrogation-log.jsonl` へ 1 行 append (schema 必須)。独立判定の発火条件該当時は**別個体 fresh agent** に改善 diff だけを渡し「generator 改善か / 緩め操作か」を判定させる (期待する答え・改善履歴・score は渡さない)

### 局面: edit

skill 層を `batch_per_iter_max` 件以下 Edit する (writer-prompt の rule 追加 / SKILL.md の手順明文化 / scripts の bug fix と defensive guard 注入 / schema 制約強化)。**禁止**: evaluator / rubric / 採点 mode を「score を通すため」に緩める編集。rubric が goal の悪い代理と判明したら、それは「緩める」のではなく target を evaluator skill に切り替えて「goal に寄せて作り直す」別ループで行う。

### 局面: commit

eval data 確認後に 1 ロジック 1 commit (`wrap-git-commit-safe` 経由、INVARIANT 6)。message に iter 番号 / 観測根拠 (どの run のどの弱点) / 期待効果を書き、複数ロジックを 1 commit に混ぜない (revert 可能性を保つ)。

### 局面: GOAL VERIFICATION + 収束判定

収束判定は 2 段。**score だけで停止してはいけない (INVARIANT 3)**:

1. **score gate**: avg overall ≥ `score_threshold_default` / `max_iter` 到達 / 連続 2 iter +0
2. **GOAL VERIFICATION**: 契約の正本は `goal-seek-paradigm.md`「達成判定 (GOAL VERIFICATION)」節。実走成果物 / 行動ログ実体を入力に **PASS|FAIL + blocker 列挙のみ** (点数出力禁止・SKILL.md 静的レビューでの代替禁止)。score gate 通過でも FAIL なら **PASS 詐欺疑い** — blocker を次 iter の改善対象にして続行 (score gate は無視)。`max_iter` 到達かつ FAIL は「score X / goal FAIL / 残 blocker」を隠さず報告して停止

停止時の最終報告に必ず含める:

- 全 iter の score summary (iter / N samples / avg / range) + **goal 達成度の推移** (乖離監視の証跡)
- 全 commit 一覧 (hash + 1 行要約) と **審問ログで破棄した改善案の一覧** (何を PASS 詐欺と判定したか)
- 残課題 (plateau 突破に必要な structural change 候補)
- **評価の前提明示**: 最終 score がどの mode / rubric / 前提で出たか (同一成果物が文脈で点数割れするのを防ぐ)

## 判定者独立性 (3 役は別個体・履歴非共有)

| 役割 | 受け取る入力 | 禁止事項 |
|---|---|---|
| fan-out eval agent (N 体) | target + task args のみ | 改善履歴・前回 score の知悉 / target skill ファイルの編集 |
| 審問独立判定 agent | 改善 diff のみ | GOAL VERIFICATION agent との兼任 / 期待する答え・改善履歴・score の受領 |
| GOAL VERIFICATION agent | 実走成果物・行動ログ実体のみ | 審問独立判定 agent との兼任 / score・breakdown・改善履歴の受領 / 点数出力 |

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
