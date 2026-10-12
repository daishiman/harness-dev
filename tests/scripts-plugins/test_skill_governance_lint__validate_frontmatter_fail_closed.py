"""fail-closed の回帰テスト: plugins/skill-governance-lint/scripts/validate-frontmatter.py

coverage レビューの指摘 3 件を赤で固定する。
  - scalar のはずのキーを list で書くと `.split` / `.lower` で traceback になり、
    --skills-dir の残りの skill が報告されないまま終わっていた。
  - 2つ目以降のパスや --skills-dir / --self-test の後ろの引数を黙って捨て、
    検査したつもりの SKILL.md が素通りしていた。
  - `../` や絶対パス、外を指す symlink の参照を、実在するというだけで通していた。

main() は in-process で呼ぶ (s2 と同じく monkeypatch(sys.argv))。fixture は tmp_path だけ。
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "validate-frontmatter.py"

_SPEC = importlib.util.spec_from_file_location("validate_frontmatter_fail_closed", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)

BASE = {
    "name": "run-x",
    "description": "実行するとき、また再実行する場合に使う。",
    "kind": "run",
    "version": "1.0.0",
    "owner": "t",
    "source": "doc/x.md",
}


def _fm(changes=None) -> str:
    """BASE に changes を重ねた frontmatter。list の値は block list で書く。"""
    lines = []
    for key, value in {**BASE, **(changes or {})}.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {item}" for item in value)
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _skill(skill_dir: Path, fm: str, filename: str = "SKILL.md") -> Path:
    skill_dir.mkdir(parents=True, exist_ok=True)
    p = skill_dir / filename
    p.write_text(f"---\n{fm}\n---\n本文\n", encoding="utf-8")
    return p


def _run_main(monkeypatch, *argv):
    monkeypatch.setattr("sys.argv", ["validate-frontmatter.py", *argv])
    return MOD.main()


# --------------------------------------------------------------------------
# 1. list の値: traceback にせず型の指摘にして、残りの検査と残りの skill を続ける
# --------------------------------------------------------------------------

LIST_KEYS = [
    "name", "description", "kind", "version", "owner", "effect", "merge_strategy",
    "conflict_policy", "source", "source-tier", "last-audited", "cross_platform",
    "disable-model-invocation", "user-invocable", "context",
]


@pytest.mark.parametrize("key", LIST_KEYS)
def test_list_value_is_a_type_finding_not_a_traceback(tmp_path, key):
    p = _skill(tmp_path / "run-x", _fm({key: ["a", "b"]}))
    _, errs = MOD.validate_file(p)
    assert f"field '{key}' must be a scalar, got list: ['a', 'b']" in errs


def test_inline_list_value_is_also_a_type_finding(tmp_path):
    p = _skill(tmp_path / "run-x", _fm({"kind": "[run, ref]"}))
    _, errs = MOD.validate_file(p)
    assert "field 'kind' must be a scalar, got list: ['run', 'ref']" in errs


def test_list_value_does_not_hide_the_other_findings(tmp_path):
    # 型の指摘の後も、同じ skill の別の検査 (SemVer) は続く
    p = _skill(tmp_path / "run-x", _fm({"kind": ["run"], "version": "x"}))
    _, errs = MOD.validate_file(p)
    assert "field 'kind' must be a scalar, got list: ['run']" in errs
    assert "version 'x' must be SemVer (X.Y.Z)" in errs


def test_list_value_in_a_capability_file_is_a_type_finding(tmp_path):
    p = _skill(tmp_path / "agents", _fm({"kind": "agent", "name": ["x-agent"]}), "x-agent.md")
    _, errs = MOD.validate_file(p)
    assert "field 'name' must be a scalar, got list: ['x-agent']" in errs


def test_skills_dir_reports_the_skills_after_a_list_value(monkeypatch, tmp_path, capsys):
    # run-a (list) が先に走査される。traceback で止まると run-b の指摘が出ない
    skills = tmp_path / "skills"
    _skill(skills / "run-a", _fm({"kind": ["run"]}))
    _skill(skills / "run-b", _fm({"name": "run-b", "version": "x"}))
    rc = _run_main(monkeypatch, "--skills-dir", str(skills))
    assert rc == 1
    err = capsys.readouterr().err
    assert "run-a: field 'kind' must be a scalar, got list: ['run']" in err
    assert "run-b: version 'x' must be SemVer (X.Y.Z)" in err


def test_single_path_with_list_value_returns_1(monkeypatch, tmp_path, capsys):
    p = _skill(tmp_path / "run-x", _fm({"cross_platform": ["true"]}))
    rc = _run_main(monkeypatch, str(p))
    assert rc == 1
    assert "field 'cross_platform' must be a scalar" in capsys.readouterr().err


# --------------------------------------------------------------------------
# 2. 余分な引数: 黙って捨てずに usage error (exit 2)
# --------------------------------------------------------------------------

def test_second_skill_path_is_usage_error(monkeypatch, tmp_path, capsys):
    # 1つ目が合格でも、2つ目 (指摘あり) を捨てて 0 を返さない
    good = _skill(tmp_path / "run-good", _fm())
    bad = _skill(tmp_path / "run-bad", _fm({"version": "x"}))
    rc = _run_main(monkeypatch, str(good), str(bad))
    assert rc == 2
    captured = capsys.readouterr()
    assert "only one SKILL.md path is accepted, got 2" in captured.err
    assert "usage:" in captured.err
    assert captured.out == ""


@pytest.mark.parametrize("argv", [
    ("--skills-dir", "{d}", "extra"),
    ("extra", "--skills-dir", "{d}"),
    ("--skills-dir", "{d}", "--skills-dir", "{d}"),
])
def test_skills_dir_with_extra_arguments_is_usage_error(monkeypatch, tmp_path, capsys, argv):
    skills = tmp_path / "skills"
    _skill(skills / "run-x", _fm())
    rc = _run_main(monkeypatch, *(a.format(d=skills) for a in argv))
    assert rc == 2
    captured = capsys.readouterr()
    assert "usage: validate-frontmatter.py --skills-dir" in captured.err
    assert captured.out == ""


@pytest.mark.parametrize("argv", [("--self-test", "extra"), ("extra", "--self-test")])
def test_self_test_with_extra_arguments_is_usage_error(monkeypatch, capsys, argv):
    rc = _run_main(monkeypatch, *argv)
    assert rc == 2
    captured = capsys.readouterr()
    assert "--self-test takes no other arguments" in captured.err
    assert "self-test ok" not in captured.out


# --------------------------------------------------------------------------
# 3. repo の外: 実在しても参照として認めない
# --------------------------------------------------------------------------

@pytest.fixture
def repo(tmp_path):
    """tmp_path/repo を repo root にし、その外に tmp_path/outside を置く。"""
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "scripts" / "real.py").write_text("", encoding="utf-8")
    (root / "doc").mkdir()
    (root / "doc" / "x.md").write_text("", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("", encoding="utf-8")
    (outside / "doc.md").write_text("", encoding="utf-8")
    (root / "scripts" / "link.py").symlink_to(outside / "secret.py")
    skill_dir = root / "plugins" / "p" / "skills" / "run-x"
    return root, skill_dir, outside


def _outside_refs(outside: Path):
    return [
        "../outside/secret.py",              # repo root からの ../
        "../../../../../outside/secret.py",  # skill dir からの ../
        str(outside / "secret.py"),          # 絶対パス
        "scripts/link.py",                   # repo の中の symlink が外を指す
    ]


def test_outside_refs_are_reported(repo):
    root, skill_dir, outside = repo
    p = _skill(skill_dir, _fm())
    for entry in _outside_refs(outside):
        errs = MOD.check_refs_exist({"script_refs": [entry]}, p)
        assert errs == [
            f"OUTSIDE_REPO_REF: script_refs '{entry}' resolves outside the repository ({root})"
        ], entry


def test_inside_refs_still_pass(repo):
    _, skill_dir, _ = repo
    p = _skill(skill_dir, _fm())
    # repo の中に留まる ../ は通す
    refs = ["scripts/real.py", "../../../../scripts/real.py"]
    assert MOD.check_refs_exist({"script_refs": refs}, p) == []


def test_main_returns_1_for_outside_ref(monkeypatch, repo, capsys):
    _, skill_dir, _ = repo
    p = _skill(skill_dir, _fm({"script_refs": ["../outside/secret.py"]}))
    rc = _run_main(monkeypatch, str(p))
    assert rc == 1
    assert "OUTSIDE_REPO_REF: script_refs '../outside/secret.py'" in capsys.readouterr().err


@pytest.mark.parametrize("source", ["../outside/doc.md", "{abs}"])
def test_outside_source_is_a_demotion_warning(repo, source):
    # source の実在しない場合と同じ重さ (warn) で、外のパスを確認済み正本として扱わない
    _, skill_dir, outside = repo
    source = source.format(abs=outside / "doc.md")
    p = _skill(skill_dir, _fm({"source": source, "source-tier": "code-verified"}))
    _, errs = MOD.validate_file(p)
    assert (
        "warn: source-tier 'code-verified' may need demotion "
        f"(source path outside the repository: {source})"
    ) in errs


def test_inside_source_has_no_demotion_warning(repo):
    _, skill_dir, _ = repo
    p = _skill(skill_dir, _fm({"source": "doc/x.md", "source-tier": "code-verified"}))
    _, errs = MOD.validate_file(p)
    assert not any("may need demotion" in e for e in errs)
