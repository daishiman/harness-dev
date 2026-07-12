"""validate-llm-coverage.py の unit テスト (このスクリプト自体を >=80% 行カバレッジで dogfood)。

LLM 被覆 = feedback_contract.criteria のうち検証 test/fixture を持つ割合、という計測ロジックを
tmp の擬似 skill ツリーで検証する。
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "validate_llm_coverage", ROOT / "scripts" / "validate-llm-coverage.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _make_skill(plugins_dir: Path, plugin: str, skill: str, *, kind="run",
                criteria=("IN1", "OUT1"), checklist=2, skip_reason=None):
    d = plugins_dir / plugin / "skills" / skill
    d.mkdir(parents=True, exist_ok=True)
    crit_lines = []
    for cid in criteria:
        scope = "inner" if cid.startswith("IN") else "outer"
        crit_lines.append(
            f"    - id: {cid}\n      loop_scope: {scope}\n"
            f"      text: {cid} を検証する\n      verify_by: lint"
        )
    fc = "feedback_contract:\n  max_iterations: 3\n  criteria:\n" + "\n".join(crit_lines)
    if skip_reason:
        fc = f"feedback_contract:\n  skip_reason: {skip_reason}"
    checklist_md = "\n".join(f"- [ ] item{i}" for i in range(checklist))
    (d / "SKILL.md").write_text(
        f"---\nname: {skill}\nkind: {kind}\nsince: 2026-06-24\n{fc}\n---\n\n"
        f"### 完了チェックリスト (Checklist)\n{checklist_md}\n",
        encoding="utf-8",
    )
    return d


def test_measure_skill_partial_coverage(tmp_path):
    m = _load()
    m.PLUGINS_DIR = tmp_path / "plugins"
    d = _make_skill(m.PLUGINS_DIR, "p", "run-x", criteria=("IN1", "OUT1"), checklist=2)
    (d / "tests").mkdir()
    (d / "tests" / "t.py").write_text("# covers IN1 only\nassert 'IN1'\n", encoding="utf-8")
    r = m.measure_skill("p", "run-x", repo_tests="")
    assert r["criteria_total"] == 2
    assert r["covered_ids"] == ["IN1"]
    assert r["uncovered_ids"] == ["OUT1"]
    assert r["coverage_pct"] == 50.0
    assert r["under_derived"] is False
    assert r["since"] == "2026-06-24"


def test_measure_skill_manifest_and_full(tmp_path):
    m = _load()
    m.PLUGINS_DIR = tmp_path / "plugins"
    d = _make_skill(m.PLUGINS_DIR, "p", "run-y", criteria=("IN1", "OUT1"))
    (d / "coverage-manifest.json").write_text(
        json.dumps({"covered_criteria": ["IN1", "OUT1"]}), encoding="utf-8"
    )
    r = m.measure_skill("p", "run-y", repo_tests="")
    assert r["coverage_pct"] == 100.0
    assert r["uncovered_ids"] == []


def test_measure_skill_repo_tests_reference(tmp_path):
    m = _load()
    m.PLUGINS_DIR = tmp_path / "plugins"
    _make_skill(m.PLUGINS_DIR, "p", "run-z", criteria=("IN1",))
    # repo tests が skill 名と id を共に参照 → covered
    r = m.measure_skill("p", "run-z", repo_tests="test run-z covers IN1 here")
    assert r["coverage_pct"] == 100.0


def test_under_derived_flag(tmp_path):
    m = _load()
    m.PLUGINS_DIR = tmp_path / "plugins"
    _make_skill(m.PLUGINS_DIR, "p", "run-u", criteria=("IN1", "OUT1"), checklist=5)
    r = m.measure_skill("p", "run-u", repo_tests="")
    assert r["under_derived"] is True  # checklist 5 > criteria 2


def test_non_loop_and_skip_reason_return_none(tmp_path):
    m = _load()
    m.PLUGINS_DIR = tmp_path / "plugins"
    _make_skill(m.PLUGINS_DIR, "p", "ref-a", kind="ref")
    assert m.measure_skill("p", "ref-a", repo_tests="") is None
    # loop-kind + skip_reason のみ (criteria 未整備) は ids 空により計測対象外。
    # skip_reason 自体は計測 skip の根拠にしない (lint-feedback-contract と対称)。
    _make_skill(m.PLUGINS_DIR, "p", "run-skip", skip_reason="N/A")
    assert m.measure_skill("p", "run-skip", repo_tests="") is None


def test_loop_kind_skip_reason_with_criteria_is_measured(tmp_path):
    # criteria 整備済みなら skip_reason 残存でも計測される (skip_reason escape 封鎖)。
    m = _load()
    m.PLUGINS_DIR = tmp_path / "plugins"
    d = _make_skill(m.PLUGINS_DIR, "p", "run-sr", criteria=("IN1", "OUT1"))
    md = d / "SKILL.md"
    md.write_text(
        md.read_text(encoding="utf-8").replace(
            "feedback_contract:\n", "feedback_contract:\n  skip_reason: 残存フィールド\n", 1
        ),
        encoding="utf-8",
    )
    r = m.measure_skill("p", "run-sr", repo_tests="")
    assert r is not None
    assert r["criteria_total"] == 2


def test_main_warn_mode(tmp_path, monkeypatch, capsys):
    m = _load()
    m.PLUGINS_DIR = tmp_path / "plugins"
    m.TESTS_DIR = tmp_path / "tests"
    m.EVAL_LOG = tmp_path / "eval-log"
    _make_skill(m.PLUGINS_DIR, "p", "run-x", criteria=("IN1", "OUT1"))
    monkeypatch.setattr(m, "_all_skills", lambda: {("p", "run-x")})
    monkeypatch.setattr("sys.argv", ["x", "--all", "--json", str(tmp_path / "out.json")])
    assert m.main() == 0  # WARN は非 fail
    out = capsys.readouterr().out
    assert "llm-coverage" in out and "WARN" in out
    data = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert data["skills_measured"] == 1 and data["below_threshold"] == 1


def test_main_gate_new_fails_for_new_skill(tmp_path, monkeypatch, capsys):
    m = _load()
    m.PLUGINS_DIR = tmp_path / "plugins"
    m.TESTS_DIR = tmp_path / "tests"
    m.EVAL_LOG = tmp_path / "eval-log"
    _make_skill(m.PLUGINS_DIR, "p", "run-new", criteria=("IN1", "OUT1"))
    monkeypatch.setattr(m, "_all_skills", lambda: {("p", "run-new")})
    monkeypatch.setattr(
        "sys.argv",
        ["x", "--all", "--gate-new", "--since", "2026-06-01", "--json", str(tmp_path / "o.json")],
    )
    assert m.main() == 1  # since(2026-06-24) >= 2026-06-01 かつ <80% → gate fail


def test_main_gate_new_requires_since(tmp_path, monkeypatch):
    m = _load()
    monkeypatch.setattr("sys.argv", ["x", "--all", "--gate-new"])
    assert m.main() == 2


def test_all_skills_and_repo_tests_helpers(tmp_path):
    m = _load()
    m.PLUGINS_DIR = tmp_path / "plugins"
    m.TESTS_DIR = tmp_path / "tests"
    _make_skill(m.PLUGINS_DIR, "p", "run-a")
    # symlink は実体側で計測 → 除外
    (m.PLUGINS_DIR / "p" / "skills" / "run-link").symlink_to(m.PLUGINS_DIR / "p" / "skills" / "run-a")
    found = m._all_skills()
    assert ("p", "run-a") in found and ("p", "run-link") not in found
    m.TESTS_DIR.mkdir(parents=True, exist_ok=True)
    (m.TESTS_DIR / "t_demo.py").write_text("def test_x():\n    assert 1\n", encoding="utf-8")
    assert "test_x" in m._repo_tests_text()


def test_git_changed_skills(tmp_path, monkeypatch):
    m = _load()
    monkeypatch.setattr(
        m.subprocess, "check_output",
        lambda *a, **k: "plugins/p/skills/run-a/SKILL.md\nREADME.md\n",
    )
    assert m._git_changed_skills("origin/main") == {("p", "run-a")}


def test_git_changed_skills_error(monkeypatch):
    m = _load()

    def _boom(*a, **k):
        raise m.subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(m.subprocess, "check_output", _boom)
    assert m._git_changed_skills("origin/main") == set()


def test_manifest_bad_json_returns_empty(tmp_path):
    m = _load()
    m.PLUGINS_DIR = tmp_path / "plugins"
    d = _make_skill(m.PLUGINS_DIR, "p", "run-bad")
    (d / "coverage-manifest.json").write_text("{not json", encoding="utf-8")
    assert m._manifest_covered(d) == set()


def test_main_ok_when_all_covered(tmp_path, monkeypatch, capsys):
    m = _load()
    m.PLUGINS_DIR = tmp_path / "plugins"
    m.TESTS_DIR = tmp_path / "tests"
    m.EVAL_LOG = tmp_path / "eval-log"
    d = _make_skill(m.PLUGINS_DIR, "p", "run-ok", criteria=("IN1", "OUT1"))
    (d / "coverage-manifest.json").write_text(
        json.dumps({"covered_criteria": ["IN1", "OUT1"]}), encoding="utf-8"
    )
    monkeypatch.setattr(m, "_all_skills", lambda: {("p", "run-ok")})
    monkeypatch.setattr("sys.argv", ["x", "--all", "--json", str(tmp_path / "o.json")])
    assert m.main() == 0
    assert "OK] llm-coverage" in capsys.readouterr().out


def test_main_gate_ok_for_new_covered(tmp_path, monkeypatch, capsys):
    m = _load()
    m.PLUGINS_DIR = tmp_path / "plugins"
    m.TESTS_DIR = tmp_path / "tests"
    m.EVAL_LOG = tmp_path / "eval-log"
    d = _make_skill(m.PLUGINS_DIR, "p", "run-okn", criteria=("IN1", "OUT1"))
    (d / "coverage-manifest.json").write_text(
        json.dumps({"covered_criteria": ["IN1", "OUT1"]}), encoding="utf-8"
    )
    monkeypatch.setattr(m, "_all_skills", lambda: {("p", "run-okn")})
    monkeypatch.setattr(
        "sys.argv",
        ["x", "--all", "--gate-new", "--since", "2026-06-01", "--json", str(tmp_path / "o.json")],
    )
    assert m.main() == 0
    assert "OK] llm-coverage gate" in capsys.readouterr().out
