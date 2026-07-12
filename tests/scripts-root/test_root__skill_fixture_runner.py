"""scripts/skill-fixture-runner.py の genuine で網羅的な機能テスト (network 不要)。

このスクリプトは量産スキルの smoke regression runner。各スキル dir に対し
  1. validate-frontmatter.py
  2. lint-skill-name.py
  3. fixture baseline JSON (max_lines) があれば行数 cap
を実行し、結果を eval-log/fixture-results.json に書き、1件でも失敗で exit 1。

本ファイルは module を in-process import し、ハードコード定数
(SKILLS_DIR / FIXTURE_DIR / OUT_PATH) を monkeypatch で tmp_path へ向けて
実 eval-log を書き換えずに各分岐を網羅する:
  - run(): 正常終了 / 例外 (rc=99)
  - check_skill(): SKILL.md 欠落 / 全 PASS / 名前違反 / frontmatter 違反 /
    baseline 行数超過 PASS+FAIL / baseline JSON 破損
  - main(): SKILLS_DIR 欠落 (rc=2) / 全 PASS (rc=0) / 1件失敗 (rc=1) /
    出力 JSON 構造 / 空ディレクトリ

LINT 定数は実 lint スクリプト (network 不要・決定論的) をそのまま使うため、
PASS/FAIL は本物の lint 判定で担保される (Goodhart 回避)。
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "skill-fixture-runner.py"

_SPEC = importlib.util.spec_from_file_location("skill_fixture_runner_uut", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# --- helpers -----------------------------------------------------------------

_PASS_FM = (
    "---\n"
    "name: {name}\n"
    "description: テスト用のサンプルです。実行するとき、または確認する場合に使う。\n"
    "kind: run\n"
    "version: 1.0.0\n"
    "owner: team-test\n"
    "user-invocable: true\n"
    "source: doc/internal.md\n"
    "---\n"
    "# Sample\n"
    "body\n"
)


def _make_skill(skills_dir: Path, name: str, body: str | None = None,
                *, with_md: bool = True) -> Path:
    sd = skills_dir / name
    sd.mkdir(parents=True)
    if with_md:
        (sd / "SKILL.md").write_text(
            body if body is not None else _PASS_FM.format(name=name),
            encoding="utf-8",
        )
    return sd


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """SKILLS_DIR / FIXTURE_DIR / OUT_PATH を tmp_path へ閉じ込める。"""
    skills = tmp_path / "skills"
    skills.mkdir()
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    out = tmp_path / "eval-log" / "fixture-results.json"
    monkeypatch.setattr(MOD, "SKILLS_DIR", skills)
    monkeypatch.setattr(MOD, "FIXTURE_DIR", fixtures)
    monkeypatch.setattr(MOD, "OUT_PATH", out)
    return skills, fixtures, out


# --- run() -------------------------------------------------------------------

def test_run_success_returns_zero_and_output():
    rc, out = MOD.run(["python3", "-c", "print('hello world')"])
    assert rc == 0
    assert "hello world" in out


def test_run_nonzero_returncode_captured():
    rc, out = MOD.run(["python3", "-c", "import sys; sys.stderr.write('boom'); sys.exit(7)"])
    assert rc == 7
    assert "boom" in out


def test_run_exception_returns_99():
    # 実行不能なコマンド -> FileNotFoundError -> 99
    rc, out = MOD.run(["this-binary-does-not-exist-xyz"])
    assert rc == 99
    assert out  # 例外文字列


def test_run_truncates_to_last_2000_chars():
    rc, out = MOD.run(["python3", "-c", "print('x' * 5000)"])
    assert rc == 0
    assert len(out) <= 2000


# --- check_skill(): SKILL.md 欠落 -------------------------------------------

def test_check_skill_missing_md_fails(env):
    skills, _fixtures, _out = env
    sd = _make_skill(skills, "run-nomd", with_md=False)
    result = MOD.check_skill(sd)
    assert result["passed"] is False
    assert result["checks"] == [
        {"name": "exists", "passed": False, "msg": "SKILL.md missing"}
    ]


# --- check_skill(): 全 PASS --------------------------------------------------

def test_check_skill_all_pass(env):
    skills, _fixtures, _out = env
    sd = _make_skill(skills, "run-sample")
    result = MOD.check_skill(sd)
    assert result["passed"] is True
    names = {c["name"] for c in result["checks"]}
    assert names == {"validate-frontmatter", "lint-skill-name"}
    assert all(c["passed"] for c in result["checks"])
    assert all(c["msg"] == "" for c in result["checks"])


# --- check_skill(): 名前違反 (lint-skill-name FAIL) -------------------------

def test_check_skill_name_violation(env):
    skills, _fixtures, _out = env
    # dir 名 = name で kebab だが prefix なし -> 第2条違反 (lint-skill-name 失敗)
    sd = _make_skill(skills, "sample")
    result = MOD.check_skill(sd)
    assert result["passed"] is False
    name_check = next(c for c in result["checks"] if c["name"] == "lint-skill-name")
    assert name_check["passed"] is False
    assert "第" in name_check["msg"]  # 条文違反メッセージが格納される


# --- check_skill(): frontmatter 違反 (validate-frontmatter FAIL) ------------

def test_check_skill_frontmatter_violation(env):
    skills, _fixtures, _out = env
    body = "---\nname: run-broke\n---\nbody\n"  # 必須フィールド欠落
    sd = _make_skill(skills, "run-broke", body=body)
    result = MOD.check_skill(sd)
    assert result["passed"] is False
    fm_check = next(c for c in result["checks"] if c["name"] == "validate-frontmatter")
    assert fm_check["passed"] is False
    assert "missing required field" in fm_check["msg"]


# --- check_skill(): baseline 行数 cap ---------------------------------------

def test_check_skill_baseline_line_cap_pass(env):
    skills, fixtures, _out = env
    sd = _make_skill(skills, "run-sample")
    (fixtures / "run-sample.baseline.json").write_text(
        json.dumps({"max_lines": 500}), encoding="utf-8"
    )
    result = MOD.check_skill(sd)
    # 行数は max_lines 以下なので fixture-line-cap チェックは追加されない
    assert result["passed"] is True
    assert not any(c["name"] == "fixture-line-cap" for c in result["checks"])


def test_check_skill_baseline_line_cap_fail(env):
    skills, fixtures, _out = env
    sd = _make_skill(skills, "run-sample")
    # 実ファイルは ~10 行。max_lines=3 で必ず超過 -> fixture-line-cap FAIL
    (fixtures / "run-sample.baseline.json").write_text(
        json.dumps({"max_lines": 3}), encoding="utf-8"
    )
    result = MOD.check_skill(sd)
    assert result["passed"] is False
    cap = next(c for c in result["checks"] if c["name"] == "fixture-line-cap")
    assert cap["passed"] is False
    assert "baseline.max_lines=3" in cap["msg"]


def test_check_skill_baseline_default_max_lines_300(env):
    skills, fixtures, _out = env
    sd = _make_skill(skills, "run-sample")
    # max_lines キー無し -> default 300 が使われ、短いファイルは PASS
    (fixtures / "run-sample.baseline.json").write_text(
        json.dumps({"other": 1}), encoding="utf-8"
    )
    result = MOD.check_skill(sd)
    assert result["passed"] is True


def test_check_skill_baseline_corrupt_json(env):
    skills, fixtures, _out = env
    sd = _make_skill(skills, "run-sample")
    (fixtures / "run-sample.baseline.json").write_text("{not json", encoding="utf-8")
    result = MOD.check_skill(sd)
    # JSON 破損 -> fixture-parse チェックが追加される (passed=False の check)
    parse = next(c for c in result["checks"] if c["name"] == "fixture-parse")
    assert parse["passed"] is False
    assert parse["msg"]  # 例外文字列


# --- main(): SKILLS_DIR 欠落 -> exit 2 --------------------------------------

def test_main_missing_skills_dir_returns_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MOD, "SKILLS_DIR", tmp_path / "absent")
    monkeypatch.setattr(MOD, "OUT_PATH", tmp_path / "out.json")
    rc = MOD.main()
    assert rc == 2
    assert "missing:" in capsys.readouterr().err


# --- main(): 全 PASS -> exit 0 ----------------------------------------------

def test_main_all_pass_returns_0_and_writes_json(env, capsys):
    skills, _fixtures, out = env
    _make_skill(skills, "run-alpha")
    _make_skill(skills, "run-beta")
    rc = MOD.main()
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    skill_names = sorted(r["skill"] for r in data["results"])
    assert skill_names == ["run-alpha", "run-beta"]
    assert all(r["passed"] for r in data["results"])
    stdout = capsys.readouterr().out
    assert "2 skills, 0 failed" in stdout


# --- main(): 1件失敗 -> exit 1 ----------------------------------------------

def test_main_one_failure_returns_1(env, capsys):
    skills, _fixtures, out = env
    _make_skill(skills, "run-good")
    _make_skill(skills, "bad-prefixless")  # 第2条違反で FAIL
    rc = MOD.main()
    assert rc == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    failed = [r for r in data["results"] if not r["passed"]]
    assert [r["skill"] for r in failed] == ["bad-prefixless"]
    stdout = capsys.readouterr().out
    assert "1 failed" in stdout
    assert "FAIL bad-prefixless" in stdout


# --- main(): 空 SKILLS_DIR -> exit 0 (0 skills) -----------------------------

def test_main_empty_skills_dir_returns_0(env, capsys):
    skills, _fixtures, out = env
    rc = MOD.main()
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["results"] == []
    assert "0 skills, 0 failed" in capsys.readouterr().out


# --- main(): 非ディレクトリエントリは無視される ----------------------------

def test_main_ignores_non_dir_entries(env):
    skills, _fixtures, out = env
    _make_skill(skills, "run-only")
    (skills / "stray-file.txt").write_text("ignore me", encoding="utf-8")
    rc = MOD.main()
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [r["skill"] for r in data["results"]] == ["run-only"]


# --- main(): OUT_PATH の親ディレクトリが無くても作成される ------------------

def test_main_creates_out_parent_dir(env):
    skills, _fixtures, out = env
    assert not out.parent.exists()  # env fixture では eval-log を未作成
    _make_skill(skills, "run-x")
    MOD.main()
    assert out.exists()
    assert out.parent.is_dir()
