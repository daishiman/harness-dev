#!/usr/bin/env python3
"""fix-qa-knowledge-ref (壊れた knowledge_ref だけの接地し直し) の acceptance tests。

``set-qa-design-applications`` は design_applications を丸ごと一単位として保護するため、
対話経路 (provenance なし) の entry では綴り違いすら訂正できず、参照先の無い引用が
``validate-design-knowledge-refs.py`` を恒久的に赤にしていた。この op は保護意図
(対話で得た解釈内容を後から書き換えない) を壊さない範囲だけを開ける。

したがって固定すべき不変則は 2 方向ある。
- 通すべきもの: 旧 ref が実在せず、新 ref (と anchor) が実在する差し替え。旧 ref の path は
  実在するが見出しだけが無い場合の、同じ文書内の見出しへの訂正。
- 拒むべきもの: 実在する参照の付け替え (=解釈の変更)、実在しない先への差し替え、
  見出しの無い anchor、対象 application の不在、見出しだけ壊れた参照の別文書への付け替え。
あわせて解釈本文 (principle/rationale/tradeoffs/applicability) が不変であることと、
訂正痕跡が append-only で残ることを検査する。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "apply-spec-transition.py"
_SPEC = importlib.util.spec_from_file_location("apply_spec_transition_fix_ref", SCRIPT)
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
TransitionError = _MOD.TransitionError
fix_qa_knowledge_ref = _MOD.fix_qa_knowledge_ref

BROKEN = "refs/testing-strategy.md#中核概念"
FIXED = "refs/test-strategy.md#中核概念"


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    card = tmp_path / "refs" / "test-strategy.md"
    card.parent.mkdir(parents=True)
    card.write_text("# Test Strategy\n\n## 中核概念\n\n本文\n", encoding="utf-8")
    return tmp_path


def _state(*refs: str) -> dict:
    return {
        "qa_log": [
            {
                "id": "qa-240",
                "question": "テストはどこまで自動化するか",
                "answer": "認可と冪等は自動、描画は目視",
                "design_applications": [
                    {
                        "knowledge_ref": ref,
                        "principle": "risk-based testing",
                        "applicability": "applied",
                        "rationale": "壊れても画面上は正常に見える欠陥を優先する",
                        "tradeoffs": ["描画の退行は自動検知できない"],
                    }
                    for ref in refs
                ],
            }
        ]
    }


def _apps(state: dict) -> list[dict]:
    return state["qa_log"][0]["design_applications"]


def test_broken_ref_is_regrounded(repo):
    state = _state(BROKEN)
    fix_qa_knowledge_ref(state, "qa-240", BROKEN, FIXED, repo)
    assert _apps(state)[0]["knowledge_ref"] == FIXED


def test_interpretation_body_is_untouched(repo):
    state = _state(BROKEN)
    before = {k: v for k, v in _apps(state)[0].items() if k != "knowledge_ref"}
    fix_qa_knowledge_ref(state, "qa-240", BROKEN, FIXED, repo)
    after = {k: v for k, v in _apps(state)[0].items() if k != "knowledge_ref"}
    assert before == after


def test_all_matching_applications_are_corrected(repo):
    state = _state(BROKEN, BROKEN, "refs/test-strategy.md#中核概念")
    fix_qa_knowledge_ref(state, "qa-240", BROKEN, FIXED, repo)
    assert [a["knowledge_ref"] for a in _apps(state)] == [FIXED, FIXED, FIXED]
    assert state["qa_log"][0]["knowledge_ref_corrections"][0]["applied_to"] == 2


def test_correction_is_recorded_as_audit_trail(repo):
    state = _state(BROKEN)
    fix_qa_knowledge_ref(state, "qa-240", BROKEN, FIXED, repo)
    record = state["qa_log"][0]["knowledge_ref_corrections"][0]
    assert record["old_ref"] == BROKEN
    assert record["new_ref"] == FIXED
    assert record["writer"] == "fix-qa-knowledge-ref"


def test_replaying_the_same_correction_is_idempotent(repo):
    state = _state(BROKEN)
    fix_qa_knowledge_ref(state, "qa-240", BROKEN, FIXED, repo)
    snapshot = json.dumps(state, ensure_ascii=False, sort_keys=True)
    fix_qa_knowledge_ref(state, "qa-240", BROKEN, FIXED, repo)
    assert json.dumps(state, ensure_ascii=False, sort_keys=True) == snapshot


def test_repointing_an_existing_ref_is_rejected(repo):
    # 実在する参照の付け替えは「どの知識で判断したか」の書き換えであり、保護対象。
    other = repo / "refs" / "clean-code.md"
    other.write_text("# Clean Code\n\n## 中核概念\n\n本文\n", encoding="utf-8")
    state = _state(FIXED)
    with pytest.raises(TransitionError, match="実在する参照の付け替え"):
        fix_qa_knowledge_ref(state, "qa-240", FIXED, "refs/clean-code.md#中核概念", repo)


def test_broken_anchor_in_an_existing_document_is_corrected_in_place(repo):
    # path は実在し見出しだけが無い参照は validator が赤にするが、どの文書で判断したかは生きている。
    broken = "refs/test-strategy.md#中核の概念"
    state = _state(broken)
    fix_qa_knowledge_ref(state, "qa-240", broken, FIXED, repo)
    assert _apps(state)[0]["knowledge_ref"] == FIXED
    record = state["qa_log"][0]["knowledge_ref_corrections"][0]
    assert record["reason"].startswith("見出しが実在しない引用を")


def test_broken_anchor_cannot_be_repointed_to_another_document(repo):
    other = repo / "refs" / "clean-code.md"
    other.write_text("# Clean Code\n\n## 中核概念\n\n本文\n", encoding="utf-8")
    broken = "refs/test-strategy.md#中核の概念"
    state = _state(broken)
    with pytest.raises(TransitionError, match="同じ文書内に限る"):
        fix_qa_knowledge_ref(state, "qa-240", broken, "refs/clean-code.md#中核概念", repo)


def test_valid_ref_without_anchor_is_still_protected(repo):
    # anchor の無い参照は path の実在だけで有効。見出しを足す変更も付け替えとして拒否する。
    state = _state("refs/test-strategy.md")
    with pytest.raises(TransitionError, match="実在する参照の付け替え"):
        fix_qa_knowledge_ref(state, "qa-240", "refs/test-strategy.md", FIXED, repo)


def test_new_ref_must_exist(repo):
    state = _state(BROKEN)
    with pytest.raises(TransitionError, match="new_ref の参照先が実在しない"):
        fix_qa_knowledge_ref(state, "qa-240", BROKEN, "refs/absent.md#中核概念", repo)


def test_new_anchor_must_exist(repo):
    state = _state(BROKEN)
    with pytest.raises(TransitionError, match="見出しが実在しない"):
        fix_qa_knowledge_ref(state, "qa-240", BROKEN, "refs/test-strategy.md#無い見出し", repo)


def test_missing_old_ref_is_rejected(repo):
    state = _state("refs/other-broken.md#中核概念")
    with pytest.raises(TransitionError, match="old_ref に一致する design_application が無い"):
        fix_qa_knowledge_ref(state, "qa-240", BROKEN, FIXED, repo)


@pytest.mark.parametrize("bad", ["/etc/passwd#x", "../outside.md#x", "   "])
def test_unsafe_refs_are_rejected(repo, bad):
    state = _state(BROKEN)
    with pytest.raises(TransitionError):
        fix_qa_knowledge_ref(state, "qa-240", bad, FIXED, repo)


def test_identical_refs_are_rejected(repo):
    state = _state(BROKEN)
    with pytest.raises(TransitionError, match="同一"):
        fix_qa_knowledge_ref(state, "qa-240", BROKEN, BROKEN, repo)


def test_qa_without_design_applications_is_rejected(repo):
    state = {"qa_log": [{"id": "qa-240"}]}
    with pytest.raises(TransitionError, match="design_applications を持たない"):
        fix_qa_knowledge_ref(state, "qa-240", BROKEN, FIXED, repo)


def test_unknown_qa_id_is_rejected(repo):
    state = _state(BROKEN)
    with pytest.raises(TransitionError):
        fix_qa_knowledge_ref(state, "qa-999", BROKEN, FIXED, repo)


# plugin を別の場所へ install した利用側 repo では、C04 card は repo root に無く、validator は
# 自 plugin root で解決し直す。writer の実在判定が repo root だけだと、validator が有効と認める
# 参照の付け替えを許し、推奨形への訂正を拒んでしまう。
CARD_DIR = "plugins/system-spec-harness/skills/ref-system-design-knowledge/references"


def test_plugin_layout_ref_that_resolves_via_plugin_root_is_not_repointed(tmp_path):
    assert not (tmp_path / "plugins").exists()
    state = _state(f"{CARD_DIR}/ddd.md#中核概念")
    with pytest.raises(TransitionError, match="実在する参照の付け替え"):
        fix_qa_knowledge_ref(state, "qa-240", f"{CARD_DIR}/ddd.md#中核概念", f"{CARD_DIR}/clean-architecture.md#中核概念", tmp_path)


def test_typo_ref_is_regrounded_to_the_plugin_layout_in_a_consumer_repo(tmp_path):
    assert not (tmp_path / "plugins").exists()
    broken = f"{CARD_DIR}/domain-driven-design.md#中核概念"
    fixed = f"{CARD_DIR}/ddd.md#中核概念"
    state = _state(broken)
    fix_qa_knowledge_ref(state, "qa-240", broken, fixed, tmp_path)
    assert [app["knowledge_ref"] for app in _apps(state)] == [fixed]
