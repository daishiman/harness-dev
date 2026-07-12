#!/usr/bin/env python3
"""skill-fixture-runner — 既存16スキルの smoke regression test (stdlib only).

設計書08章「Gotchas から決定論へ」段階3 (CI script) / 09章 P0 評価層に対応。
量産スキルの継続品質保証を機械化する。

実行内容 (各スキルに対し):
  1. SKILL.md frontmatter validate (validate-frontmatter.py)
  2. 名前規約 (lint-skill-name.py)
  3. 行数 cap (lint-skill-tree.py)
  4. description 形式 (lint-skill-description.py)
  5. fixture baseline JSON があれば対比

出力: eval-log/fixture-results.json
Exit: 全PASSで0、1件でも失敗で1
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "plugins" / "harness-creator" / "skills"
FIXTURE_DIR = ROOT / "eval-log" / "fixtures"
OUT_PATH = ROOT / "eval-log" / "fixture-results.json"
LINT = ROOT / "plugins" / "skill-governance-lint" / "scripts"


def run(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return p.returncode, (p.stdout + p.stderr)[-2000:]
    except Exception as e:
        return 99, str(e)


def check_skill(skill_path: Path) -> dict:
    name = skill_path.name
    skill_md = skill_path / "SKILL.md"
    result: dict = {"skill": name, "checks": [], "passed": True}
    if not skill_md.exists():
        result["passed"] = False
        result["checks"].append({"name": "exists", "passed": False, "msg": "SKILL.md missing"})
        return result
    checks = [
        ("validate-frontmatter", [sys.executable, str(LINT / "validate-frontmatter.py"), str(skill_md)]),
        ("lint-skill-name", [sys.executable, str(LINT / "lint-skill-name.py"), str(skill_md)]),
    ]
    for chk_name, cmd in checks:
        rc, out = run(cmd)
        ok = rc == 0
        result["checks"].append({"name": chk_name, "passed": ok, "msg": out if not ok else ""})
        if not ok:
            result["passed"] = False
    # fixture baseline 比較
    fixture = FIXTURE_DIR / f"{name}.baseline.json"
    if fixture.exists():
        try:
            baseline = json.loads(fixture.read_text())
            cur_lines = len(skill_md.read_text().splitlines())
            max_lines = baseline.get("max_lines", 300)
            if cur_lines > max_lines:
                result["passed"] = False
                result["checks"].append({
                    "name": "fixture-line-cap",
                    "passed": False,
                    "msg": f"{cur_lines} > baseline.max_lines={max_lines}",
                })
        except Exception as e:
            result["checks"].append({"name": "fixture-parse", "passed": False, "msg": str(e)})
    return result


def main() -> int:
    if not SKILLS_DIR.exists():
        print(f"missing: {SKILLS_DIR}", file=sys.stderr)
        return 2
    results = [check_skill(d) for d in sorted(SKILLS_DIR.iterdir()) if d.is_dir()]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({"results": results}, indent=2, ensure_ascii=False))
    failed = [r for r in results if not r["passed"]]
    print(f"skill-fixture-runner: {len(results)} skills, {len(failed)} failed")
    for r in failed:
        print(f"  FAIL {r['skill']}: {[c['name'] for c in r['checks'] if not c['passed']]}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
