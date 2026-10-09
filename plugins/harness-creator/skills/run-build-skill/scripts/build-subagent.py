#!/usr/bin/env python3
# /// script
# name: build-subagent
# purpose: Emit a Claude Code subagent markdown derived from a SKILL.md
# inputs:
#   - argv: --skill-name, --skill-md, --output-dir, --model
# outputs:
#   - file: <output-dir>/<skill-name>-subagent.md
#   - stdout: generated path
# contexts: [C]
# network: false
# write-scope: output-dir
# dependencies: []
# ///
"""Generate a subagent definition (.claude/agents/<name>-subagent.md) from a
SKILL.md. Stdlib only. Simple YAML 1-level parser tuned for SKILL frontmatter.

Usage:
  build-subagent.py --skill-name run-build-skill \\
      --skill-md /path/to/SKILL.md \\
      [--output-dir .claude/agents/]

Output format (Anthropic Claude Code subagent spec):
  ---
  name: <skill-name>-subagent
  description: <from SKILL.md description>
  tools: <comma-joined from allowed-tools>
  model: opus  # default changed to opus (PF-F3-001)
  ---
  # role / thinking / output sections derived from SKILL.md
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_raw, body = parts[1], parts[2]
    fm: dict = {}
    cur_list_key: str | None = None
    for line in fm_raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") and cur_list_key:
            fm[cur_list_key].append(line[4:].strip())
            continue
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val == "":
            fm[key] = []
            cur_list_key = key
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            fm[key] = [v.strip() for v in inner.split(",") if v.strip()] if inner else []
            cur_list_key = None
        else:
            fm[key] = val.strip().strip('"').strip("'")
            cur_list_key = None
    return fm, body


def extract_section(body: str, heading: str) -> str:
    pat = re.compile(rf"^{re.escape(heading)}\s*$", re.MULTILINE)
    m = pat.search(body)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"^##\s", body[start:], re.MULTILINE)
    end = start + nxt.start() if nxt else len(body)
    return body[start:end].strip()


def map_tools(allowed: list[str] | str) -> str:
    if isinstance(allowed, str):
        items = re.split(r",\s*(?![^(]*\))", allowed)
    else:
        items = list(allowed or [])
    # strip parenthesized arg patterns: "Bash(python3 *)" -> "Bash"
    cleaned = []
    seen = set()
    for t in items:
        base = re.split(r"[\s(]", t, 1)[0].strip()
        if base and base not in seen:
            cleaned.append(base)
            seen.add(base)
    return ", ".join(cleaned)


def resolve_language(body: str, requested: str = "auto") -> str:
    if requested != "auto":
        return requested
    for language, heading in (("ja", "## 選んだ深さでの改善の実行"), ("en", "## Post-choice selected improvement execution")):
        if re.search(rf"^{re.escape(heading)}[ \t]*$", body, re.M):
            return language
    return "ja" if re.search(r"^## 目的と出力契約[ \t]*$", body, re.M) else "en"


def render_agent_body(name: str, purpose: str, source_operations: str, language: str, role: str) -> str:
    """Two role profiles share the current seven-layer contract, without losing source constraints."""
    ja = language == "ja"
    labels = ("基本定義層", "ドメイン定義層", "インフラストラクチャ定義層", "共通ポリシー層", "エージェント定義層", "オーケストレーション層", "ユーザーインタラクション層") if ja else ("Basic definition", "Domain definition", "Infrastructure", "Shared policy", "Agent definition", "Orchestration", "User interaction")
    role_rule = ("読み取り専用。値やファイルを変更せず、根拠付きの助言を親へ返す。" if role == "advisor" else "書き込み先は親の許可範囲に限り、出力契約の検証に合格してから保存する。検査の実行失敗は停止して親へ返す。") if ja else ("Read only: return evidence and advice to the parent without changing files or user values." if role == "advisor" else "Write only within the parent-authorized scope; validate the output contract before saving. Stop and return validator execution errors to the parent.")
    goal_heading = "### 5.2 ゴール定義" if ja else "### 5.2 Goal definition"
    checklist = "### 5.3 完了チェックリスト" if ja else "### 5.3 Completion checklist"
    goal = "達成ゴール: 親が要求した出力が、目的と出力契約を満たし、根拠をたどれる状態になっている。" if ja else "Achievement goal: the parent-requested output satisfies the purpose and output contract and its evidence can be traced."
    checks = "- [ ] 必須入力とパスの出所を確かめた。\n- [ ] 出力が上の目的と出力契約を満たす。\n- [ ] 役割の許可範囲を守り、検証の成否と根拠を親へ返せる。" if ja else "- [ ] Required inputs and path provenance are verified.\n- [ ] The output satisfies the purpose and output contract above.\n- [ ] Role permissions are respected and validation results and evidence are available to the parent."
    loop = "目的と完了チェックリストを読み、未達を解消する方法を状況に応じて決める。実行後に検証し、original_goal（不変）/ current_goal_snapshot / delta_from_original / merged_directive_for_next / drift_signal を親へ返す。親の反復上限に達した場合は残る未達と根拠を返す。" if ja else "Read the goal and completion checklist, choose actions for unmet conditions, execute, and validate. Return original_goal (immutable), current_goal_snapshot, delta_from_original, merged_directive_for_next, and drift_signal to the parent. At the parent-defined iteration bound, return remaining gaps and evidence."
    prompt = "## プロンプトの型" if ja else "## Prompt Templates"
    evaluate = "## 自己採点" if ja else "## Self-Evaluation"
    return f"""# {name}

## Layer 1: {labels[0]}

{purpose}

## Layer 2: {labels[1]}

{role_rule}

## Layer 3: {labels[2]}

{"親から入力・解決済み絶対パス・出力契約を受け取る。元スキルの操作制約:" if ja else "Receive inputs, resolved absolute paths, and the output contract from the parent. Source skill operation constraints:"}

{source_operations or ("元スキルの目的と出力契約を参照する。" if ja else "Refer to the source skill purpose and output contract.")}

## Layer 4: {labels[3]}

{role_rule}

## Layer 5: {labels[4]}

### 5.1 {"担当エージェント" if ja else "Assigned agent"}

{name} ({role})

{goal_heading}

{"目的: 上記の目的と出力契約を満たす。背景: 親が独立した役割として委譲した作業を実行する。" if ja else "Purpose: satisfy the purpose and output contract above. Background: the parent delegates this work as an independent role."}

{goal}

{checklist}

{checks}

### 5.4 {"実行方式" if ja else "Execution mode"}

{loop}

## Layer 6: {labels[5]}

{"親が指定した依存順序と停止条件に従い、最終出力・検証結果・未達だけを返す。" if ja else "Respect the parent-defined dependencies and stop conditions; return final output, validation, and unmet conditions."}

## Layer 7: {labels[6]}

{"ユーザーへの対話と保存許可は親が担当する。" if ja else "The parent owns user interaction and save authorization."}

{prompt}

(対話なし: 自動実行 agent) — {"親が入力・役割・出力契約を渡す。" if ja else "The parent supplies inputs, role, and output contract."}

{evaluate}

{"検証可能性と簡潔性を上の完了チェックリストで確かめ、未達は親へ返す。" if ja else "Check verifiability (検証可能性) and conciseness against the completion checklist; return remaining gaps to the parent."}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-name", required=True)
    ap.add_argument("--skill-md", required=True)
    ap.add_argument("--output-dir", default=".claude/agents/")
    ap.add_argument("--language", choices=("auto", "ja", "en"), default="auto")
    ap.add_argument("--role", choices=("auto", "advisor", "writer"), default="auto")
    ap.add_argument("--model", default="opus")  # PF-F3-001: 全Opus既定 (ユーザー方針)
    args = ap.parse_args()

    skill_md = Path(args.skill_md)
    if not skill_md.exists():
        print(f"SKILL.md not found: {skill_md}", file=sys.stderr)
        return 2
    text = skill_md.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)

    desc = fm.get("description", "") or f"Subagent derived from {args.skill_name}"
    tools = map_tools(fm.get("allowed-tools", []))
    # goal-seek format を優先抽出し、legacy "## Steps" にフォールバックする
    steps = extract_section(body, "## ゴールシーク実行") or extract_section(body, "## Steps")
    purpose = extract_section(body, "## 目的と出力契約") or extract_section(body, "## Purpose & Output Contract")
    language = resolve_language(body, args.language)
    role = args.role if args.role != "auto" else ("writer" if {"Write", "Edit"} & set(tools.split(", ")) else "advisor")
    if role == "advisor" and {"Write", "Edit"} & set(tools.split(", ")):
        print("advisor role cannot declare Write/Edit tools", file=sys.stderr)
        return 2

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.skill_name}-subagent.md"

    fm_lines = [
        "---",
        f"name: {args.skill_name}-subagent",
        f"description: {json.dumps(desc, ensure_ascii=False)}",
    ]
    fm_lines.append(f"tools: {tools or 'Read'}")
    fm_lines.append(f"model: {args.model}")
    fm_lines.append("---")

    # Preserve operational constraints in infrastructure, never as a fixed thinking process.
    operations = "\n".join(f"- {line[4:].strip()}" if line.startswith("### ") else line for line in steps.splitlines())
    md = "\n".join(fm_lines) + "\n\n" + render_agent_body(args.skill_name + "-subagent", purpose or desc, operations, language, role)

    out_path.write_text(md, encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
