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
import os
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


@pytest.mark.parametrize("base", ["0000000000000000000000000000000000000000", "does-not-exist"])
def test_main_changed_only_unknown_base_is_an_input_error(base):
    # 旧 test_main_changed_only_no_diff_is_ok。存在しない base を渡すと「no target skill」rc0 になる
    # 動き (fail-open) を固定していた。base を誤っただけで本当の違反が隠れるので、git の失敗は
    # 「対象なし」にせず exit 2 で止める (独立レビューの再現: --base does-not-exist)。
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--changed-only", "--base", base],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 2
    assert "no target skill" not in r.stdout
    assert f"git diff {base}...HEAD failed" in r.stderr


def test_main_changed_only_empty_diff_is_ok():
    # 差分が本当に空 (HEAD...HEAD) のときは、今までどおり「no target skill」で rc0
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--changed-only", "--base", "HEAD"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "no target skill" in r.stdout


# ---------- 形の崩れた verdict は traceback にせず違反にする (fail-closed) ----------

def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


_REQUIRED_KEYS = ["target", "review_kind", "verdict", "reviewer", "reviewed_at", "iterations", "feedback_loop"]


@pytest.mark.parametrize("data, json_type", [
    (None, "null"),
    (5, "number"),
    (_REQUIRED_KEYS, "array"),  # 必須キーの名前を並べた配列は `key not in data` を素通りする
    ("PASS", "string"),
])
def test_check_verdict_top_level_not_object(skill_tree, tmp_path, data, json_type):
    # 独立レビューの再現: verdict が null / 5 → TypeError、必須キーの配列 → AttributeError だった
    path = _write(tmp_path / "v.json", data)
    res = LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json")
    assert res == f"schema: verdict must be a JSON object, got {json_type}"


@pytest.mark.parametrize("field, value, message", [
    # 再現: criteria_evaluated=[{"id":"IN1"}] は set() で unhashable だった
    ("criteria_evaluated", [{"id": "IN1"}], "schema: feedback_loop.criteria_evaluated[1] must be string, got object"),
    ("criteria_evaluated", ["IN1", ["OUT1"]], "schema: feedback_loop.criteria_evaluated[2] must be string, got array"),
    # 再現: loop_scope=["both"] / next_action={} は set の in で unhashable だった
    ("loop_scope", ["both"], "schema: feedback_loop.loop_scope invalid"),
    ("next_action", {}, "schema: feedback_loop.next_action invalid"),
])
def test_check_verdict_unhashable_feedback_loop_fields(skill_tree, tmp_path, field, value, message):
    data = _good_verdict("p1", "run-x", skill_tree["sha"])
    data["feedback_loop"][field] = value
    path = _write(tmp_path / "v.json", data)
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == message


def test_check_verdict_unreadable_skill_md_is_stale(skill_tree, tmp_path):
    # 再現: SKILL.md を変えて chmod 000 にすると current_sha が None になり、stale の検査が外れて rc0 だった
    data = _good_verdict("p1", "run-x", skill_tree["sha"])
    path = _write(tmp_path / "v.json", data)
    md = skill_tree["md"]
    md.write_text(md.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
    md.chmod(0)
    try:
        if os.access(md, os.R_OK):
            pytest.skip("権限を外しても読める環境 (root など) では再現できない")
        assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == "stale-sha: cannot read SKILL.md"
    finally:
        md.chmod(0o644)


def test_read_kind_undecodable_skill_md_returns_none(skill_tree):
    # UTF-8 でない SKILL.md は kind が分からないので None (除外せず検査に回す)
    skill_tree["md"].write_bytes(b"---\nkind: \xff\xfe\n---\n")
    assert LCR._read_kind("p1", "run-x") is None


# ---------- --print-target の正規化 ----------

def test_print_target_drops_a_trailing_slash():
    # 再現: --print-target p1/run-x/ は skill "run-x/" を出して rc0 だった (その target は target-mismatch になる)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--print-target", "harness-creator/run-goal-seek/"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    target = json.loads(proc.stdout)
    assert (target["plugin"], target["skill"]) == ("harness-creator", "run-goal-seek")


@pytest.mark.parametrize("spec", ["harness-creator//run-goal-seek", "harness-creator/run-goal-seek/references"])
def test_print_target_rejects_nested_paths(spec):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--print-target", spec], capture_output=True, text=True, cwd=ROOT
    )
    assert proc.returncode == 2
    assert proc.stdout == ""


# ---------- frontmatter ----------

def test_script_has_a_valid_frontmatter():
    # 前回の指摘 (1): # /// script の frontmatter が無かった。exit の意味と write-scope を宣言する
    linter = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-script-frontmatter.py"
    proc = subprocess.run([sys.executable, str(linter), str(SCRIPT)], capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    head = SCRIPT.read_text(encoding="utf-8").split("# ///\n", 1)[0]
    assert "# write-scope: none" in head
    assert "0=違反なし" in head and "1=違反あり" in head and "2=usage" in head
