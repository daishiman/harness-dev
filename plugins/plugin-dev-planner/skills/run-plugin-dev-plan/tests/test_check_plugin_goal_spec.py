from __future__ import annotations

import json
from pathlib import Path

import pytest

# tests/ -> run-plugin-dev-plan -> schemas/plugin-goal-spec.schema.json
_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "plugin-goal-spec.schema.json"


def _schema() -> dict:
    if not _SCHEMA.is_file():
        pytest.skip(f"plugin-goal-spec.schema.json 不在: {_SCHEMA}")
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _goal_spec() -> dict:
    return {
        "purpose": "Notion task sync plugin の計画を作る",
        "background": "既存台帳と Notion DB の同期を再現可能にする必要がある",
        "goal": "notion-task-sync の plan artifacts が検証可能な状態になる",
        "artifact_class": "plugin-plan",
        "target_plugin_slug": "notion-task-sync",
        "plan_dir": "plugin-plans/notion-task-sync",
        "out_dir": None,
        "requested_count": None,
        "checklist": [
            {"id": "C1", "criterion": "component inventory が生成されている", "done": False, "verify_by": "script"}
        ],
        "constraints": [],
        "handoff_targets": ["plugin-dev-plan-architect"],
        "max_loops": 5,
        "open_questions": [],
    }


def test_plugin_goal_spec_accepts_valid_contract(tmp_path, plugin_goal_spec):
    path = tmp_path / "goal-spec.json"
    path.write_text(json.dumps(_goal_spec(), ensure_ascii=False), encoding="utf-8")

    assert plugin_goal_spec.main([str(path)]) == 0


def test_plugin_goal_spec_rejects_extra_key(plugin_goal_spec):
    data = _goal_spec()
    data["unexpected"] = True

    errors = plugin_goal_spec.validate(data)

    assert any("additionalProperties" in e for e in errors)


def test_plugin_goal_spec_rejects_bad_slug(plugin_goal_spec):
    data = _goal_spec()
    data["target_plugin_slug"] = "Notion Task Sync"

    errors = plugin_goal_spec.validate(data)

    assert any("ASCII kebab-case" in e for e in errors)


def test_plugin_goal_spec_rejects_plan_dir_slug_mismatch(plugin_goal_spec):
    """plan_dir が target_plugin_slug 由来の正本と食い違えば再現性アンカー違反 (out_dir 未指定時)。"""
    data = _goal_spec()
    data["plan_dir"] = "plugin-plans/some-other-dir"  # slug=notion-task-sync と不一致

    errors = plugin_goal_spec.validate(data)

    assert any("再現性アンカー" in e for e in errors), errors


def test_plugin_goal_spec_accepts_explicit_out_dir(plugin_goal_spec):
    """out_dir 明示時は plan_dir==正規化 out_dir なら受理 (slug 由来既定でなく out_dir を正本にする)。"""
    data = _goal_spec()
    data["out_dir"] = "custom/plans/x"
    data["plan_dir"] = "custom/plans/x"

    errors = plugin_goal_spec.validate(data)

    assert not any("再現性アンカー" in e for e in errors), errors


def test_plugin_goal_spec_rejects_unknown_force_13(plugin_goal_spec):
    """per-phase 転換で force_13 は廃止。残置すると additionalProperties でエラー。"""
    data = _goal_spec()
    data["force_13"] = True

    errors = plugin_goal_spec.validate(data)

    assert any("additionalProperties" in e for e in errors)


def test_plugin_goal_spec_requested_count_optional(plugin_goal_spec):
    """requested_count は任意 (欠落しても required エラーにならない)。"""
    data = _goal_spec()
    del data["requested_count"]

    errors = plugin_goal_spec.validate(data)

    assert not any("required keys missing" in e for e in errors), errors


# ─────────── schema ↔ validator parity (CRIT-2: 重複契約の drift 封止) ───────────
# goal-spec 契約は plugin-goal-spec.schema.json (宣言) と check-plugin-goal-spec.py の
# 手書き validate() (REQUIRED/ALLOWED/enum/pattern) で二重に持たれる。本 plugin は
# test_schema_parity.py / test_kind_key_doc_parity.py で「重複契約には必ず parity test を
# 付ける」を慣行化しており、goal-spec だけがその例外だった (2026-06-30 elegant-review G-A)。
# 以下は両者を縛り、将来どちらかが drift したら fail させる (片肺更新の無音化を防ぐ)。


def test_validator_required_matches_schema(plugin_goal_spec):
    """check-plugin-goal-spec.py の REQUIRED が schema.required と集合一致する。"""
    schema = _schema()
    assert plugin_goal_spec.REQUIRED == set(schema["required"]), (
        f"required drift: validator-schema={sorted(plugin_goal_spec.REQUIRED - set(schema['required']))} "
        f"schema-validator={sorted(set(schema['required']) - plugin_goal_spec.REQUIRED)}"
    )


def test_validator_allowed_matches_schema_properties(plugin_goal_spec):
    """ALLOWED が schema.properties キー集合と一致する (additionalProperties:false ゆえ等価)。"""
    schema = _schema()
    assert schema.get("additionalProperties") is False, "schema が additionalProperties:false でない"
    props = set(schema["properties"].keys())
    assert plugin_goal_spec.ALLOWED == props, (
        f"allowed/properties drift: validator-schema={sorted(plugin_goal_spec.ALLOWED - props)} "
        f"schema-validator={sorted(props - plugin_goal_spec.ALLOWED)}"
    )


def test_validator_slug_pattern_matches_schema(plugin_goal_spec):
    """target_plugin_slug の正規表現が schema の pattern と逐語一致する。"""
    schema = _schema()
    assert plugin_goal_spec.SLUG_RE.pattern == schema["properties"]["target_plugin_slug"]["pattern"], (
        "target_plugin_slug pattern が schema と drift"
    )


def test_validator_enums_match_schema_behaviorally(plugin_goal_spec):
    """artifact_class / checklist.verify_by の enum が schema と behavioral 一致する。

    validate() は enum を関数内リテラルで持つため (定数未露出)、schema の各 enum 値を
    validate() が受理し、enum 外値を拒否することで両者の一致を間接検証する (stdlib のみ)。
    """
    schema = _schema()
    props = schema["properties"]

    # artifact_class: schema enum の各値を受理・範囲外を拒否
    for v in props["artifact_class"]["enum"]:
        d = _goal_spec()
        d["artifact_class"] = v
        assert not any("artifact_class" in e for e in plugin_goal_spec.validate(d)), (
            f"schema enum 値 {v!r} を validator が artifact_class で拒否 (enum drift)"
        )
    d = _goal_spec()
    d["artifact_class"] = "__not_in_enum__"
    assert any("artifact_class" in e for e in plugin_goal_spec.validate(d)), (
        "validator が artifact_class の enum 外値を拒否しない (enum drift)"
    )

    # checklist.verify_by: schema enum の各値を受理・範囲外を拒否
    verify_enum = props["checklist"]["items"]["properties"]["verify_by"]["enum"]
    for v in verify_enum:
        d = _goal_spec()
        d["checklist"] = [{"id": "C1", "criterion": "x", "done": False, "verify_by": v}]
        assert not any("verify_by" in e for e in plugin_goal_spec.validate(d)), (
            f"schema enum 値 {v!r} を validator が verify_by で拒否 (enum drift)"
        )
    d = _goal_spec()
    d["checklist"] = [{"id": "C1", "criterion": "x", "done": False, "verify_by": "__not_in_enum__"}]
    assert any("verify_by" in e for e in plugin_goal_spec.validate(d)), (
        "validator が verify_by の enum 外値を拒否しない (enum drift)"
    )


# ─────────── E1/E3 provenance (source_intake / source_improvement) ───────────
# C03: 存在時は schema 準拠を fatal 検査 (IN1)、欠落は WARN 受理 (OUT1・後方互換)。
def _prov():
    return {"ref": "plugins/plugin-dev-planner/.../intake.json", "schema_version": "2.0.0"}


def test_provenance_present_valid_accepted(plugin_goal_spec):
    data = _goal_spec()
    data["source_intake"] = _prov()
    data["source_improvement"] = {"ref": "improvement-handoff.json", "schema_version": "1.0.0"}
    assert plugin_goal_spec.validate(data) == []


def test_provenance_absent_is_not_fatal(plugin_goal_spec):
    """欠落は validate() で error にならない (後方互換)。"""
    data = _goal_spec()
    assert not any("source_intake" in e or "source_improvement" in e for e in plugin_goal_spec.validate(data))


def test_provenance_absent_emits_warnings(plugin_goal_spec):
    """欠落は provenance_warnings が 2 件 (source_intake/source_improvement) を返す。"""
    warns = plugin_goal_spec.provenance_warnings(_goal_spec())
    assert len(warns) == 2
    assert any("source_intake" in w for w in warns)


def test_provenance_null_treated_as_absent(plugin_goal_spec):
    data = _goal_spec()
    data["source_intake"] = None
    assert not any("source_intake" in e for e in plugin_goal_spec.validate(data))
    assert any("source_intake" in w for w in plugin_goal_spec.provenance_warnings(data))


def test_provenance_not_object_is_fatal(plugin_goal_spec):
    data = _goal_spec()
    data["source_intake"] = "intake.json"
    assert any("source_intake は object" in e for e in plugin_goal_spec.validate(data))


def test_provenance_missing_ref_is_fatal(plugin_goal_spec):
    data = _goal_spec()
    data["source_improvement"] = {"schema_version": "1.0.0"}
    assert any("source_improvement.ref" in e for e in plugin_goal_spec.validate(data))


def test_provenance_bad_schema_version_is_fatal(plugin_goal_spec):
    data = _goal_spec()
    data["source_intake"] = {"ref": "intake.json", "schema_version": "2.0"}
    assert any("source_intake.schema_version" in e and "semver" in e for e in plugin_goal_spec.validate(data))


def test_provenance_extra_key_is_fatal(plugin_goal_spec):
    data = _goal_spec()
    data["source_intake"] = {"ref": "intake.json", "schema_version": "2.0.0", "bogus": 1}
    assert any("source_intake additionalProperties" in e for e in plugin_goal_spec.validate(data))


def test_provenance_present_valid_main_exit_zero(tmp_path, plugin_goal_spec):
    data = _goal_spec()
    data["source_intake"] = _prov()
    path = tmp_path / "goal-spec.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert plugin_goal_spec.main([str(path)]) == 0


def test_provenance_in_allowed_and_schema_properties(plugin_goal_spec):
    """新 provenance フィールドが ALLOWED と schema.properties の双方に載る (parity 維持)。"""
    schema = _schema()
    for key in ("source_intake", "source_improvement"):
        assert key in plugin_goal_spec.ALLOWED
        assert key in schema["properties"]
