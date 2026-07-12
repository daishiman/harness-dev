"""validate-procedure-completeness.py (C02) を network/LLM 無しで網羅検証する。

対象 script:
  plugins/skill-intake/scripts/validate-procedure-completeness.py

方針 (goal-spec C1/C2/C6/C7 の受入テスト具現化, P04):
  - 純関数 (parse_patterns / extract_procedure / extract_true_problem /
    check_completeness / check_contamination / run) を実入力で呼ぶ。
  - main は in-process (argv) と subprocess (exit code 契約) の双方で assert。
  - interview.json (トップレベル procedure + five_axes.rows) と intake.json
    (sections.6_five_axes_summary.procedure + axes[real_problem]) の両形式を検証。
  - tmp_path のみで完結し repo を汚染しない。network は一切叩かない。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "validate-procedure-completeness.py"
PATTERNS = (
    ROOT / "plugins" / "skill-intake" / "skills" / "run-intake-interview"
    / "references" / "to-be-vocabulary-patterns.md"
)

_SPEC = importlib.util.spec_from_file_location("validate_procedure_completeness_ut", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# ---------------------------------------------------------------------------
# fixtures helpers
# ---------------------------------------------------------------------------

def _step(action="Slackログを収集", input="Slackチャンネル", output="生ログtxt",
          tool="Slack API", frequency="毎朝"):
    return {"action": action, "input": input, "output": output,
            "tool": tool, "frequency": frequency}


def _interview_detailed(steps=None, true_problem="報告作成に時間がかかる現状"):
    return {
        "procedure": {"mode": "detailed", "steps": steps or [_step()]},
        "five_axes": {"rows": [{"name": "真の課題", "content": true_problem}]},
    }


def _interview_overview(step_count="5〜7工程", participants="自分と経理", frequency="月次"):
    return {
        "procedure": {
            "mode": "overview_fallback", "difficulty_flag": True,
            "overview": {"step_count_estimate": step_count,
                         "participants": participants, "frequency": frequency},
        },
    }


def _intake_form(procedure=None, real_problem="報告作成に時間がかかる現状"):
    return {
        "sections": {
            "6_five_axes_summary": {
                "procedure": procedure or {"mode": "detailed", "steps": [_step()]},
                "axes": [{"axis_id": "real_problem", "answer": real_problem}],
            }
        }
    }


# ---------------------------------------------------------------------------
# parse_patterns
# ---------------------------------------------------------------------------

def test_parse_patterns_from_real_md():
    text = PATTERNS.read_text(encoding="utf-8")
    strong, weak, modal = MOD.parse_patterns(text)
    assert "べきである" in strong
    assert "本来は" in strong
    assert "最適化" in weak
    assert "効率化" in weak
    assert "すべき" in modal
    # 説明括弧を含む行 (例) はどのバケットにも入らない
    assert not any("(" in w for w in strong + weak + modal)


def test_parse_patterns_empty_falls_back_to_defaults():
    strong, weak, modal = MOD.parse_patterns("")
    assert strong == MOD.DEFAULT_STRONG
    assert weak == MOD.DEFAULT_WEAK
    assert modal == MOD.DEFAULT_MODAL


# ---------------------------------------------------------------------------
# extract_procedure / extract_true_problem (両形式)
# ---------------------------------------------------------------------------

def test_extract_procedure_interview_form():
    proc = MOD.extract_procedure(_interview_detailed())
    assert proc["mode"] == "detailed"


def test_extract_procedure_intake_form():
    proc = MOD.extract_procedure(_intake_form())
    assert proc["mode"] == "detailed"


def test_extract_procedure_absent():
    assert MOD.extract_procedure({"five_axes": {}}) is None
    assert MOD.extract_procedure("not a dict") is None


def test_extract_true_problem_interview_rows():
    assert MOD.extract_true_problem(_interview_detailed(true_problem="X")) == "X"


def test_extract_true_problem_intake_axes():
    assert MOD.extract_true_problem(_intake_form(real_problem="Y")) == "Y"


def test_extract_true_problem_absent():
    assert MOD.extract_true_problem({"five_axes": {"rows": []}}) is None


# ---------------------------------------------------------------------------
# check_completeness (C1 詳細 / C2 フォールバック)
# ---------------------------------------------------------------------------

def test_completeness_detailed_ok():
    complete, mode, missing = MOD.check_completeness({"mode": "detailed", "steps": [_step()]})
    assert complete is True and mode == "detailed" and missing == []


@pytest.mark.parametrize("field", ["action", "input", "output", "tool", "frequency"])
def test_completeness_detailed_each_field_missing(field):
    st = _step()
    st[field] = ""
    complete, _, missing = MOD.check_completeness({"mode": "detailed", "steps": [st]})
    assert complete is False
    assert any(field in m for m in missing)


def test_completeness_detailed_empty_steps():
    complete, _, missing = MOD.check_completeness({"mode": "detailed", "steps": []})
    assert complete is False
    assert any("steps" in m for m in missing)


def test_completeness_detailed_steps_not_list():
    complete, _, missing = MOD.check_completeness({"mode": "detailed", "steps": "x"})
    assert complete is False


def test_completeness_detailed_step_not_dict():
    complete, _, missing = MOD.check_completeness({"mode": "detailed", "steps": ["x"]})
    assert complete is False
    assert any("object でない" in m for m in missing)


def test_completeness_overview_ok():
    complete, mode, missing = MOD.check_completeness({
        "mode": "overview_fallback", "difficulty_flag": True,
        "overview": {"step_count_estimate": "3", "participants": "自分", "frequency": "日次"},
    })
    assert complete is True and mode == "overview_fallback" and missing == []


def test_completeness_overview_difficulty_flag_false():
    complete, _, missing = MOD.check_completeness({
        "mode": "overview_fallback", "difficulty_flag": False,
        "overview": {"step_count_estimate": "3", "participants": "自分", "frequency": "日次"},
    })
    assert complete is False
    assert any("difficulty_flag" in m for m in missing)


@pytest.mark.parametrize("field", ["step_count_estimate", "participants", "frequency"])
def test_completeness_overview_each_field_missing(field):
    ov = {"step_count_estimate": "3", "participants": "自分", "frequency": "日次"}
    ov[field] = "  "
    complete, _, missing = MOD.check_completeness({
        "mode": "overview_fallback", "difficulty_flag": True, "overview": ov})
    assert complete is False
    assert any(field in m for m in missing)


def test_completeness_overview_missing_overview_object():
    complete, _, missing = MOD.check_completeness({
        "mode": "overview_fallback", "difficulty_flag": True})
    assert complete is False
    assert any("overview" in m for m in missing)


def test_completeness_bad_mode():
    complete, mode, missing = MOD.check_completeness({"mode": "wat"})
    assert complete is False and mode == "wat"


def test_completeness_procedure_not_dict():
    complete, mode, missing = MOD.check_completeness(None)
    assert complete is False and mode is None
    assert any("存在しない" in m for m in missing)


# ---------------------------------------------------------------------------
# check_contamination (C7 混入検出)
# ---------------------------------------------------------------------------

def _pat():
    return MOD.parse_patterns(PATTERNS.read_text(encoding="utf-8"))


def test_contamination_clean():
    strong, weak, modal = _pat()
    r = MOD.check_contamination({"p": "請求書をfreeeで毎月作成している"}, strong, weak, modal)
    assert r["detected"] is False and r["fields"] == [] and r["matched_terms"] == []


def test_contamination_strong_signal():
    strong, weak, modal = _pat()
    r = MOD.check_contamination({"p": "本来はSlackに一本化すべき"}, strong, weak, modal)
    assert r["detected"] is True
    assert "p" in r["fields"]
    assert "本来は" in r["matched_terms"]


def test_contamination_weak_with_modal_is_detected():
    strong, weak, modal = _pat()
    r = MOD.check_contamination({"p": "請求書作成を自動化すべき"}, strong, weak, modal)
    assert r["detected"] is True
    assert "自動化" in r["matched_terms"]


def test_contamination_weak_nominal_is_warn_only():
    strong, weak, modal = _pat()
    r = MOD.check_contamination({"p": "在庫最適化ツールを日次で回している"}, strong, weak, modal)
    assert r["detected"] is False
    assert any("warn" in f and "最適化" in f for f in r["fields"])
    assert r["matched_terms"] == []


def test_contamination_general_average_regression():
    strong, weak, modal = _pat()
    r = MOD.check_contamination({"p": "一般的にはCSVで受け渡すことが多い"}, strong, weak, modal)
    assert r["detected"] is True
    assert "一般的には" in r["matched_terms"]


def test_contamination_matched_terms_dedup():
    strong, weak, modal = _pat()
    r = MOD.check_contamination(
        {"a": "本来はすべき", "b": "本来はすべき"}, strong, weak, modal)
    # 2 フィールドで検出されるが matched_terms は語単位で dedup
    assert r["detected"] is True
    assert r["matched_terms"].count("本来は") == 1
    assert len(r["fields"]) == 2


# ---------------------------------------------------------------------------
# run (統合) — 両形式
# ---------------------------------------------------------------------------

def test_run_interview_complete_clean():
    r = MOD.run(_interview_detailed(), PATTERNS.read_text(encoding="utf-8"))
    assert r["complete"] is True and r["contamination"]["detected"] is False


def test_run_intake_form_complete_clean():
    r = MOD.run(_intake_form(), PATTERNS.read_text(encoding="utf-8"))
    assert r["complete"] is True and r["contamination"]["detected"] is False


def test_run_true_problem_contamination():
    data = _interview_detailed(true_problem="本来はもっと効率化すべき")
    r = MOD.run(data, PATTERNS.read_text(encoding="utf-8"))
    assert r["contamination"]["detected"] is True
    assert any("真の課題" in f for f in r["contamination"]["fields"])


def test_run_deterministic_same_input_same_output():
    data = _interview_detailed()
    txt = PATTERNS.read_text(encoding="utf-8")
    assert MOD.run(data, txt) == MOD.run(data, txt)


# ---------------------------------------------------------------------------
# main — in-process
# ---------------------------------------------------------------------------

def _write(tmp_path, data, name="iv.json"):
    p = tmp_path / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def test_main_exit0_complete_clean(tmp_path, capsys):
    p = _write(tmp_path, _interview_detailed())
    rc = MOD.main(["--interview", str(p)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["complete"] is True


def test_main_exit1_incomplete(tmp_path, capsys):
    bad = _interview_detailed(steps=[_step(tool="")])
    p = _write(tmp_path, bad)
    rc = MOD.main(["--interview", str(p)])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["complete"] is False


def test_main_exit1_contaminated(tmp_path, capsys):
    bad = _interview_detailed(steps=[_step(action="本来はすべき")])
    p = _write(tmp_path, bad)
    rc = MOD.main(["--interview", str(p)])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["contamination"]["detected"] is True


def test_main_exit2_bad_input(tmp_path, capsys):
    rc = MOD.main(["--interview", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "input error" in capsys.readouterr().err


def test_main_patterns_fallback_when_missing(tmp_path, capsys):
    # --patterns が読めなくても DEFAULT_* で contamination を検出できる
    bad = _interview_detailed(steps=[_step(action="本来はすべき")])
    p = _write(tmp_path, bad)
    rc = MOD.main(["--interview", str(p), "--patterns", str(tmp_path / "no.md")])
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["contamination"]["detected"] is True


# ---------------------------------------------------------------------------
# main — subprocess (exit code 契約)
# ---------------------------------------------------------------------------

def _run(args, cwd):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=cwd)


def test_subprocess_exit0(tmp_path):
    p = _write(tmp_path, _interview_detailed())
    proc = _run(["--interview", str(p)], str(ROOT))
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["complete"] is True


def test_subprocess_exit1_incomplete(tmp_path):
    p = _write(tmp_path, _interview_detailed(steps=[_step(input="")]))
    proc = _run(["--interview", str(p)], str(ROOT))
    assert proc.returncode == 1


def test_subprocess_usage_exit2():
    proc = _run([], str(ROOT))
    assert proc.returncode == 2
    assert "required" in proc.stderr or "usage" in proc.stderr
