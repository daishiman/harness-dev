"""emit-improvement-handoff.py (PB-C09) の機能テスト。

改善成果物 findings → improvement-handoff.json 正規化 emitter の受入・正規化・
負例・usage error を固定する。E3 境界: 出力は PB-C01 が --mode update で受理する。
"""
from __future__ import annotations

import json


def _args(tmp_path, findings, **over):
    """argparse Namespace 相当を組む (build_handoff/validate の単体呼び出し用)。"""
    import types
    base = dict(
        source_kind="elegant-review",
        source_ref="plugin-plans/sample/elegant-review-20260705.md",
        target_plugin_slug="sample-plugin",
        plan_dir="plugin-plans/sample-plugin",
        schema_version="1.0.0",
        generated_by=None,
        source_intake=None,
        prev_goal_spec=None,
        origin_request_kind="notion-improvement-request",
        origin_request_ref=None,
    )
    base.update(over)
    ns = types.SimpleNamespace(**base)
    return ns


def _findings_file(tmp_path, payload):
    p = tmp_path / "findings.json"
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return p


_GOOD = [{"id": "F1", "severity": "high", "summary": "断線 X", "recommendation": "配線する"}]


# ─────────────────── normalize_findings ───────────────────
def test_normalize_bare_array(emit):
    out = emit.normalize_findings(_GOOD)
    assert out[0]["id"] == "F1" and out[0]["severity"] == "high"


def test_normalize_wrapped_object(emit):
    out = emit.normalize_findings({"findings": _GOOD})
    assert len(out) == 1 and out[0]["summary"] == "断線 X"


def test_normalize_defaults_id_and_severity(emit):
    out = emit.normalize_findings([{"summary": "no id"}])
    assert out[0]["id"] == "F1" and out[0]["severity"] == "medium"


def test_normalize_accepts_text_alias_for_summary(emit):
    out = emit.normalize_findings([{"text": "review text"}])
    assert out[0]["summary"] == "review text"


def test_normalize_skips_non_dict(emit):
    out = emit.normalize_findings(["scalar", {"summary": "ok"}])
    assert len(out) == 1


def test_normalize_non_list_returns_empty(emit):
    assert emit.normalize_findings(42) == []


# ─────────────────── build_handoff ───────────────────
def test_build_handoff_shape(emit, tmp_path):
    h = emit.build_handoff(_args(tmp_path, _GOOD), emit.normalize_findings(_GOOD))
    assert h["source"]["kind"] == "elegant-review"
    assert h["target_plugin_slug"] == "sample-plugin"
    assert "provenance" not in h  # provenance 引数未指定なら省略


def test_build_handoff_includes_provenance_and_generated_by(emit, tmp_path):
    ns = _args(tmp_path, _GOOD, generated_by="run-elegant-review",
               source_intake="intake.json", prev_goal_spec="prev/goal-spec.json")
    h = emit.build_handoff(ns, emit.normalize_findings(_GOOD))
    assert h["source"]["generated_by"] == "run-elegant-review"
    assert h["provenance"]["source_intake"] == "intake.json"
    assert h["provenance"]["prev_goal_spec"] == "prev/goal-spec.json"


def test_build_handoff_records_origin_request(emit, tmp_path):
    """人間ブリッジ (feedback-to-improvement-runbook Stage 3): 起点 Notion 要望を provenance に刻む。"""
    ns = _args(tmp_path, _GOOD, source_kind="manual",
               origin_request_ref="https://notion.so/req-abc")
    h = emit.build_handoff(ns, emit.normalize_findings(_GOOD))
    assert h["provenance"]["origin_request"] == {
        "kind": "notion-improvement-request",
        "ref": "https://notion.so/req-abc",
    }
    assert emit.validate(h) == []


def test_build_handoff_omits_origin_request_when_absent(emit, tmp_path):
    """origin_request 未指定なら provenance ごと省略され後方互換を保つ。"""
    h = emit.build_handoff(_args(tmp_path, _GOOD), emit.normalize_findings(_GOOD))
    assert "provenance" not in h


def test_validate_manual_requires_origin_request(emit, tmp_path):
    ns = _args(tmp_path, _GOOD, source_kind="manual")
    h = emit.build_handoff(ns, emit.normalize_findings(_GOOD))
    assert any("origin_request" in e for e in emit.validate(h))


def test_validate_bad_origin_request_kind(emit, tmp_path):
    ns = _args(tmp_path, _GOOD, origin_request_ref="r", origin_request_kind="bogus")
    h = emit.build_handoff(ns, emit.normalize_findings(_GOOD))
    assert any("origin_request.kind" in e for e in emit.validate(h))


# ─────────────────── validate ───────────────────
def test_validate_clean(emit, tmp_path):
    h = emit.build_handoff(_args(tmp_path, _GOOD), emit.normalize_findings(_GOOD))
    assert emit.validate(h) == []


def test_validate_bad_schema_version(emit, tmp_path):
    h = emit.build_handoff(_args(tmp_path, _GOOD, schema_version="1.0"), emit.normalize_findings(_GOOD))
    assert any("semver" in e for e in emit.validate(h))


def test_validate_bad_slug(emit, tmp_path):
    h = emit.build_handoff(_args(tmp_path, _GOOD, target_plugin_slug="Bad_Slug"), emit.normalize_findings(_GOOD))
    assert any("kebab" in e for e in emit.validate(h))


def test_validate_empty_findings(emit, tmp_path):
    h = emit.build_handoff(_args(tmp_path, []), [])
    assert any("findings" in e for e in emit.validate(h))


def test_validate_bad_severity(emit, tmp_path):
    h = emit.build_handoff(_args(tmp_path, _GOOD), [{"id": "F1", "severity": "urgent", "summary": "x"}])
    assert any("severity" in e for e in emit.validate(h))


def test_validate_empty_summary(emit, tmp_path):
    h = emit.build_handoff(_args(tmp_path, _GOOD), [{"id": "F1", "severity": "low", "summary": ""}])
    assert any("summary" in e for e in emit.validate(h))


# ─────────────────── main / CLI ───────────────────
def _cli(tmp_path, findings, out=None, **over):
    f = _findings_file(tmp_path, findings)
    argv = [
        "--source-kind", over.get("source_kind", "elegant-review"),
        "--source-ref", "plugin-plans/sample/review.md",
        "--target-plugin-slug", over.get("slug", "sample-plugin"),
        "--plan-dir", "plugin-plans/sample-plugin",
        "--findings", str(f),
    ]
    if out:
        argv += ["-o", str(out)]
    return argv


def test_main_stdout_emits_valid_json(tmp_path, emit, capsys):
    rc = emit.main(_cli(tmp_path, _GOOD))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["findings"][0]["id"] == "F1"


def test_main_writes_output_file(tmp_path, emit):
    out = tmp_path / "improvement-handoff.json"
    rc = emit.main(_cli(tmp_path, _GOOD, out=out))
    assert rc == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["target_plugin_slug"] == "sample-plugin"


def test_main_validation_failure_returns_one(tmp_path, emit):
    rc = emit.main(_cli(tmp_path, [{"id": "F1", "severity": "nope", "summary": "x"}]))
    assert rc == 1


def test_main_empty_findings_returns_one(tmp_path, emit):
    rc = emit.main(_cli(tmp_path, []))
    assert rc == 1


def test_main_missing_findings_file_returns_two(tmp_path, emit):
    argv = [
        "--source-kind", "elegant-review", "--source-ref", "r",
        "--target-plugin-slug", "sample-plugin", "--plan-dir", "d",
        "--findings", str(tmp_path / "nope.json"),
    ]
    assert emit.main(argv) == 2


def test_main_bad_findings_json_returns_two(tmp_path, emit):
    f = tmp_path / "findings.json"
    f.write_text("{ broken", encoding="utf-8")
    argv = [
        "--source-kind", "elegant-review", "--source-ref", "r",
        "--target-plugin-slug", "sample-plugin", "--plan-dir", "d",
        "--findings", str(f),
    ]
    assert emit.main(argv) == 2


def test_main_roundtrip_output_passes_parity_of_schema_fields(tmp_path, emit):
    """emit した JSON が schema 必須フィールドを全て備える (PB-C01/PB-C05 消費前提)。"""
    out = tmp_path / "improvement-handoff.json"
    emit.main(_cli(tmp_path, _GOOD, out=out))
    data = json.loads(out.read_text(encoding="utf-8"))
    for key in ("schema_version", "source", "target_plugin_slug", "plan_dir", "findings"):
        assert key in data
