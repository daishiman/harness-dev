#!/usr/bin/env python3
# /// script
# name: lint-skill-description
# purpose: Enforce description trigger and wording rules for skills and agents.
# inputs:
#   - argv: optional --report, --skills-dir, or target path
# outputs:
#   - stdout: OK status or report
#   - stderr: description findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""lint-skill-description.py

SKILL.md / agents/*.md の description フィールドを 03章 §description設計規律 で機械強制する。

整合性メモ:
  R1 のトリガー上限は plugins/skill-governance-lint/scripts/validate-frontmatter.py の
  「trigger count == 2 (hard rule)」と同一基準。両者は同じ設計書03章を
  単一情報源 (SSOT) としており、本 R1 は「2 を超えたら違反」の上限のみ
  を担当する。下限 (== 2) は validate-frontmatter.py 側で強制する。

ルール (R1-R5):
  R1 トリガー上限: 「〜とき」「Use when」相当のトリガー句は 2 個前後。3 個以上は違反
  R2 動詞・段数・処理流れ禁止: 「採点する」「JSONで返す」「N個のパラダイム」「並列実行」「ウィザード」「runbook」「E2E」「一気通貫」「複数段」等の語を含まない
  R3 紹介文禁止: 「〜機能」「〜サマリ」「〜の正本」のような役割説明は frontmatter の他フィールド (kind / pair / base / rubric_refs) で示す
  R4 長さ: description は 280 文字以内 (description + when_to_use の合算 1536 字制限の余裕を確保)
  R5 末尾統一: 末尾は「使う」「読む」「起動する」のいずれかで終わる

usage:
  python3 scripts/lint-skill-description.py
  python3 scripts/lint-skill-description.py --report
  python3 scripts/lint-skill-description.py --skills-dir plugins/harness-creator/skills
  python3 scripts/lint-skill-description.py --skills-dir .claude/skills

exit code: 0 OK / 1 違反検出 / 2 設定エラー
"""
import json
import pathlib
import re
import sys

BANNED_TERMS = [
    "採点する", "JSONで返す", "並列実行", "複数段", "ウィザード", "runbook",
    "E2E", "一気通貫", "ランブック", "JSONで出力", "段並列", "段で実行",
    "を実行する", "を構築する", "を解決する", "を取得・参照", "を取得する",
    "サマリを参照", "正本を参照", "辞書を参照", "条文（", "条文(",
]
BANNED_DIGIT_PARADIGM = re.compile(r"\d+(つの|個の|思考法|パラダイム|思考)")
NUMBERED_LIST = re.compile(r"[（(][^）)]{15,}[/／][^）)]{15,}[）)]")
ALLOWED_TAIL = ("使う。", "読む。", "起動する。")
TRIGGER_RE = re.compile(r"(?:とき|場合|際|時に)")
MAX_LEN = 280

SKILL_GLOBS = [
    "plugins/harness-creator/skills/*/SKILL.md",
    ".claude/skills/*/SKILL.md",
    ".claude/agents/*.md",
]


def parse_frontmatter(path: pathlib.Path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = {}
    for line in parts[1].splitlines():
        if ":" in line and not line.lstrip().startswith("-"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def check(name: str, desc: str):
    issues = []
    if not desc:
        return ["R0: description missing"]
    if len(desc) > MAX_LEN:
        issues.append(f"R4: length {len(desc)} > {MAX_LEN}")
    if not desc.rstrip().endswith(ALLOWED_TAIL):
        issues.append(f"R5: must end with one of {ALLOWED_TAIL}")
    triggers = TRIGGER_RE.findall(desc)
    if len(triggers) > 2:
        issues.append(f"R1: trigger count {len(triggers)} > 2 (overflow)")
    if len(triggers) == 0 and "Use when" not in desc:
        issues.append("R1: no trigger condition found")
    for term in BANNED_TERMS:
        if term in desc:
            issues.append(f"R2: banned term '{term}'")
    if BANNED_DIGIT_PARADIGM.search(desc):
        issues.append("R2: digit+paradigm/思考法 enumeration not allowed")
    if NUMBERED_LIST.search(desc):
        issues.append("R3: paradigm enumeration in parentheses not allowed")
    return issues


def _parse_skills_dir(argv):
    """Extract --skills-dir VALUE or --skills-dir=VALUE from argv.

    Returns a list of override directories (may be empty).
    """
    out = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--skills-dir" and i + 1 < len(argv):
            out.append(argv[i + 1])
            i += 2
            continue
        if a.startswith("--skills-dir="):
            out.append(a.split("=", 1)[1])
        i += 1
    return out


def main(argv):
    report = "--report" in argv
    override_dirs = _parse_skills_dir(argv)
    targets = []
    if override_dirs:
        for d in override_dirs:
            base = pathlib.Path(d)
            targets.extend(base.glob("*/SKILL.md"))
    else:
        for pattern in SKILL_GLOBS:
            targets.extend(pathlib.Path(".").glob(pattern))
    results = {"OK": [], "VIOLATION": []}
    for p in sorted(set(targets)):
        if p.name.lower() == "readme.md":
            continue
        fm = parse_frontmatter(p)
        name = fm.get("name", p.stem)
        desc = fm.get("description", "")
        if desc.startswith('"') and desc.endswith('"'):
            desc = desc[1:-1]
        issues = check(name, desc)
        entry = {"path": str(p), "name": name, "description": desc, "issues": issues}
        results["VIOLATION" if issues else "OK"].append(entry)
    if report:
        print(json.dumps({
            "summary": {k: len(v) for k, v in results.items()},
            "violations": results["VIOLATION"],
        }, indent=2, ensure_ascii=False))
    else:
        for v in results["VIOLATION"]:
            print(f"VIOLATION {v['path']} ({v['name']})", file=sys.stderr)
            for i in v["issues"]:
                print(f"  - {i}", file=sys.stderr)
        print(f"summary: OK={len(results['OK'])} VIOLATION={len(results['VIOLATION'])}")
    return 1 if results["VIOLATION"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
