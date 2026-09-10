#!/usr/bin/env python3
# /// script
# name: lint-matrix-sync
# purpose: lint-matrix.json (lint 集合の単一正本) と3消費面 (SKILL.md Step4 / p0-lint.commands / CI) の突合を検査する。
# inputs:
#   - argv: lint-matrix.json path or --self-test
# outputs:
#   - stdout: OK status
#   - stderr: violation findings (FAIL)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""lint 集合3箇所分散 (LS-02/LS-07) の突合 lint。

正本 = plugins/harness-creator/references/lint-matrix.json。検査:
  (a) build-preflight: run-build-skill SKILL.md の Step 4 セクション bash ブロックの
      lint/validate script 集合 == matrix[build-preflight]  (双方向・集合一致)
  (b) p0-gate: run-skill-create workflow-manifest.json の p0-lint.commands の
      script 集合 == matrix[p0-gate]  (双方向・集合一致)
  (c) ci: contexts に "ci" を持つ lint は consumers.ci の workflow いずれかに
      script 名が出現する (matrix ⊆ CI の片方向)。"ci" を持たない lint は
      ci_exclusion_reason 非空が必須 (除外理由の宣言なき欠落を禁止)。

消費面のパスは matrix の consumers から導出する (matrix 自身が突合先も宣言する)。
Exit 0 = ok, 1 = violation, 2 = usage/parse error.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

SCRIPT_NAME_RE = re.compile(r"\b((?:lint|validate)-[a-z0-9-]+\.py)\b")
STEP4_HEAD_RE = re.compile(r"^### Step 4\b", re.MULTILINE)
SECTION_SPLIT_RE = re.compile(r"^###? ", re.MULTILINE)
BASH_FENCE_RE = re.compile(r"```bash\n(.*?)```", re.DOTALL)
VALID_CONTEXTS = {"build-preflight", "p0-gate", "ci"}


def _extract_step4_scripts(skill_md_text: str) -> set[str]:
    """SKILL.md の Step 4 セクション内 bash フェンスから script 名集合を抽出する。"""
    m = STEP4_HEAD_RE.search(skill_md_text)
    if not m:
        return set()
    rest = skill_md_text[m.end():]
    nxt = SECTION_SPLIT_RE.search(rest)
    section = rest[: nxt.start()] if nxt else rest
    names: set[str] = set()
    for block in BASH_FENCE_RE.findall(section):
        names.update(SCRIPT_NAME_RE.findall(block))
    return names


def _extract_p0_scripts(manifest_text: str) -> tuple[set[str], list[str]]:
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_text)
    except json.JSONDecodeError as exc:
        return set(), [f"workflow-manifest.json parse error: {exc}"]
    names: set[str] = set()
    for phase in manifest.get("phases", []):
        if phase.get("id") != "p0-lint":
            continue
        for cmd in phase.get("commands", []):
            names.update(SCRIPT_NAME_RE.findall(str(cmd)))
    if not names:
        errors.append("p0-lint phase の commands から script 名を抽出できません")
    return names, errors


def check_matrix(matrix_path: Path, repo_root: Path) -> list[str]:
    errs: list[str] = []
    try:
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{matrix_path}: 読込失敗 {exc}"]

    lints = matrix.get("lints", [])
    consumers = matrix.get("consumers", {})
    declared: dict[str, set[str]] = {c: set() for c in VALID_CONTEXTS}
    for entry in lints:
        script = str(entry.get("script", "")).strip()
        contexts = entry.get("contexts", [])
        if not script:
            errs.append(f"lints[{entry.get('id')!r}].script が空です")
            continue
        unknown = set(contexts) - VALID_CONTEXTS
        if unknown:
            errs.append(f"{script}: 未知の context {sorted(unknown)}")
        for c in set(contexts) & VALID_CONTEXTS:
            declared[c].add(script)
        if "ci" not in contexts and not str(entry.get("ci_exclusion_reason", "")).strip():
            errs.append(
                f"{script}: contexts に ci が無いのに ci_exclusion_reason が空です "
                "(除外理由の宣言なき CI 欠落は禁止)"
            )

    # (a) build-preflight: SKILL.md Step4 と集合一致
    skill_md_ref = str(consumers.get("build-preflight", ""))
    skill_md_path = repo_root / skill_md_ref.split("#")[0]
    if not skill_md_path.is_file():
        errs.append(f"consumers.build-preflight の実体が不在: {skill_md_path}")
    else:
        actual = _extract_step4_scripts(skill_md_path.read_text(encoding="utf-8"))
        want = declared["build-preflight"]
        for miss in sorted(want - actual):
            errs.append(f"build-preflight: matrix 宣言 {miss} が SKILL.md Step4 に不在")
        for extra in sorted(actual - want):
            errs.append(f"build-preflight: SKILL.md Step4 の {extra} が matrix 未宣言")

    # (b) p0-gate: workflow-manifest と集合一致
    manifest_ref = str(consumers.get("p0-gate", ""))
    manifest_path = repo_root / manifest_ref.split("#")[0]
    if not manifest_path.is_file():
        errs.append(f"consumers.p0-gate の実体が不在: {manifest_path}")
    else:
        actual, perrs = _extract_p0_scripts(manifest_path.read_text(encoding="utf-8"))
        errs.extend(perrs)
        want = declared["p0-gate"]
        for miss in sorted(want - actual):
            errs.append(f"p0-gate: matrix 宣言 {miss} が p0-lint.commands に不在")
        for extra in sorted(actual - want):
            errs.append(f"p0-gate: p0-lint.commands の {extra} が matrix 未宣言")

    # (c) ci: matrix ⊆ CI (片方向)。コメント行での言及を偽陽性にしないため
    # python3 実行行のみを対象に照合する。
    ci_refs = consumers.get("ci", [])
    ci_exec_lines: list[str] = []
    found_any = False
    for ref in ci_refs:
        p = repo_root / str(ref)
        if not p.is_file():
            errs.append(f"consumers.ci の実体が不在: {p}")
            continue
        found_any = True
        for line in p.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if "python3" in stripped and not stripped.startswith("#"):
                ci_exec_lines.append(stripped)
    if found_any:
        ci_exec_text = "\n".join(ci_exec_lines)
        for script in sorted(declared["ci"]):
            if script not in ci_exec_text:
                errs.append(f"ci: matrix 宣言 {script} が CI workflow の実行行に不在")
    return errs


def self_test() -> int:
    matrix = {
        "consumers": {
            "build-preflight": "SKILL.md",
            "p0-gate": "manifest.json",
            "ci": ["ci.yml"],
        },
        "lints": [
            {"id": "a", "script": "lint-a.py", "contexts": ["build-preflight", "p0-gate", "ci"]},
            {"id": "b", "script": "validate-b.py", "contexts": ["build-preflight"],
             "ci_exclusion_reason": "既知債務"},
        ],
    }
    skill_md = (
        "## x\n### Step 4: Lint (phase: scripts)\n\n```bash\n"
        "python3 lint-a.py x\npython3 validate-b.py y\n```\n\n### Step 5: next\n"
    )
    manifest = {"phases": [{"id": "p0-lint", "commands": ["python3 lint-a.py --skills-dir d"]}]}
    ci = "run: python3 lint-a.py\n"
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "SKILL.md").write_text(skill_md, encoding="utf-8")
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (root / "ci.yml").write_text(ci, encoding="utf-8")
        mp = root / "lint-matrix.json"

        # case1: 整合 → ok
        mp.write_text(json.dumps(matrix), encoding="utf-8")
        assert check_matrix(mp, root) == [], "case1 整合が ok にならない"

        # case2: SKILL.md 側に matrix 未宣言 script → FAIL
        bad_md = skill_md.replace("```\n", "python3 lint-rogue.py z\n```\n", 1)
        (root / "SKILL.md").write_text(bad_md, encoding="utf-8")
        errs = check_matrix(mp, root)
        assert any("lint-rogue.py" in e and "未宣言" in e for e in errs), "case2 未宣言検出漏れ"
        (root / "SKILL.md").write_text(skill_md, encoding="utf-8")

        # case3: matrix 宣言が manifest に不在 → FAIL
        m2 = json.loads(json.dumps(matrix))
        m2["lints"].append({"id": "c", "script": "lint-c.py", "contexts": ["p0-gate", "ci"]})
        mp.write_text(json.dumps(m2), encoding="utf-8")
        errs = check_matrix(mp, root)
        assert any("lint-c.py" in e and "p0-lint.commands に不在" in e for e in errs), "case3 不在検出漏れ"
        assert any("lint-c.py" in e and "実行行に不在" in e for e in errs), "case3 CI 不在検出漏れ"

        # case4: ci 欠落 + 理由なし → FAIL
        m3 = json.loads(json.dumps(matrix))
        m3["lints"][1] = {"id": "b", "script": "validate-b.py", "contexts": ["build-preflight"]}
        mp.write_text(json.dumps(m3), encoding="utf-8")
        errs = check_matrix(mp, root)
        assert any("ci_exclusion_reason" in e for e in errs), "case4 理由なし検出漏れ"
    print("self-test: ok (4 cases)")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        print("usage: lint-matrix-sync.py <lint-matrix.json> | --self-test", file=sys.stderr)
        return 2
    repo_root = Path.cwd()
    all_errs: list[str] = []
    for p in paths:
        all_errs.extend(check_matrix(Path(p), repo_root))
    if all_errs:
        for e in all_errs:
            print(f"FAIL: {e}", file=sys.stderr)
        print(f"NG: {len(all_errs)} violation(s)", file=sys.stderr)
        return 1
    print("OK: lint-matrix と全消費面 (Step4/p0-gate/CI) が整合")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
