# build-steps（詳細手順）

SKILL.md 本文 300行制約により分離した詳細。

## Phase 0: 正本フロー確認

01章と01a章を最小ロードし、生成対象が「プロンプト保存」ではなく再利用可能な業務部品になっているか確認する。続けて02/03/04章の必要節だけを読み、Skill構造、frontmatter、発動/権限の判断を trace に残す。

1. 01章の5要素を埋める: Intent / Contract / Boundary / Execution / Feedback。
2. 01aの全体フローを今回の対象に対応付ける。
3. 02章で配置スコープ、Reference/Task 境界、Additional Resources の索引方針を決める。
4. 03章で trigger 2〜3個、frontmatter、独自メタデータ、依存注入フィールドを決める。
5. 04章で allowed-tools と permissions.deny / hook の責務分離を決める。
6. 05章のレイヤー判断で、Skill / Subagent / Hook / MCP / CLI / script の配置理由を決める。
7. 決定論で落とせる検査を LLM 手順に残していないか確認する。

## Phase A: 要求整形

1. ユーザー要求を1文に圧縮（"<verb> <object>"）。
2. kind を5択から確定。
3. trigger 2〜3個を動詞ベースで起草。
4. description ドラフトを生成し、動作詳細が混入していないかセルフチェック。
5. Boundary を明記し、「この Skill がやらないこと」を1〜3個書く。
6. Feedback を明記し、evaluator / lint / hook / usage log のどれで改善ループを閉じるか決める。

## Phase B: 雛形選定

- run → `templates/run.md`
- ref → `templates/ref.md`
- assign (gen) → `templates/assign-generator.md`
- assign (eval) → `templates/assign-evaluator.md`
- wrap → `templates/wrap.md`
- delegate → `templates/delegate.md`

## Phase C: scaffold

```bash
SKILL_NAME=run-my-thing
KIND=run
OUT_BASE="${CLAUDE_SKILL_OUT_BASE:-creator-kit/skills}"
ROOT="$OUT_BASE/$SKILL_NAME"
mkdir -p $ROOT/{templates,references,scripts,examples}
python3 creator-kit/skills/run-build-skill/scripts/render-frontmatter.py \
  --name $SKILL_NAME --kind $KIND \
  --brief eval-log/skill-brief.json \
  --template creator-kit/skills/run-build-skill/templates/$KIND.md \
  > $ROOT/SKILL.md
```

## Phase D: 本文執筆

- 「Purpose & Output Contract」: 入力/出力/完了条件
- 「Key Rules」: 5〜10個
- 「Steps」: 番号付き、各StepはBashブロック or 短い手順
- 「Gotchas」: 反パターン3〜5個
- 「Additional Resources」: references/ への索引

## Phase E: lint

```bash
python3 creator-kit/scripts/lint-skill-name.py "$ROOT/SKILL.md"
python3 creator-kit/scripts/lint-skill-tree.py "$ROOT"
python3 creator-kit/scripts/validate-frontmatter.py "$ROOT/SKILL.md"
python3 creator-kit/skills/run-build-skill/scripts/validate-build-trace.py eval-log/skill-build-trace.json
```

## Phase F: 評価

`assign-skill-design-evaluator` を fork で呼出。
score >= 80 かつ high=0 で完了。

## Phase G: 登録

- alias 不要なら commit
- 改名/移動なら `aliases:` を追加

## Goodhart 罠回避

- 自Skillを自分で採点しない（必ず別Skill）
- score 80 を取るためにrubric改変する場合は `run-skill-rubric-governance` 経由

---

## Reproducibility Trace

`run-build-skill` は生成・更新ごとに `eval-log/skill-build-trace.json` を残す。目的は、task→refs map で選ばれた設計書を読んだ人が同じ入力から同じ判断順序を再現できる状態にすること。

最小 schema:

```json
{
  "skill_name": "<name>",
  "mode": "create|update",
  "source_docs": [
    "doc/ClaudeCodeスキルの設計書/<actually-read>.md"
  ],
  "context_map_decision": {
    "map": "creator-kit/skills/run-build-skill/references/resource-map.yaml",
    "task_category": "<selected category>",
    "selected_docs": ["doc/ClaudeCodeスキルの設計書/<selected>.md"],
    "reason": "<why these docs were sufficient>"
  },
  "design_model": {
    "intent": "<why>",
    "contract": "<input/output/done>",
    "boundary": ["<non-goal>"],
    "execution": ["skill|subagent|hook|mcp|cli|script"],
    "feedback": ["lint|evaluator|elegant-review|governance|usage-log"]
  },
  "build_flow_coverage": [
    {"step": "problem-definition", "status": "PASS", "evidence": "SKILL.md#Purpose & Output Contract"},
    {"step": "execution-layer", "status": "PASS", "evidence": "skill-build-trace.json#layer_decisions"},
    {"step": "classification", "status": "PASS", "evidence": "frontmatter.kind"},
    {"step": "naming", "status": "PASS", "evidence": "frontmatter.name"},
    {"step": "frontmatter", "status": "PASS", "evidence": "SKILL.md frontmatter"},
    {"step": "body", "status": "PASS", "evidence": "SKILL.md body"},
    {"step": "support-files", "status": "PASS|N/A", "evidence": "references/|scripts/|templates/"},
    {"step": "permissions-hooks", "status": "PASS|N/A", "evidence": "allowed-tools|settings hook"},
    {"step": "validation", "status": "PASS", "evidence": "eval-log or command output"},
    {"step": "operation-improvement", "status": "PASS", "evidence": "Gotchas|feedback log"}
  ],
  "doc_coverage": [
    {"doc": "02-skill-structure", "status": "PASS", "evidence": "placement|Additional Resources|Reference/Task boundary"},
    {"doc": "03-frontmatter", "status": "PASS", "evidence": "frontmatter|description|rubric_refs/reference_refs/script_refs"},
    {"doc": "04-invocation-permissions", "status": "PASS|N/A", "evidence": "allowed-tools|permissions|hooks", "reason": "<required when N/A>"},
    {"doc": "05-layering", "status": "PASS", "evidence": "layer_decisions + deterministic checks moved to script/hook"},
    {"doc": "06-classification-naming", "status": "PASS", "evidence": "variant_support + validated name/prefix/role_suffix"},
    {"doc": "07-progressive-disclosure", "status": "PASS", "evidence": "SKILL.md line budget + Additional Resources + resource-map when needed"},
    {"doc": "08-skill-writing-guidelines", "status": "PASS", "evidence": "description 2..3 triggers + body <=300 + Gotchas escalation path"},
    {"doc": "09-evaluation-orchestration", "status": "PASS", "evidence": "rubric_refs + fork evaluator + evaluator:N/A reason when skipped"},
    {"doc": "10-subagents-hooks-integration", "status": "PASS|N/A", "evidence": "Subagent/Hook layer_decisions + permissions.deny/PostToolUse proposal", "reason": "<required when N/A>"},
    {"doc": "11-templates", "status": "PASS", "evidence": "selected template path + rendered frontmatter/body"},
    {"doc": "13-checklists", "status": "PASS", "evidence": "P0/P1/P2 checklist items mapped to lint/evaluator/governance gates"},
    {"doc": "14-dynamic-context-injection", "status": "PASS|N/A", "evidence": "cross_platform/os_preamble_required + OS preamble or N/A reason", "reason": "<required when N/A>"},
    {"doc": "15-official-source-notes", "status": "PASS", "evidence": "ref-yaml-spec-fetcher/yaml-spec-cache.md checked + source date"},
    {"doc": "16-official-skills-reference", "status": "PASS", "evidence": "frontmatter fields checked against official 15 fields + local metadata separation"},
    {"doc": "26-meta-skill-dogfooding", "status": "PASS|N/A", "evidence": "dogfooding_model + forked evaluator + eval-log path", "reason": "<required when N/A>"},
    {"doc": "27-rubric-governance-runbook", "status": "PASS|N/A", "evidence": "governance_model + rubric hash/version + impact/grace policy", "reason": "<required when N/A>"},
    {"doc": "28-script-execution-model", "status": "PASS|N/A", "evidence": "script_execution_model + contexts A-E + permission boundary", "reason": "<required when N/A>"},
    {"doc": "29-multi-project-rubric-composition", "status": "PASS|N/A", "evidence": "rubric_composition_model + ordered_refs + merge policy", "reason": "<required when N/A>"},
    {"doc": "30-paradigm-analogy-map", "status": "PASS|N/A", "evidence": "paradigm_analogy_model + placement_decision", "reason": "<required when N/A>"},
    {"doc": "31-output-routing-adapter-architecture", "status": "PASS|N/A", "evidence": "output_routing_model + route/registry/fallback/secret boundary", "reason": "<required when N/A>"}
  ],
  "layer_decisions": [
    {
      "layer": "Skill",
      "decision": "use",
      "deterministic": false,
      "reason": "<operational knowledge/workflow>",
      "placement_evidence": "<brief field or SKILL.md section>",
      "fallback": "<fallback or N/A reason>",
      "dependency_direction_ok": true,
      "macos_stdlib_ok": true
    },
    {"layer": "Subagent", "decision": "use|skip", "deterministic": false, "reason": "<parallel/expert context or not>", "placement_evidence": "<evidence>", "fallback": "<fallback or N/A reason>", "dependency_direction_ok": true, "macos_stdlib_ok": true},
    {"layer": "Hook", "decision": "use|skip", "deterministic": true, "reason": "<lifecycle guard or not>", "placement_evidence": "<evidence>", "fallback": "<fallback or N/A reason>", "dependency_direction_ok": true, "macos_stdlib_ok": true},
    {"layer": "MCP", "decision": "use|skip", "deterministic": true, "reason": "<external integration or not>", "placement_evidence": "<evidence>", "fallback": "<CLI/API/manual fallback>", "dependency_direction_ok": true, "macos_stdlib_ok": true},
    {"layer": "CLI", "decision": "use|skip", "deterministic": true, "reason": "<external executable or not>", "placement_evidence": "<evidence>", "fallback": "<script/manual fallback>", "dependency_direction_ok": true, "macos_stdlib_ok": true},
    {"layer": "script", "decision": "use|skip", "deterministic": true, "reason": "<deterministic check or not>", "placement_evidence": "<evidence>", "fallback": "<manual fallback or N/A reason>", "dependency_direction_ok": true, "macos_stdlib_ok": true}
  ],
  "variant_support": {
    "prefix": "run|ref|assign|wrap|delegate",
    "role_suffix": "generator|evaluator|contributor|delegate|none",
    "subagent": "required|optional|none",
    "hook": "required|optional|none"
  },
  "pattern_decisions": [
    {
      "pattern_ref": "orchestrator|hook-integrated|agent-team|evaluator-pair|delegate-external|wrap-safe",
      "decision": "use|skip",
      "reason": "<why this pattern applies or not>",
      "source_docs": ["doc/ClaudeCodeスキルの設計書/08-skill-writing-guidelines.md"],
      "reuse_target": "template|rubric|lint|hook|none",
      "negative_cases": ["<when not to use>"]
    }
  ],
  "script_execution_model": {
    "contexts": ["A", "B", "C", "D", "E"],
    "responsibility_matrix": "doc/ClaudeCodeスキルの設計書/28-script-execution-model.md#3-実行責務マトリクス",
    "priority_order": "E > C > D > B > A",
    "permission_boundary": "Hook/CI はフルパス、Stop/SubagentStop は read-only、adapter 以外は network 禁止",
    "scripts": [
      {
        "path": "scripts/<script-name>.py",
        "type": "lint|validate|format|render|extract|diff|guard|build|adapter",
        "allowed_contexts": ["C", "E"],
        "frontmatter_status": "PASS|PENDING_RENAME|EXCEPTION|N/A"
      }
    ]
  },
  "governance_model": {
    "rubric_version": "<version or N/A>",
    "rubric_hash": "sha256:<hash or N/A>",
    "proposal_required": "yes|no|N/A",
    "impact_assessment": "impact-report.json|N/A reason",
    "newly_failing_count": 0,
    "grace_period": "min 1 release / 30 days when newly_failing_count > 0",
    "roles": {
      "proposer": "<owner or N/A>",
      "reviewer": "<different owner or N/A>",
      "approver": "<different owner or N/A>",
      "tooling": "<owner or N/A>"
    }
  },
  "dogfooding_model": {
    "artifact_type": "skill|design-doc|script|config|agent",
    "adapter": "doc-to-skill-adapter.py|N/A",
    "forked_evaluator": "assign-skill-design-evaluator",
    "eval_log_path": "eval-log/<plugin>/<date>-score.jsonl",
    "recursive_checks": ["DRY", "Less is More", "Why-driven", "4conditions", "Gotchas", "Progressive Disclosure"]
  },
  "source_traceability": {
    "image_map_checked": "N/A|PASS",
    "evidence": "12-image-extraction-map.md only when source article/image extraction is part of the task",
    "reason": "<required when N/A>"
  },
  "reproducibility_gates": {
    "lint": "PASS|FAIL|N/A",
    "evaluator": "PASS|FAIL|N/A",
    "elegant_review": "PASS|FAIL|N/A",
    "governance": "PASS|FAIL|N/A"
  },
  "rubric_composition_model": {
    "status": "PASS|N/A",
    "ordered_refs": ["ref-skill-design-rubric", "{{DOMAIN_RUBRIC_REFS}}", "references/rubric.json"],
    "merge_strategy": "deep-merge",
    "conflict_policy": "most-specific-wins",
    "composition_hash_evidence": "eval-log/...json",
    "reason": "<required when N/A>"
  },
  "paradigm_analogy_model": {
    "status": "PASS|N/A",
    "primary_analogy": "ESLint plugin|pytest plugin|LSP|Terraform module|Unix command|Hexagonal Architecture",
    "matched_skill_concept": "skill|evaluator|hook|subagent|adapter|rubric",
    "limits": ["<where analogy breaks>"],
    "placement_decision": "<final placement based on canonical docs>",
    "reason": "<required when N/A>"
  },
  "output_routing_model": {
    "status": "PASS|N/A",
    "task_kind": "{{TASK_KIND}}",
    "payload_schema_version": "1.0",
    "route_ref": "creator-kit/config/output-routing.json.example",
    "adapter_registry_ref": "creator-kit/config/adapter-registry.json",
    "fallback": "local",
    "secret_boundary": "keychain-ref-only",
    "reason": "<required when N/A>"
  },
  "variable_contract": [
    {
      "name": "{{PROJECT_ROOT}}",
      "meaning": "対象プロジェクトのルート",
      "default": "実行時 cwd",
      "required": true,
      "not_applicable_when": "対象がプロジェクト外の単一ファイル",
      "source_trace": "user request or cwd"
    }
  ]
}
```

判定ルール:

- `build_flow_coverage` / `doc_coverage` / 完了必須 gate に FAIL が1つでもあれば未完成。
- evidence は実ファイル、frontmatter field、または eval-log のいずれかを指す。
- Hook / MCP / CLI / dynamic injection / pattern_refs を使わない場合も `N/A` または `skip` と理由を残す。空欄にしない。
- update モードでは変更した Step だけでなく、既存 Step が壊れていないことも再判定する。

---

## Phase H: 実装層詳細（B3/C4 パッチ）

### H.1 run-build-skill 引数詳細

| 引数 | 型 | デフォルト | 説明 |
|---|---|---|---|
| `skill_name` | string (required) | — | kebab-case スキル名 |
| `kind` | enum | — | run\|ref\|assign\|wrap\|delegate |
| `mode` | enum | create | create=新規作成 / update=増分改修 |
| `with_subagent` | flag | false | 指定時のみ Step7 の SubAgent 生成を実行 |
| `model` | enum | opus | build-subagent.py に渡すモデル名 |

引数の受け渡し例:
```
Skill(run-build-skill) skill_name=run-my-skill kind=run mode=create with_subagent model=opus
```

### H.2 SubAgent 生成の詳細実装

Step7 (`--with-subagent` 指定時のみ実行):

```bash
python3 creator-kit/skills/run-build-skill/scripts/build-subagent.py \
  --skill-name "$SKILL_NAME" \
  --skill-md "$OUT_BASE/$SKILL_NAME/SKILL.md" \
  --output-dir ".claude/agents/" \
  --model "${MODEL:-opus}"
```

生成される `.claude/agents/<skill-name>-subagent.md` の frontmatter:
```yaml
---
name: <skill-name>-subagent
description: <SKILL.md の description から自動生成>
tools: <allowed-tools から自動抽出>
model: opus  # PF-F3-001: デフォルト opus
---
```

### H.3 Hook 設定の実装詳細

`.claude/settings.json` に定義された hook の役割と実装:

| Hook | タイミング | スクリプト | 目的 |
|---|---|---|---|
| `PreToolUse` | Write/Edit 前 | `hook-guard-rubric.py` | rubric.json への不正書き込みを deny |
| `PostToolUse` | Write/Edit 後 | `hook-validate-skill-md.py` | SKILL.md の frontmatter を検証 |
| `SubagentStop` | assign-* 終了時 | `hook-verify-evaluator-json.py` | JSON contract 違反を exit 2 でブロック (PF-E2-001) |
| `PreCompact` | context compaction 前 | `hook-handoff.py` | handoff スナップショットを生成 |
| `PostCompact` | context compaction 後 | `hook-post-compact.py` | handoff から状態を復元 (PF-G3-001) |

### H.4 YAML 仕様自動取得の実装詳細

`ref-yaml-spec-fetcher` と GitHub Actions の役割分担:

```text
[GitHub Actions: update-yaml-spec.yml (週次)]
  build-yaml-spec-cache.py (TODO: 実装予定)
    ↓
  .claude/skills/ref-yaml-spec-fetcher/references/yaml-spec-cache.md を更新
    ↓
  git commit & push

[run-build-skill / validate-frontmatter.py]
  ref-yaml-spec-fetcher を Read して最新仕様を参照
    ↓
  03-yaml-frontmatter-reference.md との差分を確認
```

### H.5 evaluator ペア生成

generator として作った Skill に対し、`--with-evaluator` 指定時または
`brief.generate_pair_evaluator=true` の場合だけ対称 evaluator を生成する。
`jq` は使わず Python 標準ライブラリで brief を読む。

```bash
GEN_PAIR=$(python3 -c "import json; b=json.load(open('$BRIEF_PATH')); print('true' if b.get('generate_pair_evaluator') else 'false')")
if [[ "$WITH_EVALUATOR" == "true" ]] || [[ "$GEN_PAIR" == "true" ]]; then
  PAIR_NAME="assign-${SKILL_NAME#run-}-evaluator"
  RUBRIC_CSV=$(python3 -c "import json; print(','.join(json.load(open('$BRIEF_PATH')).get('rubric_refs',[])))")
  python3 "$SKILL_DIR/scripts/render-frontmatter.py" \
    --name "$PAIR_NAME" --kind assign \
    --template "$SKILL_DIR/templates/assign-evaluator.md" \
    --brief "$BRIEF_PATH" \
    --pair "$SKILL_NAME" \
    --rubric-refs "$RUBRIC_CSV" \
    --out "$OUT_BASE/$PAIR_NAME/SKILL.md"
  python3 "$SKILL_DIR/scripts/set-frontmatter-field.py" \
    --file "$OUT_BASE/$SKILL_NAME/SKILL.md" --key pair --value "$PAIR_NAME"
fi
```

### H.6 Hook 配線生成

Hook 統合スキルでは `brief.hook_events` から skeleton と settings proposal を生成する。
settings.json は権限設定を含むため自動 merge しない。

```bash
HOOK_EVENTS=$(python3 -c "import json; print(' '.join(json.load(open('$BRIEF_PATH')).get('hook_events',[])))")
if [[ "$WITH_HOOKS" == "true" ]] || [[ -n "$HOOK_EVENTS" ]]; then
  for event in $HOOK_EVENTS; do
    python3 "$SKILL_DIR/scripts/render-hook-skeleton.py" \
      --skill-name "$SKILL_NAME" --event "$event" \
      --out "scripts/hook-${SKILL_NAME}-$(echo "$event" | tr 'A-Z' 'a-z').py"
  done
  python3 "$SKILL_DIR/scripts/render-settings-proposal.py" \
    --skill-name "$SKILL_NAME" --brief "$BRIEF_PATH" \
    --out ".claude/settings.proposal.json"
fi
```

TODO(human): `scripts/build-yaml-spec-cache.py` の実装は、Claude Code 公式ドキュメントの
機械取得方法が確定した後に実施する。`llms.txt` または公式 API 経由の可否を確認すること。
