---
name: run-goal-seek
description: 目的・背景・ゴールに対し固定手順なしでタスクを遂行したいとき、完了チェックリストが全充足するまで手順を都度生成して反復実行したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[topic?] [--spec eval-log/goal-spec.json]"
arguments: [topic, spec]
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(python3 *)
  - Skill
  - Agent
kind: run
prefix: run
effect: local-artifact
owner: team-platform
since: 2026-05-24
version: 0.1.0
role_suffix: orchestrator
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-24
audit-trigger: quarterly
schema_refs:
  - ../run-goal-elicit/schemas/goal-spec.schema.json
reference_refs:
  - ../run-build-skill/references/goal-seek-paradigm.md
completeness_exempt:
  - "prompts: 責務単位プロンプトを持たない汎用オーケストレーター。手順は固定化せずゴールシークループで都度生成するため、prompt-creator の R-id 単位 7 層プロンプトは適用外 (prompt-placement-convention.md の ref/wrap/delegate 同等の skip 扱い)。ループ規約は ../run-build-skill/references/goal-seek-paradigm.md を共有正本として参照。"
  - "manifest: ゴールシークループで手順を都度生成するため phase/gate 固定の workflow-manifest は適用外。"
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)。content-review verdict の criteria_evaluated と突合
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 中間成果物アンカー run-goal-seek-intermediate.jsonl が毎周回6必須キーを持ち original_goal が全行不変で progress.original_goal_hash の SHA-256 と一致し drift_signal が固定enumに収まる(検証ブロックで機械判定)
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: 完了判定が goal-spec.checklist 全項目 done true または max_loops 到達時 open_issues 記録のいずれかで閉じ intermediate 行数が progress.iteration+1 と一致する
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: ループ本体を親で直接回さず Agent ツールで SubAgent または Agent Team に fork し親へ返すのは最終成果物パスと handoff-goal-seek.json 要約のみで周回の試行錯誤を漏らさない
      verify_by: elegant-review
    - id: OUT2
      loop_scope: outer
      text: 固定手順を SKILL.md にハードコードせず Step1-3 を本文に焼かない都度生成原則を保ち paradigm.md を共有正本として参照し本スキル固有差分のみ記す
      verify_by: evaluator
---

# run-goal-seek

> **配布注記**: 本 skill の cross-skill `schema_refs` / `reference_refs` (`../run-goal-elicit/`, `../run-build-skill/`) は repo-bundled 前提 (単独配布非対応)。

## 目的と出力契約

既存コンテキストから最適ゴールを推定し、そのゴールに対して **手順を固定せず**、完了チェックリストが全て満たされるまで「手順を都度生成 → 実行 → 検証」を反復するゴールシーク実行オーケストレーター。**ループ本体は親セッションを汚さないよう SubAgent（または Agent Team）に fork して実行**し、親には最終成果物とハンドオフ要約のみを返す。達成した成果物を後続 Capability へ受け渡す。

- **入力**: `goal-spec.json` (`--spec`、既定 `eval-log/goal-spec.json`)。無ければ会話履歴・`topic`・関連ファイルから `run-goal-elicit` 相当の推定を内部実行して生成する。
- **出力**:
  - 各タスク固有の成果物（goal で定義された最終状態）
  - `eval-log/goal-seek-progress.json` — 各周回のチェックリスト状態と生成手順の記録
  - `eval-log/run-goal-seek-intermediate.jsonl` — 各周回末の中間成果物アンカー (`original_goal`/`current_goal_snapshot`/`delta_from_original`/`merged_directive_for_next`/`drift_signal`)。次周回 Step2 への必須入力。集約化ドリフト圧縮機構 (`../run-build-skill/references/goal-seek-paradigm.md`「中間成果物」)。命名規約: `eval-log/<skill>-intermediate.jsonl` の `<skill>` は本スキル名 `run-goal-seek` を採る
  - `eval-log/handoff-goal-seek.json` — 成果物パスと達成チェックリスト（後続 skill が拾う汎用ハンドオフ）
- **完了条件**: `goal-spec.checklist` が全項目 `done:true`。または `max_loops` 到達で残項目を `open_issues` に記録して停止。

## 境界

ユーザーへの追加ヒアリングはしない。`goal-spec` が無い場合は AI が「仮想ヒアリング済み」としてゴールとチェックリストを推定する。本スキルはそのゴールを**達成するまで回す**ことに専念し、達成手順を事前に固定しない。

## 主要ルール

1. **手順を事前固定しない**: 各周回でチェックリストの未達項目を見てから手順を立てる。
2. **チェックリストで完了判定**: 自然言語の「できた気がする」ではなく、各項目を観測可能に検証して `done` を更新する。
3. **決定論検査を優先**: `verify_by` が `script`/`lint`/`test` の項目は機械検証で判定する。
4. **最大周回数を守る**: `max_loops`（既定 5）超過で停止し `open_issues` に残項目を記録、人間 or 上位 orchestrator に差し戻す。
5. **ハンドオフ**: 完了後、`handoff_targets` があれば各 skill へ成果物を渡す。無くても汎用 `handoff-goal-seek.json` を必ず出す。
6. **コンテキスト分離（必須）**: ループは親セッションで直接回さず、`Agent` ツールで専用 SubAgent に fork して実行する。複数ゴールを並列で回すなら Agent Team に分離する。親に返すのは最終成果物パスと `handoff-goal-seek.json` 要約のみで、周回の中間情報（生成手順・試行錯誤）は fork 内に留める。詳細は `../run-build-skill/references/goal-seek-paradigm.md` の「コンテキスト分離」。
7. **質問しない自走**: 不足情報は最尤仮説で補い、仮定を `goal-spec.constraints` / `goal-seek-progress.json.open_issues` に残す。
8. **中間成果物アンカー（必須）**: 各周回末 (Anchor Step) に `eval-log/run-goal-seek-intermediate.jsonl` へ `{iteration, original_goal, current_goal_snapshot, delta_from_original, merged_directive_for_next, drift_signal}` を 1 行追記する。`original_goal` は全周回で**不変** (SHA-256 を `progress.original_goal_hash` に固定し毎周回照合)。次周回 Step2（手順生成）は直前の `merged_directive_for_next` と `original_goal` を**必須入力**として読み、AI が単独で再導出してはならない。`drift_signal` は schema 必須 (`initial`/`aligned`/`compressing`/`stagnant`/`widening`/`oscillating`)。これにより固定手順なしの自由度を保ちつつ、確率的最尤の抽象解へ集約化していくドリフトをアンカーで毎周回押し戻す。

## ゴールシーク実行
> 固定手順は書かない。毎周「ゴール・目的/背景・チェックリスト」を読み、その時点で最適な手順を AI が生成・実行する。詳細は `../run-build-skill/references/goal-seek-paradigm.md`。

### ゴール (Goal)
`goal-spec.goal` で宣言された最終状態に到達し、`checklist` が全項目 `done:true` になった状態。

### 目的・背景 (Why)
固定手順は実行時の文脈変化に脆い。ゴールとチェックリストを到達点として固定し、手順はその都度導出することで、各プラグイン/タスクが自律的にゴールへ収束できる。

### 完了チェックリスト (Checklist)
> 実体は `goal-spec.json` の `checklist`（タスク固有）。本スキル自身のメタチェックは以下。
- [ ] goal-spec をロードし schema 検証を通過した（無ければAIが既存コンテキストから推定生成）
- [ ] goal-spec.checklist の全項目を `done:true` にした、または `max_loops` 到達で `open_issues` を記録した
- [ ] `eval-log/handoff-goal-seek.json` を出力し、`handoff_targets` があれば各 skill へ渡した

### ゴールシークループ
正本 `../run-build-skill/references/goal-seek-paradigm.md` の 6 ステップ（現状評価→手順生成→実行→検証→Anchor Step (中間成果物追記)→反復/差し戻し）に従う。本スキル固有の差分のみ記す:
- 現状評価は `goal-spec.checklist` の `done:false` 項目を対象にする。
- `goal-spec` 不在時は、会話履歴・`topic`・関連ファイル・直近 diff を根拠に `purpose/background/goal/checklist` を生成してから開始する。
- 手順生成 (Step 2) は直前周回 intermediate の `merged_directive_for_next` と `original_goal` を**必須入力**として読む (AI 単独再導出禁止)。1 周目は paradigm.md「iteration=0 初期化規定」に従う。
- 手順生成で必要なら子 Skill を `Skill()` で起動する。
- 検証で `verify_by` 判定後、周回記録を `goal-seek-progress.json` に追記する。
- Anchor Step (Step 5) で `eval-log/run-goal-seek-intermediate.jsonl` へ 1 行 append、初回は `progress.original_goal_hash` に SHA-256 を固定し以降全周回で照合する。
- `max_loops` 超過時、または `drift_signal` が `stagnant`/`widening`/`oscillating` で 2 周連続停滞時は、残項目と差分を `open_issues` に記録して停止する。

## 検証

```bash
# 完了判定: 全 checklist が done:true か、open_issues が記録されているか
# + 中間成果物アンカー機構 (Anchor Step) の機械検査 (存在/行数/必須キー/不変性)
# engine 本体 (引数 3: spec/progress/intermediate)。量産スキル inline 版は引数 2 (progress/intermediate) で
# render-combinators.py GOAL_SEEK_WIRING_SECTION と同型のアンカー検査ロジックを共有する (SSOT は lint-goal-seek --self-test)。
python3 - "$PWD/eval-log/goal-spec.json" "$PWD/eval-log/goal-seek-progress.json" "$PWD/eval-log/run-goal-seek-intermediate.jsonl" <<'PY'
import json, sys, os, hashlib
spec = json.load(open(sys.argv[1], encoding="utf-8"))
undone = [c["id"] for c in spec["checklist"] if not c.get("done")]
prog_path, inter_path = sys.argv[2], sys.argv[3]
prog = json.load(open(prog_path, encoding="utf-8")) if os.path.exists(prog_path) else {}

# 中間成果物アンカー機構の機械検査 (paradigm.md「中間成果物」)
required_keys = {"iteration","original_goal","current_goal_snapshot","delta_from_original","merged_directive_for_next","drift_signal"}
if not os.path.exists(inter_path):
    iters_fallback = prog.get("iteration", 0)
    assert iters_fallback == 0, f"intermediate.jsonl 不在だが progress.iteration={iters_fallback} (周回実行済みなら anchor jsonl 必須)"
    print("intermediate.jsonl 未生成 (ループ未実行)")
else:
    lines = [l for l in open(inter_path, encoding="utf-8").read().splitlines() if l.strip()]
    assert lines, "intermediate.jsonl が空"
    iters = prog.get("iteration", len(lines) - 1)
    assert len(lines) == iters + 1, f"intermediate 行数 {len(lines)} != progress.iteration+1 ({iters+1})"
    first_anchor = None
    for i, line in enumerate(lines):
        entry = json.loads(line)
        missing = required_keys - entry.keys()
        assert not missing, f"intermediate[{i}] 必須キー不足: {missing}"
        if i == 0:
            first_anchor = entry["original_goal"]
            expected_hash = hashlib.sha256(first_anchor.encode()).hexdigest()
            actual_hash = prog.get("original_goal_hash")
            assert actual_hash is None or actual_hash == expected_hash, f"original_goal_hash drift: progress={actual_hash} vs sha256(intermediate[0])={expected_hash}"
        assert entry["original_goal"] == first_anchor, f"intermediate[{i}] anchor 不変性違反: {entry['original_goal']!r} != {first_anchor!r}"
    print(f"intermediate 検査 OK: {len(lines)} 行 / anchor 不変 / hash 一致")

if undone:
    assert prog.get("open_issues"), f"未達 {undone} があるが open_issues 未記録"
    print(f"停止: open_issues に {len(undone)} 件記録済み")
else:
    print("完了: 全 checklist done")
PY
```

## 注意点

- **手順を SKILL.md に固定で書かない**: このスキルの価値は「都度生成」。Step 1/2/3 を本文にハードコードしない。
- **無限ループ防止**: 同じ未達項目が 2 周連続で進まない場合は手順アプローチを変える。それでも `max_loops` で必ず止める。
- **ハンドオフの取り違え**: `handoff_targets` の skill 入力契約を満たしているか渡す前に確認する。
- **goal-spec 不在**: `--spec` も既定パスも無ければ追加質問せず、AI が `run-goal-elicit` 相当の推定で spec を作ってから本ループへ入る。

## 追加リソース

- `../run-goal-elicit/SKILL.md` — 前段のゴール抽出スキル
- `../run-goal-elicit/schemas/goal-spec.schema.json` — 入力契約の正本
- `../run-build-skill/references/goal-seek-paradigm.md` — ゴールシークの正本定義
