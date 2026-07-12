#!/usr/bin/env python3
# /// script
# name: validate-llm-coverage
# purpose: loop-kind スキルの LLM 駆動部分(feedback_contract.criteria + goal-seek checklist)のテスト被覆率を測る。
# inputs:
#   - argv: --all | --changed-only [--base origin/main] [--threshold 80] [--gate-new --since <ISO8601>] [--json <path>]
# outputs:
#   - stdout: 被覆率サマリ / WARN
#   - eval-log/llm-coverage.json: per-skill 被覆レポート
#   - exit: 0=PASS(WARN含む) / 1=gate違反(--gate-new時のみ) / 2=usage
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: eval-log
# ///
"""LLM 駆動部分のテスト被覆率を計測する (コード側は pytest-cov の行カバレッジ=make coverage)。

ユーザー決定 (2026-06-24): 「LLM を動かす部分」のカバレッジは
**feedback_contract.criteria + goal-seek checklist 項目のうち、検証する test/fixture を持つ割合**
で測り ≥80% を目標とする。強制は「計測+WARN→段階的に gate」。

母数と被覆の定義:
  - 一次母数 = feedback_contract.criteria の id 集合 (各 id は verify_by を持つ検証契約)
  - criterion id (IN1/OUT1/Cn) が次のいずれかで参照されれば covered:
      * 当該 skill ディレクトリ配下 (tests/ fixtures/ examples/ や *test*/*.fixture.* ファイル)
      * repo-root tests/*.py で skill 名と id を共に参照
      * skill-local coverage-manifest.json の covered_criteria[]
  - 二次チェック = checklist 項目数。criteria が checklist と同源 (R4) であることを前提に、
    checklist 項目数 > criteria 数なら「criteria 未導出 (under-derived)」を smell として report に残す。

enforcement:
  - 既定: 全 loop-kind skill を計測し <threshold を WARN (非 fail。ratchet 用 baseline)。
  - --gate-new --since <ISO>: frontmatter since が当該日以降の新規 skill のみ <threshold で exit1。
    新規生成スキルから fail-closed で 80% を強制し、既存は段階的に底上げする。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"
TESTS_DIR = ROOT / "tests"
EVAL_LOG = ROOT / "eval-log"

sys.path.insert(0, str(ROOT / "scripts"))
import feedback_contract_ssot as FC  # noqa: E402

LOOP_KINDS = FC.FEEDBACK_LOOP_KINDS
CHECKLIST_ITEM_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s+\S", re.M)
SINCE_RE = re.compile(r"^since:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", re.M)


def _git_changed_skills(base: str) -> set[tuple[str, str]]:
    try:
        diff = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base}...HEAD"], cwd=ROOT, text=True
        )
    except subprocess.CalledProcessError:
        return set()
    pat = re.compile(r"^plugins/([^/]+)/skills/([^/]+)/")
    return {(m.group(1), m.group(2)) for line in diff.splitlines() if (m := pat.match(line.strip()))}


def _all_skills() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    if not PLUGINS_DIR.exists():
        return out
    for plugin_dir in PLUGINS_DIR.iterdir():
        sk_dir = plugin_dir / "skills"
        if not sk_dir.is_dir():
            continue
        for s in sk_dir.iterdir():
            if s.is_symlink():  # symlink は実体側で計測
                continue
            if (s / "SKILL.md").is_file():
                out.add((plugin_dir.name, s.name))
    return out


def _skill_artifact_text(skill_dir: Path) -> str:
    """skill 配下の test/fixture/example 系ファイルを連結して返す (被覆判定の探索対象)。"""
    chunks: list[str] = []
    for sub in ("tests", "fixtures", "examples"):
        d = skill_dir / sub
        if d.is_dir():
            for f in d.rglob("*"):
                if f.is_file():
                    try:
                        chunks.append(f.read_text(encoding="utf-8", errors="ignore"))
                    except OSError:
                        pass
    for f in skill_dir.rglob("*"):
        if f.is_file() and ("test" in f.name.lower() or ".fixture." in f.name.lower()):
            try:
                chunks.append(f.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
    return "\n".join(chunks)


def _repo_tests_text() -> str:
    chunks: list[str] = []
    if TESTS_DIR.is_dir():
        for f in TESTS_DIR.rglob("*.py"):
            try:
                chunks.append(f.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
    return "\n".join(chunks)


def _manifest_covered(skill_dir: Path) -> set[str]:
    mf = skill_dir / "coverage-manifest.json"
    if not mf.is_file():
        return set()
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
    except Exception:
        return set()
    cov = data.get("covered_criteria")
    return {str(x).strip() for x in cov} if isinstance(cov, list) else set()


def measure_skill(plugin: str, skill: str, repo_tests: str) -> dict | None:
    """1 skill の LLM 被覆を測る。loop-kind でなければ None。"""
    skill_dir = PLUGINS_DIR / plugin / "skills" / skill
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return None
    text = md.read_text(encoding="utf-8")
    if FC.read_kind(text) not in LOOP_KINDS:
        return None
    fc = FC.extract_frontmatter_feedback_contract(text)
    if not isinstance(fc, dict):
        return None
    # skip_reason は計測 skip の根拠にしない (N/A escape は FEEDBACK_SKIP_KINDS=ref/assign
    # 限定で、それらは上の LOOP_KINDS 判定で除外済み。lint-feedback-contract と対称)。
    # criteria 未整備の loop-kind は下の ids 空判定で計測対象外になる。
    ids = sorted(FC.criteria_ids(fc.get("criteria")))
    if not ids:
        return None

    artifact_text = _skill_artifact_text(skill_dir)
    manifest = _manifest_covered(skill_dir)
    covered: list[str] = []
    for cid in ids:
        in_skill = re.search(rf"\b{re.escape(cid)}\b", artifact_text) is not None
        in_repo = (re.search(rf"\b{re.escape(cid)}\b", repo_tests) is not None
                   and skill in repo_tests)
        if cid in manifest or in_skill or in_repo:
            covered.append(cid)

    checklist_count = len(CHECKLIST_ITEM_RE.findall(text))
    total = len(ids)
    pct = round(100.0 * len(covered) / total, 1) if total else 100.0
    since = (m.group(1) if (m := SINCE_RE.search(text)) else None)
    return {
        "plugin": plugin,
        "skill": skill,
        "criteria_total": total,
        "criteria_covered": len(covered),
        "covered_ids": covered,
        "uncovered_ids": [c for c in ids if c not in covered],
        "checklist_items": checklist_count,
        "under_derived": checklist_count > total,  # checklist > criteria = criteria 未導出 smell
        "coverage_pct": pct,
        "since": since,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--changed-only", action="store_true")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--threshold", type=float, default=80.0)
    ap.add_argument("--gate-new", action="store_true", help="--since 以降の新規 skill のみ閾値未満で exit1")
    ap.add_argument("--since", default="", help="新規 skill 判定の境界日 (YYYY-MM-DD)")
    ap.add_argument("--json", default=str(EVAL_LOG / "llm-coverage.json"))
    ap.add_argument("--check", action="store_true",
                    help="書き込まず、生成結果が既存 llm-coverage.json と一致するか parity 検査 (乖離で exit1)")
    args = ap.parse_args()
    if args.gate_new and not args.since:
        print("usage: --gate-new requires --since YYYY-MM-DD", file=sys.stderr)
        return 2

    targets = _git_changed_skills(args.base) if args.changed_only else _all_skills()
    repo_tests = _repo_tests_text()
    reports = [r for plugin, skill in sorted(targets)
               if (r := measure_skill(plugin, skill, repo_tests))]

    below = [r for r in reports if r["coverage_pct"] < args.threshold]
    out_path = Path(args.json)
    avg = round(sum(r["coverage_pct"] for r in reports) / len(reports), 1) if reports else 100.0
    content = json.dumps({
        "threshold": args.threshold,
        "skills_measured": len(reports),
        "below_threshold": len(below),
        "average_coverage_pct": avg,
        "reports": reports,
    }, ensure_ascii=False, indent=2)

    # --check: 書き込まず、生成結果が既存 llm-coverage.json と一致するか parity 検査。
    # llm-coverage.json は毎回無条件 write される派生レポートで、roster のような
    # git-stale 検出が無いと skill 変更/改名時の更新漏れを CI が見逃す (2026-07-02 の
    # harness-creator 改名で checklist_items stale が長期潜伏していた事故の恒久対策)。
    if args.check:
        existing = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
        if existing == content:
            print(f"OK: {out_path.name} は最新 ({len(reports)} skills / 平均 {avg}%)")
            return 0
        print(
            f"STALE: {out_path.name} が生成結果と乖離。"
            "make llm-coverage (python3 scripts/validate-llm-coverage.py --all) で再生成してください。",
            file=sys.stderr,
        )
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")

    print(f"[llm-coverage] {len(reports)} loop-kind skill 計測 / 平均 {avg}% / 閾値 {args.threshold}%")
    for r in below:
        print(f"  ~ {r['plugin']}/{r['skill']}: {r['coverage_pct']}% "
              f"({r['criteria_covered']}/{r['criteria_total']} criteria) uncovered={r['uncovered_ids']}")

    if args.gate_new:
        gated = [r for r in below if r["since"] and r["since"] >= args.since]
        if gated:
            print(f"[FAIL] llm-coverage gate: {len(gated)} 新規 skill が閾値未満 (since>={args.since})")
            for r in gated:
                print(f"  - {r['plugin']}/{r['skill']}: {r['coverage_pct']}% "
                      f"→ criteria を検証する test/fixture を追加し ≥{args.threshold}% にすること")
            return 1
        print(f"[OK] llm-coverage gate: 新規 skill (since>={args.since}) は全て ≥{args.threshold}%")
        return 0

    if below:
        print(f"[WARN] llm-coverage: {len(below)} skill が閾値未満 (ratchet で底上げ。新規は --gate-new で fail-closed)")
    else:
        print(f"[OK] llm-coverage: 全 loop-kind skill が ≥{args.threshold}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
