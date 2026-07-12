"""check-intake-consumption.py (C04) の機能テスト。

intake.json の主要項目が goal-spec へ反映されたかを signal 重複で検出する E1 情報漏れ
ゲート。反映済み受理・未反映 FAIL/WARN・--strict 昇格・usage error を固定する。
"""
from __future__ import annotations

import json


def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return p


# intake の executive_summary / purpose_excavator を含む v2 相当の最小構造。
def _intake(summary="請求書の発行漏れを検出したい", excavator="毎月の請求業務を自動化する"):
    return {
        "sections": {
            "0_executive_summary": {"text": summary},
            "3_purpose_excavator": {"findings": [excavator]},
        }
    }


def _goal_spec(reflected=True):
    if reflected:
        return {
            "purpose": "請求書の発行漏れを検出し毎月の請求業務を自動化する plugin を計画する",
            "background": "毎月の請求業務で発行漏れが起きている",
            "goal": "発行漏れ検出が可能な状態",
            "checklist": [{"id": "C1", "criterion": "請求書の発行漏れを検出する", "done": False}],
        }
    return {
        "purpose": "全く無関係な天気予報アプリを作る",
        "background": "気象データの可視化",
        "goal": "予報表示ができる",
        "checklist": [{"id": "C1", "criterion": "気温を表示する", "done": False}],
    }


# ─────────────────── 単体 (extract / signals / unreflected) ───────────────────
def test_extract_items_collects_sections(intake_consumption):
    items = intake_consumption.extract_items(_intake(), None)
    labels = [i[0] for i in items]
    assert any("executive_summary" in l for l in labels)
    assert any("purpose_excavator" in l for l in labels)
    assert all(sev == "fail" for _, _, sev in items)


def test_extract_includes_next_action_split_candidates(intake_consumption):
    na = {"split_candidates": ["経費精算 skill を分ける"]}
    items = intake_consumption.extract_items(_intake(), na)
    assert any("split_candidates" in l and sev == "warn" for l, _, sev in items)


def test_find_sections_is_key_substring_tolerant(intake_consumption):
    # ネストしたキー名部分一致で拾える (schema 微変更頑健)。
    data = {"deep": {"my_executive_summary_v2": {"text": "X"}}}
    assert intake_consumption._find_sections(data, "executive_summary")


def test_reflected_items_have_no_unreflected(intake_consumption):
    items = intake_consumption.extract_items(_intake(), None)
    sig = intake_consumption.goal_spec_signals(_goal_spec(reflected=True))
    assert intake_consumption.find_unreflected(items, sig) == []


def test_unreflected_detected_when_goal_spec_unrelated(intake_consumption):
    items = intake_consumption.extract_items(_intake(), None)
    sig = intake_consumption.goal_spec_signals(_goal_spec(reflected=False))
    unref = intake_consumption.find_unreflected(items, sig)
    assert len(unref) >= 1


def test_signalless_item_is_not_flagged(intake_consumption):
    # 記号のみ (signal を持たない) item は判定保留=反映扱い (偽陽性回避)。
    assert intake_consumption.find_unreflected([("x", "!!! ---", "fail")], set()) == []


# ─────────────────── main / CLI ───────────────────
def test_main_reflected_returns_zero(tmp_path, intake_consumption):
    intake = _write(tmp_path, "intake.json", _intake())
    gs = _write(tmp_path, "goal-spec.json", _goal_spec(reflected=True))
    assert intake_consumption.main(["--intake", str(intake), "--goal-spec", str(gs)]) == 0


def test_main_unreflected_fail_returns_one(tmp_path, intake_consumption):
    intake = _write(tmp_path, "intake.json", _intake())
    gs = _write(tmp_path, "goal-spec.json", _goal_spec(reflected=False))
    assert intake_consumption.main(["--intake", str(intake), "--goal-spec", str(gs)]) == 1


def test_main_warn_severity_does_not_fail_by_default(tmp_path, intake_consumption):
    # split_candidates (warn) だけ未反映で fail-severity は全反映 → exit 0。
    intake = _write(tmp_path, "intake.json", _intake())
    na = _write(tmp_path, "next-action.json", {"split_candidates": ["全く無関係な独立テーマXYZ"]})
    gs = _write(tmp_path, "goal-spec.json", _goal_spec(reflected=True))
    rc = intake_consumption.main(
        ["--intake", str(intake), "--goal-spec", str(gs), "--next-action", str(na)]
    )
    assert rc == 0


def test_main_strict_promotes_warn_to_fail(tmp_path, intake_consumption):
    intake = _write(tmp_path, "intake.json", _intake())
    na = _write(tmp_path, "next-action.json", {"split_candidates": ["全く無関係な独立テーマXYZ"]})
    gs = _write(tmp_path, "goal-spec.json", _goal_spec(reflected=True))
    rc = intake_consumption.main(
        ["--intake", str(intake), "--goal-spec", str(gs), "--next-action", str(na), "--strict"]
    )
    assert rc == 1


def test_main_missing_input_returns_two(tmp_path, intake_consumption):
    gs = _write(tmp_path, "goal-spec.json", _goal_spec())
    assert intake_consumption.main(["--intake", str(tmp_path / "nope.json"), "--goal-spec", str(gs)]) == 2


def test_main_bad_json_returns_two(tmp_path, intake_consumption):
    bad = tmp_path / "intake.json"
    bad.write_text("{ broken", encoding="utf-8")
    gs = _write(tmp_path, "goal-spec.json", _goal_spec())
    assert intake_consumption.main(["--intake", str(bad), "--goal-spec", str(gs)]) == 2


# ─────────────────── pass marker (C11 digest pin 契約) ───────────────────
def test_marker_written_on_pass(tmp_path, intake_consumption):
    import hashlib
    intake = _write(tmp_path, "intake.json", _intake())
    gs = _write(tmp_path, "goal-spec.json", _goal_spec(reflected=True))
    rc = intake_consumption.main(
        ["--intake", str(intake), "--goal-spec", str(gs), "--marker-dir", str(tmp_path)]
    )
    assert rc == 0
    marker = tmp_path / ".gate" / "intake-consumption.pass"
    assert marker.is_file()
    assert marker.read_text().strip() == hashlib.sha256(gs.read_bytes()).hexdigest()


def test_marker_not_written_on_fail(tmp_path, intake_consumption):
    intake = _write(tmp_path, "intake.json", _intake())
    gs = _write(tmp_path, "goal-spec.json", _goal_spec(reflected=False))
    intake_consumption.main(
        ["--intake", str(intake), "--goal-spec", str(gs), "--marker-dir", str(tmp_path)]
    )
    assert not (tmp_path / ".gate" / "intake-consumption.pass").exists()
