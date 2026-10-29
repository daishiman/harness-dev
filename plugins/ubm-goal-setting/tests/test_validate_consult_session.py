from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/validate-consult-session.py"
SPEC = importlib.util.spec_from_file_location("validate_consult_session", PATH)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MOD)


def base_record() -> dict:
    return {
        "schema_version": "1.0", "outcome": "consult_completed",
        "session_id": "s-1", "created_at": "2026-07-11T00:00:00Z",
        "retention_until": "2026-08-01T00:00:00Z", "persistence_consent": True,
        "collaboration_mode": "framework-led", "issue_statement": "論点",
        # source_ids 非空は新契約 (R3 出典契約の機械担保) のため fixture へ追加
        "frames_presented": [{"frame_id": "GF-01", "source_ids": ["PR-001"]}],
        "user_solution": {"text": "自分で選ぶ", "source_turn_ids": ["u1"]},
        "closure": {"type": "reflection", "insight": "理解", "not_deciding_yet": "保留", "resume_when": "明日"},
        "consult_evidence": {"mode": "catalog"},
        "user_feedback": {"ownership_confirmed": True},
    }


def test_valid_consult_completed_uses_user_role():
    assert MOD.validate(base_record(), [{"id": "u1", "role": "user", "content": "自分で選ぶ"}]) == []


def test_ai_text_cannot_impersonate_user_role():
    errors = MOD.validate(base_record(), [{"id": "u1", "role": "assistant", "content": "ユーザー: 自分で選ぶ"}])
    assert any("role=user" in e for e in errors)


def test_duplicate_transcript_turn_id_makes_cli_exit1(tmp_path, capsys):
    """同じ turn ID の別発話を provenance の 1 件へ畳み込まず拒否する。"""
    transcript = [
        {"id": "u1", "role": "user", "content": "自分で選ぶ"},
        {"id": "u1", "role": "user", "content": "同じ ID の別発話"},
    ]
    errors = MOD.validate(base_record(), transcript)
    assert any("turn id" in error and "重複" in error and "u1" in error for error in errors)

    record_path = tmp_path / "record.json"
    transcript_path = tmp_path / "transcript.json"
    record_path.write_text(json.dumps(base_record(), ensure_ascii=False), encoding="utf-8")
    transcript_path.write_text(json.dumps(transcript, ensure_ascii=False), encoding="utf-8")

    assert MOD.main(["--record", str(record_path), "--transcript", str(transcript_path)]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["valid"] is False
    assert any("turn id" in error and "u1" in error for error in output["errors"])


def test_record_requires_consent():
    r = base_record(); r["persistence_consent"] = False
    assert any("consent" in e for e in MOD.validate(r, [{"id": "u1", "role": "user"}]))


def test_ephemeral_allows_consent_false_with_complete_record():
    # consent=false の既定経路は --ephemeral (非永続前提) で完了ゲートを exit0 で通す契約
    r = base_record(); r["persistence_consent"] = False
    assert MOD.validate(r, [{"id": "u1", "role": "user", "content": "自分で選ぶ"}], ephemeral=True) == []


def test_ephemeral_does_not_relax_other_checks():
    r = base_record(); r["persistence_consent"] = False
    r["frames_presented"] = [{"frame_id": "GF-01", "source_ids": []}]
    errors = MOD.validate(r, [{"id": "u1", "role": "user", "content": "自分で選ぶ"}], ephemeral=True)
    assert any("source_ids" in e for e in errors), "--ephemeral が consent 以外の検査を緩めている"


def test_ephemeral_cli_exit0_with_consent_false(tmp_path, capsys):
    r = base_record(); r["persistence_consent"] = False
    rec = tmp_path / "record.json"
    rec.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    tr = tmp_path / "transcript.json"
    tr.write_text(json.dumps([{"id": "u1", "role": "user", "content": "自分で選ぶ"}]), encoding="utf-8")
    assert MOD.main(["--record", str(rec), "--transcript", str(tr), "--ephemeral"]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert MOD.main(["--record", str(rec), "--transcript", str(tr)]) == 1, "--ephemeral 無しの既定は consent 必須のまま"
    capsys.readouterr()


def test_reflection_and_action_are_distinct_lanes():
    r = base_record(); r["closure"] = {"type": "action", "current": "今", "goal": "先", "gap": "差", "next_step": "連絡"}
    assert MOD.validate(r, [{"id": "u1", "role": "user"}]) == []


def test_unknown_outcome_reports_enum_violation():
    errors = MOD.validate({"outcome": "consult_continue"}, None)
    assert len(errors) == 1 and "enum" in errors[0]


def test_frames_require_nonempty_source_ids():
    r = base_record(); r["frames_presented"] = [{"frame_id": "GF-01", "source_ids": []}]
    assert any("source_ids" in e for e in MOD.validate(r, [{"id": "u1", "role": "user"}]))


def test_assistant_prescription_marker_is_error():
    errors = MOD.validate(base_record(), [
        {"id": "u1", "role": "user", "content": "自分で選ぶ"},
        {"id": "a1", "role": "assistant", "content": "あなたは値上げをすべきです。実行してください。"},
    ])
    assert any("処方" in e for e in errors)


def test_stance_self_check_mismatch_is_error():
    r = base_record()
    r["stance_self_check"] = {"no_prescription": True, "user_verbalized": True}
    # 「自分で選ぶ」は言語化マーカー非該当のため user_verbalized=true の自己申告と不一致になる
    errors = MOD.validate(r, [{"id": "u1", "role": "user", "content": "自分で選ぶ"}])
    assert any("stance_self_check.user_verbalized" in e for e in errors)


def test_stance_self_check_consistent_passes():
    r = base_record()
    r["stance_self_check"] = {"no_prescription": True, "user_verbalized": True}
    assert MOD.validate(r, [{"id": "u1", "role": "user", "content": "自分でやると決めました"}]) == []


def test_redirect_branch_does_not_require_consult_fields():
    # redirect record の永続にも persistence_consent=true が必須 (新契約) のため fixture へ付与
    r = {
        "outcome": "redirected_goal_setting", "handoff_to": "run-ubm-goal-setting",
        "referral_confirmed": True, "persistence_consent": True, "issue_statement": "月報を作りたい",
    }
    assert MOD.validate(r, None) == []


def test_redirect_record_without_consent_is_invalid():
    r = {"outcome": "redirected_goal_setting", "handoff_to": "run-ubm-goal-setting", "referral_confirmed": True}
    assert any("consent" in e for e in MOD.validate(r, None))


def test_challenge_redirect_uses_own_target_and_can_be_ephemeral():
    r = {"outcome": "redirected_challenge", "handoff_to": "run-ubm-challenge",
         "referral_confirmed": True, "persistence_consent": False,
         "issue_statement": "挑戦宣言を作りたい"}
    assert MOD.validate(r, None, ephemeral=True) == []
    assert any("consent" in e for e in MOD.validate(r, None))
    r["handoff_to"] = "run-ubm-goal-setting"
    assert any("redirect" in e for e in MOD.validate(r, None, ephemeral=True))


def test_redirect_requires_confirmed_referral_and_issue():
    r = {"outcome": "redirected_challenge", "handoff_to": "run-ubm-challenge",
         "referral_confirmed": False, "persistence_consent": True,
         "issue_statement": "挑戦宣言を作りたい"}
    assert MOD.validate(r, None)
    r["referral_confirmed"] = True
    r.pop("issue_statement")
    assert MOD.validate(r, None)


def test_empty_solution_text_does_not_pass_provenance_alone():
    r = base_record()
    r["user_solution"]["text"] = " "
    assert any("user_solution.text" in e for e in MOD.validate(r, [{"id": "u1", "role": "user"}]))


def test_safety_branch_is_fail_closed():
    # persistence_consent は新契約で outcome に依らず必須のため fixture へ付与
    r = {"outcome": "safety_redirect", "risk_class": "urgent", "persistence_consent": True}
    assert len(MOD.validate(r, None)) == 2


# --------------------------------------------------------------------------- #
# --gc: retention 超過/orphan session の回収 (dry-run 既定)
# --------------------------------------------------------------------------- #
def _write_session(root: Path, sid: str, retention: str) -> Path:
    d = root / sid
    d.mkdir()
    (d / "handoff.json").write_text(
        json.dumps({"session_id": sid, "created_at": "2026-01-01T00:00:00Z", "retention_until": retention}),
        encoding="utf-8",
    )
    return d


def test_gc_dry_run_lists_expired_without_deleting(tmp_path):
    expired = _write_session(tmp_path, "s-old", "2026-02-01T00:00:00Z")
    _write_session(tmp_path, "s-live", "2099-01-01T00:00:00Z")
    report = MOD.gc_sessions(tmp_path, apply=False)
    assert report["mode"] == "dry-run"
    assert [d["session_id"] for d in report["deleted"]] == ["s-old"]
    assert expired.is_dir(), "dry-run が実削除している"
    assert not (tmp_path / "index.jsonl").exists()


def test_gc_apply_deletes_expired_and_appends_index(tmp_path):
    expired = _write_session(tmp_path, "s-old", "2026-02-01T00:00:00Z")
    live = _write_session(tmp_path, "s-live", "2099-01-01T00:00:00Z")
    report = MOD.gc_sessions(tmp_path, apply=True)
    assert report["mode"] == "apply"
    assert not expired.exists()
    assert live.is_dir(), "期限内 session が削除された"
    lines = [json.loads(x) for x in (tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 1
    assert lines[0]["session_id"] == "s-old" and lines[0]["status"] == "deleted"
    assert lines[0]["reason"] == "retention_expired"


def test_gc_collects_orphan_sessions(tmp_path):
    orphan = tmp_path / "s-orphan"
    orphan.mkdir()
    (orphan / "progress.json").write_text("{}", encoding="utf-8")
    report = MOD.gc_sessions(tmp_path, apply=False)
    assert [d["reason"] for d in report["deleted"]] == ["orphan"]
    assert orphan.is_dir(), "dry-run が orphan を実削除している"


def test_gc_keeps_corrupted_handoff(tmp_path):
    broken = tmp_path / "s-broken"
    broken.mkdir()
    (broken / "handoff.json").write_text("{not json", encoding="utf-8")
    report = MOD.gc_sessions(tmp_path, apply=True)
    assert report["deleted"] == [] and broken.is_dir(), "破損 handoff は誤削除せず保持する契約"


def test_gc_cli_dry_run_exit0(tmp_path, capsys):
    _write_session(tmp_path, "s-old", "2026-02-01T00:00:00Z")
    assert MOD.main(["--gc", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "dry-run" and out["deleted"][0]["session_id"] == "s-old"


def test_cli_requires_record_or_gc(capsys):
    assert MOD.main([]) == 2


# --------------------------------------------------------------------------- #
# 型の違う record・日時の形・CLI の引数 (レビュー D の再発防止)
# --------------------------------------------------------------------------- #
def test_type_mismatched_record_reports_errors_without_traceback(tmp_path, capsys):
    cases = [
        ({"outcome": []}, [{"id": "u1", "role": "user"}]),
        ({**base_record(), "collaboration_mode": ["framework-led"]}, [{"id": "u1", "role": "user"}]),
        ({**base_record(), "user_solution": {"text": "自分で選ぶ", "source_turn_ids": [{"id": "u1"}]}},
         [{"id": "u1", "role": "user"}]),
        (base_record(), ["u1", {"id": "u1", "role": "user"}]),
    ]
    for record, transcript in cases:
        assert MOD.validate(record, transcript), record
        rec = tmp_path / "record.json"
        rec.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        tr = tmp_path / "transcript.json"
        tr.write_text(json.dumps(transcript, ensure_ascii=False), encoding="utf-8")
        assert MOD.main(["--record", str(rec), "--transcript", str(tr)]) == 1
        assert json.loads(capsys.readouterr().out)["valid"] is False


def test_created_at_and_retention_until_must_be_iso8601():
    r = base_record()
    r["created_at"], r["retention_until"] = "x", "forever"
    errors = MOD.validate(r, [{"id": "u1", "role": "user", "content": "自分で選ぶ"}])
    assert any("created_at が ISO 8601" in e for e in errors)
    assert any("retention_until が ISO 8601" in e for e in errors)
    r = base_record()
    r["retention_until"] = "2026-07-01T00:00:00Z"
    assert any("created_at より後でない" in e for e in MOD.validate(r, [{"id": "u1", "role": "user"}]))


def test_null_turn_id_does_not_satisfy_provenance():
    r = base_record()
    r["user_solution"]["source_turn_ids"] = [None]
    errors = MOD.validate(r, [{"role": "user", "content": "自分で選ぶ"}])
    assert any("source_turn_ids" in e for e in errors)


def test_stance_self_check_requires_bool():
    r = base_record()
    r["stance_self_check"] = {"no_prescription": "false"}
    errors = MOD.validate(r, [{"id": "u1", "role": "user", "content": "自分で選ぶ"}])
    assert any("stance_self_check.no_prescription が真偽値でない" in e for e in errors)


def test_cli_rejects_conflicting_or_stray_flags(tmp_path, capsys):
    rec = tmp_path / "record.json"
    rec.write_text(json.dumps(base_record(), ensure_ascii=False), encoding="utf-8")
    assert MOD.main(["--record", str(rec), "--apply"]) == 2
    assert MOD.main(["--gc", str(tmp_path), "--record", str(rec)]) == 2
    assert MOD.main(["--gc", str(tmp_path / "missing")]) == 2
    capsys.readouterr()


def test_cli_non_utf8_record_is_usage_error(tmp_path, capsys):
    rec = tmp_path / "record.json"
    rec.write_bytes(b"\xff\xfe{}")
    assert MOD.main(["--record", str(rec)]) == 2
    assert json.loads(capsys.readouterr().out)["valid"] is False


def test_gc_plans_before_deleting_and_keeps_malformed_handoffs(tmp_path, capsys):
    (tmp_path / "s_dir_handoff" / "handoff.json").mkdir(parents=True)
    expired = _write_session(tmp_path, "s_expired", "2026-02-01T00:00:00Z")
    listed = tmp_path / "s_list"
    listed.mkdir()
    (listed / "handoff.json").write_text("[]", encoding="utf-8")
    bad_retention = _write_session(tmp_path, "s_forever", "forever")
    assert MOD.main(["--gc", str(tmp_path)]) == 0
    dry = json.loads(capsys.readouterr().out)
    assert [d["session_id"] for d in dry["deleted"]] == ["s_expired"] and expired.is_dir()
    assert MOD.main(["--gc", str(tmp_path), "--apply"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert [d["session_id"] for d in report["deleted"]] == ["s_expired"] and not expired.exists()
    reasons = {r["session_id"]: r["reason"] for r in report["needs_review"]}
    assert set(reasons) == {"s_dir_handoff", "s_list", "s_forever"}
    assert reasons["s_forever"] == "不正な retention_until"
    assert (tmp_path / "s_dir_handoff").is_dir() and listed.is_dir() and bad_retention.is_dir()


def test_gc_uses_default_retention_when_retention_until_is_absent(tmp_path):
    d = tmp_path / "s-redirect"
    d.mkdir()
    (d / "handoff.json").write_text(
        json.dumps({"outcome": "redirected_goal_setting", "created_at": "2026-01-01T00:00:00Z"}), encoding="utf-8")
    report = MOD.gc_sessions(tmp_path, apply=False)
    assert [(x["session_id"], x["reason"]) for x in report["deleted"]] == [("s-redirect", "retention_default_expired")]


def test_gc_does_not_delete_when_index_cannot_be_opened(tmp_path):
    expired = _write_session(tmp_path, "s-old", "2026-02-01T00:00:00Z")
    (tmp_path / "index.jsonl").mkdir()
    report = MOD.gc_sessions(tmp_path, apply=True)
    assert report["errors"] and report["deleted"] == [] and expired.is_dir()
