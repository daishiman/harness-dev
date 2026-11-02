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
import os
import subprocess
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
        "gate_kind": "rescue",
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


def test_codex_lint_uses_native_runtime_guard(lint, monkeypatch):
    """runtimeのラベルとPASSの自己申告だけでは合格させない。"""
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["environment"]["runtime"] = "codex"
    path = _write_verdict(lint, doc)
    verdict_mod, backend_mod, schema = lint.load_harness()
    # schema/closureは別の単体テストで検証。この境界ではnative検査への委譲を測る。
    monkeypatch.setattr(verdict_mod, "validate_schema", lambda *_: [])
    seen = []

    def digest(source, runtime="claude"):
        seen.append(runtime)
        return doc["skill_dir_tree_sha"]

    monkeypatch.setattr(verdict_mod, "skill_dir_tree_sha", digest)
    monkeypatch.setattr(
        verdict_mod, "validate_runtime_evidence",
        lambda *_: ["native activation missing"], raising=False,
    )
    errors = lint.check_verdict(path, "demo-plugin", "run-demo", verdict_mod, backend_mod, schema)
    assert seen == ["codex"]
    assert any("runtime-evidence: native activation missing" in item for item in errors)


def test_contractual_gate_exemption_is_surfaced(lint, capsys):
    """契約 gate 免除は合格だが黙って通さない — [NOTE] で必ず可視化されること。"""
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["gate_response_count"] = 1
    doc["gate_kind"] = "contractual"
    doc["gate_contract_evidence"] = ["frontmatter.external_mutation_guard"]
    _write_verdict(lint, doc)
    assert lint.run_lint() == 0
    out = capsys.readouterr().out
    assert "[NOTE]" in out
    assert "gate_kind=contractual" in out
    assert "frontmatter.external_mutation_guard" in out


def test_contractual_without_evidence_is_a_violation(lint, capsys):
    """接地根拠なき contractual は手書き verdict でも通さないこと (CLI 迂回の封鎖)。"""
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["gate_response_count"] = 1
    doc["gate_kind"] = "contractual"
    _write_verdict(lint, doc)
    assert lint.run_lint() == 1
    assert "gate_contract_evidence が空" in capsys.readouterr().out


def test_rescue_gate_is_not_reported_as_exemption(lint, capsys):
    """rescue の gate 応答は免除ではない (降格側で裁かれる) — NOTE を出さないこと。"""
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["gate_response_count"] = 1
    _write_verdict(lint, doc)
    lint.run_lint()
    assert "[NOTE]" not in capsys.readouterr().out


def test_verdict_without_gate_kind_stays_valid(lint):
    """gate_kind 導入前の verdict (gate=0) を schema 違反にしないこと。"""
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    del doc["gate_kind"]
    _write_verdict(lint, doc)
    assert lint.run_lint() == 0


def test_missing_gate_kind_is_not_an_exemption(lint, capsys):
    """gate_kind 欠落は fail-closed に rescue — 免除として扱わないこと。"""
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    del doc["gate_kind"]
    doc["gate_response_count"] = 1
    _write_verdict(lint, doc)
    lint.run_lint()
    assert "[NOTE]" not in capsys.readouterr().out


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


def test_stale_sha_names_drifted_skill_and_skips_manifest_version(lint, monkeypatch, tmp_path, capsys):
    """未追跡の合成 fixture はファイル名を足さない。git 上の受領ツリーなら挙動ファイルだけ足す。"""
    monkeypatch.setattr(lint, "ROOT", tmp_path)
    plugin = tmp_path / "plugins" / "demo-plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "demo-plugin", "version": "0.0.1", "dependencies": []}),
        encoding="utf-8",
    )
    skill_dir = _make_skill(lint)
    verdict_path = _write_verdict(lint, _valid_doc(lint, skill_dir))
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    })
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=tmp_path, check=True, env=env)
    manifest = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    manifest["version"] = "9.9.9"
    (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        SKILL_MD_DECLARING.format(name="run-demo") + "\nchanged\n", encoding="utf-8"
    )
    assert lint.run_lint() == 1
    out = capsys.readouterr().out
    assert "stale-sha" in out
    assert "plugins/demo-plugin/skills/run-demo/SKILL.md" in out
    assert "plugin.json" not in out
    assert verdict_path.name == "verdict.json"


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


def _receipt(lint, ref, skill="run-demo"):
    path = lint.EVAL_LOG / "demo-plugin" / skill / "criteria-test" / "scenario-verdict.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "criteria_results": {
            "OUT1": {"verify_by": "live-trial", "live_trial_verdict_ref": ref},
        },
    }), encoding="utf-8")
    return path


def test_criteria_receipt_pass_beats_newer_non_pass(lint):
    """辞書順で新しい失敗 run は、receipt が採用した current PASS を受理証跡にしない。"""
    skill_dir = _make_skill(lint)
    good = _valid_doc(lint, skill_dir)
    bad = _valid_doc(lint, skill_dir)
    bad["overall"]["verdict"] = "BLOCKED"
    bad["downgrade_reason"] = "tmux 不在 / HARD_CAP 超過等の fail-closed"
    _write_verdict(lint, good, run_id="20260701T000000")
    _write_verdict(lint, bad, run_id="20260702T000000")
    _receipt(lint, "eval-log/demo-plugin/run-demo/live-trial/20260701T000000/verdict.json")
    assert lint.run_lint() == 0


def test_corrupt_criteria_receipt_does_not_fall_through(lint, capsys):
    skill_dir = _make_skill(lint)
    _write_verdict(lint, _valid_doc(lint, skill_dir), run_id="20260702T000000")
    path = _receipt(lint, "eval-log/demo-plugin/run-demo/live-trial/20260702T000000/verdict.json")
    path.write_text("{", encoding="utf-8")
    assert lint.run_lint() == 1
    assert "criteria-receipt-invalid-json" in capsys.readouterr().out


def test_stale_receipt_verdict_is_reported_instead_of_newer_fail(lint, capsys):
    skill_dir = _make_skill(lint)
    good = _valid_doc(lint, skill_dir)
    good["skill_dir_tree_sha"] = "0" * 64
    bad = _valid_doc(lint, skill_dir)
    bad["overall"]["verdict"] = "FAIL"
    _write_verdict(lint, good, run_id="20260701T000000")
    _write_verdict(lint, bad, run_id="20260702T000000")
    _receipt(lint, "eval-log/demo-plugin/run-demo/live-trial/20260701T000000/verdict.json")
    assert lint.run_lint() == 1
    out = capsys.readouterr().out
    assert "20260701T000000/verdict.json stale-sha" in out
    assert "verdict=FAIL" not in out


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
