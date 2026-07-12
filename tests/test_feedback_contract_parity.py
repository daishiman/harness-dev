"""feedback_contract の SSOT 整合 (drift 防止) を機械担保するテスト。

elegant-review (2026-06-24) で検出した綻びを再発防止する:
- SS2/LS1: 評価・改善ループ契約節が templates 直書き (template モード) と
  render-combinators 定数 (atomic モード) の2経路に並存し、片方だけ文面が drift
  していた。両経路は各 COMPOSER_MODE で load-bearing なので、文面一致を test で固定。
- SS10/LS10/MD2: brief 非導出のフォールバック既定文面の正本を feedback_contract_ssot に
  集約し、render-frontmatter の出力と一致することを固定 (is_fallback_text で検出可能)。
- LS4: kind 抽出を feedback_contract_ssot.read_kind に一本化したことを固定。
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_BUILD = ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
RENDER_COMBINATORS = RUN_BUILD / "scripts" / "render-combinators.py"
RENDER_FRONTMATTER = RUN_BUILD / "scripts" / "render-frontmatter.py"
SSOT = ROOT / "scripts" / "feedback_contract_ssot.py"
TEMPLATES = RUN_BUILD / "templates"
VALIDATE_BUILD_TRACE = RUN_BUILD / "scripts" / "validate-build-trace.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_templates_match_combinator_section_body():
    """templates 直書きの評価・改善ループ契約節 == combinator 定数 (両経路の文面一致)。"""
    rc = _load(RENDER_COMBINATORS, "render_combinators")
    section = rc.FEEDBACK_CONTRACT_SECTION
    heading = section.splitlines()[0]
    body = "".join(section.splitlines()[1:])  # 定数本文は1段落 (内部改行なし)
    assert heading == "## 評価・改善ループ契約"
    for tpl in ("run.md", "wrap.md", "delegate.md"):
        text = (TEMPLATES / tpl).read_text(encoding="utf-8")
        assert heading in text, f"{tpl}: 評価・改善ループ契約 見出し欠落"
        assert body in text, (
            f"{tpl}: 契約節の文面が render-combinators の FEEDBACK_CONTRACT_SECTION と drift"
        )


def test_render_frontmatter_fallback_matches_ssot():
    """brief 非導出時の fallback 文面が SSOT (feedback_contract_ssot) と同源。"""
    fc = _load(SSOT, "feedback_contract_ssot")
    rf = _load(RENDER_FRONTMATTER, "render_frontmatter")
    m = rf._feedback_contract_mapping({"skill_name": "run-x", "goal": "G を達成する"})
    assert m["feedback_contract_inner_criteria_text"] == fc.fallback_inner_text("run-x")
    assert m["feedback_contract_outer_criteria_text"] == fc.fallback_outer_text("G を達成する")
    assert fc.is_fallback_text(m["feedback_contract_inner_criteria_text"])
    assert fc.is_fallback_text(m["feedback_contract_outer_criteria_text"])


def test_is_fallback_text_rejects_genuine_criteria():
    fc = _load(SSOT, "feedback_contract_ssot")
    assert not fc.is_fallback_text("demo lint が exit0 で通過する")
    assert not fc.is_fallback_text("")


def test_read_kind_single_implementation():
    """kind 抽出は末尾コメント・ハイフンを許容する単一実装 (lint 間の乖離を排除)。"""
    fc = _load(SSOT, "feedback_contract_ssot")
    assert fc.read_kind("kind: run\n") == "run"
    assert fc.read_kind("kind: run  # loop 実行系\n") == "run"
    assert fc.read_kind("kind: ref\n") == "ref"
    assert fc.read_kind("name: x\nno kind line\n") is None


# --- LS-01/06/08/09: validate-build-trace の criteria 検査が SSOT へ委譲済みであることの担保 ---
# 旧 _validate_feedback_contract は L381-419 で criteria ループ (必須キー / id pattern /
# id 重複 / verify_by enum / loop_scope / inner+outer) を独自再実装し、SSOT
# (feedback_contract_ssot.validate_criteria) と二重実装になっていた。委譲後は loop-kind の
# 非空 criteria に対する戻り値が FC.validate_criteria と完全一致する。これを固定して drift を封じる。

def _loop_kind_data(criteria):
    """loop 実行系 (run) の最小トレース断片。kind/skip_reason escape を素通りし
    criteria 検査経路 (委譲点) に到達させる。"""
    return {"skill_kind": "run", "feedback_contract": {"criteria": criteria}}


_PARITY_CRITERIA_CASES = [
    # 正常 (inner+outer 揃い)
    [
        {"id": "IN1", "loop_scope": "inner", "text": "t", "verify_by": "lint"},
        {"id": "OUT1", "loop_scope": "outer", "text": "t", "verify_by": "test"},
    ],
    # id pattern 違反
    [
        {"id": "X9", "loop_scope": "inner", "text": "t", "verify_by": "lint"},
        {"id": "OUT1", "loop_scope": "outer", "text": "t", "verify_by": "lint"},
    ],
    # verify_by enum 違反
    [
        {"id": "IN1", "loop_scope": "inner", "text": "t", "verify_by": "magic"},
        {"id": "OUT1", "loop_scope": "outer", "text": "t", "verify_by": "lint"},
    ],
    # id 重複
    [
        {"id": "IN1", "loop_scope": "inner", "text": "t", "verify_by": "lint"},
        {"id": "IN1", "loop_scope": "outer", "text": "t", "verify_by": "lint"},
    ],
    # inner 欠落 (outer のみ → scope 欠落検出)
    [
        {"id": "OUT1", "loop_scope": "outer", "text": "t", "verify_by": "lint"},
    ],
    # 必須キー欠落 + 非 dict 要素混在 + loop_scope 不正
    [
        {"id": "IN1", "loop_scope": "inner"},  # text/verify_by 欠落
        "not-a-dict",
        {"id": "OUT1", "loop_scope": "weird", "text": "t", "verify_by": "lint"},
    ],
]


def test_validate_feedback_contract_delegates_to_ssot():
    """loop-kind の非空 criteria では _validate_feedback_contract の戻りが
    FC.validate_criteria の戻りと完全一致 (二重実装解消の機械担保)。"""
    M = _load(VALIDATE_BUILD_TRACE, "validate_build_trace")
    FC = _load(SSOT, "feedback_contract_ssot")
    for criteria in _PARITY_CRITERIA_CASES:
        expected = FC.validate_criteria(
            criteria, require_both_scopes=True, prefix="feedback_contract.criteria"
        )
        got = M._validate_feedback_contract(_loop_kind_data(criteria))
        assert got == expected, (
            f"委譲ドリフト検出: criteria={criteria}\n got={got}\n expected={expected}"
        )


def test_validate_feedback_contract_propagates_ssot_canonical_messages():
    """SSOT の正準メッセージがそのまま伝播し、旧独自 suffix は残存しない。"""
    M = _load(VALIDATE_BUILD_TRACE, "validate_build_trace")
    errs = M._validate_feedback_contract(
        _loop_kind_data(
            [
                {"id": "X9", "loop_scope": "inner", "text": "t", "verify_by": "magic"},
                {"id": "OUT1", "loop_scope": "outer", "text": "t", "verify_by": "lint"},
            ]
        )
    )
    assert any("must match ^(IN|OUT|C)[0-9]+$" in e for e in errs)
    assert any("verify_by='magic' not in" in e for e in errs)
    # 旧再実装の独自 suffix は SSOT 委譲で消える (canonical 採用)
    assert all("と同型" not in e for e in errs)


def test_ssot_validate_criteria_signature_supports_delegation():
    """委譲が依拠する FC.validate_criteria のシグネチャ契約 (prefix/require_both_scopes) を固定。"""
    import inspect

    FC = _load(SSOT, "feedback_contract_ssot")
    sig = inspect.signature(FC.validate_criteria)
    assert "require_both_scopes" in sig.parameters
    assert "prefix" in sig.parameters
    # prefix が出力メッセージへ反映される (アダプタが固有 prefix を渡せる)
    out = FC.validate_criteria([], prefix="XYZ")
    assert out and out[0].startswith("XYZ")
