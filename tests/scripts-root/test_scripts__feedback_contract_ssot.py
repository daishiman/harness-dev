"""Genuine functional tests for scripts/feedback_contract_ssot.py.

既存 tests/test_feedback_contract_ssot.py を補完し、未カバー経路を実入力で検証する:
  - read_kind (末尾コメント / ハイフン kind / 不在)
  - fallback_inner_text / fallback_outer_text / is_fallback_text (同源性)
  - extract_frontmatter_feedback_contract の yaml 非搭載フォールバックパーサ
    (_parse_feedback_contract_block: max_iterations/skip_reason スカラ + criteria)
  - validate_criteria の非 dict 要素 / 空文字キー / 不正 loop_scope

import module via importlib.util (ハイフン無しだが規約に従い spec_from_file_location)。
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "feedback_contract_ssot.py"


def _load():
    spec = importlib.util.spec_from_file_location("feedback_contract_ssot_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FC = _load()


# --- read_kind ---------------------------------------------------------------
def test_read_kind_plain():
    assert FC.read_kind("kind: run\n") == "run"


def test_read_kind_with_trailing_comment():
    # 末尾コメントを許容するのが本モジュールの統一仕様 (lint 群の乖離解消)
    assert FC.read_kind("kind: wrap  # loop kind\n") == "wrap"


def test_read_kind_hyphenated():
    assert FC.read_kind("kind: elegant-review\n") == "elegant-review"


def test_read_kind_absent_returns_none():
    assert FC.read_kind("name: foo\nversion: 1\n") is None


# --- fallback text helpers ---------------------------------------------------
def test_fallback_inner_text_is_detected_as_fallback():
    t = FC.fallback_inner_text("run-foo")
    assert t.startswith("run-foo ")
    assert t.endswith(FC.FALLBACK_INNER_SUFFIX)
    assert FC.is_fallback_text(t) is True


def test_fallback_outer_text_is_detected_as_fallback():
    t = FC.fallback_outer_text("ユーザー目的X")
    assert t.startswith("ユーザー目的X ")
    assert t.endswith(FC.FALLBACK_OUTER_SUFFIX)
    assert FC.is_fallback_text(t) is True


def test_is_fallback_text_on_real_text_is_false():
    assert FC.is_fallback_text("per-skill 固有の検証基準を満たす") is False


def test_is_fallback_text_handles_none_and_nonstr():
    assert FC.is_fallback_text(None) is False
    assert FC.is_fallback_text(123) is False


# --- validate_criteria edge paths -------------------------------------------
def test_validate_criteria_non_dict_item():
    errs = FC.validate_criteria(["not a dict"])
    assert any("must be object" in e for e in errs)


def test_validate_criteria_empty_required_key():
    c = [
        {"id": "IN1", "loop_scope": "inner", "text": "   ", "verify_by": "test"},
        {"id": "OUT1", "loop_scope": "outer", "text": "ok", "verify_by": "lint"},
    ]
    errs = FC.validate_criteria(c)
    assert any(".text is empty" in e for e in errs)


def test_validate_criteria_bad_loop_scope():
    c = [
        {"id": "IN1", "loop_scope": "sideways", "text": "ok", "verify_by": "test"},
        {"id": "OUT1", "loop_scope": "outer", "text": "ok", "verify_by": "lint"},
    ]
    errs = FC.validate_criteria(c)
    assert any("must be inner or outer" in e for e in errs)


def test_validate_criteria_all_verify_by_enum_accepted():
    for vb in sorted(FC.CRITERIA_VERIFY_BY):
        c = [
            {"id": "IN1", "loop_scope": "inner", "text": "ok", "verify_by": vb},
            {"id": "OUT1", "loop_scope": "outer", "text": "ok", "verify_by": vb},
        ]
        assert FC.validate_criteria(c) == [], f"verify_by={vb} should be valid"


def test_verify_by_live_trial_accepted():
    # D7: 実走証拠 (live-trial verdict) を verify_by 語彙へ追加 (SSOT 1点変更で lint 群へ伝播)
    assert "live-trial" in FC.CRITERIA_VERIFY_BY
    c = [
        {"id": "IN1", "loop_scope": "inner", "text": "ok", "verify_by": "live-trial"},
        {"id": "OUT1", "loop_scope": "outer", "text": "ok", "verify_by": "live-trial"},
    ]
    assert FC.validate_criteria(c) == []


def test_verify_by_live_trial_near_miss_rejected():
    # 負例: underscore 表記の類似語は enum 外 (typo の素通り禁止)
    c = [
        {"id": "IN1", "loop_scope": "inner", "text": "ok", "verify_by": "live_trial"},
        {"id": "OUT1", "loop_scope": "outer", "text": "ok", "verify_by": "lint"},
    ]
    errs = FC.validate_criteria(c)
    assert any("verify_by='live_trial' not in" in e for e in errs)


# --- extract_frontmatter via fallback parser (no-yaml path) ------------------
FM_BLOCK = """---
name: run-x
kind: run
feedback_contract:
  max_iterations: 4
  skip_reason: "n/a for loop kinds"
  criteria:
    - id: IN1
      loop_scope: inner
      text: "inner text"
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: outer text
      verify_by: lint
---
body
"""


def test_fallback_parser_extracts_block(monkeypatch):
    # yaml import を強制失敗させ、最小パーサ経路 (_parse_feedback_contract_block) を踏ませる
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "yaml":
            raise ImportError("forced: yaml unavailable")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    fc = FC.extract_frontmatter_feedback_contract(FM_BLOCK)
    assert isinstance(fc, dict)
    assert fc["max_iterations"] == 4  # スカラが int 化される
    assert fc["skip_reason"] == "n/a for loop kinds"  # クォート剥がし
    assert FC.criteria_ids(fc["criteria"]) == {"IN1", "OUT1"}
    # 抽出結果が SSOT バリデーションを通る
    assert FC.validate_criteria(fc["criteria"]) == []


def test_parse_block_directly_returns_none_when_absent():
    # frontmatter に feedback_contract が無ければ None
    assert FC._parse_feedback_contract_block("name: x\nkind: ref\n") is None


def test_extract_not_starting_with_dashes_is_none():
    assert FC.extract_frontmatter_feedback_contract("no frontmatter here") is None


# --- インラインコメント: yaml 搭載/非搭載の一致 -------------------------------
# 回帰の実例: `verify_by: evaluator  # 検証主体は deck-evaluator` が PyYAML では
# 'evaluator'、フォールバックでは 'evaluator  # 検証主体は…' となり、PyYAML を持つ
# ローカルは緑・持たない CI だけが enum 不一致で赤になった。両経路の一致を固定する。
@pytest.mark.parametrize(
    "raw,want",
    [
        ("evaluator  # 検証主体は deck-evaluator", "evaluator"),
        ("script", "script"),
        ('"a # b"', "a # b"),          # 引用符内の # は値の一部
        ("'x  # y'", "x  # y"),
        ("https://x/y#frag", "https://x/y#frag"),  # 空白なしの # はコメントでない (YAML 規約)
        ("lint\t# tab 区切り", "lint"),
    ],
)
def test_strip_inline_comment_matches_yaml_semantics(raw, want):
    assert FC._strip_inline_comment(raw) == want


def _fm(verify_by: str) -> str:
    return (
        "---\n"
        "kind: run\n"
        "feedback_contract:\n"
        "  criteria:\n"
        "    - id: IN1\n"
        "      loop_scope: inner\n"
        "      text: t\n"
        "      verify_by: lint\n"
        "    - id: OUT1\n"
        "      loop_scope: outer\n"
        f"      verify_by: {verify_by}\n"
        "      text: t\n"
        "---\nbody\n"
    )


def test_fallback_parser_agrees_with_yaml_on_inline_comment():
    """yaml 経路とフォールバック経路が同じ criteria を返す (環境差で lint 結果が割れない)。"""
    text = _fm("evaluator  # 検証主体は deck-evaluator")
    via_yaml = FC.extract_frontmatter_feedback_contract(text)
    fm_only = text.split("\n---", 1)[0].lstrip("-").lstrip("\n")
    via_fallback = FC._parse_feedback_contract_block(fm_only)
    assert via_yaml is not None and via_fallback is not None
    key = lambda fc: [
        {k: c.get(k) for k in ("id", "loop_scope", "verify_by")} for c in fc["criteria"]
    ]
    assert key(via_yaml) == key(via_fallback)
    assert key(via_fallback)[1]["verify_by"] == "evaluator"
    assert key(via_fallback)[1]["verify_by"] in FC.CRITERIA_VERIFY_BY


def test_repo_skill_md_parses_identically_on_both_paths():
    """実 repo の全 SKILL.md で 2 経路の解析結果が一致する (CI と手元の乖離ゼロ)。"""
    mismatches = []
    for path in sorted(ROOT.glob("plugins/*/skills/*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        via_yaml = FC.extract_frontmatter_feedback_contract(text)
        fm_only = text.split("\n---", 1)[0].lstrip("-").lstrip("\n")
        via_fallback = FC._parse_feedback_contract_block(fm_only)
        pick = lambda fc: [
            {k: c.get(k) for k in ("id", "loop_scope", "verify_by")}
            for c in (fc or {}).get("criteria", [])
        ]
        if pick(via_yaml) != pick(via_fallback):
            mismatches.append(str(path.relative_to(ROOT)))
    assert not mismatches, f"yaml/フォールバックで解析が割れる SKILL.md: {mismatches}"
