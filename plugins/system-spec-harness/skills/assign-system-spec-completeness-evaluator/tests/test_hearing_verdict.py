# /// script
# name: test-hearing-verdict
# purpose: C06 (hearing-auditor) の重大度付き検出から matrix_coverage の sub-input 判定を導く derive_hearing_verdict の受入テスト
# inputs:
#   - pytest 実行 (argv なし)
# outputs:
#   - pytest 結果
# contexts: [C]
# network: false
# write-scope: tmp_path のみ
# dependencies: []
# ///
"""derive_hearing_verdict と CLI ``--hearing --state`` の受入テスト。

対応の正本は references/aspect-criteria.md の「ヒアリング監査 (C06) の重大度と判定の対応」。
以前は C06 が「1 軸以上に検出があれば FAIL」とし、R1-score が「監査 verdict FAIL → 該当観点
FAIL」としていたため、low 1 件で matrix_coverage が FAIL になっていた。ここでは

- 判定が C06 の宣言した verdict ではなく、検出の重大度と接地の位置から導かれること
- 確定の根拠に効く検出 (high、主たる接地根拠の問への medium、軸 2 以外の medium) は FAIL のままであること
  (判定を緩めて緑にしていないこと)
- 置き換えは (a)(b)(c) と「旧い問が主たる接地根拠でない」を全て満たすときだけ閉じた検出になること
- 形の不正は INDETERMINATE (fail-closed) になること

を確かめる。
"""
from __future__ import annotations

import copy
import importlib.util
import json
import re
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
R6 = SKILL_DIR.parent / "run-system-spec-elicit" / "prompts" / "R6-audit-hearing.md"


def _load():
    path = SKILL_DIR / "scripts" / "aggregate-completeness.py"
    spec = importlib.util.spec_from_file_location("aggregate_completeness_hearing", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()


def _state():
    """qa-a は確定セルの主根拠、qa-b は裏付け (qa_refs) だけ、qa-new は置き換え先の候補。"""
    return {
        "categories": ["database"],
        "platforms": ["web", "mobile"],
        "matrix": {
            "database": {
                "web": {"state": "確定", "qa_ref": "qa-a", "qa_refs": ["qa-b"]},
                "mobile": {"state": "対象外", "reason": "web のみ", "qa_ref": "qa-c"},
            }
        },
        "qa_log": [
            {"id": "qa-a", "question": "保存先はどれにしますか", "answer": "D1", "basis": "user-decision",
             "answered_at": "2026-09-01T00:00:00Z"},
            {"id": "qa-b", "question": "推奨の D1 でよいですか", "answer": "はい", "basis": "user-decision",
             "answered_at": "2026-09-01T00:01:00Z"},
            {"id": "qa-c", "question": "mobile は対象ですか", "answer": "いいえ", "basis": "user-decision",
             "answered_at": "2026-09-01T00:02:00Z"},
        ],
    }


def _superseded_state(*, new_basis="user-decision", old_is_primary=False):
    """qa-old (誘導あり) を qa-new (中立に問い直し・利用者の回答あり) で置き換えた state。"""
    st = _state()
    st["qa_log"].append(
        {"id": "qa-old", "question": "A (推奨) / B のどちらにしますか", "answer": "A",
         "basis": "user-decision", "answered_at": "2026-09-02T00:00:00Z",
         "superseded_by": "qa-new", "superseded_at": "2026-09-03T00:05:00Z",
         "superseded_note": "N1 違反 (推奨の印) を、印なし・保留ありの問で問い直した"}
    )
    st["qa_log"].append(
        {"id": "qa-new", "question": "A / B / 保留 のどれにしますか (比較と参考の推奨は上に示した)",
         "answer": "A", "basis": new_basis, "answered_at": "2026-09-03T00:00:00Z"}
    )
    st["matrix"]["database"]["web"]["qa_ref"] = "qa-old" if old_is_primary else "qa-new"
    return st


def _leading(qa_id, severity, **extra):
    f = {"axis": "leading-question", "severity": severity, "qa_id": qa_id, "criteria": ["N1"],
         "observation": f"{qa_id} の選択肢に推奨の印がある"}
    f.update(extra)
    return f


def _audit(*findings, verdict="FAIL"):
    return {"verdict": verdict, "findings": list(findings)}


# ---------- 重大度と接地の位置 ----------

def test_low_only_passes_even_when_c06_declares_fail():
    """旧実装の失敗の本体: low 1 件で FAIL になっていた。C06 の宣言は判定に使わない。"""
    r = MOD.derive_hearing_verdict(_audit(_leading("qa-a", "low"), verdict="FAIL"), _state())
    assert r["verdict"] == "PASS"
    assert r["declared"] == "FAIL"
    assert [f["qa_id"] for f in r["notes"]] == ["qa-a"]  # 報告からは消さない
    assert r["blocking"] == [] and r["closed"] == []


def test_info_is_a_note():
    finding = {"axis": "premature-stop", "severity": "info", "field": "hearing_progress.loop_count",
               "observation": "5 周目で保存され resume 可能"}
    r = MOD.derive_hearing_verdict(_audit(finding, verdict="PASS"), _state())
    assert r["verdict"] == "PASS" and len(r["notes"]) == 1


def test_high_fails_on_any_axis():
    for finding in (
        _leading("qa-b", "high"),
        {"axis": "missed-collection", "severity": "high", "cell": "database/mobile", "observation": "放置"},
        {"axis": "foundation-trace", "severity": "high", "u_item": "U2", "observation": "利用者の発言に遡れない"},
    ):
        r = MOD.derive_hearing_verdict(_audit(finding), _state())
        assert r["verdict"] == "FAIL", finding
        assert len(r["blocking"]) == 1


def test_medium_leading_on_primary_ground_fails():
    r = MOD.derive_hearing_verdict(_audit(_leading("qa-a", "medium")), _state())
    assert r["verdict"] == "FAIL"
    assert r["blocking"][0]["primary_ground"] is True


def test_medium_leading_on_supporting_or_excluded_question_is_a_note():
    """裏付け (qa_refs) だけ・対象外セルの qa_ref の問は、確定の主根拠ではない。"""
    r = MOD.derive_hearing_verdict(_audit(_leading("qa-b", "medium"), _leading("qa-c", "medium")), _state())
    assert r["verdict"] == "PASS"
    assert sorted(f["qa_id"] for f in r["notes"]) == ["qa-b", "qa-c"]
    assert all(f["primary_ground"] is False for f in r["notes"])


def test_medium_outside_axis_2_still_fails():
    """緩和は問 (軸 2) に限る。セルや進捗の medium は FAIL のまま。"""
    finding = {"axis": "traceability", "severity": "medium", "cell": "database/web",
               "observation": "裏付けの qa_refs の 1 件が dangling"}
    r = MOD.derive_hearing_verdict(_audit(finding), _state())
    assert r["verdict"] == "FAIL"


# ---------- 置き換え (supersession) ----------

def test_valid_supersession_is_a_closed_detection_not_a_failure():
    st = _superseded_state()
    r = MOD.derive_hearing_verdict(_audit(_leading("qa-old", "high", supersession_valid=True)), st)
    assert r["verdict"] == "PASS"
    assert r["blocking"] == [] and r["notes"] == []
    assert len(r["closed"]) == 1
    assert r["closed"][0]["qa_id"] == "qa-old" and r["closed"][0]["superseded_by"] == "qa-new"


@pytest.mark.parametrize(
    "case",
    ["c06_did_not_validate", "c06_rejected", "replacement_is_leading", "old_still_primary", "no_user_answer"],
)
def test_invalid_supersession_counts_the_old_question_at_its_severity(case):
    st = _superseded_state(
        new_basis="agent-inference" if case == "no_user_answer" else "user-decision",
        old_is_primary=case == "old_still_primary",
    )
    old = _leading("qa-old", "high")
    if case == "c06_rejected":
        old["supersession_valid"] = False
    elif case != "c06_did_not_validate":
        old["supersession_valid"] = True
    findings = [old]
    if case == "replacement_is_leading":
        findings.append(_leading("qa-new", "low"))  # low は (a) を崩さない
        findings.append(_leading("qa-new", "medium"))
    r = MOD.derive_hearing_verdict(_audit(*findings), st)
    assert r["verdict"] == "FAIL", case
    assert r["closed"] == []
    rejected = [f for f in r["blocking"] if f["qa_id"] == "qa-old"]
    assert rejected and rejected[0]["supersession_rejected"], case


def test_replacement_with_only_a_low_detection_still_closes():
    st = _superseded_state()
    r = MOD.derive_hearing_verdict(
        _audit(_leading("qa-old", "high", supersession_valid=True), _leading("qa-new", "low")), st
    )
    assert r["verdict"] == "PASS"
    assert [f["qa_id"] for f in r["closed"]] == ["qa-old"]
    assert [f["qa_id"] for f in r["notes"]] == ["qa-new"]


def test_supersession_chain_is_followed_to_the_final_replacement():
    st = _superseded_state()
    # qa-new をさらに qa-newer で置き換える。最終の置き換え先に利用者の回答が無ければ無効。
    st["qa_log"][-1].update({"superseded_by": "qa-newer", "superseded_at": "2026-09-04T00:05:00Z",
                             "superseded_note": "N4"})
    st["qa_log"].append({"id": "qa-newer", "question": "A / B / 保留", "answer": "",
                         "basis": "user-decision", "answered_at": "2026-09-04T00:00:00Z"})
    st["matrix"]["database"]["web"]["qa_ref"] = "qa-a"
    r = MOD.derive_hearing_verdict(_audit(_leading("qa-old", "high", supersession_valid=True)), st)
    assert r["verdict"] == "FAIL"
    assert "qa-newer" in r["blocking"][0]["supersession_rejected"]

    st2 = copy.deepcopy(st)
    st2["qa_log"][-1]["answer"] = "A"
    r2 = MOD.derive_hearing_verdict(_audit(_leading("qa-old", "high", supersession_valid=True)), st2)
    assert r2["verdict"] == "PASS" and len(r2["closed"]) == 1


def test_supersession_cycle_is_invalid():
    st = _superseded_state()
    st["qa_log"][-1].update({"superseded_by": "qa-old"})  # 手で壊した state (writer は作れない)
    r = MOD.derive_hearing_verdict(_audit(_leading("qa-old", "high", supersession_valid=True)), st)
    assert r["verdict"] == "FAIL"
    assert "循環" in r["blocking"][0]["supersession_rejected"]


# ---------- fail-closed ----------

@pytest.mark.parametrize(
    "finding",
    [
        {"axis": "tone", "severity": "low", "qa_id": "qa-a", "observation": "x"},              # 未知の軸
        {"axis": "leading-question", "severity": "minor", "qa_id": "qa-a", "observation": "x"},  # 未知の重大度
        {"axis": "leading-question", "severity": "low", "qa_id": "qa-zzz", "observation": "x"},  # 存在しない qa
        {"axis": "leading-question", "severity": "low", "observation": "x"},                    # 対象の欠落
        {"axis": "missed-collection", "severity": "high", "observation": "x"},                  # 対象の欠落
        {"axis": "traceability", "severity": "low", "cell": "database/web", "observation": " "},  # 根拠の欠落
    ],
)
def test_malformed_finding_is_indeterminate(finding):
    r = MOD.derive_hearing_verdict(_audit(finding, verdict="PASS"), _state())
    assert r["verdict"] == "INDETERMINATE"
    assert r["errors"]


def test_c06_indeterminate_or_broken_input_is_indeterminate():
    assert MOD.derive_hearing_verdict({"verdict": "INDETERMINATE", "findings": []}, _state())["verdict"] == "INDETERMINATE"
    assert MOD.derive_hearing_verdict({"verdict": "PASS"}, _state())["verdict"] == "INDETERMINATE"
    assert MOD.derive_hearing_verdict([], _state())["verdict"] == "INDETERMINATE"
    assert MOD.derive_hearing_verdict(_audit(verdict="PASS"), {"qa_log": []})["verdict"] == "INDETERMINATE"


def test_no_findings_passes():
    r = MOD.derive_hearing_verdict(_audit(verdict="PASS"), _state())
    assert r["verdict"] == "PASS" and r["notes"] == [] and r["blocking"] == []


# ---------- 軸の正本との一致 ----------

def test_axis_ids_are_exactly_the_five_axes_of_r6():
    """C06 の軸は R6 の監査 5 軸を参照する。集計側の軸 id も R6 の出力形と一致させる。"""
    text = R6.read_text(encoding="utf-8")
    assert "監査 5 軸" in text
    m = re.search(r'"axis": "([a-z|-]+)"', text)
    assert m, "R6 Layer 6 に finding の axis の列挙が無い"
    r6_axes = m.group(1).split("|")
    assert r6_axes == list(MOD.HEARING_AXES)
    assert sorted(MOD.HEARING_AXES.values()) == [1, 2, 3, 4, 5]


# ---------- CLI ----------

def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return p


def test_cli_hearing_pass_and_fail(tmp_path, capsys):
    st = _write(tmp_path, "spec-state.json", _state())
    ok = _write(tmp_path, "ok.json", _audit(_leading("qa-a", "low")))
    ng = _write(tmp_path, "ng.json", _audit(_leading("qa-a", "medium")))
    assert MOD.main(["--hearing", str(ok), "--state", str(st)]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "PASS"
    assert MOD.main(["--hearing", str(ng), "--state", str(st)]) == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "FAIL"


def test_cli_hearing_requires_state_and_existing_files(tmp_path):
    ok = _write(tmp_path, "ok.json", _audit())
    with pytest.raises(SystemExit):
        MOD.main(["--hearing", str(ok)])
    assert MOD.main(["--hearing", str(ok), "--state", str(tmp_path / "nope.json")]) == 2
