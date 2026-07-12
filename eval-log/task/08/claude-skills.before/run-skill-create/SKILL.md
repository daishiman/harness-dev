---
name: run-skill-create
description: 新規Skillを端から端まで作りたいとき、複数Gateを通した品質保証付きフローを起動したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[topic?] [--mode create|update] [--fast]"
arguments: [topic, mode, fast]
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Skill
model: opus
kind: run
effect: local-artifact
owner: team-platform
since: 2026-05-18
pair: assign-skill-design-evaluator
rubric_refs:
  - ref-skill-design-rubric
reference_refs:
  - ref-task-context-map
  - ref-skill-glossary
# context-budget: orchestrationのみ。各子スキルがそれぞれの設計書を参照する。本スキルは05/06/07/13/23/25章のみ参照。
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
---

# run-skill-create

> ※ creator-kit Phase 0 移行中は `creator-kit/skills/` が正本、`.claude/skills/` への配置は派生。本SKILL.mdは両配置で動作するよう self-relative パスを使用。

## Purpose & Output Contract

ユーザー要望→`skill-brief.md`→Skill生成→creator-kit登録判定→P0 lint→設計評価→パラダイム評価→governance承認 を**ゲートあり自動連鎖**で実行する端から端までのオーケストレーター。

### 引数なしで呼ばれた場合
`/run-skill-create` を引数なしで呼ぶと、Step 1 (run-skill-elicit) が起動し対話フローで topic を確定する。初回ユーザーはそのまま無引数で起動して問題ない。各 brief フィールドの意味は `references/skill-brief-schema.json` を参照（フィールドごとに description あり）。

### `--fast` モード (低リスク変更向け)
以下の条件をすべて満たすとき軽量フロー (Gate 2 段化) を許可する:
- 既存スキルへの **1ファイル変更のみ**
- diff 行数 **<= 30 行**
- 対象スキル kind ∈ {ref, wrap}（評価ピラミッド P2 不要な低リスク種別）
- evaluator pair が **不要** (ref/wrap skill)

`--fast` 時のフロー: Step 1 brief → Step 2 build → Step 4a P0 lint → Step 6 governance (auto-approve)。Step 4b/5 (fork評価/elegant-review) を skip する。判定は機械的に行い、変更ファイル数・evaluator pair 不要条件も確認する:
```bash
CHANGED_FILES=$(git diff --name-only -- "creator-kit/skills/$SKILL_NAME/" | wc -l | tr -d ' ')
PAIR_REQUIRED=$(python3 -c "import json; b=json.load(open('eval-log/skill-brief.json')); print('true' if b.get('generate_pair_evaluator') or b.get('needs_independent_context') else 'false')")
if [[ "$FAST" == "true" ]] && [[ "$CHANGED_FILES" == "1" ]] && [[ "$DIFF_LINES" -le 30 ]] && [[ "$KIND" =~ ^(ref|wrap)$ ]] && [[ "$PAIR_REQUIRED" == "false" ]]; then
  echo "fast mode: skip Step 4b/5"
fi
```
誤判定を防ぐため、条件不一致時は **fast を黙って解除して通常フロー** に戻る。

**入力**: topic (任意), mode ∈ {create, update}
**出力**:
- `creator-kit/skills/<skill_name>/` 一式 (SKILL.md + references/ + scripts/)。`.claude/skills/` は派生/symlink/deploy target
- `eval-log/skill-build-trace.json` (01/01a/02/03/04/05/06/07/08/09/10/11/13/14/15/16 正本フローへの対応証跡)
- 共通基盤の場合は `creator-kit/manifest.json` 登録差分
- `eval-log/docs/<NN>-<timestamp>.json` (評価結果)
- 完了レポート (どのゲートでユーザー承認を得たか。本文はパラメーター名を除き日本語)

**完了条件**: P0 lint pass + evaluator JSON pass（`--fast` で条件を満たす低リスク ref/wrap は `evaluator: N/A` 理由必須）+ (solo_operator_mode下) LLM-reviewer pass。

## Key Rules

1. **ゲート前で必ず止まる**: ユーザー承認なしに次フェーズへ進まない。全ゲートは AskUserQuestion or 明示的確認。
2. **子スキルへの委譲**: 各フェーズは独立スキルをSkill toolで起動。本スキルは制御のみ。
3. **失敗時の停止**: P0 lint failまたは evaluator FAIL なら停止し、findings提示。
4. **context:fork**: evaluator/governance reviewer は必ず context:fork で起動 (Sycophancy防止)。
5. **handoff保存**: 各ゲート通過時点で `eval-log/handoff-<step>.json` を残し、PostCompact hook で復元可能にする。
6. **creator-kit登録は確認後**: 共通基盤に該当する追加物は manifest 登録案を自動生成するが、ユーザー承認なしに `manifest.json` を更新しない。
7. **resource-map先読み**: local reference を読む前に `references/resource-map.yaml` を読み、必要な補助ファイルだけを開く。
8. **日本語成果物ゲート**: brief の `output_language=ja` と `parameter_language_exception=true` を既定とし、生成本文・レビュー・完了レポートの説明文を日本語にする。

## End-to-End Flow

```
[Step 1] run-skill-elicit  ──→  eval-log/skill-brief.json
                                    │
                              [Gate 1: brief確認]
                                    ▼
[Step 2] run-build-skill   ──→  creator-kit/skills/<name>/ + eval-log/skill-build-trace.json
                                    │
                              [Step 3: creator-kit登録判定]
                                    │
                              [Gate 2.5: 横展開対象確認]
                                    │
                              [Step 4a: P0 lint (自動)]
                                    │  (fail時: findings提示 → Step 2 へ戻る、最大3周)
                              [Gate 2: diff確認]
                                    ▼
[Step 4b] assign-skill-design-evaluator (context:fork)
                                    │
                            (大規模変更時のみ)
                                    ▼
[Step 5] run-elegant-review (context:fork) ──→ 4条件評価
                                    │
                              [Gate 3: 評価結果確認]
                                    ▼
[Step 6] run-skill-rubric-governance
                              (solo_operator_modeなら自動承認条件チェック)
                                    │
                              [Gate 4: 承認]
                                    ▼
                              [完了レポート]
```

## Steps

### Step 1: 要求ヒアリング

```
Skill(run-skill-elicit, args=topic)
```
出力: `eval-log/skill-brief.json` (固定パス。`references/skill-brief-schema.json` に準拠)。
含むフィールド: `skill_name, prefix, role_suffix, kind, hierarchy_level, trigger_conditions, output_contract, key_constraints, boundary, deterministic_checks, external_systems, needs_independent_context, needs_lifecycle_enforcement, cli_tools, mcp_tools, placement_candidates, base_skill, delegate_agent, rubric_refs, open_questions`。

### Gate 1: brief確認

ユーザーに `eval-log/skill-brief.json` を提示し、open_questions があれば確認。承認後 Step 2 へ。
**離脱条件**: ユーザーが skill_name または kind を否認した場合は Step 1 へ戻る (最大3回)。

### Step 2: スキル生成

```
Skill(run-build-skill, args=[skill_name, kind, --mode={mode}])
```
mode=create なら新規、mode=update なら既存スキルの増分更新。
出力された `eval-log/skill-build-trace.json` で、01章5要素、01a Step 1〜9、02/03/04/05/06/07/08/09/10/11/13/14/15/16 の doc_coverage と `pattern_decisions` が全て PASS/N/A/skip 理由付きになっていることを Gate 2 の前提にする。

### Step 3: creator-kit登録判定

生成・更新した成果物が次のいずれかに該当する場合、横展開対象候補として扱う:

- Skill作成・更新・評価・governance に関係する `run-*` / `assign-*` / `ref-*`
- `creator-kit` に入れるべき hook / lint / adapter / secret helper / config
- 複数プロジェクトで共通利用する rubric / reference / template

該当する場合は、成果物を `creator-kit/` 側へ置き、次を実行して manifest 登録案を作る:

```bash
python3 creator-kit/scripts/build-manifest-registration-plan.py
```

### Gate 2.5: 横展開対象確認

`build-manifest-registration-plan.py` の出力をユーザーに提示し、`creator-kit` に登録してよいか確認する。承認された場合のみ:

```bash
python3 creator-kit/scripts/build-manifest-registration-plan.py --apply
```

プロジェクト固有Skillの場合は manifest 登録しない。登録しない理由を完了レポートに残す。

### Step 4a: P0 lint (自動)

cwd は {{PROJECT_ROOT}} プロジェクトルート。`--skills-dir` には creator-kit/skills/ または .claude/skills/ を明示する。
SKILLS_DIR は Phase 0 中の正本である `creator-kit/skills` を既定とし、`.claude/skills` に配置した派生を検査する場合のみ上書きする。

```bash
SKILLS_DIR="${CLAUDE_SKILLS_DIR:-creator-kit/skills}"

# creator-kit lint: manifest/依存方向を含め、配布対象の実体と設定例を検査。
python3 creator-kit/scripts/lint-skill-name.py --skills-dir "$SKILLS_DIR"
python3 creator-kit/scripts/lint-skill-description.py --skills-dir "$SKILLS_DIR"
python3 creator-kit/scripts/lint-skill-tree.py --skills-dir "$SKILLS_DIR"
python3 creator-kit/scripts/validate-frontmatter.py --skills-dir "$SKILLS_DIR"
python3 creator-kit/scripts/lint-dependency-direction.py --skills-dir "$SKILLS_DIR"
python3 creator-kit/scripts/lint-skill-dep-step7.py --skills-dir "$SKILLS_DIR"
python3 creator-kit/scripts/lint-forbidden-deps.py --skills-dir "$SKILLS_DIR"
python3 creator-kit/scripts/lint-manifest-contents.py
```
**全てexit 0必須**。失敗時: findings をユーザー提示 → Step 2 へ戻る (最大3周)。Gate 2 は全 lint exit 0 の場合のみ通過可。
加えて、生成テンプレートに `TODO`、未展開 `{{...}}`、英語の仮文が残る場合は Step 2 へ戻す。パラメーター名、frontmatterキー、JSONキー、CLI引数は英語のままでよい。

### Gate 2: diff確認

`git diff creator-kit/skills/<name>/` をユーザーに提示し承認を得る。派生配置を検査する場合のみ `.claude/skills/<name>/` も併記する。前提: Step 4a が全 pass していること。
あわせて `eval-log/skill-build-trace.json` を提示し、設計書準拠の判断が再現可能か確認する。

### Step 4b: 設計評価

```
Skill(assign-skill-design-evaluator, args=<skill_path>, context=fork)
```
出力: `eval-log/docs/<NN>-<timestamp>.json` (rubric項目別pass/fail)。
**FAIL項目があれば**: findings をユーザーに提示し、Step 2 へ戻るか TODO(human) で残すか判断を仰ぐ。

### Step 5: パラダイム評価 (条件付き)

新規スキルまたは大規模更新 (>30行変更) の場合のみ実行する。判定は機械化:

```bash
# git diff --shortstat の "X insertions" + "Y deletions" を加算して 30 を超えるか判定
DIFF_LINES=$(git diff --shortstat -- "creator-kit/skills/$SKILL_NAME/" \
  | python3 -c "import sys,re; s=sys.stdin.read(); ins=sum(int(m) for m in re.findall(r'(\d+) insertion',s)); dels=sum(int(m) for m in re.findall(r'(\d+) deletion',s)); print(ins+dels)")
NEW_SKILL=$(test -n "$(git ls-files --others --exclude-standard creator-kit/skills/$SKILL_NAME/)" && echo "true" || echo "false")
if [[ "$NEW_SKILL" == "true" ]] || [[ "$DIFF_LINES" -gt 30 ]]; then
  echo "elegant-review triggered: new=$NEW_SKILL diff_lines=$DIFF_LINES"
  # Skill 起動
fi
```
```
Skill(run-elegant-review, args=[skill, <skill_path>], context=fork)
```
4条件 (C1-C4) すべてPASS必須。判定をLLMに委ねず必ず上記 bash で機械決定する。

PASS時は `findings.json` の `pattern_ref_candidates` / `new_patterns` / `mass_production_risk` を確認し、再利用可能なものは `eval-log/pattern-feedback.json` に提案として残す。template / rubric / lint / hook へ反映する場合は Step 6 governance を通し、直接書き換えない。

### Gate 3: 評価結果確認

評価レポートをユーザーに提示。FAIL残存時は修正方針を確認。

### Step 6: governance承認

プロジェクトルートの `references/governance-params.json` (skill-local ではなく {{PROJECT_ROOT}} 直下) の `solo_operator_mode` を読み取り:
- `solo_operator_mode: true` かつ 3条件 (安定版凍結済み / newly_failing=0 / LLM-reviewer pass) 満たすなら自動承認
- それ以外は通常 governance フロー (`run-skill-rubric-governance`) を起動

### Gate 4: 最終承認

完了レポートを提示しユーザーの最終承認を得る。

### Step 7: 完了レポート

```markdown
# Skill Creation Report: <skill_name>

- mode: create|update
- gates_passed: [1,2,3,4]
- creator_kit_registration: applied|skipped|not_applicable
- evaluator_result: PASS
- elegant_review: PASS (or N/A)
- governance: solo_auto_approved (or manual)
- TODO(human): [...]
```

## Gotchas

1. **Gate skip禁止**: 「次へ」を自動推測しない。明示確認なしに次ステップへ進まない。
2. **同一context評価禁止**: evaluator/governance reviewer は必ず context:fork。同コンテキストだとSycophancyで偽陽性PASS。
3. **lint失敗時の自動修正禁止**: lint failの根本原因をユーザーに提示。LLM判断で勝手に直さない。
4. **mode=update時の改名**: 名前変更を伴う更新は `run-skill-rename` に委譲。本スキルでは扱わない。
5. **context予算**: 31章全部を読み込まない。本スキルは05/06/07/13/23/25章のみを参照し、子スキルが各章を担当。
6. **handoff保存**: 各ゲート通過時に handoff JSON を必ず保存。PostCompact hook で復元できるようにする。
7. **manifest二重管理禁止**: manifest登録は `build-manifest-registration-plan.py` の提案を経由し、手書き追加後も `lint-manifest-contents.py` を必ず通す。

## Additional Resources

- `references/gate-templates.md` — 各ゲートの確認質問テンプレート (Step8検証1-3手動チェックリスト含む)
- `references/resource-map.yaml` — read first; local references の read_when map
- `references/handoff-schema.json` — handoff JSONスキーマ
- `references/skill-brief-schema.json` — Step1→Step2 渡しの skill-brief.json スキーマ
- 子スキル: `run-skill-elicit`, `run-build-skill`, `assign-skill-design-evaluator`, `run-elegant-review`, `run-skill-rubric-governance`, `run-skill-rename`
- 設計書: `05-layering-skill-subagent-hook-mcp-cli.md`, `06-classification-and-naming.md`, `07-progressive-disclosure.md`, `11-templates.md`, `13-checklists.md`, `23-meta-skill-architecture.md`, `25-meta-skill-runbook.md`
