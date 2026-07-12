#!/usr/bin/env python3
# /// script
# name: lint-agent-prompt-section
# purpose: SubAgent files must declare Prompt Templates and Self-Evaluation sections.
# inputs:
#   - argv: agent .md path or --agents-dir <dir> or --plugins-root <dir>
# outputs:
#   - stdout: OK status
#   - stderr: violation findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Lint SubAgent markdown files for required sections.

Required sections (agent-template.md):
  - ## Prompt Templates
  - ## Self-Evaluation

Skip rule:
  If body contains the literal '(対話なし: 自動実行 agent)' then Prompt Templates
  section may omit a question example block (only the heading is required).

Tier 2 (responsibility coverage) is enabled by `--strict-coverage --brief <path>`.
It cross-checks brief.responsibilities[] ids with `<!-- responsibility: <id> -->`
anchors inside the Prompt Templates section.

Usage:
  lint-agent-prompt-section.py path/to/agent.md
  lint-agent-prompt-section.py --agents-dir plugins/skill-intake/agents
  lint-agent-prompt-section.py --plugins-root plugins
  lint-agent-prompt-section.py --strict-coverage --brief eval-log/skill-brief.json path/to/agent.md

Exit 0 = ok, 1 = violation, 2 = usage error.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

REQUIRED_HEADINGS = ("## Prompt Templates", "## Self-Evaluation")
DIMENSIONS = ("完全性", "一貫性", "深度", "検証可能性", "簡潔性")
AUTO_AGENT_MARKER = "(対話なし: 自動実行 agent)"
ANCHOR_RE = re.compile(r"<!--\s*responsibility:\s*(R[0-9]+)\s*-->")
PLACEHOLDER_RE = re.compile(r"(?:<[^>]+>|\bTODO\b)")


def find_section(text: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"^{re.escape(heading)}\s*\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1) if m else None


def extract_anchor_blocks(prompt_body: str) -> list[tuple[str, str]]:
    """Return list of (responsibility_id, body_under_anchor) tuples.

    Body extends from the anchor up to the next anchor or end of section.
    """
    blocks: list[tuple[str, str]] = []
    anchors = list(ANCHOR_RE.finditer(prompt_body))
    for i, m in enumerate(anchors):
        start = m.end()
        end = anchors[i + 1].start() if i + 1 < len(anchors) else len(prompt_body)
        blocks.append((m.group(1), prompt_body[start:end]))
    return blocks


def load_brief_responsibilities(brief_path: Path) -> tuple[list[dict], str | None]:
    try:
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [], f"brief read error: {e}"
    return brief.get("responsibilities", []) or [], brief.get("kind")


def lint_file(
    path: Path,
    strict_coverage: bool = False,
    brief_path: Path | None = None,
) -> list[str]:
    findings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{path}: read error: {e}"]

    # Tier 1: 形式検査 (現行ロジック維持)
    for heading in REQUIRED_HEADINGS:
        if heading not in text:
            findings.append(f"{path}: missing required heading '{heading}'")

    prompt_body = find_section(text, "## Prompt Templates")
    if prompt_body is not None and AUTO_AGENT_MARKER not in prompt_body:
        has_quote = re.search(r"^>\s*", prompt_body, re.MULTILINE) is not None
        has_round = re.search(r"^### ", prompt_body, re.MULTILINE) is not None
        if not (has_quote or has_round):
            findings.append(
                f"{path}: Prompt Templates section needs either a '> ' quote "
                "or '### Round' subheading, or marker '(対話なし: 自動実行 agent)'"
            )

    eval_body = find_section(text, "## Self-Evaluation")
    if eval_body is not None:
        if not any(d in eval_body for d in DIMENSIONS):
            findings.append(
                f"{path}: Self-Evaluation must reference at least one of "
                f"{'/'.join(DIMENSIONS)}"
            )

    # Tier 2: 責務 coverage 検査
    if strict_coverage and brief_path is not None and prompt_body is not None:
        findings.extend(_lint_responsibility_coverage(path, prompt_body, brief_path))

    return findings


def _lint_responsibility_coverage(
    path: Path,
    prompt_body: str,
    brief_path: Path,
) -> list[str]:
    """Tier 2: brief.responsibilities[] と SubAgent.md anchor 集合を照合する。

    照合ポリシーの設計判断:
      (a) 完全集合一致: brief.responsibilities[].id == anchor 集合 (missing/extra 両方 violation)
      (b) カウント比較: anchor 数 >= responsibilities 数 (順序問わない)
      (c) 順序一致: brief 配列順と anchor 出現順が一致

    どれを採用するかは「責務 prompt の再現性」の解釈次第。Phase 3 の TODO(human)。
    """
    findings: list[str] = []
    responsibilities, _kind = load_brief_responsibilities(brief_path)
    if not responsibilities:
        return findings  # brief に責務が無いなら Tier 2 適用外

    # kind 別適用: delegate は Tier 2 skip (agent-template.md kind 表)
    _, kind = load_brief_responsibilities(brief_path)
    if kind == "delegate":
        return findings

    brief_ids = [r.get("id") for r in responsibilities if r.get("id")]
    anchor_blocks = extract_anchor_blocks(prompt_body)
    anchor_ids = [aid for aid, _ in anchor_blocks]
    body_by_id = {aid: body for aid, body in anchor_blocks}
    required_by_id = {
        r["id"]: bool(r.get("prompt_required"))
        for r in responsibilities
        if r.get("id")
    }

    # 照合ポリシー (a): 完全集合一致
    brief_set = set(brief_ids)
    anchor_set = set(anchor_ids)
    missing = brief_set - anchor_set
    extra = anchor_set - brief_set
    if missing:
        findings.append(
            f"{path}: missing responsibility anchors: {sorted(missing)} "
            "(expected `<!-- responsibility: <id> -->` for each brief.responsibilities[].id)"
        )
    if extra:
        findings.append(
            f"{path}: extra responsibility anchors not in brief: {sorted(extra)}"
        )

    # 本文検査: prompt_required=true の責務のみ placeholder/空を violation 扱い
    for rid, body in body_by_id.items():
        if rid not in required_by_id:
            continue
        if not required_by_id[rid]:
            continue  # prompt_required=false は anchor 行のみで可
        stripped = body.strip()
        if not stripped:
            findings.append(
                f"{path}: anchor body for {rid} is empty "
                "(prompt_required=true requires Round heading + '>' quote)"
            )
            continue
        # placeholder 検出: 実発話を担う `>` quote 行が存在し、かつその中身が
        # placeholder/TODO のみでないことを要求 (agent-template 規約)
        quote_lines = re.findall(r"^>\s*(.*?)\s*$", body, re.MULTILINE)
        if not quote_lines:
            findings.append(
                f"{path}: anchor body for {rid} has no '>' quote line "
                "(prompt_required=true requires concrete prompt text)"
            )
            continue
        # placeholder marker (`<...>` or TODO) を含む quote 行は非実体扱い。
        # agent-template の `> 「<実発話例>」` 雛形が未充填のまま残るケースを検出。
        substantive = [
            ln for ln in quote_lines
            if ln.strip() and not PLACEHOLDER_RE.search(ln)
        ]
        if not substantive:
            findings.append(
                f"{path}: anchor body for {rid} contains only placeholders/TODO "
                "in '>' quote lines (prompt_required=true requires concrete prompt text)"
            )

    return findings


def parse_args(argv: list[str]) -> tuple[list[Path], bool, Path | None, int | None]:
    """Returns (targets, strict_coverage, brief_path, error_code).

    error_code is None on success, else the exit code to return.
    """
    strict_coverage = False
    brief_path: Path | None = None
    positional: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--strict-coverage":
            strict_coverage = True
            i += 1
        elif a == "--brief":
            if i + 1 >= len(argv):
                sys.stderr.write("--brief requires a path argument\n")
                return [], False, None, 2
            brief_path = Path(argv[i + 1])
            i += 2
        else:
            positional.append(a)
            i += 1

    if strict_coverage and brief_path is None:
        sys.stderr.write("--strict-coverage requires --brief <path>\n")
        return [], False, None, 2

    targets = collect_targets(positional)
    return targets, strict_coverage, brief_path, None


def collect_targets(argv: list[str]) -> list[Path]:
    if not argv:
        return []
    if argv[0] == "--agents-dir":
        if len(argv) < 2:
            return []
        d = Path(argv[1])
        return sorted(d.glob("*.md")) if d.is_dir() else []
    if argv[0] == "--plugins-root":
        if len(argv) < 2:
            return []
        root = Path(argv[1])
        if not root.is_dir():
            return []
        return sorted(root.glob("*/agents/*.md"))
    return [Path(p) for p in argv]


def main(argv: list[str]) -> int:
    targets, strict_coverage, brief_path, err = parse_args(argv)
    if err is not None:
        return err
    if not targets:
        sys.stderr.write(
            "usage: lint-agent-prompt-section.py <agent.md> | "
            "--agents-dir <dir> | --plugins-root <dir> "
            "[--strict-coverage --brief <skill-brief.json>]\n"
        )
        return 2

    all_findings: list[str] = []
    for path in targets:
        all_findings.extend(
            lint_file(path, strict_coverage=strict_coverage, brief_path=brief_path)
        )

    if all_findings:
        for f in all_findings:
            sys.stderr.write(f + "\n")
        return 1

    tier = "Tier 1+2" if strict_coverage else "Tier 1"
    sys.stdout.write(f"OK: {len(targets)} agent file(s) passed ({tier})\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
