"""lint-rubric-refs-exist.py の rubric_refs / rubric-registry 物理存在検証を独立に網羅する (scripts4 系列)。

対象 script:
  plugins/skill-governance-lint/scripts/lint-rubric-refs-exist.py

このスイートは tests/scripts3 の同名テストとは独立に純関数と main の全分岐をゼロから被覆する。
  - find_frontmatter: fence あり/無し / スカラー / リスト / 空リスト / 末尾コメント除去 /
    全行コメント / インデント無しコロン分割
  - resolve_rubric_ref: ローカル相対 / ref- creator-kit ヒット / .claude フォールバック /
    どちらも無いとき 1 番目候補
  - check_skill_md: 全解決 / ローカル欠落 / rubric_refs 無し / 非 list / 混在
  - check_registry: registry 不在 / 全存在 / rubric 欠落 / upstream 欠落 / 両方
  - main: 明示 target PASS/FAIL / 非存在 target スキップ / 既定 glob / registry 伝播 /
    in-process(monkeypatch PROJECT_ROOT) と subprocess(env PROJECT_ROOT) 双方
純ローカル lint (network=false, write-scope=none) のため stub 不要。全 fixture は tmp_path。
PROJECT_ROOT は module load 時に env から固定されるので in-process は monkeypatch.setattr で、
subprocess は env で差し替えて repo を一切汚染しない。
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-rubric-refs-exist.py"


def _load():
    spec = importlib.util.spec_from_file_location("lint_rubric_refs_exist_r4_uut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def MOD():
    return _load()


def _run(args, project_root: Path):
    env = dict(os.environ)
    env["PROJECT_ROOT"] = str(project_root)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def _mk_skill(root: Path, name: str, frontmatter: str) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    p = d / "SKILL.md"
    p.write_text(f"---\n{frontmatter}\n---\n\nbody\n", encoding="utf-8")
    return p


def _write_registry(project_root: Path, rubrics: list) -> None:
    cfg = project_root / "plugins" / "skill-governance-config" / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "rubric-registry.json").write_text(
        json.dumps({"rubrics": rubrics}), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# find_frontmatter
# ---------------------------------------------------------------------------
def test_find_frontmatter_scalar_list_empty_comment(MOD, tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\n"
        "name: ref-foo\n"
        "rubric_refs:\n"
        "  - references/rubric.json  # コメント除去される\n"
        "  - ref-other\n"
        "scalar: value  # これも除去\n"
        "empty_list:\n"
        "# 全行コメントは無視\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )
    fm = MOD.find_frontmatter(p)
    assert fm["name"] == "ref-foo"
    assert fm["rubric_refs"] == ["references/rubric.json", "ref-other"]
    assert fm["scalar"] == "value"
    assert fm["empty_list"] == []


def test_find_frontmatter_no_fence(MOD, tmp_path):
    p = tmp_path / "x.md"
    p.write_text("no frontmatter\n", encoding="utf-8")
    assert MOD.find_frontmatter(p) == {}


def test_find_frontmatter_indented_whole_line_comment_skipped(MOD, tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("---\n  # indented comment\nname: a\n---\n", encoding="utf-8")
    assert MOD.find_frontmatter(p) == {"name": "a"}


def test_find_frontmatter_no_space_before_hash_not_stripped(MOD, tmp_path):
    # strip_comment は " #" (空白+#) のみ除去する。空白無しの # は値の一部に残る。
    p = tmp_path / "SKILL.md"
    p.write_text("---\nname: a#b\n---\n", encoding="utf-8")
    fm = MOD.find_frontmatter(p)
    assert fm["name"] == "a#b"


# ---------------------------------------------------------------------------
# resolve_rubric_ref
# ---------------------------------------------------------------------------
def test_resolve_local_relative(MOD, tmp_path):
    skill_dir = tmp_path / "ref-foo"
    skill_dir.mkdir()
    out = MOD.resolve_rubric_ref("references/rubric.json", skill_dir)
    assert out == (skill_dir / "references" / "rubric.json").resolve()


def test_resolve_ref_prefix_plugins_hit(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    # 正規パスは plugins/*/skills/<ref>/references/rubric.json
    target = tmp_path / "plugins" / "p" / "skills" / "ref-x" / "references" / "rubric.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")
    out = MOD.resolve_rubric_ref("ref-x", tmp_path / "anything")
    assert out == target


def test_resolve_ref_prefix_claude_fallback(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    target = tmp_path / ".claude" / "skills" / "ref-y" / "references" / "rubric.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")
    out = MOD.resolve_rubric_ref("ref-y", tmp_path / "anything")
    assert out == target


def test_resolve_ref_prefix_missing_returns_first_candidate(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    out = MOD.resolve_rubric_ref("ref-none", tmp_path / "anything")
    # plugins glob は空なので 1 番目候補は .claude フォールバックパスになる
    assert out == tmp_path / ".claude" / "skills" / "ref-none" / "references" / "rubric.json"


# ---------------------------------------------------------------------------
# check_skill_md
# ---------------------------------------------------------------------------
def test_check_skill_md_all_resolved(MOD, tmp_path):
    p = _mk_skill(tmp_path, "ref-foo", "name: ref-foo\nrubric_refs:\n  - references/rubric.json")
    refs = tmp_path / "ref-foo" / "references"
    refs.mkdir()
    (refs / "rubric.json").write_text("{}", encoding="utf-8")
    assert MOD.check_skill_md(p) == []


def test_check_skill_md_missing_local(MOD, tmp_path):
    p = _mk_skill(tmp_path, "ref-foo", "name: ref-foo\nrubric_refs:\n  - references/rubric.json")
    failures = MOD.check_skill_md(p)
    assert len(failures) == 1
    assert "references/rubric.json" in failures[0]
    assert "NOT FOUND" in failures[0]


def test_check_skill_md_no_rubric_refs(MOD, tmp_path):
    p = _mk_skill(tmp_path, "ref-foo", "name: ref-foo")
    assert MOD.check_skill_md(p) == []


def test_check_skill_md_rubric_refs_scalar_not_list(MOD, tmp_path):
    # rubric_refs がスカラー (list でない) → check スキップ
    p = _mk_skill(tmp_path, "ref-foo", "name: ref-foo\nrubric_refs: just-a-string")
    assert MOD.check_skill_md(p) == []


def test_check_skill_md_mixed_resolved_and_missing(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    ck = tmp_path / "plugins" / "p" / "skills" / "ref-ok" / "references" / "rubric.json"
    ck.parent.mkdir(parents=True)
    ck.write_text("{}", encoding="utf-8")
    p = _mk_skill(
        tmp_path,
        "ref-foo",
        "name: ref-foo\nrubric_refs:\n  - ref-ok\n  - references/missing.json",
    )
    failures = MOD.check_skill_md(p)
    assert len(failures) == 1
    assert "references/missing.json" in failures[0]


# ---------------------------------------------------------------------------
# check_registry
# ---------------------------------------------------------------------------
def test_check_registry_absent(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    assert MOD.check_registry() == []


def test_check_registry_all_present(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    (tmp_path / "good.json").write_text("{}", encoding="utf-8")
    (tmp_path / "up.md").write_text("x", encoding="utf-8")
    _write_registry(tmp_path, [{"domain": "d1", "rubric": "good.json", "upstream": ["up.md"]}])
    assert MOD.check_registry() == []


def test_check_registry_missing_rubric_only(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    _write_registry(tmp_path, [{"domain": "d2", "rubric": "missing.json"}])
    failures = MOD.check_registry()
    assert len(failures) == 1
    assert "rubric=missing.json" in failures[0]
    assert "domain=d2" in failures[0]


def test_check_registry_missing_rubric_and_upstream(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    (tmp_path / "good.json").write_text("{}", encoding="utf-8")
    _write_registry(
        tmp_path,
        [
            {"domain": "d1", "rubric": "good.json", "upstream": ["missing_up.md"]},
            {"domain": "d2", "rubric": "missing.json"},
        ],
    )
    joined = "\n".join(MOD.check_registry())
    assert "upstream=missing_up.md" in joined
    assert "rubric=missing.json" in joined


# ---------------------------------------------------------------------------
# main (in-process)
# ---------------------------------------------------------------------------
def _argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["lint-rubric-refs-exist.py", *args])


def test_main_inproc_explicit_pass(MOD, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    p = _mk_skill(tmp_path, "ref-foo", "name: ref-foo\nrubric_refs:\n  - references/r.json")
    refs = tmp_path / "ref-foo" / "references"
    refs.mkdir()
    (refs / "r.json").write_text("{}", encoding="utf-8")
    _argv(monkeypatch, str(p))
    assert MOD.main() == 0
    out = capsys.readouterr().out
    assert "PASS: rubric_refs 全件解決" in out
    assert "1 SKILL.md checked" in out


def test_main_inproc_explicit_fail(MOD, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    p = _mk_skill(tmp_path, "ref-foo", "name: ref-foo\nrubric_refs:\n  - references/missing.json")
    _argv(monkeypatch, str(p))
    assert MOD.main() == 1
    err = capsys.readouterr().err
    assert "FAIL: rubric_refs 未解決" in err
    assert "missing.json" in err


def test_main_inproc_nonexistent_target_skipped(MOD, tmp_path, monkeypatch, capsys):
    # 存在しない target は t.exists() で弾かれ registry も無いので PASS
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    _argv(monkeypatch, str(tmp_path / "ghost" / "SKILL.md"))
    assert MOD.main() == 0
    assert "PASS" in capsys.readouterr().out


def test_main_inproc_default_glob_both_roots(MOD, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    ck = tmp_path / "plugins" / "harness-creator" / "skills"
    _mk_skill(ck, "ref-a", "name: ref-a\nrubric_refs:\n  - references/r.json")
    (ck / "ref-a" / "references").mkdir()
    (ck / "ref-a" / "references" / "r.json").write_text("{}", encoding="utf-8")
    cl = tmp_path / ".claude" / "skills"
    _mk_skill(cl, "ref-b", "name: ref-b")  # rubric_refs 無し
    _argv(monkeypatch)
    assert MOD.main() == 0
    assert "2 SKILL.md checked" in capsys.readouterr().out


def test_main_inproc_registry_failure_propagates(MOD, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    _write_registry(tmp_path, [{"domain": "d2", "rubric": "missing.json"}])
    _argv(monkeypatch)
    assert MOD.main() == 1
    assert "missing.json" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# main (subprocess) — __main__ ガード + exit code 契約 (env PROJECT_ROOT)
# ---------------------------------------------------------------------------
def test_main_subprocess_pass(MOD, tmp_path):
    p = _mk_skill(tmp_path, "ref-foo", "name: ref-foo")  # rubric_refs 無し
    r = _run([str(p)], project_root=tmp_path)
    assert r.returncode == 0
    assert "PASS" in r.stdout


def test_main_subprocess_fail(MOD, tmp_path):
    p = _mk_skill(tmp_path, "ref-foo", "name: ref-foo\nrubric_refs:\n  - references/missing.json")
    r = _run([str(p)], project_root=tmp_path)
    assert r.returncode == 1
    assert "FAIL" in r.stderr
