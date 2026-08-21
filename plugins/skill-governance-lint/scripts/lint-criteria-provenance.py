#!/usr/bin/env python3
# /// script
# name: lint-criteria-provenance
# purpose: 完了チェックリスト (CL-n アンカー) と feedback_contract.criteria[].derived_from の写像被覆を検査する。
# inputs:
#   - argv: SKILL.md path(s) / --skills-dir <dir> / --self-test
# outputs:
#   - stdout: OK status
#   - stderr: violation findings (FAIL)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""完了条件の系統分散 (LS-05/PF-DLOOP) に対する Checklist→criteria 写像の突合 lint。

契約:
  - Checklist 項目行末アンカー: `<!-- CL-n -->` (免除は `<!-- CL-n exempt: 理由 -->`)
  - frontmatter: `feedback_contract.criteria[].derived_from: [CL-1, ...]` (flow style)

検査 (presence-based opt-in: アンカーも derived_from も無い skill は skip):
  R1 アンカー重複                                → FAIL
  R2 derived_from があるのに本文アンカー不在      → FAIL
  R3 derived_from の参照先アンカーが不在          → FAIL
  R4 アンカーがあるのに derived_from が皆無       → FAIL
  R5 非 exempt アンカーがどの criteria からも未参照 → FAIL (被覆漏れ)
  R6 exempt の理由が空                            → FAIL

写像の意味的正しさ (テキストの対応が妥当か) は検査しない = content-review
(LLM 層) の責務。本 lint は被覆と実在のみの決定論検査 (二層分離)。
Exit 0 = ok, 1 = violation, 2 = usage error.
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

ANCHOR_RE = re.compile(r"<!--\s*(CL-\d+)(?:\s+exempt:\s*(.*?))?\s*-->")
DERIVED_RE = re.compile(r"^\s*derived_from:\s*\[(.*?)\]\s*(?:#.*)?$")
CL_ID_RE = re.compile(r"^CL-\d+$")


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end < 0:
        return "", text
    return text[: end + 4], text[end + 4:]


def check_skill_md(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{path}: 読込失敗 {exc}"]
    fm, body = _split_frontmatter(text)

    anchors: dict[str, str | None] = {}
    errs: list[str] = []
    for m in ANCHOR_RE.finditer(body):
        cid, exempt = m.group(1), m.group(2)
        if cid in anchors:
            errs.append(f"{path}: アンカー {cid} が重複 (R1)")
        anchors[cid] = exempt
        if exempt is not None and not exempt.strip():
            errs.append(f"{path}: {cid} の exempt 理由が空 (R6)")

    derived: set[str] = set()
    for line in fm.splitlines():
        dm = DERIVED_RE.match(line)
        if not dm:
            continue
        for tok in dm.group(1).split(","):
            tok = tok.strip().strip("'\"")
            if not tok:
                continue
            if not CL_ID_RE.match(tok):
                errs.append(f"{path}: derived_from の {tok!r} は CL-n 形式でない (R3)")
                continue
            derived.add(tok)

    if not anchors and not derived:
        return errs  # opt-in 前の skill は対象外
    if derived and not anchors:
        errs.append(f"{path}: derived_from があるのに本文に CL アンカーが無い (R2)")
        return errs
    if anchors and not derived:
        errs.append(
            f"{path}: Checklist に CL アンカーがあるのに criteria の derived_from が皆無 (R4)"
        )
        return errs
    for cid in sorted(derived - set(anchors)):
        errs.append(f"{path}: derived_from の {cid} に対応するアンカーが本文に無い (R3)")
    for cid, exempt in sorted(anchors.items()):
        if exempt is None and cid not in derived:
            errs.append(
                f"{path}: {cid} がどの criteria の derived_from からも参照されず "
                f"exempt 宣言も無い (R5 被覆漏れ)"
            )
    return errs


def self_test() -> int:
    ok_md = (
        "---\nfeedback_contract:\n  criteria:\n"
        "    - id: IN1\n      derived_from: [CL-1, CL-2]\n---\n"
        "# t\n- [ ] a <!-- CL-1 -->\n- [ ] b <!-- CL-2 -->\n"
        "- [ ] c <!-- CL-3 exempt: 運用操作項目 -->\n"
    )
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "SKILL.md"

        p.write_text(ok_md, encoding="utf-8")
        assert check_skill_md(p) == [], "case1 整合が ok にならない"

        p.write_text(ok_md.replace("[CL-1, CL-2]", "[CL-1]"), encoding="utf-8")
        assert any("R5" in e for e in check_skill_md(p)), "case2 被覆漏れ検出漏れ"

        p.write_text(ok_md.replace("[CL-1, CL-2]", "[CL-1, CL-9]"), encoding="utf-8")
        assert any("R3" in e for e in check_skill_md(p)), "case3 dangling 検出漏れ"

        p.write_text(ok_md.replace(" <!-- CL-2 -->", " <!-- CL-1 -->"), encoding="utf-8")
        assert any("R1" in e for e in check_skill_md(p)), "case4 重複検出漏れ"

        p.write_text(ok_md.replace("exempt: 運用操作項目", "exempt:"), encoding="utf-8")
        assert any("R6" in e for e in check_skill_md(p)), "case5 exempt 空理由検出漏れ"

        p.write_text("---\nx: 1\n---\n# 素の skill\n- [ ] a\n", encoding="utf-8")
        assert check_skill_md(p) == [], "case6 opt-in 前 skill が skip されない"
    print("self-test: ok (6 cases)")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    targets: list[Path] = []
    it = iter(range(len(argv)))
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--skills-dir":
            if i + 1 >= len(argv):
                print("usage: --skills-dir <dir>", file=sys.stderr)
                return 2
            targets.extend(sorted(Path(argv[i + 1]).glob("*/SKILL.md")))
            i += 2
            continue
        if not a.startswith("--"):
            targets.append(Path(a))
        i += 1
    if not targets:
        print(
            "usage: lint-criteria-provenance.py <SKILL.md...> | --skills-dir <dir> | --self-test",
            file=sys.stderr,
        )
        return 2
    all_errs: list[str] = []
    checked = 0
    for t in targets:
        all_errs.extend(check_skill_md(t))
        checked += 1
    if all_errs:
        for e in all_errs:
            print(f"FAIL: {e}", file=sys.stderr)
        print(f"NG: {len(all_errs)} violation(s)", file=sys.stderr)
        return 1
    print(f"OK: {checked} skill(s) — Checklist↔criteria 写像整合")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
