"""feedback_contract_ssot (criteria 単一正本) の機械担保テスト。

検査対象:
  - validate_criteria: id pattern / verify_by enum / loop_scope / inner+outer 必須 / 重複
  - criteria_ids 抽出
  - is_loop_kind 判定
  - extract_frontmatter_feedback_contract (yaml fallback 含む)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import feedback_contract_ssot as FC  # noqa: E402


def _ok_criteria():
    return [
        {"id": "IN1", "loop_scope": "inner", "text": "内側基準", "verify_by": "test"},
        {"id": "OUT1", "loop_scope": "outer", "text": "外側基準", "verify_by": "lint"},
    ]


def test_valid_criteria_passes():
    assert FC.validate_criteria(_ok_criteria()) == []


def test_empty_criteria_is_error():
    assert FC.validate_criteria([])
    assert FC.validate_criteria("oops")


def test_bad_id_pattern_is_error():
    c = _ok_criteria()
    c[0]["id"] = "X9"
    errs = FC.validate_criteria(c)
    assert any("must match" in e for e in errs)


def test_bad_verify_by_enum_is_error():
    c = _ok_criteria()
    c[0]["verify_by"] = "magic"
    errs = FC.validate_criteria(c)
    assert any("verify_by" in e and "magic" in e for e in errs)


def test_missing_outer_scope_is_error():
    c = [_ok_criteria()[0]]  # inner のみ
    errs = FC.validate_criteria(c)
    assert any("outer" in e for e in errs)


def test_missing_inner_scope_is_error():
    c = [_ok_criteria()[1]]  # outer のみ
    errs = FC.validate_criteria(c)
    assert any("inner" in e for e in errs)


def test_duplicate_id_is_error():
    c = _ok_criteria()
    c[1]["id"] = "IN1"
    errs = FC.validate_criteria(c)
    assert any("duplicated" in e for e in errs)


def test_require_both_scopes_false_allows_single():
    c = [_ok_criteria()[0]]
    assert FC.validate_criteria(c, require_both_scopes=False) == []


def test_criteria_ids():
    assert FC.criteria_ids(_ok_criteria()) == {"IN1", "OUT1"}
    assert FC.criteria_ids(None) == set()


def test_is_loop_kind():
    assert FC.is_loop_kind("run")
    assert FC.is_loop_kind("wrap")
    assert FC.is_loop_kind("delegate")
    assert not FC.is_loop_kind("ref")
    assert not FC.is_loop_kind("assign")
    assert not FC.is_loop_kind(None)


FRONTMATTER_SAMPLE = """---
name: run-x
kind: run
feedback_contract:
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: hello
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: world
      verify_by: lint
---
body text
"""


def test_extract_frontmatter_feedback_contract():
    fc = FC.extract_frontmatter_feedback_contract(FRONTMATTER_SAMPLE)
    assert isinstance(fc, dict)
    assert FC.criteria_ids(fc.get("criteria")) == {"IN1", "OUT1"}
    assert FC.validate_criteria(fc.get("criteria")) == []


def test_extract_no_feedback_contract_returns_none():
    md = "---\nname: run-y\nkind: run\n---\nbody"
    assert FC.extract_frontmatter_feedback_contract(md) is None


def test_extract_no_frontmatter_returns_none():
    assert FC.extract_frontmatter_feedback_contract("# just a heading") is None
