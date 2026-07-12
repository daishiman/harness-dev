"""Genuine functional tests for scripts/lint-content-review.py.

純関数 (_check_verdict / _expected_review_kind / _all_skills / _read_kind /
_skill_sha256 / _expected_criteria_ids) を実入力で呼び実出力を assert する。
main は subprocess で安全な引数 (--all を tmp ROOT 風に分離せず、ここでは
git diff を空にする --changed-only / 必須引数欠落) を与え returncode を assert。

副作用は無し: git diff は読み取り専用、eval-log は tmp_path に作る fixture を
monkeypatch で差し替えて検査する (repo を汚さない)。
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-content-review.py"

_SPEC = importlib.util.spec_from_file_location("lint_content_review", SCRIPT)
LCR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(LCR)


# ---------- _expected_review_kind (純関数) ----------

def test_expected_review_kind_elegance():
    assert LCR._expected_review_kind("elegance-verdict.json") == "elegance"


def test_expected_review_kind_rubric():
    assert LCR._expected_review_kind("rubric-verdict.json") == "rubric"


def test_expected_review_kind_unknown():
    assert LCR._expected_review_kind("other-verdict.json") is None


# ---------- _check_verdict (核となる検証ロジック) ----------

def _good_verdict(plugin, skill, sha, review_kind="elegance"):
    return {
        "target": {"plugin": plugin, "skill": skill, "skill_md_sha256": sha},
        "review_kind": review_kind,
        "verdict": "PASS",
        "reviewer": "tester",
        "reviewed_at": "2026-06-24T00:00:00Z",
        "iterations": 1,
        "feedback_loop": {
            "criteria_evaluated": ["IN1", "OUT1"],
            "iteration_limit": 3,
            "iteration": 1,
            "loop_scope": "both",
            "positive_feedback": ["good"],
            "negative_feedback": [],
            "next_action": "none",
            "hook_trigger": "Stop",
        },
    }


@pytest.fixture
def skill_tree(tmp_path, monkeypatch):
    """plugins/<plugin>/skills/<skill>/SKILL.md と eval-log を tmp に作り module を向ける。"""
    plugin, skill = "p1", "run-x"
    md = tmp_path / "plugins" / plugin / "skills" / skill / "SKILL.md"
    md.parent.mkdir(parents=True)
    md.write_text("---\nname: run-x\nkind: run\n---\nbody\n", encoding="utf-8")
    sha = hashlib.sha256(md.read_bytes()).hexdigest()

    monkeypatch.setattr(LCR, "ROOT", tmp_path)
    monkeypatch.setattr(LCR, "PLUGINS_DIR", tmp_path / "plugins")
    monkeypatch.setattr(LCR, "EVAL_LOG", tmp_path / "eval-log")
    return {"tmp": tmp_path, "plugin": plugin, "skill": skill, "sha": sha, "md": md}


def test_check_verdict_missing_file(skill_tree, tmp_path):
    path = tmp_path / "nope.json"
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == "missing"


def test_check_verdict_invalid_json(skill_tree, tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    res = LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json")
    assert res.startswith("invalid-json")


def test_check_verdict_missing_schema_key(skill_tree, tmp_path):
    data = _good_verdict("p1", "run-x", skill_tree["sha"])
    del data["reviewer"]
    path = tmp_path / "v.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == "schema: missing reviewer"


def test_check_verdict_target_mismatch(skill_tree, tmp_path):
    data = _good_verdict("OTHER", "run-x", skill_tree["sha"])
    path = tmp_path / "v.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    res = LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json")
    assert res.startswith("target-mismatch")


def test_check_verdict_review_kind_mismatch(skill_tree, tmp_path):
    data = _good_verdict("p1", "run-x", skill_tree["sha"], review_kind="rubric")
    path = tmp_path / "v.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    res = LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json")
    assert res == "review_kind=rubric expected=elegance"


def test_check_verdict_not_pass(skill_tree, tmp_path):
    data = _good_verdict("p1", "run-x", skill_tree["sha"])
    data["verdict"] = "REJECT"
    path = tmp_path / "v.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == "verdict=REJECT"


def test_check_verdict_stale_sha(skill_tree, tmp_path):
    data = _good_verdict("p1", "run-x", "deadbeef" * 8)
    path = tmp_path / "v.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    res = LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json")
    assert res.startswith("stale-sha")


def test_check_verdict_feedback_loop_bad_next_action(skill_tree, tmp_path):
    data = _good_verdict("p1", "run-x", skill_tree["sha"])
    data["feedback_loop"]["next_action"] = "explode"
    path = tmp_path / "v.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == "schema: feedback_loop.next_action invalid"


def test_check_verdict_criteria_duplicates(skill_tree, tmp_path):
    data = _good_verdict("p1", "run-x", skill_tree["sha"])
    data["feedback_loop"]["criteria_evaluated"] = ["IN1", "IN1"]
    path = tmp_path / "v.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == "schema: feedback_loop.criteria_evaluated has duplicates"


def test_check_verdict_passes_clean(skill_tree, tmp_path):
    data = _good_verdict("p1", "run-x", skill_tree["sha"])
    path = tmp_path / "v.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    # SKILL.md has no frontmatter feedback_contract criteria -> _expected_criteria_ids empty -> no criteria-missing
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") is None


def test_check_verdict_criteria_missing_against_frontmatter(skill_tree, tmp_path):
    # SKILL.md frontmatter に feedback_contract.criteria を足し、verdict が一部欠落するケース
    md = skill_tree["md"]
    md.write_text(
        "---\n"
        "name: run-x\n"
        "kind: run\n"
        "feedback_contract:\n"
        "  criteria:\n"
        "    - id: IN1\n"
        "      loop_scope: inner\n"
        "      text: t\n"
        "      verify_by: lint\n"
        "    - id: OUT1\n"
        "      loop_scope: outer\n"
        "      text: t\n"
        "      verify_by: evaluator\n"
        "    - id: C1\n"
        "      loop_scope: inner\n"
        "      text: t\n"
        "      verify_by: test\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    sha = hashlib.sha256(md.read_bytes()).hexdigest()
    data = _good_verdict("p1", "run-x", sha)
    data["feedback_loop"]["criteria_evaluated"] = ["IN1", "OUT1"]  # C1 を欠落
    path = tmp_path / "v.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    res = LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json")
    assert res is not None and "criteria-missing" in res and "C1" in res


# ---------- _read_kind / _skill_sha256 / _all_skills ----------

def test_read_kind_run(skill_tree):
    assert LCR._read_kind("p1", "run-x") == "run"


def test_read_kind_missing_file_returns_none(skill_tree):
    assert LCR._read_kind("p1", "nonexistent") is None


def test_skill_sha256_matches(skill_tree):
    assert LCR._skill_sha256("p1", "run-x") == skill_tree["sha"]


def test_skill_sha256_missing_returns_none(skill_tree):
    assert LCR._skill_sha256("p1", "nonexistent") is None


def test_all_skills_finds_real_skill(skill_tree):
    skills = LCR._all_skills()
    assert ("p1", "run-x") in skills


def test_all_skills_empty_when_no_plugins_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(LCR, "PLUGINS_DIR", tmp_path / "does-not-exist")
    assert LCR._all_skills() == set()


def test_all_skills_skips_symlink(tmp_path, monkeypatch):
    plugins = tmp_path / "plugins"
    real = plugins / "p1" / "skills" / "real-skill"
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("---\nkind: run\n---\nx\n", encoding="utf-8")
    # symlink another skill name pointing at the real dir
    link = plugins / "p1" / "skills" / "linked-skill"
    link.symlink_to(real, target_is_directory=True)
    monkeypatch.setattr(LCR, "PLUGINS_DIR", plugins)
    skills = LCR._all_skills()
    assert ("p1", "real-skill") in skills
    assert ("p1", "linked-skill") not in skills


# ---------- _expected_criteria_ids ----------

def test_expected_criteria_ids_from_frontmatter(skill_tree):
    md = skill_tree["md"]
    md.write_text(
        "---\n"
        "name: run-x\n"
        "feedback_contract:\n"
        "  criteria:\n"
        "    - id: IN1\n"
        "      loop_scope: inner\n"
        "      text: t\n"
        "      verify_by: lint\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    assert LCR._expected_criteria_ids("p1", "run-x") == {"IN1"}


def test_expected_criteria_ids_empty_when_none(skill_tree):
    assert LCR._expected_criteria_ids("p1", "run-x") == set()


# ---------- main via subprocess (副作用なし) ----------

def test_main_requires_mode():
    # --changed-only / --all のどちらも無いと argparse が exit 2
    r = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert r.returncode == 2


def test_main_changed_only_no_diff_is_ok(tmp_path):
    # 存在しない base ref を渡すと _git_changed_skills は空集合になり「no target skill」
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--changed-only", "--base",
         "0000000000000000000000000000000000000000"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 0
    assert "no target skill" in r.stdout
