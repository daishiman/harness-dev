"""The published spec-state schema mirrors the writer's version boundary."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest


ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "plugins" / "system-spec-harness"
SCHEMA = PLUGIN / "schemas" / "spec-state.schema.json"
ELICIT = PLUGIN / "skills" / "run-system-spec-elicit"
FIXTURES = ELICIT / "fixtures"
# 製品の実 state ではなく、writer が決定論的に生成した canonical 最終 state を基準にする
# (1.0・確定 foundation・effective_source_refs あり・qa_log あり)。
BASE_STATE = FIXTURES / "expected-final-spec-state.json"
TAXONOMY = PLUGIN / "skills" / "ref-system-design-knowledge" / "references" / "system-category-taxonomy.json"


def validator() -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


def base_state() -> dict:
    return json.loads(BASE_STATE.read_text(encoding="utf-8"))


def _writer():
    spec = importlib.util.spec_from_file_location(
        "apply_spec_transition_schema_contract", ELICIT / "scripts" / "apply-spec-transition.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("name", ["expected-resume-spec-state.json", "expected-final-spec-state.json"])
def test_golden_fixtures_satisfy_schema(name: str) -> None:
    validator().validate(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


@pytest.mark.parametrize("schema_version", [None, "1.1"])
def test_writer_init_output_satisfies_schema(schema_version: str | None) -> None:
    mod = _writer()
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    validator().validate(json.loads(mod.dump_state(mod.init_state(taxonomy, schema_version=schema_version))))


def test_current_state_requires_design_application_contract_marker() -> None:
    state = base_state()
    state["schema_version"] = "1.1"
    state.pop("design_application_contract_version", None)
    with pytest.raises(jsonschema.ValidationError):
        validator().validate(state)
    state["design_application_contract_version"] = "1.0"
    validator().validate(state)


def test_current_confirmed_state_requires_all_effective_source_refs() -> None:
    state = base_state()
    state["schema_version"] = "1.1"
    state["design_application_contract_version"] = "1.0"
    state["requirements_foundation"].pop("effective_source_refs", None)
    with pytest.raises(jsonschema.ValidationError):
        validator().validate(state)


def test_legacy_confirmed_state_may_omit_effective_source_refs() -> None:
    state = base_state()
    state["schema_version"] = "1.0"
    state.pop("design_application_contract_version", None)
    state["requirements_foundation"].pop("effective_source_refs", None)
    validator().validate(state)


def test_unknown_versions_and_malformed_design_applications_are_rejected() -> None:
    state = base_state()
    state["schema_version"] = "2.0"
    with pytest.raises(jsonschema.ValidationError):
        validator().validate(state)

    current = copy.deepcopy(state)
    current["schema_version"] = "1.1"
    current["design_application_contract_version"] = "1.0"
    current["qa_log"][0]["design_applications"] = [{"principle": "incomplete"}]
    with pytest.raises(jsonschema.ValidationError):
        validator().validate(current)


# qa entry の出所メタデータは、schema (宣言) と apply-spec-transition.py (writer) の
# 双方が契約を持つ。schema が緩いと、次の writer が schema だけを見て契約外の形状を書き、
# validator で初めて落ちる (あるいは validator を通らない経路なら永久に残る)。
# ここは「実データが通ること」ではなく「契約外が落ちること」を固定する。
# 締めを緩める変更 (additionalProperties を外す等) はこの test が検出する。
MALFORMED_QA_FIELDS = [
    # normalize_qa_source は object 必須。素の文字列は type_repair で 0 件へ修復済み。
    ("source", "対話で確認"),
    # kind は 4 種のみ。増やすなら writer と contract を同時に動かす。
    ("source", {"kind": "ai-guess"}),
    # user-dialogue は付帯情報を持たないことが「その場で答えた」の証拠になる。
    ("source", {"kind": "user-dialogue", "path": "a.md"}),
    # written は path/section/sha256 が揃って初めて原文へ遡及できる。
    ("source", {"kind": "written-requirements", "path": "a.md", "section": "s"}),
    # 是正は trigger が無いと「AI が勝手に足した」と区別できない。
    ("source", {"kind": "harness-remediation"}),
    # 統合は由来 qa と承認証跡の両方を要求する。
    ("source", {"kind": "derived-consolidation", "derived_from": ["qa-1"]}),
    # 後付けであること自体を隠さないための印。mode を自由文字列にすると印が意味を失う。
    ("source_provenance", {"mode": "looks_fine", "writer": "set-qa-source"}),
    # writer 名を const で縛らないと、別経路の後付けを schema 層で検出できない。
    ("source_provenance", {"mode": "metadata_backfill", "writer": "hand-edit"}),
    (
        "knowledge_ref_corrections",
        [{"old_ref": "a", "new_ref": "b", "applied_to": 1, "writer": "hand-edit", "reason": "r"}],
    ),
    # 根拠の性質は 3 種のみ (validate-coverage-matrix --require-basis と同じ語彙)。
    ("basis", "gut-feeling"),
    # 訂正は何をいつ直したかが無いと append-only の履歴にならない。
    ("corrections", [{"note": "日時なし"}]),
    ("corrections", [{"corrected_at": "2026-01-01T00:00:00Z", "note": "n", "corrected_field": "answer"}]),
    # supersede は置き換え先を空にできない。
    ("superseded_by", ""),
    # 綴り間違いや新種キーの素通りを塞ぐ (additionalProperties: false)。
    ("sorce", "typo"),
]


@pytest.mark.parametrize(
    "field,value", MALFORMED_QA_FIELDS, ids=[f"{f}-{i}" for i, (f, _) in enumerate(MALFORMED_QA_FIELDS)]
)
def test_qa_provenance_fields_reject_contract_violations(field: str, value: object) -> None:
    state = base_state()
    state["qa_log"][0][field] = value
    with pytest.raises(jsonschema.ValidationError):
        validator().validate(state)


def test_qa_provenance_valid_shapes_are_accepted() -> None:
    """拒否側だけを固定すると、締めすぎて正当な writer 出力まで落とす退行を見逃す。"""
    base = base_state()
    answer = base["qa_log"][0]["answer"]
    digest = hashlib.sha256(answer.encode("utf-8")).hexdigest()
    for source in (
        {"kind": "user-dialogue"},
        {"kind": "written-requirements", "path": "docs/req.md", "section": "2.1", "sha256": digest},
        {"kind": "harness-remediation", "trigger": "content-review medium"},
        {"kind": "derived-consolidation", "derived_from": ["qa-1"], "approval_ref": "appr-001"},
    ):
        state = copy.deepcopy(base)
        state["qa_log"][0]["source"] = source
        validator().validate(state)


def test_qa_correction_and_supersession_shapes_are_accepted() -> None:
    """writer の correct-qa / supersede-qa が書く形を schema が拒否しないこと。"""
    state = base_state()
    entry = state["qa_log"][0]
    entry["answered_at"] = "2026-01-02T00:00:00Z"
    entry["corrections"] = [
        {"corrected_at": "2026-01-03T00:00:00Z", "note": "表記を補足"},
        {
            "corrected_at": "2026-01-04T00:00:00Z",
            "note": "回答日時の誤記を訂正",
            "corrected_field": "answered_at",
            "previous_value": None,
            "corrected_value": "2026-01-02T00:00:00Z",
        },
    ]
    entry["superseded_by"] = "qa-001"
    entry["superseded_at"] = "2026-01-05T00:00:00Z"
    entry["superseded_note"] = "後続の回答で置き換え"
    validator().validate(state)
