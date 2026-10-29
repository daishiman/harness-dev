#!/usr/bin/env python3
"""set-qa-source (出所メタデータの追記専用 writer) の acceptance tests。

schema 1.1 移行前に記録された qa には ``source`` も ``legacy_exempt`` も持たないものがあり、
対話由来か書面索引かを監査が判別できない。reopen → 再確認で回答ごと作り直すと一次根拠を
失うため、逐語を保ったまま出所だけを補える経路を用意した。ただし後付けであることは
``source_provenance`` で常に可視化し、対話時に記録された source の差し替えは拒否する。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SKILL_DIR.parents[1]
TAXONOMY = (
    PLUGIN_ROOT
    / "skills"
    / "ref-system-design-knowledge"
    / "references"
    / "system-category-taxonomy.json"
)


def _load_mod():
    path = SKILL_DIR / "scripts" / "apply-spec-transition.py"
    spec = importlib.util.spec_from_file_location("apply_spec_transition_qa_source", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_mod()

BACKFILL_PROVENANCE = {"mode": "metadata_backfill", "writer": "set-qa-source"}


def _taxonomy() -> dict:
    return json.loads(TAXONOMY.read_text(encoding="utf-8"))


def _state_with_qa(**extra) -> dict:
    state = mod.init_state(_taxonomy())
    entry = {"id": "qa-legacy", "question": "元の質問", "answer": "元の回答"}
    entry.update(extra)
    state["qa_log"].append(entry)
    return state


def _entry(state: dict) -> dict:
    return next(q for q in state["qa_log"] if q["id"] == "qa-legacy")


def test_dialogue_source_backfill_preserves_qa_and_marks_provenance():
    state = _state_with_qa()
    mod.set_qa_source(state, "qa-legacy", {"kind": "user-dialogue"})
    entry = _entry(state)
    assert entry["question"] == "元の質問" and entry["answer"] == "元の回答"
    assert entry["source"] == {"kind": "user-dialogue"}
    # 後付けであることを隠さない。対話時に記録された source と区別できる必要がある。
    assert entry["source_provenance"] == BACKFILL_PROVENANCE


def test_same_payload_replay_is_idempotent():
    state = _state_with_qa()
    mod.set_qa_source(state, "qa-legacy", {"kind": "user-dialogue"})
    before = json.dumps(state, ensure_ascii=False, sort_keys=True)
    mod.set_qa_source(state, "qa-legacy", {"kind": "user-dialogue"})
    assert json.dumps(state, ensure_ascii=False, sort_keys=True) == before


def test_existing_dialogue_source_is_protected():
    state = _state_with_qa(source={"kind": "user-dialogue"})
    with pytest.raises(mod.TransitionError, match="保護"):
        mod.set_qa_source(state, "qa-legacy", {"kind": "user-dialogue"})


def test_differing_payload_after_backfill_is_rejected():
    answer = "元の回答"
    state = _state_with_qa()
    mod.set_qa_source(state, "qa-legacy", {"kind": "user-dialogue"})
    written = {
        "kind": "written-requirements",
        "path": "docs/brief.md",
        "section": "目的",
        "sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
    }
    with pytest.raises(mod.TransitionError, match="異なる値の再適用"):
        mod.set_qa_source(state, "qa-legacy", written)


def test_written_source_requires_digest_matching_answer():
    state = _state_with_qa()
    with pytest.raises(mod.TransitionError, match="answer 原文と不一致"):
        mod.set_qa_source(state, "qa-legacy", {
            "kind": "written-requirements",
            "path": "docs/brief.md",
            "section": "目的",
            "sha256": "0" * 64,
        })


def test_written_source_accepts_matching_digest():
    state = _state_with_qa()
    digest = hashlib.sha256("元の回答".encode("utf-8")).hexdigest()
    mod.set_qa_source(state, "qa-legacy", {
        "kind": "written-requirements",
        "path": "docs/brief.md",
        "section": "目的",
        "sha256": digest,
    })
    assert _entry(state)["source"]["sha256"] == digest


@pytest.mark.parametrize("path", ["/abs/brief.md", "../outside/brief.md", "  "])
def test_written_source_rejects_unsafe_path(path):
    state = _state_with_qa()
    with pytest.raises(mod.TransitionError, match="安全な相対パス"):
        mod.set_qa_source(state, "qa-legacy", {
            "kind": "written-requirements",
            "path": path,
            "section": "目的",
            "sha256": hashlib.sha256("元の回答".encode("utf-8")).hexdigest(),
        })


def test_unknown_kind_is_rejected():
    state = _state_with_qa()
    with pytest.raises(mod.TransitionError, match="source.kind"):
        mod.set_qa_source(state, "qa-legacy", {"kind": "ai-summary"})


def test_missing_qa_id_is_rejected():
    state = _state_with_qa()
    with pytest.raises(mod.TransitionError, match="存在しない qa_id"):
        mod.set_qa_source(state, "qa-absent", {"kind": "user-dialogue"})


def test_cli_set_qa_source(tmp_path):
    state_path = tmp_path / "spec-state.json"
    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--out", str(state_path)]) == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["qa_log"].append({"id": "qa-legacy", "question": "q", "answer": "a"})
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    assert mod.main([
        "set-qa-source", "--state", str(state_path),
        "--qa-id", "qa-legacy", "--source", json.dumps({"kind": "user-dialogue"}),
    ]) == 0
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    entry = next(q for q in saved["qa_log"] if q["id"] == "qa-legacy")
    assert entry["source"] == {"kind": "user-dialogue"}
    assert entry["source_provenance"] == BACKFILL_PROVENANCE


def test_cli_set_qa_source_bad_kind_returns_1(tmp_path):
    state_path = tmp_path / "spec-state.json"
    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--out", str(state_path)]) == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["qa_log"].append({"id": "qa-legacy", "question": "q", "answer": "a"})
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    before = state_path.read_text(encoding="utf-8")

    assert mod.main([
        "set-qa-source", "--state", str(state_path),
        "--qa-id", "qa-legacy", "--source", json.dumps({"kind": "ai-summary"}),
    ]) == 1
    assert state_path.read_text(encoding="utf-8") == before


# --- 非一次 kind と型不正の修復 -------------------------------------------
# 利用者の新規入力を伴わない entry を user-dialogue と索引すると、C06 中立性監査と
# foundation trace が「利用者が答えた」という前提のまま偽の一次根拠を数える。専用 kind で
# 明示し、由来を必須フィールドとして要求する。あわせて、契約が object と定める source に
# 素の文字列 (注記) が混入していた 8 件を、注記を捨てずに契約形状へ戻せることを固定する。


def test_harness_remediation_requires_trigger():
    state = _state_with_qa()
    with pytest.raises(mod.TransitionError, match="trigger"):
        mod.set_qa_source(state, "qa-legacy", {"kind": "harness-remediation"})


def test_harness_remediation_records_its_trigger():
    state = _state_with_qa()
    mod.set_qa_source(
        state, "qa-legacy", {"kind": "harness-remediation", "trigger": "elegant-review F-0003"}
    )
    assert _entry(state)["source"] == {
        "kind": "harness-remediation",
        "trigger": "elegant-review F-0003",
    }


def test_derived_consolidation_requires_origin_and_approval():
    state = _state_with_qa()
    with pytest.raises(mod.TransitionError, match="derived_from"):
        mod.set_qa_source(state, "qa-legacy", {"kind": "derived-consolidation", "approval_ref": "appr-040"})
    with pytest.raises(mod.TransitionError, match="approval_ref"):
        mod.set_qa_source(state, "qa-legacy", {"kind": "derived-consolidation", "derived_from": ["qa-1"]})


def test_derived_consolidation_records_origin_and_approval():
    state = _state_with_qa()
    mod.set_qa_source(
        state,
        "qa-legacy",
        {"kind": "derived-consolidation", "derived_from": ["qa-1", "qa-2"], "approval_ref": "appr-040"},
    )
    assert _entry(state)["source"] == {
        "kind": "derived-consolidation",
        "derived_from": ["qa-1", "qa-2"],
        "approval_ref": "appr-040",
    }


def test_type_invalid_source_is_repaired_and_note_is_preserved():
    # 素の文字列は「対話経路で記録済みの source」ではなく壊れた値なので保護対象に含めない。
    # ただし注記本文は、なぜこの qa が存在するかの唯一の手掛かりなので捨てない。
    state = _state_with_qa(source="renumbered_from=qa-144 (qa id 衝突解消)")
    mod.set_qa_source(state, "qa-legacy", {"kind": "user-dialogue"})
    entry = _entry(state)
    assert entry["source"] == {"kind": "user-dialogue"}
    assert entry["source_note"] == "renumbered_from=qa-144 (qa id 衝突解消)"
    assert entry["source_provenance"] == {"mode": "type_repair", "writer": "set-qa-source"}


def test_repaired_source_replay_is_idempotent():
    state = _state_with_qa(source="renumbered_from=qa-144")
    mod.set_qa_source(state, "qa-legacy", {"kind": "user-dialogue"})
    before = json.dumps(state, ensure_ascii=False, sort_keys=True)
    mod.set_qa_source(state, "qa-legacy", {"kind": "user-dialogue"})
    assert json.dumps(state, ensure_ascii=False, sort_keys=True) == before


def test_repaired_source_cannot_be_silently_reinterpreted():
    state = _state_with_qa(source="renumbered_from=qa-144")
    mod.set_qa_source(state, "qa-legacy", {"kind": "user-dialogue"})
    with pytest.raises(mod.TransitionError, match="異なる値の再適用"):
        mod.set_qa_source(
            state, "qa-legacy", {"kind": "harness-remediation", "trigger": "後から書き換え"}
        )


# --- 主経路 (apply_turn) の source も同じ契約で検査する ---------------------
# 後付け経路 (set-qa-source) だけを厳しくし、新規 entry を作る主経路が素通りだと契約が逆転する。
# 特に危険なのが path/section/sha256 を持たない written-requirements で、「書面を典拠に索引した」
# と主張しながら原文ハッシュを一切持たない entry が決定論ゲート緑のまま残せてしまう
# (validate-coverage-matrix はこの形状を捕まえない)。

MALFORMED_TURN_SOURCES = [
    ("素の文字列", "対話で確認"),
    ("未知 kind", {"kind": "ai-guess"}),
    # path/section/sha256 が全欠落。原文へ遡及できない「書面典拠」を主張させない。
    ("原文ハッシュ無しの書面主張", {"kind": "written-requirements"}),
    ("user-dialogue に余分な key", {"kind": "user-dialogue", "path": "a.md"}),
    ("trigger 無しの是正", {"kind": "harness-remediation"}),
]


@pytest.mark.parametrize(
    "source", [value for _, value in MALFORMED_TURN_SOURCES],
    ids=[label for label, _ in MALFORMED_TURN_SOURCES],
)
def test_apply_turn_rejects_contract_violating_source(source):
    state = mod.init_state(_taxonomy())
    with pytest.raises(mod.TransitionError):
        mod.apply_turn(
            state,
            {"qa_id": "qa-new", "question": "q", "answer": "a", "source": source, "ops": []},
        )
    assert not state["qa_log"], "拒否した turn の entry を残さない"


def test_apply_turn_normalizes_accepted_source():
    state = mod.init_state(_taxonomy())
    mod.apply_turn(
        state,
        {
            "qa_id": "qa-new",
            "question": "q",
            "answer": "a",
            # 前後空白は writer が正規化する。後付け経路と同じ形へ揃うことを固定する。
            "source": {"kind": "harness-remediation", "trigger": "  content-review medium  "},
            "ops": [],
        },
    )
    assert state["qa_log"][-1]["source"] == {
        "kind": "harness-remediation",
        "trigger": "content-review medium",
    }


def test_apply_turn_written_source_requires_digest_matching_answer():
    state = mod.init_state(_taxonomy())
    written = {
        "kind": "written-requirements",
        "path": "docs/brief.md",
        "section": "目的",
        "sha256": hashlib.sha256("別の本文".encode("utf-8")).hexdigest(),
    }
    with pytest.raises(mod.TransitionError, match="answer 原文と不一致"):
        mod.apply_turn(
            state,
            {"qa_id": "qa-new", "question": "q", "answer": "この回答", "source": written, "ops": []},
        )


@pytest.mark.parametrize("broken", ["", 0, [], False])
def test_type_repair_note_is_always_a_readable_string(broken):
    # 退避先は「読める注記」。"" / 0 / [] / False をそのまま代入すると writer は受理するが
    # schema (minLength 1) が拒否する値を書けてしまう。かといって捨てると壊れた値が
    # 入っていた事実まで消えるので、型と値を明示した文字列へ包んで残す。
    state = _state_with_qa(source=broken)
    mod.set_qa_source(state, "qa-legacy", {"kind": "user-dialogue"})
    note = _entry(state)["source_note"]
    assert isinstance(note, str) and note.strip()
    assert repr(broken) in note
