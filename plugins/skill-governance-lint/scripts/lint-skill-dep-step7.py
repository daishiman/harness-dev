#!/usr/bin/env python3
# /// script
# name: lint-skill-dep-step7
# purpose: Validate doc/20 Step 7 dependency constraints for migrated skills.
# inputs:
#   - argv: --skills-dir or skill paths
# outputs:
#   - stdout: OK status
#   - stderr: dependency constraint findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""doc/20-migration-path.md Step 7「依存関係を lint する」5条件を機械検証する。

検査対象:
  (1) wrap-* に base: フィールドがある
  (2) assign-*-evaluator に pair: フィールドがある
  (3) pair: の相手スキルが plugins/harness-creator/skills か .claude/skills に存在する
  (4) dangerous run-* に disable-model-invocation: true がある
      ("dangerous" の判定は frontmatter に danger: true / effect: external-mutation
       のいずれかを持つこと)
  (5) ref-* が disable-model-invocation: true で到達不能になっていない
      (ref-* は model から explicit に呼ばれる必要があるため、user-invocable: false
       かつ disable-model-invocation: true は到達不能)

Python 3.9+ 標準ライブラリのみ。設計書22 no-deps 原則に準拠。

Usage:
  lint-skill-dep-step7.py --skills-dir plugins/harness-creator/skills [--allow-partial]
  lint-skill-dep-step7.py /path/to/SKILL.md ...
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def parse_fm(text: str) -> dict:
    """簡易 YAML frontmatter パーサ。scalar のみ対応で十分。"""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm: dict = {}
    for raw in parts[1].splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm


def _repo_root(p: Path) -> Path:
    cur = p.resolve()
    for parent in [cur, *cur.parents]:
        if (parent / ".git").exists():
            return parent
    return cur.parent


def skill_exists(name: str, repo: Path) -> bool:
    if (repo / ".claude" / "skills" / name).is_dir():
        return True
    return any(path.is_dir() for path in (repo / "plugins").glob(f"*/skills/{name}"))


def _collect_inbound_refs(repo: Path) -> set[str]:
    """全 SKILL.md を走査し、reference_refs / script_refs / rubric_refs に
    現れるスキル名 (ref-/run-/assign-/wrap-/delegate-) の集合を返す。
    Step 7-5 の到達可能性判定で、disable-model-invocation=true かつ
    user-invocable=false の ref-* でも、他スキルから参照されていれば到達可能とみなす。
    """
    inbound: set[str] = set()
    skill_name_re = re.compile(r"(ref|run|assign|wrap|delegate)-[a-z0-9-]+")
    skills_roots = [repo / ".claude" / "skills"]
    skills_roots.extend((repo / "plugins").glob("*/skills"))
    for skills_root in skills_roots:
        if not skills_root.is_dir():
            continue
        for skill_md in skills_root.glob("*/SKILL.md"):
            try:
                txt = skill_md.read_text(encoding="utf-8")
            except OSError:
                continue
            # frontmatter 内の list 値全てを対象に走査
            if not txt.startswith("---"):
                continue
            parts = txt.split("---", 2)
            if len(parts) < 3:
                continue
            fm_block = parts[1]
            current_key: str | None = None
            for raw in fm_block.splitlines():
                line = raw.rstrip()
                m_kv = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
                if m_kv:
                    current_key = m_kv.group(1)
                    val = m_kv.group(2).strip()
                    if current_key in {"reference_refs", "script_refs", "rubric_refs"} and val:
                        for tok in skill_name_re.findall(val):
                            pass
                        for m in skill_name_re.finditer(val):
                            inbound.add(m.group(0))
                m_item = re.match(r"^\s+-\s+(.+?)\s*$", line)
                if m_item and current_key in {"reference_refs", "script_refs", "rubric_refs"}:
                    for m in skill_name_re.finditer(m_item.group(1)):
                        inbound.add(m.group(0))
    return inbound


def check_skill(
    skill_md: Path,
    inbound_refs: set[str] | None = None,
    allow_partial: bool = False,
) -> list[str]:
    fm = parse_fm(skill_md.read_text(encoding="utf-8"))
    name = fm.get("name", skill_md.parent.name)
    errs: list[str] = []
    repo = _repo_root(skill_md)
    if inbound_refs is None:
        inbound_refs = _collect_inbound_refs(repo)

    # (1) wrap-* に base: があるか
    if name.startswith("wrap-"):
        if not fm.get("base"):
            if not allow_partial:
                errs.append(f"{name}: wrap-* requires 'base:' field (doc/20 Step 7-1)")

    # (2) assign-*-evaluator に pair: があるか
    if name.startswith("assign-") and name.endswith("-evaluator"):
        if not fm.get("pair"):
            if not allow_partial:
                errs.append(
                    f"{name}: assign-*-evaluator requires 'pair:' field (doc/20 Step 7-2)"
                )

    # (3) pair: の相手スキルが存在するか
    pair = fm.get("pair", "")
    if pair and not skill_exists(pair, repo):
        errs.append(
            f"{name}: pair target '{pair}' not found under "
            f"plugins/*/skills or .claude/skills (doc/20 Step 7-3)"
        )

    # (4) dangerous run-* に disable-model-invocation: true があるか
    if name.startswith("run-"):
        danger = fm.get("danger", "false").lower() == "true"
        effect = fm.get("effect", "")
        is_dangerous = danger or effect == "external-mutation"
        dmi = fm.get("disable-model-invocation", "false").lower() == "true"
        if is_dangerous and not dmi:
            errs.append(
                f"{name}: dangerous run-* (danger/effect=external-mutation) "
                f"requires disable-model-invocation: true (doc/20 Step 7-4)"
            )

    # (5) ref-* が到達不能になっていないか
    # 到達経路: (a) model自律呼び出し  (b) user-invocable slash command
    # (c) 他スキルの reference_refs/script_refs/rubric_refs からの参照
    # (a)(b)を両方無効にしても、(c)があれば到達可能とみなす。
    if name.startswith("ref-"):
        dmi = fm.get("disable-model-invocation", "false").lower() == "true"
        ui_false = fm.get("user-invocable", "true").lower() == "false"
        inbound = name in inbound_refs
        if dmi and ui_false and not inbound:
            errs.append(
                f"{name}: ref-* is unreachable "
                f"(disable-model-invocation=true AND user-invocable=false AND "
                f"not referenced by any other skill's reference_refs/script_refs/rubric_refs) "
                f"(doc/20 Step 7-5)"
            )

    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="SKILL.md ファイル群")
    ap.add_argument("--skills-dir", help="スキル群ディレクトリ (各サブディレクトリの SKILL.md を検査)")
    ap.add_argument(
        "--allow-partial",
        action="store_true",
        help="移行途中の skeleton で wrap base / evaluator pair 未確定を一時許容する",
    )
    args = ap.parse_args()

    targets: list[Path] = []
    if args.skills_dir:
        d = Path(args.skills_dir)
        if not d.is_dir():
            print(f"not a directory: {d}", file=sys.stderr)
            return 2
        targets.extend(sorted(d.glob("*/SKILL.md")))
    for s in args.paths:
        targets.append(Path(s))

    if not targets:
        print("usage: lint-skill-dep-step7.py [SKILL.md ...] [--skills-dir DIR]", file=sys.stderr)
        return 2

    all_errs: list[str] = []
    # 全スキル走査時は inbound_refs を一度だけ構築して使い回す（N+1走査を避ける）
    inbound_refs: set[str] | None = None
    if targets:
        inbound_refs = _collect_inbound_refs(_repo_root(targets[0]))
    for t in targets:
        if not t.exists():
            all_errs.append(f"not found: {t}")
            continue
        all_errs.extend(
            check_skill(t, inbound_refs=inbound_refs, allow_partial=args.allow_partial)
        )

    if all_errs:
        for e in all_errs:
            print(e, file=sys.stderr)
        return 1
    suffix = " (partial allowed)" if args.allow_partial else ""
    print(f"ok: doc/20 Step 7 全5条件 PASS ({len(targets)} skills){suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
