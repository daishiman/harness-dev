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
  - main: 明示 target PASS/FAIL / 非存在 target は exit 2 / 既定 glob / registry 伝播 /
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
def test_check_skill_md_all_resolved(MOD, tmp_path, monkeypatch):
    # 参照先は PROJECT_ROOT の中で探す (repo 外は v0.3.0 から FAIL)
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    p = _mk_skill(tmp_path, "ref-foo", "name: ref-foo\nrubric_refs:\n  - references/rubric.json")
    refs = tmp_path / "ref-foo" / "references"
    refs.mkdir()
    (refs / "rubric.json").write_text("{}", encoding="utf-8")
    assert MOD.check_skill_md(p) == []


def test_check_skill_md_missing_local(MOD, tmp_path, monkeypatch):
    # 参照先は PROJECT_ROOT の中で探す (repo 外は v0.3.0 から FAIL)
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    p = _mk_skill(tmp_path, "ref-foo", "name: ref-foo\nrubric_refs:\n  - references/rubric.json")
    failures = MOD.check_skill_md(p)
    assert len(failures) == 1
    assert "references/rubric.json" in failures[0]
    assert "NOT FOUND" in failures[0]


def test_check_skill_md_no_rubric_refs(MOD, tmp_path):
    p = _mk_skill(tmp_path, "ref-foo", "name: ref-foo")
    assert MOD.check_skill_md(p) == []


def test_check_skill_md_rubric_refs_scalar_not_list(MOD, tmp_path):
    # rubric_refs がスカラー (list でない) → 黙って読み飛ばさず FAIL
    p = _mk_skill(tmp_path, "ref-foo", "name: ref-foo\nrubric_refs: just-a-string")
    failures = MOD.check_skill_md(p)
    assert len(failures) == 1 and "list でない" in failures[0]


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


def test_main_inproc_nonexistent_target_is_input_error(MOD, tmp_path, monkeypatch, capsys):
    # 存在しない target は入力不正 (exit 2)。以前は 0 件検査のまま PASS していた
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    _argv(monkeypatch, str(tmp_path / "ghost" / "SKILL.md"))
    assert MOD.main() == 2
    assert "指定した SKILL.md が無い" in capsys.readouterr().err


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
    # 走査対象が0件だと exit 2 になるので、rubric_refs の無い skill を1つ置く
    _mk_skill(tmp_path / "plugins" / "harness-creator" / "skills", "run-x", "name: run-x")
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


# ---------------------------------------------------------------------------
# 独立レビュー (FAIL 72) の指摘の再発防止
# ---------------------------------------------------------------------------
def _ref_without_rubric(project_root: Path, name: str) -> None:
    d = project_root / "plugins" / "harness-creator" / "skills" / name / "references"
    d.mkdir(parents=True)
    (d / "sink-contract.md").write_text("# not a rubric\n", encoding="utf-8")


@pytest.mark.parametrize("refs_line", [
    "rubric_refs: [ref-sink]",
    'rubric_refs: ["ref-sink"]',
    "rubric_refs: [ref-sink]  # flow list with comment",
])
def test_flow_list_refs_are_checked_not_skipped(MOD, tmp_path, monkeypatch, refs_line):
    # 実例: assign-notion-fidelity-evaluator の `rubric_refs: [ref-output-routing]` が
    # 文字列として読まれ、rubric.json の無い ref が黙って PASS していた
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    _ref_without_rubric(tmp_path, "ref-sink")
    p = _mk_skill(tmp_path, "assign-x", f"name: assign-x\n{refs_line}")
    failures = MOD.check_skill_md(p)
    assert len(failures) == 1 and "ref-sink" in failures[0] and "NOT FOUND" in failures[0]


def test_empty_flow_list_is_a_list(MOD, tmp_path):
    p = _mk_skill(tmp_path, "assign-x", "name: assign-x\nrubric_refs: []")
    assert MOD.check_skill_md(p) == []


@pytest.mark.parametrize("item", ["- references/missing.json", "    - references/missing.json"])
def test_block_items_are_read_at_any_indent(MOD, tmp_path, item):
    p = _mk_skill(tmp_path, "assign-x", f"name: assign-x\nrubric_refs:\n{item}")
    failures = MOD.check_skill_md(p)
    assert len(failures) == 1 and "missing.json" in failures[0]


def test_undecodable_skill_md_exits_2_without_traceback(MOD, tmp_path):
    d = tmp_path / "assign-x"
    d.mkdir()
    (d / "SKILL.md").write_bytes(b"---\nname: \xff\xfe\n---\n")
    r = _run([str(d / "SKILL.md")], project_root=tmp_path)
    assert r.returncode == 2 and "入力を読めない" in r.stderr
    assert "Traceback" not in r.stderr


@pytest.mark.parametrize("registry", [
    "{broken",
    '{"rubrics": [{"rubric": "x.json"}]}',
])
def test_broken_registry_exits_2_without_traceback(MOD, tmp_path, registry):
    reg = tmp_path / "plugins" / "skill-governance-config" / "config" / "rubric-registry.json"
    reg.parent.mkdir(parents=True)
    reg.write_text(registry, encoding="utf-8")
    p = _mk_skill(tmp_path, "assign-x", "name: assign-x")
    r = _run([str(p)], project_root=tmp_path)
    assert r.returncode == 2 and "入力を読めない" in r.stderr
    assert "Traceback" not in r.stderr


def test_default_scope_reaches_other_plugins_through_claude_skills(MOD, tmp_path, monkeypatch, capsys):
    # 既定の走査は全 plugin と .claude/skills。.claude/skills の symlink から辿った skill も
    # 検査され、同じ実体は1回だけ数える
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    _ref_without_rubric(tmp_path, "ref-sink")
    other = tmp_path / "plugins" / "other" / "skills"
    p = _mk_skill(other, "assign-x", "name: assign-x\nrubric_refs: [ref-sink]")
    link_dir = tmp_path / ".claude" / "skills"
    link_dir.mkdir(parents=True)
    (link_dir / "assign-x").symlink_to(p.parent)
    _argv(monkeypatch)
    assert MOD.main() == 1
    assert "ref-sink" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 独立レビュー (PASS 89) の low 指摘: 黙って PASS する書き方を残さない
# ---------------------------------------------------------------------------
def test_mapping_value_is_not_a_list(MOD, tmp_path):
    # `rubric_refs:` の下が mapping だと、以前は空の list として黙って PASS していた
    p = _mk_skill(tmp_path, "assign-x", "name: assign-x\nrubric_refs:\n  default: references/missing.json")
    failures = MOD.check_skill_md(p)
    assert len(failures) == 1 and "list でない" in failures[0]


def test_key_with_space_before_colon_is_read(MOD, tmp_path):
    p = _mk_skill(tmp_path, "assign-x", "name: assign-x\nrubric_refs :\n  - references/missing.json")
    failures = MOD.check_skill_md(p)
    assert len(failures) == 1 and "missing.json" in failures[0]


@pytest.mark.parametrize("raw", [
    "\ufeff---\nname: assign-x\nrubric_refs:\n  - references/missing.json\n---\n",
    "---\r\nname: assign-x\r\nrubric_refs:\r\n  - references/missing.json\r\n---\r\n",
    "---\nname: assign-x\nrubric_refs:\n  - references/missing.json\n---",
])
def test_bom_crlf_and_no_trailing_newline_are_read(MOD, tmp_path, raw):
    d = tmp_path / "assign-x"
    d.mkdir()
    (d / "SKILL.md").write_bytes(raw.encode("utf-8"))
    failures = MOD.check_skill_md(d / "SKILL.md")
    assert len(failures) == 1 and "missing.json" in failures[0]


@pytest.mark.parametrize("item", ["  -", "  - ", "  - ''"])
def test_empty_item_fails(MOD, tmp_path, item):
    p = _mk_skill(tmp_path, "assign-x", f"name: assign-x\nrubric_refs:\n{item}")
    failures = MOD.check_skill_md(p)
    assert len(failures) == 1 and "空の要素" in failures[0]


def test_directory_ref_is_not_a_file(MOD, tmp_path, monkeypatch):
    # 参照先は PROJECT_ROOT の中で探す (repo 外は v0.3.0 から FAIL)。
    # v0.4.0 から、実在するディレクトリは NOT FOUND (免除の対象) でなく「ファイルでない」と報告する
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    p = _mk_skill(tmp_path, "assign-x", "name: assign-x\nrubric_refs:\n  - references")
    (tmp_path / "assign-x" / "references").mkdir()
    failures = MOD.check_skill_md(p)
    assert len(failures) == 1 and "ファイルでない" in failures[0]


def test_ref_prefix_rubric_directory_is_not_found(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    (tmp_path / "plugins" / "p" / "skills" / "ref-x" / "references" / "rubric.json").mkdir(parents=True)
    p = _mk_skill(tmp_path, "assign-x", "name: assign-x\nrubric_refs: [ref-x]")
    failures = MOD.check_skill_md(p)
    assert len(failures) == 1 and "ref-x" in failures[0]


def test_registry_rubric_directory_is_not_found(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    (tmp_path / "dir.json").mkdir()
    _write_registry(tmp_path, [{"domain": "d", "rubric": "dir.json"}])
    assert len(MOD.check_registry()) == 1


def test_no_targets_in_default_scan_exits_2(MOD, tmp_path, monkeypatch, capsys):
    # PROJECT_ROOT を取り違えると0件になる。「0件検査して PASS」にしない
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    _argv(monkeypatch)
    assert MOD.main() == 2
    assert "0件" in capsys.readouterr().err


def test_absent_registry_warns(MOD, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path)
    p = _mk_skill(tmp_path, "assign-x", "name: assign-x")
    _argv(monkeypatch, str(p))
    assert MOD.main() == 0
    assert "rubric-registry.json が無い" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 独立レビュー (PASS 82) の指摘: v0.3.0 で塞いだ穴の再発防止
# ---------------------------------------------------------------------------
def _real_rubric(project_root: Path, name: str) -> None:
    d = project_root / "plugins" / "harness-creator" / "skills" / name / "references"
    d.mkdir(parents=True)
    (d / "rubric.json").write_text("{}", encoding="utf-8")


def _python39():
    """Python 3.9 の実行系を探す。無ければ None (test は skip)。"""
    import shutil
    for cand in ("python3.9", "/usr/bin/python3"):
        exe = shutil.which(cand) if not cand.startswith("/") else (cand if Path(cand).is_file() else None)
        if not exe:
            continue
        r = subprocess.run([exe, "-c", "import sys; print(sys.version_info[:2] == (3, 9))"],
                           capture_output=True, text=True)
        if r.stdout.strip() == "True":
            return exe
    return None


def test_runs_on_python39_as_declared(tmp_path):
    # header の requires-python >=3.9 を守る。`list | None` の注釈が import 時に評価されて
    # TypeError の traceback (rc=1) にならないこと
    exe = _python39()
    if exe is None:
        pytest.skip("Python 3.9 の実行系が無い")
    p = _mk_skill(tmp_path, "assign-x", "name: assign-x\nrubric_refs: [references/missing.json]")
    env = dict(os.environ, PROJECT_ROOT=str(tmp_path), PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([exe, str(SCRIPT), str(p)], capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "missing.json" in r.stderr
    assert "Traceback" not in r.stderr


@pytest.mark.parametrize("ref", ["ref-*", "ref-re?l", "ref-[a-z]eal", "ref-**", "ref-x/../ref-real"])
def test_glob_or_path_in_ref_name_fails(MOD, tmp_path, monkeypatch, ref):
    # ref 名は glob に埋めて探すので、`ref-*` が実在する ref-real に一致して PASS してはいけない
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    _real_rubric(tmp_path, "ref-real")
    p = _mk_skill(tmp_path, "assign-x", f'name: assign-x\nrubric_refs: ["{ref}"]')
    failures = MOD.check_skill_md(p)
    assert len(failures) == 1 and "ref 名として読めない" in failures[0]


@pytest.mark.parametrize("fm", [
    'name: assign-x\n"rubric_refs": [ref-nope]',
    "name: assign-x\n'rubric_refs':\n  - ref-nope",
])
def test_quoted_key_is_read(MOD, tmp_path, monkeypatch, fm):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    p = _mk_skill(tmp_path, "assign-x", fm)
    failures = MOD.check_skill_md(p)
    assert len(failures) == 1 and "ref-nope" in failures[0] and "NOT FOUND" in failures[0]


def test_dash_without_space_at_column_0_is_not_a_list(MOD, tmp_path, monkeypatch):
    # `-nonexistent` は list の項目ではない。以前は読み飛ばして空の list として PASS していた
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    p = _mk_skill(tmp_path, "assign-x", "name: assign-x\nrubric_refs:\n-nonexistent")
    failures = MOD.check_skill_md(p)
    assert len(failures) == 1 and "list でない" in failures[0]


@pytest.mark.parametrize("ref", ["/etc/hosts", "../../../../../../../../etc/hosts"])
def test_ref_outside_repo_fails(MOD, tmp_path, monkeypatch, ref):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    p = _mk_skill(tmp_path, "assign-x", f"name: assign-x\nrubric_refs: [{ref}]")
    failures = MOD.check_skill_md(p)
    assert len(failures) == 1 and "リポジトリの外" in failures[0]


@pytest.mark.parametrize("entry, needle", [
    ({"domain": "d", "rubric": "/etc/hosts"}, "リポジトリの外"),
    ({"domain": "d", "rubric": "r.json", "upstream": [""]}, "空、または文字列でない"),
    ({"domain": "d", "rubric": "r.json", "upstream": [5]}, "空、または文字列でない"),
    # 実在するディレクトリは NOT FOUND でなく「ファイルでない」と報告する (v0.4.0)
    ({"domain": "d", "rubric": "r.json", "upstream": ["plugins"]}, "ファイルでない"),
    ({"domain": "d", "rubric": "r.json", "upstream": ["missing.md"]}, "NOT FOUND"),
    ({"domain": "d", "rubric": ""}, "空、または文字列でない"),
])
def test_registry_paths_must_be_files_in_repo(MOD, tmp_path, monkeypatch, entry, needle):
    # 空の upstream は PROJECT_ROOT 自体に解決され、以前は「存在する」として PASS していた
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    (tmp_path / "r.json").write_text("{}", encoding="utf-8")
    _write_registry(tmp_path, [entry])
    failures = MOD.check_registry()
    assert len(failures) == 1 and needle in failures[0]


def test_key_line_comment_then_block_list_is_read(MOD, tmp_path, monkeypatch):
    # `rubric_refs: # 評価基準` の下の list は YAML として正しい。兄弟の lint-sibling-plugin-paths と同じく読む
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    _real_rubric(tmp_path, "ref-real")
    p = _mk_skill(tmp_path, "assign-x", "name: assign-x\nrubric_refs: # 評価基準\n  - ref-real")
    assert MOD.check_skill_md(p) == []
    p2 = _mk_skill(tmp_path, "assign-y", "name: assign-y\nrubric_refs: # 評価基準\n  - ref-nope")
    assert len(MOD.check_skill_md(p2)) == 1


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_exits_0(tmp_path, flag):
    r = _run([flag], project_root=tmp_path)
    assert r.returncode == 0 and "usage" in r.stdout


def test_registry_directory_is_input_error_not_warning(MOD, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    (tmp_path / "plugins" / "skill-governance-config" / "config" / "rubric-registry.json").mkdir(parents=True)
    p = _mk_skill(tmp_path, "assign-x", "name: assign-x")
    _argv(monkeypatch, str(p))
    assert MOD.main() == 2
    err = capsys.readouterr().err
    assert "ファイルでない" in err and "無いので" not in err


def test_registry_with_bom_is_read(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    cfg = tmp_path / "plugins" / "skill-governance-config" / "config"
    cfg.mkdir(parents=True)
    (cfg / "rubric-registry.json").write_bytes(
        "\ufeff".encode("utf-8") + json.dumps({"rubrics": [{"domain": "d", "rubric": "nope.json"}]}).encode("utf-8"))
    failures = MOD.check_registry()
    assert len(failures) == 1 and "nope.json" in failures[0]


def test_default_scan_covers_every_plugin_without_symlink(MOD, tmp_path, monkeypatch, capsys):
    # .claude/skills に link されていない plugin の skill も既定の走査に入る
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    other = tmp_path / "plugins" / "other" / "skills"
    _mk_skill(other, "assign-x", "name: assign-x\nrubric_refs: [ref-nope]")
    _argv(monkeypatch)
    assert MOD.main() == 1
    assert "ref-nope" in capsys.readouterr().err


def test_default_scan_counts_symlinked_skill_once(MOD, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    p = _mk_skill(tmp_path / "plugins" / "other" / "skills", "assign-x", "name: assign-x")
    link_dir = tmp_path / ".claude" / "skills"
    link_dir.mkdir(parents=True)
    (link_dir / "assign-x").symlink_to(p.parent)
    _argv(monkeypatch)
    assert MOD.main() == 0
    assert "(1 SKILL.md checked, 0 exempted)" in capsys.readouterr().out


C03 = ("plugins", "guide-doc-generator", "skills", "assign-handout-readability-evaluator")


def test_c03_unresolved_ref_is_exempted_with_reason(MOD, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    _ref_without_rubric(tmp_path, "ref-handout-design-system")
    skills = tmp_path.joinpath(*C03).parent
    _mk_skill(skills, C03[-1], f"name: {C03[-1]}\nrubric_refs:\n  - ref-handout-design-system")
    _argv(monkeypatch)
    assert MOD.main() == 0
    cap = capsys.readouterr()
    assert "1 exempted" in cap.out and "AC-C03-17" in cap.err


@pytest.mark.parametrize("refs", ["[ref-other-missing]", "[/etc/hosts]", '["ref-handout-*"]'])
def test_c03_exemption_covers_only_that_ref(MOD, tmp_path, monkeypatch, refs):
    # 免除は (skill, ref-handout-design-system) の未解決だけ。同じ skill の他の参照や形の検査は免除しない
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    skills = tmp_path.joinpath(*C03).parent
    p = _mk_skill(skills, C03[-1], f"name: {C03[-1]}\nrubric_refs: {refs}")
    assert len(MOD.check_skill_md(p, [])) == 1


def test_exemption_does_not_apply_to_other_skills(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    p = _mk_skill(tmp_path / "plugins" / "other" / "skills", "assign-x",
                  "name: assign-x\nrubric_refs: [ref-handout-design-system]")
    exempted = []
    assert len(MOD.check_skill_md(p, exempted)) == 1 and exempted == []


def test_real_repo_default_scan_passes():
    # 実リポジトリの全 plugin を走査して PASS する (免除は C03 の1件だけ)
    r = _run([], project_root=ROOT)
    assert r.returncode == 0, r.stderr
    assert "1 exempted" in r.stdout


# ---------------------------------------------------------------------------
# 独立レビュー C1 (PASS 90) の [低] の再発防止
# ---------------------------------------------------------------------------
def test_registry_upstream_string_is_shape_error(MOD, tmp_path, monkeypatch):
    # 以前は文字列を1文字ずつ反復し「upstream=a (NOT FOUND)」を並べて rc=1 にしていた
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    (tmp_path / "r.json").write_text("{}", encoding="utf-8")
    _write_registry(tmp_path, [{"domain": "d", "rubric": "r.json", "upstream": "abc"}])
    with pytest.raises(ValueError, match="upstream"):
        MOD.check_registry()
    p = _mk_skill(tmp_path, "assign-x", "name: assign-x")
    assert _run([str(p)], project_root=tmp_path.resolve()).returncode == 2


@pytest.mark.parametrize("refs, n_failures", [
    ("[ref-real, , ref-real]", 1),   # 空の要素は block 形式と同じく FAIL
    ("[ref-real,]", 0),              # 最後の要素の後の , は YAML でも許される
    ("[ref-real, ref-real,]", 0),
])
def test_flow_list_empty_item(MOD, tmp_path, monkeypatch, refs, n_failures):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    _real_rubric(tmp_path, "ref-real")
    p = _mk_skill(tmp_path, "assign-x", f"name: assign-x\nrubric_refs: {refs}")
    failures = MOD.check_skill_md(p)
    assert len(failures) == n_failures, failures
    assert all("空の要素" in f for f in failures)


@pytest.mark.parametrize("value, n_failures", [
    ("null", 0), ("~", 0), ("NULL", 0),   # YAML の null は「参照なし」
    ("'null'", 1),                       # 引用符つきは文字列なので list でない
])
def test_null_rubric_refs_means_no_refs(MOD, tmp_path, value, n_failures):
    p = _mk_skill(tmp_path, "assign-x", f"name: assign-x\nrubric_refs: {value}")
    assert len(MOD.check_skill_md(p)) == n_failures


def test_multiline_flow_list_is_read(MOD, tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    _real_rubric(tmp_path, "ref-real")
    p = _mk_skill(tmp_path, "assign-x", "name: assign-x\nrubric_refs: [ref-real,\n  ref-real]\nversion: 1")
    assert MOD.check_skill_md(p) == []
    p2 = _mk_skill(tmp_path, "assign-y", "name: assign-y\nrubric_refs: [\n  ref-real,\n  ref-nope,\n]")
    failures = MOD.check_skill_md(p2)
    assert len(failures) == 1 and "ref-nope" in failures[0] and "NOT FOUND" in failures[0]


@pytest.mark.parametrize("make, rubric, needle", [
    (None, "a\u0000b.json", "NUL を含む"),
    ("dir", "dir.json", "ファイルでない"),
])
def test_registry_failure_reason_matches_cause(MOD, tmp_path, monkeypatch, make, rubric, needle):
    # 以前は NUL を「リポジトリの外」、ディレクトリを NOT FOUND と報告していた
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    if make == "dir":
        (tmp_path / rubric).mkdir()
    _write_registry(tmp_path, [{"domain": "d", "rubric": rubric}])
    failures = MOD.check_registry()
    assert len(failures) == 1 and needle in failures[0], failures


@pytest.mark.parametrize("ref, filename", [
    ("ref-notes.json", "ref-notes.json"),   # ref- で始まるローカルのファイル
    ('"a,b.json"', "a,b.json"),              # 引用符の中の , は区切りでない
    ('"a #b.json"', "a #b.json"),            # 引用符の中の # はコメントでない
])
def test_local_file_names_are_resolved(MOD, tmp_path, monkeypatch, ref, filename):
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    p = _mk_skill(tmp_path, "assign-x", f"name: assign-x\nrubric_refs: [{ref}]")
    (p.parent / filename).write_text("{}", encoding="utf-8")
    assert MOD.check_skill_md(p) == []


def test_help_after_target_exits_0_and_unknown_option_exits_2(MOD, tmp_path):
    p = _mk_skill(tmp_path, "assign-x", "name: assign-x")
    assert _run([str(p), "--help"], project_root=tmp_path).returncode == 0
    r = _run([str(p), "--bogus"], project_root=tmp_path)
    assert r.returncode == 2 and "未知の option" in r.stderr


@pytest.mark.parametrize("refs", ["[ref-handout-design-system]", "[]"])
def test_stale_exemption_fails(MOD, tmp_path, monkeypatch, capsys, refs):
    # 参照が解決した、または rubric_refs から外れた免除は、lint 自身が FAIL にして外させる
    monkeypatch.setattr(MOD, "PROJECT_ROOT", tmp_path.resolve())
    _real_rubric(tmp_path, "ref-handout-design-system")
    skills = tmp_path.joinpath(*C03).parent
    _mk_skill(skills, C03[-1], f"name: {C03[-1]}\nrubric_refs: {refs}")
    _argv(monkeypatch)
    assert MOD.main() == 1
    assert "使われていない" in capsys.readouterr().err
