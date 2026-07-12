#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Score a skill against rubric.json. Emits JSON to stdout.

Usage:
  render-findings-score.py --rubric <path> --target <skill-dir-or-SKILL.md> [--emit-hash]

Implementation notes:
- stdlib only. Rubric files are JSON.
- Findings collected by simple textual checks; complex checks are TODO.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SEVERITY_WEIGHTS = {"high": -20, "medium": -10, "low": -3}
PREFIXES = ("run-", "ref-", "assign-", "wrap-", "delegate-")


def load_rubric(path: Path) -> dict:
    """Load a JSON rubric."""
    return json.loads(path.read_text(encoding="utf-8"))


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_raw = parts[1]
    body = parts[2]
    fm: dict = {}
    for line in fm_raw.splitlines():
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm, body


def check_rule(rule: dict, fm: dict, body: str, skill_dir: Path) -> dict | None:
    rid = rule["id"]
    sev = rule.get("severity", "low")
    name = fm.get("name", "")
    desc = fm.get("description", "")

    def fail(msg: str, loc: str = "") -> dict:
        return {"id": rid, "severity": sev, "area": rule.get("area", ""),
                "message": msg, "loc": loc}

    if rid == "FM-001":
        if not re.fullmatch(r"(run|ref|assign|wrap|delegate)-[a-z0-9][a-z0-9-]*", name) or len(name) > 60:
            return fail(f"name '{name}' violates prefix/kebab/len<=60", "frontmatter.name")
    elif rid == "FM-002":
        jp_triggers = ("とき", "場合", "際", "時に")
        has_en = ("Use when" in desc) or ("Read when" in desc)
        has_jp = any(t in desc for t in jp_triggers)
        if not (has_en or has_jp):
            return fail("description missing trigger phrase "
                        "(〜とき/〜場合/〜際/〜時 or 'Use when'/'Read when')",
                        "frontmatter.description")
    elif rid == "FM-003":
        jp_triggers = ("とき", "場合", "際", "時に")
        has_en = ("Use when" in desc) or ("Read when" in desc)
        if has_en:
            n_when = desc.count("when ")
            m = re.search(r"(Use when|Read when)\s+(.+?)\.\s*$", desc)
            n_clauses = 0
            if m:
                tail = m.group(2)
                parts = re.split(r",\s*|\s+or\s+", tail)
                n_clauses = len([p for p in parts if p.strip()])
            n = max(n_when, n_clauses)
        else:
            n_jp = sum(desc.count(t) for t in jp_triggers)
            m = re.search(r"([^。]*?)(とき|場合|際|時に)", desc)
            n_clauses = 0
            if m:
                head = m.group(1)
                parts = re.split(r"[、・/／]|\s+や\s*", head)
                n_clauses = len([p for p in parts if p.strip()])
            n = max(n_jp, n_clauses)
        if not (2 <= n <= 3):
            return fail(f"trigger count = {n} (expected 2..3)", "frontmatter.description")
    elif rid == "FM-004":
        bad = ["採点する", "JSONで返す", "sha256", "exit code"]
        hit = [b for b in bad if b in desc]
        if hit:
            return fail(f"description contains action detail: {hit}", "frontmatter.description")
    elif rid == "FM-005":
        en_verbs = ("Build", "Score", "Read", "Wrap", "Delegate", "Generate",
                    "Rubric", "Naming", "Claude")
        # 日本語: 冒頭〜句点までの最初の文に動詞語尾が現れれば可
        jp_verb_markers = ("する", "行う", "実行", "生成", "採点", "評価",
                            "構築", "参照", "読み取", "レビュー", "管理",
                            "監査", "集約", "委譲", "観察", "検出")
        first = desc.split(" ", 1)[0] if desc else ""
        starts_en = desc.startswith(en_verbs)
        # 日本語動詞: 最初の句点までに verb marker が含まれる
        head_jp = re.split(r"[。\.]", desc, 1)[0] if desc else ""
        has_jp_verb = any(m in head_jp for m in jp_verb_markers)
        if desc and not (starts_en or has_jp_verb):
            return fail(f"description first phrase '{first}' is not a verb",
                        "frontmatter.description")
    elif rid == "BD-001":
        if "## Purpose & Output Contract" not in body:
            return fail("missing '## Purpose & Output Contract'", "body")
    elif rid == "BD-002":
        if "## Gotchas" not in body:
            return fail("missing '## Gotchas'", "body")
    elif rid == "BD-003":
        n = len(body.splitlines())
        if n > 300:
            return fail(f"body line count {n} > 300", "body")
    elif rid == "BD-004":
        # human-pending; never deduct
        return None
    elif rid == "NM-001":
        if skill_dir.name != name:
            return fail(f"dirname '{skill_dir.name}' != name '{name}'", "naming")
    elif rid == "NM-002":
        if not any(name.startswith(p) for p in PREFIXES):
            return fail("name missing required prefix", "naming")
    elif rid == "NM-003":
        # basic check: scripts must be .py, templates .md
        for p in skill_dir.glob("scripts/*"):
            if p.is_file() and p.suffix not in {".py", ".sh"}:
                return fail(f"scripts/ has non-py/sh file: {p.name}", "naming")
    elif rid == "PD-001":
        n = len(body.splitlines())
        if n > 100:
            refs = skill_dir / "references"
            if not (refs.is_dir() and any(refs.iterdir())):
                return fail("body>100 lines but references/ empty", "progressive-disclosure")
    elif rid == "RG-001":
        # always satisfied since we emit hash
        return None
    return None


def compose_rubrics(refs: list[Path], strategy: str, policy: str) -> dict:
    script = Path(__file__).resolve().parents[3] / "scripts" / "compose-rubrics.py"
    cmd = [
        sys.executable,
        str(script),
        "--rubric-refs",
        *[str(p) for p in refs],
        "--merge-strategy",
        strategy,
        "--conflict-policy",
        policy,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr.strip() or result.stdout.strip(), file=sys.stderr)
        raise SystemExit(2)
    return json.loads(result.stdout)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubric", required=False,
                    help="single rubric (legacy); ignored if --rubric-refs given")
    ap.add_argument("--rubric-refs", nargs="+", default=None,
                    help="ordered list L0..Ln of rubric.json paths to deep-merge")
    ap.add_argument("--conflict-policy", default="most-specific-wins",
                    choices=["most-specific-wins", "error", "warn-and-merge"])
    ap.add_argument("--merge-strategy", default="deep-merge",
                    choices=["deep-merge", "strict", "override", "layered"])
    ap.add_argument("--target", required=True)
    ap.add_argument("--emit-hash", action="store_true")
    args = ap.parse_args()

    refs: list[Path]
    if args.rubric_refs:
        refs = [Path(p).resolve() for p in args.rubric_refs]
    elif args.rubric:
        refs = [Path(args.rubric).resolve()]
    else:
        print("either --rubric or --rubric-refs required", file=sys.stderr)
        return 2

    for rp in refs:
        if not rp.exists():
            print(f"rubric not found: {rp}", file=sys.stderr)
            return 2
    rubric = compose_rubrics(refs, args.merge_strategy, args.conflict_policy)
    composition_hash = rubric.get("_composition_hash", "")
    # primary rubric hash = first (upstream) layer or only layer
    rubric_path = refs[0]
    rhash = hashlib.sha256(rubric_path.read_bytes()).hexdigest()

    target = Path(args.target).resolve()
    if target.is_dir():
        skill_dir = target
        skill_md = target / "SKILL.md"
    else:
        skill_md = target
        skill_dir = target.parent
    if not skill_md.exists():
        print(f"SKILL.md not found: {skill_md}", file=sys.stderr)
        return 2
    text = skill_md.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)

    findings: list[dict] = []
    pending_human: list[dict] = []
    for rule in rubric["rules"]:
        check_expr = rule.get("check", "")
        if "TODO(human)" in check_expr:
            pending_human.append({"id": rule["id"], "reason": "rubric has TODO(human) marker"})
            continue
        f = check_rule(rule, fm, body, skill_dir)
        if f:
            findings.append(f)

    score = 100
    for f in findings:
        score += SEVERITY_WEIGHTS.get(f["severity"], 0)
    score = max(0, min(100, score))
    threshold = int(rubric.get("threshold", "80"))

    out = {
        "rubric_id": rubric.get("rubric_id", "skill-design"),
        "rubric_version": rubric.get("rubric_version", "1.0.0"),
        "rubric_hash": f"sha256:{rhash}",
        "composition_hash": composition_hash,
        "rubric_refs": [str(p) for p in refs],
        "target": str(skill_md),
        "score": score,
        "threshold": threshold,
        "passed": score >= threshold and not any(f["severity"] == "high" for f in findings),
        "machine_checks": [],
        "findings": findings,
        "required_fixes": [f for f in findings if f.get("severity") == "high"],
        "pending_human": pending_human,
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
