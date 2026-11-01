---
name: assign-system-spec-completeness-evaluator
description: 生成された仕様書ドキュメントセットの完成度を独立 context で評価したいとき、上位概念trace・意思決定・マトリクス網羅性・設計知識反映・最新ドキュメント出典・prompt品質の 6 観点で合否判定したいときに使う。
disable-model-invocation: false
user-invocable: false
context: fork
argument-hint: "[--spec-dir <path>] [--output <report_path>]"
arguments: [spec_dir, output]
kind: assign
prefix: assign
role_suffix: evaluator
version: 0.1.0
effect: local-artifact
owner: team-platform
since: 2026-07-11
source: plugins/system-spec-harness/skills/assign-system-spec-completeness-evaluator/references/scoring-rubric.json
source-tier: internal
last-audited: 2026-07-11
audit-trigger: quarterly
allowed-tools:
  - Read
  - Bash(python3 *)
  # 監査 fork の現行経路は Agent。Task は schema 1.1 台帳を書く legacy 経路として残す。
  - Agent
  - Task
responsibility_refs:
  - prompts/R1-score.md
  - prompts/R2-delegate.md
responsibilities:
  - id: R1-score
    name: score
    prompt_required: true
  - id: R2-delegate
    name: delegate
    prompt_required: true
completeness_exempt:
  - "manifest: assign evaluator is a single forked scoring gate; its rubric, schema and aggregate script are the runtime SSOT."
rubric_refs:
  - references/scoring-rubric.json
reference_refs:
  - references/resource-map.yaml
  - references/aspect-criteria.md
script_refs:
  - scripts/aggregate-completeness.py
  - scripts/validate-json-schema-subset.py
  - scripts/audit_fork_attribution.py
  - scripts/build-resume-receipt.py
  - ../../scripts/validate-coverage-matrix.py
  - ../../scripts/validate-source-citation.py
schema_refs:
  - schemas/completeness-findings.schema.json
  - schemas/resume-receipt.schema.json
agent_refs:
  - ../../agents/system-spec-matrix-auditor.md
  - ../../agents/system-spec-hearing-auditor.md
  - ../../agents/system-spec-doc-freshness-auditor.md
feedback_contract:
  skip_reason: "assign kind は loop criteria 対象外。合否基準は checklist の 6 評価観点 (foundation_trace/decision_guidance/prompt_quality=C05 自前評価 / matrix_coverage=C07 監査 + C06 ヒアリング品質 sub-input / design_knowledge_reflection=C05 自前評価 / doc_freshness=C08 監査) の evaluator ゲート、および validate-coverage-matrix.py の決定論ゲートで担保する。"
runtime_root_policy: host-skill-path
---

# assign-system-spec-completeness-evaluator

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

> 生成された仕様書ドキュメントセットを、上位概念trace / 意思決定根拠 / マトリクス網羅性 / deep knowledge目的適合 / 最新出典 / prompt品質の観点で評価し、観点別スコア + 総合判定 (PASS/FAIL) + 不足事項一覧を返す independent evaluator。`context:fork` で生成者と評価者を分離する。

## Purpose & Output Contract

**入力**: `system-spec/` 配下の全 Markdown (`Path.rglob("*.md")`) + index (C03 出力) / `spec-state.json` (C01) / `fetched-references.json` (C02)
**出力**: 評価レポート (`schemas/completeness-findings.schema.json` 準拠) — 観点別スコア + 総合判定 + 不足事項一覧。総合 PASS で呼び出し側が再利用 receipt を求めたときだけ、正規 validator と fork 台帳へ束縛した `system-spec/resume-receipt.json` も生成する (Step 4)。
**完了条件**: 全観点 verdict 付与 + findings[] (info 以上を最低 1 件) + 総合判定が観点スコアからの fail-closed 再導出値と一致 + 総合 FAIL 時は不足事項一覧が非空 + `aggregate-completeness.py --report <output> --spec-dir <spec_dir>` が exit 0 (Step 4)。評価開始前に production writer の `--print-artifact-snapshot` で入力を固定し、その JSON を評価レポートの `artifact_snapshot` へ改変せず格納する。PASS の再利用は `build-resume-receipt.py` が作った resume-receipt schema 1.2 に限る (fork 台帳 schema 1.1 / 1.2 とは別の version 軸)。writer はレポートのスナップショットと現在値の完全一致を要求し、固定ゲート入力と `system-spec/` 配下の全 Markdown を個別 digest へ束縛する。

各 skill 単独では見えない全体網羅性の欠落を、生成物から独立した context で評価し客観的合否を返す。

**禁則の要約** (詳細は Key Rules): 仕様書を書き換えない / `spec_dir` に説明や注記を混ぜない / high finding が 1 件でもあれば総合 FAIL / fork していない監査の receipt を書かない。

## 監査 sub-agent 対応 (全 6 観点中、評価主体の割当に注意が要る 3 観点)

> 本 skill は全 6 観点 (上位概念trace / 意思決定 / マトリクス網羅性 / 設計知識反映 / 最新ドキュメント出典 / prompt品質) を採点する (schema/rubric/aggregate-completeness の正本)。うち foundation_trace / decision_guidance / prompt_quality は C05 R1-score の自前評価。以下は評価主体の割当に注意が要る 3 観点 (監査 sub-agent が担う 2 観点と、独立 auditor を立てない設計知識反映) の対応表。

| 観点 (aspect id) | ラベル | 評価主体 (component) | 一次根拠 |
|---|---|---|---|
| `matrix_coverage` | マトリクス網羅性 | `system-spec-matrix-auditor` (C07) + sub-input `system-spec-hearing-auditor` (C06) | `validate-coverage-matrix.py --require-complete` の exit0 + 意味層。C06 のヒアリング監査 (run-system-spec-elicit の R6-audit-hearing の監査 5 軸 = 聞き漏れ/誘導/早期停止/セルのトレーサビリティ/foundation の利用者根拠) を網羅性・トレースの補助根拠に併せる。判定への対応は `references/aspect-criteria.md` 1a (決定論実装 `aggregate-completeness.py --hearing ... --state ...`) |
| `design_knowledge_reflection` | 設計知識反映 | C05 R1-score が自前評価 (**独立 auditor なし**) | 機械層=各章の設計知識ポインタ存在 (compile 注入) + 意味層=そのポインタ原則の確定セルへの具体適用 (存在確認だけで PASS にしない = Goodhart 防止) |
| `doc_freshness` | 最新ドキュメント出典 | `system-spec-doc-freshness-auditor` (C08) | 二層監査 (形式=`validate-source-citation.py` / 内容鮮度=公式再照合) |

> `system-spec/` 配下の Markdown を読まない C06 (hearing-auditor) を設計知識反映へ束縛するのは虚偽対応のため撤去した。C06 はヒアリング品質を担い matrix_coverage の sub-input へ再配置し、設計知識反映は C05 が全 Markdown と resource-map から自前評価する。監査 sub-agent (C07/C08 と matrix sub-input の C06) は現行 `Agent` tool でそれぞれ独立 context (fork) に起動する (`Task` は legacy 互換のみ、R2-delegate)。監査ロジックは各 agent の SSOT prompt に委ね、本 skill は結果を集約するだけで書き換えない。

## 知識グラフ / doctrine の追加評価次元 (C13-C16)

> 上位 6 観点の top-level 構造 (aggregate-completeness.py の 6 aspect fail-closed 集約) は不変。C13-C16 の知識グラフ / doctrine 要件は新 aspect を増やさず、既存 aspect の追加評価次元として折り込む (各 `validate-knowledge-graph.py --profile ...` の exit0 を機械層、生成物への反映を意味層で採点)。

| 追加次元 | 折込先 aspect | 機械層ゲート | 意味層で拾う失敗 |
|---|---|---|---|
| **C13** 知識カタログが typed 辺グラフ | design_knowledge_reflection | `validate-knowledge-graph.py --profile knowledge` exit0 (循環/dangling/孤立/root到達不能 0) | knowledge-catalog の depends_on/refines/conflicts_with 型則違反・孤立 node の設計知識への未接地 |
| **C14** elicit/compile が同一 topo_order で知識消費 | design_knowledge_reflection | 上記 `--profile knowledge --order` の topo_order を C01 R5 / C03 R2 が同一順で消費 | 上位概念→下位概念の位相順を破って下位技術を先に確定した章 |
| **C15** doctrine anchor 1正本 + 全 category 写像全射 | design_knowledge_reflection | `validate-knowledge-graph.py --profile doctrine` exit0 (7 concern の concern_id 一意 + 各 authority 非空・全 category→concern 写像全射。authority は 4 種で concern 間共有可・authority 一意性は非検査) | 生成章に concern authority (Apple HIG/Clean Arch/OWASP/SRE) の上流指針が具体反映されず汎用ポインタ止まり |
| **C16** 必須情報カタログの被覆 + block ゲート | matrix_coverage | `validate-knowledge-graph.py --profile required-info` exit0 (全 in-scope domain 被覆・item 最低形状・収集順序・coverage certificate) | `missing_effect=block` の item 未回答のまま confirmed に進んだ確定セル (C01 R5 収集ゲート素通り。機械層ゲート validate-knowledge-graph.py (component C14) は blocking_items 列挙のみで runtime 施行せず・決定論 writer 施行は follow-up) |

> C15 の意味層は「存在確認だけで PASS にしない」= design_knowledge_reflection の Goodhart 防止と同一原則で、doctrine anchor が確定セル要件へ具体適用されているかを照合する。C16 は matrix_coverage の網羅性判定に「必須情報が block ゲートを通って確定に接地しているか」を加える。

## 評価レポート形状 (schema)

```
{
  "evaluator": {"name": "assign-system-spec-completeness-evaluator", "version": "0.1.0", "context": "fork"},
  "spec_dir": "<引数 spec_dir の値そのまま>",
  "verdict": "PASS" | "FAIL",
  "artifact_snapshot": {"schema_version": "system-spec-artifact-snapshot/v1", "artifacts": {"system-spec/index.md": "<sha256>", "...": "..."}},
  "audit_delegations": [
    {"aspect": "matrix_coverage", "role": "primary",   "auditor": "system-spec-matrix-auditor",
     "component": "C07", "dispatch": {"tool": "Agent", "subagent_type": "system-spec-matrix-auditor",
     "session_id": "...", "tool_use_id": "...", "response_sha256": "..."},
     "verdict": "PASS", "evidence": ["..."]},
    {"aspect": "matrix_coverage", "role": "sub_input", "auditor": "system-spec-hearing-auditor",  "component": "C06", ...},
    {"aspect": "doc_freshness",   "role": "primary",   "auditor": "system-spec-doc-freshness-auditor", "component": "C08", ...}
  ],
  "aspects": {
    "foundation_trace":             {"verdict": "...", "auditor": "assign-system-spec-completeness-evaluator", "component": "C05", "summary": "...", ...},
    "decision_guidance":            {"verdict": "...", "auditor": "assign-system-spec-completeness-evaluator", "component": "C05", "summary": "...", ...},
    "matrix_coverage":              {"verdict": "PASS|FAIL|INDETERMINATE", "auditor": "system-spec-matrix-auditor", "component": "C07", "summary": "...", "evidence": [...]},
    "design_knowledge_reflection":  {"verdict": "...", "auditor": "assign-system-spec-completeness-evaluator", "component": "C05", "summary": "...", ...},
    "doc_freshness":                {"verdict": "...", "auditor": "system-spec-doc-freshness-auditor", "component": "C08", "summary": "...", ...},
    "prompt_quality":               {"verdict": "...", "auditor": "assign-system-spec-completeness-evaluator", "component": "C05", "summary": "...", ...}
  },
  "gate_results": [
    {"id": "G-matrix", "name": "validate-coverage-matrix", "exit_code": 0, ...},
    {"id": "G-source-citation", "name": "validate-source-citation", "exit_code": 0, ...},
    {"id": "G-knowledge-graph", "name": "validate-knowledge-graph", "exit_code": 0,
     "subgates": [{"profile": "knowledge", "command": [...], "exit_code": 0, "stderr": ""}, ...]}
  ],
  "findings": [ {"severity": "high|medium|low|info", "bucket": "...", "observation": "...", "suggested_fix": "..."} ],
  "gaps": [ "不足事項1", ... ]
}
```

## 帰属の接地 (attribution / fail-closed)

> **本節は要約であり、dispatch 規約の正本は `prompts/R2-delegate.md` Layer 1.1。** 差分が生じたら R2-delegate.md を優先する (二重正本を作らない)。

> `aspects[].auditor` は評価者自身が書く文字列であり、それ単体では独立監査の実在を示さない。旧実装は定数との文字列一致しか見ておらず、**監査を 1 件も fork しない実行でも「独立 auditor が PASS を出した」と名乗るレポートが `--report` を exit 0 で通過できた**。監査 agent は `Write` を持たず自力で痕跡を残せないため、証跡は「モデルが書けない層」= PostToolUse hook に書かせる。

| 必須 receipt (`audit_delegations[]`) | role | auditor | component |
|---|---|---|---|
| `matrix_coverage` | `primary` | `system-spec-matrix-auditor` | C07 |
| `matrix_coverage` | `sub_input` | `system-spec-hearing-auditor` | C06 |
| `doc_freshness` | `primary` | `system-spec-doc-freshness-auditor` | C08 |

- 証跡台帳: `eval-log/system-spec-harness/audit-fork-ledger.jsonl` (writer = `hooks/record-audit-fork.py`。PostToolUse: `Task|Agent` が dispatch 行、`SubagentStop` が completion 行 (schema 1.3) を書く)。`--fork-ledger` または env `SYSTEM_SPEC_AUDIT_FORK_LEDGER` で上書き可。
- C05 自前評価の 4 観点に `primary` receipt を付けるのは **虚偽の独立性主張** として violation。
- 台帳が無い/空 = 裏取り 0 件 → fail-closed で violation (緑にしない)。
- **PostToolUse の per-call 契約**: 現行 PostToolUse は matching tool call ごとに 1 回、top-level `tool_use_id` と当該 call の `tool_response` を渡す。parallel dispatch 時も call ごとの hook が並行発火し、batch 全体の lifecycle は PostToolBatch が担う。writer は schema 1.2 で top-level `tool_use_id` / `verdict_state` と、**当該 per-call `tool_response` 全体**の canonical digest を記録する。nested ID block を探索して response の一部だけを digest 化しない。
- **run/session・response・ID 束縛**: schema 1.2 の receipt `dispatch.{session_id,tool,subagent_type,tool_use_id,response_sha256}` と receipt `verdict` を、台帳が hook 観測した同一 call の値へ全一致で束縛し、`verdict_state=resolved` だけを受理する。schema 1.1 台帳は `tool_use_id` を持たない旧 `Task` 専用の legacy 互換として従来の `session_id` / tool / subagent / digest / verdict で照合する。現行 `Agent` は必ず schema 1.2 + `tool_use_id` へ接地し、ID 欠落・不一致を 1.1 へ downgrade して通してはならない。必須 receipt の session は単一 run に収束させ、`--session <id>` で現在 session との一致まで検査する。
- **正式 evaluator 運用の直列化 gate**: per-call hook 仕様と parallel 対応コードの存在だけでは正式運用を parallel へ昇格しない。current runtime の fresh live-trial で 3 fork 全ての schema 1.2 行、ID / digest / verdict 照合、最終 receipt 生成が成立するまで、1 回の assistant message では 1 件だけを foreground 起動する。完全 response の最終行 `AUDIT_VERDICT` と PostToolUse 台帳行を確定してから次へ進む。parallel support は defensive hardening / canary であり正式許可ではない。
- **background は最終 verdict ではない**: background/非同期 launch の「起動済み」応答は監査の最終 response ではない。writer は現行 `Agent` の `tool_response.status=completed` だけを verdict 確定対象とし、それ以外を marker の有無にかかわらず `verdict_state=pending` / `audit_verdict=null` にする。旧 `Task` は status 欠落を互換受理するが、status が明示された場合は `completed` 以外を未完了として扱う。現行 `Agent` の top-level `tool_use_id` 欠落も schema 1.1 へ downgrade しない。`verdict_state=pending|absent|ambiguous`、または `audit_verdict=null` の台帳行は receipt に使えない。
- **2 行 join (schema 1.3 / 非同期 fork)**: 非同期・background 起動は、上の直列化 gate が解除されるまで canary 専用である。本項と次項の token・completion digest の規則は、その canary と gate 解除後の運用に適用する。台帳は 1 fork につき最大 2 行を持つ。PostToolUse が書く **dispatch 行 (schema 1.2)** と、`SubagentStop` が書く **completion 行 (schema 1.3)** である。両者を繋ぐ join key は R2 が起動 prompt 先頭へ置く `AUDIT_DISPATCH: <token>` の 1 行 (`[A-Za-z0-9._-]{8,64}`・session 内で一意・使い回さない) で、auditor は同じ 1 行を応答本文へ 1 回だけ echo する。ハーネスは親の `tool_use_id` と子の `agent_id` を繋ぐ field を提供しないため、token を発行しない並列起動は帰属が一意に決まらず `verdict_state=pending` のまま fail-closed になる (単発の 1 対 1 起動に限り読取側が fallback 昇格する)。token は R2 が発行するだけで、台帳へは書かない。
- **非同期 fork の `response_sha256` は completion 行の digest**: 非同期起動の per-call `tool_response` は起動受理 payload であって監査結果を含まない。これを receipt の束縛先にすると「起動しただけ」が verdict の根拠になる。読取側は dispatch 行を completion 行で `resolved` へ昇格させ、昇格後の digest を照合対象にする。同期 fork では従来どおり per-call `tool_response` 全体の digest を使う。
- **監査 fork に `name` を付けない**: `name` 付き Agent は `taskKind=in_process_teammate` になり、最終応答を返した後も session 終端まで生存するため `SubagentStop` が発火しない。completion 行が永久に書かれず dispatch 行が `pending` のまま残る。加えて payload の `agent_type` が `name` の値になり (`customAgentType` が本来の auditor 名を持つ) `subagent_type` 照合も外れる。監査 fork は `subagent_type` だけを指定して起動する。
- **台帳の書込み権限**: `audit-fork-ledger.jsonl` は PostToolUse / SubagentStop hook の append-only 出力であり、評価者が手書き・補正してはならない。`prompt_sha256` / `response_sha256` が空・`manual`・64桁16進数以外、または response 最終行の `AUDIT_VERDICT` marker が無効な行は集約対象から除外される。
- **機械層の限界 (正直な境界)**: 台帳は実際の response が返した verdict の書換えを拒否するが、監査 prompt の意味的十分性や証拠の妥当性そのものは content-review / human が検証する。台帳ファイルを意図的に改ざん可能な実行環境では hook 証跡だけで完全な敵対者耐性は得られないため、書込み権限の分離も必要である。

## 総合判定 (fail-closed 集約)

- 全観点PASS **かつ** high severity finding 0 件のときだけ総合 PASS。
- 1 観点でも FAIL/INDETERMINATE、または high finding が 1 件でもあれば総合 FAIL。
- 全観点を過不足なく評価していなければ総合 FAIL (監査観点の取りこぼしを PASS にしない)。
- 総合判定は `scripts/aggregate-completeness.py` の `aggregate_verdict` で再導出でき、レポートの `verdict` と一致すること (総合判定が観点スコアに接地しているかの整合検査 = Goodhart 防止)。

## Key Rules

1. **context:fork 必須**: 生成側 (elicit/doc-fetch/compile) の「網羅できた」自己肯定バイアスを断つ。
2. **proposer ≠ approver**: 評価者は仕様書を書き換えない (read-only)。修正は elicit/doc-fetch/compile への差し戻し (Goodhart 防止)。
3. **決定論ゲート優先**: マトリクス網羅性は `validate-coverage-matrix.py` の exit code を一次根拠にし、自然言語で PASS 判定しない。
4. **空 findings 禁止**: PASS 時も info severity で「確認した観点」を 1 件以上残す。
5. **総合 FAIL は差し戻し材料付き**: gaps (不足事項一覧) を非空にし、どの skill (elicit/doc-fetch/compile) または監査再実行へ戻すかを記す。

## Steps

正本責務は `prompts/R1-score.md` (スコアリング) と `prompts/R2-delegate.md` (監査 fork 集約)。要約:

### Step 0: 評価入力を固定
監査を始める前に次を実行し、stdout の JSON 全体を保持する。この後に入力が変わった場合は継続せず、Step 0 から新しい評価 run を開始する。snapshot は `<repo-root>/system-spec` 配下を読むため、`--repo-root` には `spec_dir` の親 dir を渡す (既定の `spec_dir=system-spec` を repo root から起動したなら `$CLAUDE_PROJECT_DIR`)。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/assign-system-spec-completeness-evaluator/scripts/build-resume-receipt.py" --repo-root "$CLAUDE_PROJECT_DIR" \
  --print-artifact-snapshot
```

### Step 1: 観点別監査を独立 context で集約 (R2-delegate)
現行 `Agent` tool で監査 sub-agent (`system-spec-matrix-auditor` (C07) / `system-spec-hearing-auditor` (C06) / `system-spec-doc-freshness-auditor` (C08)) をそれぞれ fork する (`Task` は legacy 互換のみ)。PostToolUse 自体は per-call だが、正式 evaluator 運用は fresh live-trial で schema 1.2 の end-to-end 帰属を実証するまで **1 message = 1 foreground fork** で直列実行する。C07 は matrix_coverage、C08 は doc_freshness の一次根拠。C06 はヒアリング品質を監査し matrix_coverage の sub-input として併せる。C06 の verdict はそのまま使わず、`python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/assign-system-spec-completeness-evaluator/scripts/aggregate-completeness.py" --hearing <C06 出力> --state <spec-state.json>` で sub-input の判定を導く (注記と閉じた検出は findings に残し gaps に入れない。C06 出力を `hearing-audit.json` へ保存する手順は `prompts/R2-delegate.md` 2.4)。design_knowledge_reflection は独立 auditor を立てず Step 3 で C05 自身が評価する。

### Step 2: マトリクス網羅性の決定論ゲート
```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/assign-system-spec-completeness-evaluator/scripts/aggregate-completeness.py" --matrix <spec-state.json> --require-complete
```
exit0 をマトリクス網羅性観点の一次根拠にする (内部で `validate-coverage-matrix.py --require-complete` を実行し、結果を `G-matrix` の gate_result として出す)。

続けて出典記録の決定論ゲート (`G-source-citation`。receipt writer と同じ `validate-source-citation.py --targets <spec-state.json> --references <fetched-references.json> --state <spec-state.json> --repo-root <repo-root>` を実行する) を回収する。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/assign-system-spec-completeness-evaluator/scripts/aggregate-completeness.py" \
  --source-citation <fetched-references.json> --state <spec-state.json> --repo-root "$CLAUDE_PROJECT_DIR"
```

続けて C13-C16 の機械層ゲートを `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/assign-system-spec-completeness-evaluator/scripts/aggregate-completeness.py" --knowledge-graph` (出荷 3 カタログを `validate-knowledge-graph.py` の knowledge/doctrine/required-info/cross 4 profile で独立再実行) の全 exit0 で確認する。C13/C14/C15 は design_knowledge_reflection (Step 3)、C16 は matrix_coverage の追加評価次元として意味層採点に併せる。

`--matrix ... --require-complete`・`--source-citation ...`・`--knowledge-graph` の 3 つの stdout JSON (`G-matrix` / `G-source-citation` / `G-knowledge-graph`) を、無改変でレポートの `gate_results` に入れる。総合 PASS のレポートは 3 gate すべての exit 0 (`G-knowledge-graph` は 4 profile すべての exit 0) が無いと `--report` の検査で落ちるため、exit code を自己申告で埋めない。

### Step 3: 設計知識反映の自前評価 (独立 auditor なし)
C05 R1-score が `system-spec/` 配下の全 Markdown (`Path.rglob("*.md")`) を直接読み、`ref-system-design-knowledge/references/resource-map.yaml` 由来の設計知識ポインタの (1) 存在 (機械層) と (2) その原則が確定セル要件へ具体適用されているか (意味層) を評価する。**存在確認だけで PASS にしない** (compile が機械注入するポインタを自己循環で肯定しない = Goodhart 防止)。汎用ポインタ (resource-map 索引) のみで具体適用が無い章は medium 以上で拾う。C06 のヒアリング品質監査は本観点でなく matrix_coverage の sub-input として使う。

### Step 4: レポート出力と整合検査
`schemas/completeness-findings.schema.json` 準拠で評価レポートを出力し、Step 0 の JSON を `artifact_snapshot` へ改変せず格納し、Step 1 で実際に fork した監査を `audit_delegations[]` へ receipt として記録する。schema 1.2 台帳を使う receipt は hook 観測の `tool_use_id` も `dispatch` へ転記する。
- 相対の `spec_dir` と `output` は、この skill を起動した cwd から解決する。評価の入力の読み込み、レポートの書き出し、下の `--report <output> --spec-dir <spec_dir>` の検証は、どれも同じ cwd を基準にする。repo 相対の値を渡す呼び出し側 (dev-graph の C19 など) は、起動の前に cwd が repo root と同じことを確かめる。
- `spec_dir` には引数 `spec_dir` の値をそのまま書く (相対パスなら相対のまま)。説明や注記を足さない。
- レポートは引数 `output` のパスに書く。そのパスは `system-spec/` の外に置き、書き出しのコマンドの中に文字列のリテラルで書く (変数・`sys.argv`・`$` を使わない。書き方は `prompts/R1-score.md` の 4.3)。`guard-confirmed-chapter-overwrite.py` は、書き先を判定できて保護領域の外ならば、本文に `system-spec` が出てきても通す。
- `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/assign-system-spec-completeness-evaluator/scripts/aggregate-completeness.py" --report <output> --spec-dir <spec_dir>` で、形状 + 総合判定整合 (fail-closed 再導出との一致) + 帰属の fork 証跡接地と、`spec_dir` が引数と同じ dir に解決することを検証する。評価 run 直後の検証では `--session <現在の session_id>` を併用する。`spec_dir_mismatch` の report は、呼び出し側 (dev-graph の C02 など) が確定の取込を拒む。

総合 PASS で、呼び出し側が再利用 receipt を求めた場合だけ、同じ report・fork ledger・具体的 session を production writer へ渡す。writer が受け付ける report は canonical の `system-spec/completeness-report.json` だけ (`schemas/resume-receipt.schema.json` の `evaluator.report_path`) なので、この場合に限り、呼び出し側は `output` にそのパスを渡し、レポートをそこへ書く (`output` を `system-spec/` の外に置く規則の唯一の例外。別のパスのまま receipt を求められたら、書かずに差し戻す。`.json` を文字列のリテラルで書けば guard は通す)。writer は `G-matrix` / `G-source-citation` / `G-knowledge-graph` (4 profile) を自分で再実行し、report の `gate_results` の exit 0 と ledger の response/session 帰属を検査してから、report digest を束縛した receipt を atomic に生成する。手書き receipt や test fixture の producer を実行時に使わない。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/assign-system-spec-completeness-evaluator/scripts/build-resume-receipt.py" --repo-root "$CLAUDE_PROJECT_DIR" \
  --report system-spec/completeness-report.json \
  --fork-ledger eval-log/system-spec-harness/audit-fork-ledger.jsonl \
  --session <current-evaluator-session> \
  --output system-spec/resume-receipt.json
```

## Gotchas

1. 観点↔評価主体を取り違えない (マトリクス=C07 + C06 ヒアリング品質 sub-input / 設計知識=C05 自前評価・独立 auditor なし / 出典鮮度=C08)。C06 は仕様書 Markdown を読まないため設計知識反映へ束縛しない。
2. `audit_delegations[]` は「fork したことにする」ための宣言欄ではない。Step 1 で実際に現行 `Agent` (`Task` は legacy) で fork した監査だけを記録する。台帳と突合されるため、fork していない監査の receipt を書いても `--report` は通らない。
3. 決定論ゲート exit0 でも、意味層 (対象外理由の具体性 / 非公式 host / 設計知識反映の形骸化) で FAIL にしうる。
4. high severity が 1 件でもあれば総合 FAIL。
5. INDETERMINATE は fail-closed で FAIL に寄せ、仕様書修正でなく監査再実行/入力補完へ差し戻す。
6. 本 skill は kind=assign のため feedback_contract.criteria は N/A (評価器自身は評価基準を携帯せず、checklist 観点 + evaluator ゲートで担保。frontmatter の skip_reason 参照)。
7. 監査 fork の起動に `name` を付けない (`SubagentStop` が発火せず completion 行が書かれないため、帰属が `pending` のまま閉じない)。非同期起動では `AUDIT_DISPATCH: <token>` を発行し、receipt の `response_sha256` は completion 行 (schema 1.3) の digest にする。起動受理 payload の digest を使わない。
8. 検査用の一時 script でキー名・対象 id・症状パターンを手で列挙しない。対象集合を先に決めてから探す検査は、決めた集合の外を「無い」と報告する (規約の正本 = `prompts/R1-score.md` Layer 1.1「走査は対象集合を先に決めない」)。
9. parallel fixture / unit test が PASS しても正式 evaluator の直列化を解除しない。解除条件は current runtime の fresh live-trial で 3 件全ての schema 1.2 `tool_use_id` / whole-response digest / `verdict_state=resolved` と receipt 照合を確認すること。
10. Step 0 後に Markdown・固定ゲート入力が追加・変更・削除されたら、古い評価レポートへ現在値を取り込まない。writer の snapshot mismatch を受けて評価全体を再実行する。
11. `spec_dir` に説明や注記 (`(read-only で評価)` など) を混ぜない。書き出しが guard に止められても、`spec_dir` の値を変えて回避しない。guard が止めるのは書き先を判定できないときなので、保存先を `system-spec/` の外の文字列のリテラルにして書き直す (Step 4)。
12. Step 0 の snapshot と再利用 receipt は `<repo-root>/system-spec` に固定されている。basename が `system-spec` でない `spec_dir` は snapshot で固定できないため、評価を始めず呼び出し側へ差し戻す (別の dir の snapshot を `artifact_snapshot` に入れない)。

## Additional Resources

- `references/scoring-rubric.json` — 全 6 観点機械判定ルールと fail-closed 集約ポリシー
- `references/aspect-criteria.md` — 観点別意味判定の詳細基準 + 観点↔監査 agent 対応
- `schemas/completeness-findings.schema.json` — 評価レポート出力スキーマ
- `scripts/aggregate-completeness.py` — 公開 schema によるレポート形状検証 + 総合 fail-closed 集約 + 帰属の fork 証跡接地検証 (決定論、外部 Python package 不要)
- `scripts/validate-json-schema-subset.py` — `completeness-findings.schema.json` が出荷する Draft 7 語彙だけを stdlib で解釈する import 専用 module。未知 keyword / 非対応形状 / 非 local または未解決 `$ref` は schema 構築時に fail-closed で拒否する。`pattern` は edge anchor + ASCII literal + 正の英数字 class/range + 基本 quantifier の portable subset のみで、escape / dot / group / alternation / lookaround / negated class は受理しない
- `scripts/audit_fork_attribution.py` — fork 台帳集計・schema 1.2 の tool-use ID を含む receipt 照合・run/session 束縛、および schema 1.1 legacy 互換を担う import 専用モジュール。公開 CLI と総合判定は `aggregate-completeness.py` が継続して所有する
- `scripts/build-resume-receipt.py` / `schemas/resume-receipt.schema.json` — canonical PASS report、gate 結果、fork ledger session、固定ゲート入力と `system-spec/` 全 Markdown の artifact digest に束縛した再利用 receipt の production writer / schema
- `../../hooks/record-audit-fork.py` — 監査 fork 台帳 writer。PostToolUse (`Task|Agent`) が dispatch 行 (schema 1.2: top-level `tool_use_id` / `verdict_state` / whole per-call response digest) を、`SubagentStop` が completion 行 (schema 1.3) を書き、`AUDIT_DISPATCH` token で 2 行を接合する帰属検証の証跡正本
- `prompts/R1-score.md` / `prompts/R2-delegate.md` — R1 (スコアリング) / R2 (監査 fork 集約) 責務正本
- fork 先 agent: `../../agents/system-spec-{matrix,hearing,doc-freshness}-auditor.md`
