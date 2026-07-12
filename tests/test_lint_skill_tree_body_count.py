"""lint-skill-tree の P0-2 が frontmatter を除外し本文のみ数えることの機械担保。

frontmatter(feedback_contract/knowledge_loop 等の機械可読契約を含む)は本文ではなく
P0-2(本文300行)の対象外。総行数で数えると契約追加で誤検出するため body-only を保証する。
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "lint_skill_tree",
    ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-skill-tree.py",
)
_M = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_M)


def test_body_excludes_frontmatter():
    fm = "---\n" + "\n".join(f"key{i}: v" for i in range(50)) + "\n---\n"
    body = "\n".join(f"line {i}" for i in range(10))
    assert _M._body_line_count(fm + body) == len((body).splitlines())


def test_no_frontmatter_counts_all():
    text = "\n".join(f"line {i}" for i in range(20))
    assert _M._body_line_count(text) == 20


def test_large_frontmatter_small_body_passes_p0_2():
    # frontmatter 200 行 + 本文 100 行 = 総 300+ でも本文は上限内
    fm = "---\n" + "\n".join(f"key{i}: v" for i in range(200)) + "\n---\n"
    body = "\n".join(f"body {i}" for i in range(100))
    assert _M._body_line_count(fm + body) <= _M.MAX_SKILL_LINES


def test_body_over_limit_still_detected():
    fm = "---\nname: x\n---\n"
    body = "\n".join(f"body {i}" for i in range(_M.MAX_SKILL_LINES + 5))
    assert _M._body_line_count(fm + body) > _M.MAX_SKILL_LINES
