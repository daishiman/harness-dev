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
        "referral_confirmed": True, "persistence_consent": True,
    }
    assert MOD.validate(r, None) == []


def test_redirect_record_without_consent_is_invalid():
    r = {"outcome": "redirected_goal_setting", "handoff_to": "run-ubm-goal-setting", "referral_confirmed": True}
    assert any("consent" in e for e in MOD.validate(r, None))


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
