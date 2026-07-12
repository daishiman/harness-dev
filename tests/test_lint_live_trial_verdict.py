"""scripts/lint-live-trial-verdict.py の機械検査を合成 fixture で固定する。

正: schema 適合 + sha 一致 + PASS + tier=live 非降格 → exit 0
負: DEGRADED / stale-sha / downgrade / schema 違反 / denylist 被験体 →
    存在する verdict の違反は record-only 中 (--enforce なし) でも exit 1
不在: verify_by: live-trial 宣言 skill の verdict 欠落は D13 パイロットゲート中
      record-only WARN (exit 0)、--enforce で exit 1。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LINT_PATH = ROOT / "scripts" / "lint-live-trial-verdict.py"


def _load():
    spec = importlib.util.spec_from_file_location("lint_live_trial_verdict", LINT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load()

SKILL_MD_DECLARING = """---
name: {name}
description: demo
kind: run
version: 0.1.0
owner: team-platform
feedback_contract:
  criteria:
    - id: OUT1
      loop_scope: outer
      text: 実走 acceptance が PASS する
      verify_by: live-trial
---
body
"""

SKILL_MD_PLAIN = """---
name: {name}
description: demo
kind: run
version: 0.1.0
owner: team-platform
---
body
"""


@pytest.fixture()
def lint(monkeypatch, tmp_path):
    monkeypatch.setattr(_MOD, "PLUGINS_DIR", tmp_path / "plugins")
    monkeypatch.setattr(_MOD, "EVAL_LOG", tmp_path / "eval-log")
    return _MOD


def _make_skill(lint, skill="run-demo", template=SKILL_MD_DECLARING):
    skill_dir = lint.PLUGINS_DIR / "demo-plugin" / "skills" / skill
    (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(template.format(name=skill), encoding="utf-8")
    (skill_dir / "scripts" / "x.py").write_text("print('x')\n", encoding="utf-8")
    return skill_dir


def _valid_doc(lint, skill_dir, skill="run-demo"):
    verdict_mod, _, _ = lint.load_harness()
    return {
        "target_skill": f"demo-plugin:{skill}",
        "args": "",
        "requested_model": "",
        "actual_model": ["claude-sonnet-5"],
        "nudge_count": 0,
        "gate_response_count": 0,
        "goal_verdict": {"result": "PASS", "blockers": []},
        "overall": {"launch": "PASS", "completion": "PASS", "goal_fit": "PASS", "verdict": "PASS"},
        "skill_dir_tree_sha": verdict_mod.skill_dir_tree_sha(skill_dir),
        "transcript_sha256": None,
        "scenario_origin": "synthetic",
        "environment": {
            "claude_version": "2.0.0",
            "tmux": True,
            "transcript_layer": "jsonl",
            "permissions_mode": "bypassPermissions",
        },
        "tier": "live",
        "downgrade_reason": None,
        "timeline": {"boot_s": 3.0, "poll_exit": "DONE", "wall_clock_s": 60.0},
    }


def _write_verdict(lint, doc, skill="run-demo", run_id="20260702T000000"):
    vdir = lint.EVAL_LOG / "demo-plugin" / skill / "live-trial" / run_id
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "verdict.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return vdir / "verdict.json"


# --- 正 fixture -------------------------------------------------------------

def test_valid_pass_verdict_exit0(lint, capsys):
    skill_dir = _make_skill(lint)
    _write_verdict(lint, _valid_doc(lint, skill_dir))
    assert lint.run_lint() == 0
    assert "[OK]" in capsys.readouterr().out


def test_valid_pass_verdict_exit0_with_enforce(lint):
    skill_dir = _make_skill(lint)
    _write_verdict(lint, _valid_doc(lint, skill_dir))
    assert lint.run_lint(enforce=True) == 0


# --- 不在 fixture (D13 record-only) ------------------------------------------

def test_missing_verdict_is_record_only_warn(lint, capsys):
    _make_skill(lint)
    assert lint.run_lint() == 0
    out = capsys.readouterr().out
    assert "WARN" in out and "record-only" in out


def test_missing_verdict_fails_with_enforce(lint):
    _make_skill(lint)
    assert lint.run_lint(enforce=True) == 1


def test_missing_not_required_without_declaration(lint, capsys):
    _make_skill(lint, template=SKILL_MD_PLAIN)
    assert lint.run_lint(enforce=True) == 0
    assert "0 missing" in capsys.readouterr().out


def test_denylisted_engine_skill_exempt_from_presence(lint):
    # run-skill-iter-improve は verify_by: live-trial を宣言するが被験 denylist
    # (再帰遮断) につき presence 要求から除外される
    _make_skill(lint, skill="run-skill-iter-improve")
    assert lint.run_lint(enforce=True) == 0


# --- 負 fixture (存在する verdict の違反は record-only 中も exit 1) -----------

def test_degraded_verdict_hard_fails(lint, capsys):
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["overall"]["verdict"] = "DEGRADED"
    _write_verdict(lint, doc)
    assert lint.run_lint() == 1
    assert "verdict=DEGRADED" in capsys.readouterr().out


def test_stale_sha_hard_fails(lint, capsys):
    skill_dir = _make_skill(lint)
    _write_verdict(lint, _valid_doc(lint, skill_dir))
    # verdict 後に挙動面 (SKILL.md) を変更 → tree sha 不一致
    (skill_dir / "SKILL.md").write_text(
        SKILL_MD_DECLARING.format(name="run-demo") + "\nchanged\n", encoding="utf-8"
    )
    assert lint.run_lint() == 1
    assert "stale-sha" in capsys.readouterr().out


def test_downgraded_tier_hard_fails(lint, capsys):
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["tier"] = "fork"
    doc["downgrade_reason"] = "tmux 不在"
    _write_verdict(lint, doc)
    assert lint.run_lint() == 1
    assert "downgraded" in capsys.readouterr().out


def test_schema_extra_key_hard_fails(lint, capsys):
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["score"] = 95  # additionalProperties false 違反 (点数出力の混入を遮断)
    _write_verdict(lint, doc)
    assert lint.run_lint() == 1
    assert "schema" in capsys.readouterr().out


def test_invalid_json_hard_fails(lint):
    skill_dir = _make_skill(lint)
    path = _write_verdict(lint, _valid_doc(lint, skill_dir))
    path.write_text("{broken", encoding="utf-8")
    assert lint.run_lint() == 1


def test_denylist_subject_detected_in_check(lint):
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["target_skill"] = "demo-plugin:run-skill-live-trial"
    path = _write_verdict(lint, doc)
    verdict_mod, backend_mod, schema = lint.load_harness()
    errs = lint.check_verdict(path, "demo-plugin", "run-demo", verdict_mod, backend_mod, schema)
    assert any("denylist-subject" in e for e in errs)


# --- 最新 run-id 選択 ---------------------------------------------------------

def test_latest_run_id_wins_newer_fail(lint):
    skill_dir = _make_skill(lint)
    good = _valid_doc(lint, skill_dir)
    bad = _valid_doc(lint, skill_dir)
    bad["overall"]["verdict"] = "FAIL"
    _write_verdict(lint, good, run_id="20260701T000000")
    _write_verdict(lint, bad, run_id="20260702T000000")
    assert lint.run_lint() == 1


def test_latest_run_id_wins_newer_pass(lint):
    skill_dir = _make_skill(lint)
    good = _valid_doc(lint, skill_dir)
    bad = _valid_doc(lint, skill_dir)
    bad["overall"]["verdict"] = "FAIL"
    _write_verdict(lint, bad, run_id="20260701T000000")
    _write_verdict(lint, good, run_id="20260702T000000")
    assert lint.run_lint() == 0


# --- self-test 経路 -----------------------------------------------------------

def test_self_test_passes():
    assert _load().self_test() == 0
