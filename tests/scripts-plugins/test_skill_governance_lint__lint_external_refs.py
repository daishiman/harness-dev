"""Plugin-local PKG-009 external reference allowlist tests."""

import importlib.util
import json
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-external-refs.py"
SPEC = importlib.util.spec_from_file_location("plugin_lint_external_refs_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _plugin(tmp_path: Path, *, depends_on: list[str] | None = None) -> tuple[Path, Path]:
    plugin = tmp_path / "plugins" / "demo"
    skill = plugin / "skills" / "run-demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    refs = plugin / "references"
    refs.mkdir()
    (refs / "package-contract.json").write_text(
        json.dumps({"package_mode": "bundle", "entry_points": {}, "depends_on": depends_on or []}),
        encoding="utf-8",
    )
    return plugin, skill


def test_declared_literal_plugin_dependency_is_allowed(tmp_path):
    plugin, skill = _plugin(tmp_path, depends_on=["dep-plugin"])
    skill.write_text("use plugins/dep-plugin/references/contract.md\n", encoding="utf-8")
    report = MOD.scan_skill(
        skill,
        MOD.DEFAULT_ALLOWED_PREFIXES,
        plugin_dir=plugin,
        declared_dependencies={"dep-plugin"},
    )
    assert report["external_refs"] == []
    assert report["refs"][0]["classification"] == "declared_plugin_dependency"


def test_declared_relative_plugin_dependency_is_allowed(tmp_path):
    plugin, skill = _plugin(tmp_path, depends_on=["dep-plugin"])
    skill.write_text("reference_refs: [../../../dep-plugin/references/contract.md]\n", encoding="utf-8")
    report = MOD.scan_skill(
        skill,
        MOD.DEFAULT_ALLOWED_PREFIXES,
        plugin_dir=plugin,
        declared_dependencies={"dep-plugin"},
    )
    assert report["external_refs"] == []
    assert report["refs"][0]["dependency"] == "dep-plugin"


def test_undeclared_plugin_dependency_fails_closed_even_with_plugins_prefix(tmp_path):
    plugin, skill = _plugin(tmp_path)
    skill.write_text("use plugins/ghost/references/contract.md\n", encoding="utf-8")
    report = MOD.scan_skill(
        skill,
        ("plugins/",),
        plugin_dir=plugin,
        declared_dependencies=set(),
    )
    assert len(report["external_refs"]) == 1
    assert report["external_refs"][0]["classification"] == "undeclared_plugin_dependency"


def test_same_plugin_relative_reference_is_allowed(tmp_path):
    plugin, skill = _plugin(tmp_path)
    skill.write_text("script_refs: [../../scripts/local.py]\n", encoding="utf-8")
    report = MOD.scan_skill(
        skill,
        MOD.DEFAULT_ALLOWED_PREFIXES,
        plugin_dir=plugin,
        declared_dependencies=set(),
    )
    assert report["external_refs"] == []
    assert report["refs"][0]["classification"] == "same_plugin"


def test_main_reads_contract_and_reports_declared_dependency(tmp_path, capsys):
    plugin, skill = _plugin(tmp_path, depends_on=["dep-plugin"])
    skill.write_text("plugins/dep-plugin/references/c.md\n", encoding="utf-8")
    rc = MOD.main([
        "prog", "--skills-dir", str(plugin / "skills"), "--fail-on-external", "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["declared_dependencies"] == ["dep-plugin"]
    assert payload["declared_dependency_ref_count"] == 1
    assert payload["external_ref_count"] == 0


def test_main_undeclared_dependency_returns_1(tmp_path, capsys):
    plugin, skill = _plugin(tmp_path)
    skill.write_text("plugins/ghost/references/c.md\n", encoding="utf-8")
    rc = MOD.main([
        "prog", "--skills-dir", str(plugin / "skills"), "--fail-on-external", "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["external_ref_count"] == 1


def test_main_malformed_contract_returns_1_in_gate_mode(tmp_path, capsys):
    plugin, skill = _plugin(tmp_path)
    skill.write_text("references/local.md\n", encoding="utf-8")
    (plugin / "references" / "package-contract.json").write_text("{broken", encoding="utf-8")
    rc = MOD.main([
        "prog", "--skills-dir", str(plugin / "skills"), "--fail-on-external", "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["contract_errors"]


def test_load_declared_dependencies_rejects_invalid_shape(tmp_path):
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"depends_on": "dep-plugin"}), encoding="utf-8")
    dependencies, errors = MOD.load_declared_dependencies(contract)
    assert dependencies == set()
    assert errors == ["package contract depends_on must be an array"]


# --- 参照の切り出し: もっと長い path の途中から一致したものは外す ----------------

def _scan(plugin: Path, skill: Path, text: str, **kwargs) -> dict:
    skill.write_text(text, encoding="utf-8")
    return MOD.scan_skill(skill, MOD.DEFAULT_ALLOWED_PREFIXES, plugin_dir=plugin, **kwargs)


def test_two_part_self_reference_is_same_plugin(tmp_path):
    """`plugins/<自分>` だけの参照 (部品が 2 つ) も自分の plugin として通す。"""
    plugin, skill = _plugin(tmp_path)
    report = _scan(plugin, skill, "see plugins/demo for the layout\n")
    assert report["external_refs"] == []
    assert [r["classification"] for r in report["refs"]] == ["same_plugin"]


def test_marketplace_file_under_plugins_is_not_a_plugin_name(tmp_path):
    plugin, skill = _plugin(tmp_path)
    report = _scan(plugin, skill, "edit plugins/marketplace.json\n")
    assert [r["classification"] for r in report["refs"]] == ["outside_plugin"]


def test_url_and_mid_path_segments_are_not_scanned(tmp_path):
    """URL や `.agents/plugins/` のように別の root の途中にある `plugins/` は数えない。"""
    plugin, skill = _plugin(tmp_path)
    text = (
        "https://example.com/plugins/ghost/x.md\n"
        ".agents/plugins/marketplace.json\n"
        "vendor/scripts/tool.py\n"
        "xscripts/tool.py\n"
    )
    report = _scan(plugin, skill, text)
    assert report["refs"] == []


def test_variable_and_default_roots_are_still_scanned(tmp_path):
    """変数 (`$ROOT/`・`${X}/`・`{{X}}/`)・shell の既定値 (`:-plugins/`)・`./` の後ろは root 起点として残す。"""
    plugin, skill = _plugin(tmp_path)
    text = (
        "$ROOT/plugins/ghost/a.md\n"
        "${REPO}/plugins/ghost/b.md\n"
        "{{REPO}}/plugins/ghost/c.md\n"
        "${DIR:-plugins/ghost/d.md}\n"
        "./plugins/ghost/e.md\n"
        "${DIR-plugins/ghost/f.md}\n"
    )
    report = _scan(plugin, skill, text, declared_dependencies=set())
    assert [r["line"] for r in report["external_refs"]] == [1, 2, 3, 4, 5, 6]
    assert {r["classification"] for r in report["external_refs"]} == {"undeclared_plugin_dependency"}


def test_hyphenated_and_url_segments_are_not_scanned(tmp_path):
    """`-` でつながった別の語 (`claude-skills/`・`my-plugins/`・`scripts-plugins/`) と URL の途中は root ではない。"""
    plugin, skill = _plugin(tmp_path)
    text = (
        "https://example.com/claude-skills/x.md\n"
        "my-plugins/ghost/x.md\n"
        "tests/scripts-plugins/test_x.py\n"
    )
    assert _scan(plugin, skill, text)["refs"] == []


@pytest.mark.parametrize(
    ("text", "ref"),
    [
        ("read assets/../../../../ghost/a.md\n", "assets/../../../../ghost/a.md"),
        ("read ./x/../../../../ghost/a.md\n", "./x/../../../../ghost/a.md"),
        ("read ${CLAUDE_PLUGIN_ROOT}/assets/../../ghost/a.md\n", "/assets/../../ghost/a.md"),
        ("read $WORK/sub/../../ghost/x.md\n", "$WORK/sub/../../ghost/x.md"),
        ("read /Users/dm/repo/x/../plugins/ghost/a.md\n", "/Users/dm/repo/x/../plugins/ghost/a.md"),
    ],
)
def test_parent_ref_after_a_named_segment_is_unnormalized(tmp_path, text, ref):
    """dir 名の後ろの `../` は、書いた形と指す先が食い違う。黙って飛ばさず、宣言があっても外部に数える。"""
    plugin, skill = _plugin(tmp_path, depends_on=["ghost"])
    report = _scan(plugin, skill, text, declared_dependencies={"ghost"})
    assert [(r["ref"], r["classification"]) for r in report["external_refs"]] == [(ref, "unnormalized_path")]


@pytest.mark.parametrize(
    ("text", "ref"),
    [
        ("see assets/scripts/../../../../../beta/skills/b1/SKILL.md\n",
         "assets/scripts/../../../../../beta/skills/b1/SKILL.md"),
        ("see $CLAUDE_PLUGIN_ROOT/vendor/scripts/../../../beta/x.md\n",
         "$CLAUDE_PLUGIN_ROOT/vendor/scripts/../../../beta/x.md"),
        ("read ./x/references/../../../../ghost/a.md\n", "./x/references/../../../../ghost/a.md"),
        ("read ${CLAUDE_PLUGIN_ROOT}/assets/skills/../../../ghost/a.md\n", "/assets/skills/../../../ghost/a.md"),
        ("read $WORK/sub/plugins/../../ghost/x.md\n", "$WORK/sub/plugins/../../ghost/x.md"),
        ("read x/plugins/../plugins/beta/x.md\n", "x/plugins/../plugins/beta/x.md"),
        ("read xscripts/../../beta/x.md\n", "xscripts/../../beta/x.md"),
    ],
)
def test_parent_segment_after_a_root_word_inside_a_longer_path_is_unnormalized(tmp_path, text, ref):
    """長い相対 path の途中の root の語 (`assets/scripts/`) から `..` が続く参照も、黙って飛ばさない。"""
    plugin, skill = _plugin(tmp_path, depends_on=["beta", "ghost"])
    report = _scan(plugin, skill, text, declared_dependencies={"beta", "ghost"})
    assert [(r["ref"], r["classification"]) for r in report["external_refs"]] == [(ref, "unnormalized_path")]


@pytest.mark.parametrize("prefix", ["$CLAUDE_PLUGIN_ROOT/./", "${CLAUDE_PLUGIN_ROOT}//", '"$CLAUDE_PLUGIN_ROOT"/'])
def test_noop_segments_and_a_closing_quote_keep_the_plugin_root_base(tmp_path, prefix):
    """変数と `../` の間の `./`・重ねた `/`・閉じの引用符は起点を変えない (SKILL.md の dir に倒さない)。"""
    plugin, skill = _plugin(tmp_path)
    report = _scan(plugin, skill, f"read {prefix}../beta/x.md\n", declared_dependencies=set())
    assert [(r["classification"], r.get("dependency")) for r in report["refs"]] == [
        ("undeclared_plugin_dependency", "beta")
    ]


@pytest.mark.parametrize("text", ['"$WORK"/../x.md', "{{ WORK }}/./../x.md", "<ROOT>/../x.md", "$(pwd)/../x.md"])
def test_parent_ref_after_an_unresolved_expression_has_unknown_base(tmp_path, text):
    plugin, skill = _plugin(tmp_path)
    report = _scan(plugin, skill, f"run {text}\n")
    assert [r["classification"] for r in report["external_refs"]] == ["unknown_base"]


def test_exact_parent_repo_ref_is_not_matched_through_noop_segments(tmp_path, capsys):
    """`$CLAUDE_PLUGIN_ROOT/./../` も plugin の root から読む参照。SKILL.md の dir から読む exact 宣言には当てない。"""
    _doc(tmp_path, "plugins/sibling/scripts/tool.py")
    plugin = _with_repo_refs(
        tmp_path,
        [{"ref": "../../../sibling/scripts/tool.py", "match": "exact",
          "target": "plugins/sibling/scripts/tool.py", "reason": "循環になるので depends_on に入れられない"}],
        "run $CLAUDE_PLUGIN_ROOT/./../../../sibling/scripts/tool.py\n",
    )
    rc, payload = _run(plugin, capsys)
    assert rc == 1
    assert [r["classification"] for r in payload["reports"][0]["external_refs"]] == ["outside_plugin"]
    assert payload["contract_errors"] == ["unused repo_ref (exact): ../../../sibling/scripts/tool.py"]


@pytest.mark.parametrize(
    "text",
    [
        'open("/Users/dm/repo/plugins/ghost/x.md")',
        'ROOT="/Users/dm/repo/plugins/ghost/x.md"',
        '{"path":"/Users/dm/repo/plugins/ghost/x.md"}',
        "['/Users/dm/repo/plugins/ghost/x.md']",
        '`"/Users/dm/repo/plugins/ghost/x.md"`',
        "cmd >/Users/dm/repo/plugins/ghost/x.md",
        "パスは/Users/dm/repo/plugins/ghost/x.md",
    ],
)
def test_absolute_path_after_an_opening_quote_or_prose_is_classified(tmp_path, text):
    """開きの引用符・redirect・続けて書いた文章の後ろの `/` は絶対 path の始まり。中の root から分類する。"""
    plugin, skill = _plugin(tmp_path)
    report = _scan(plugin, skill, f"{text}\n", declared_dependencies=set())
    assert [(r["ref"], r["classification"]) for r in report["refs"]] == [
        ("plugins/ghost/x.md", "undeclared_plugin_dependency")
    ]


def test_japanese_prose_glued_before_a_path_is_not_a_dir_name(tmp_path):
    plugin, skill = _plugin(tmp_path)
    text = (
        "詳細は./plugins/ghost/x.md\n"
        "置き場所は~/.claude/plugins/cache/mkt/ghost/x.md\n"
        "詳細は./x/../../../ghost/a.md\n"
    )
    report = _scan(plugin, skill, text, declared_dependencies=set())
    assert [(r["ref"], r["classification"]) for r in report["refs"]] == [
        ("plugins/ghost/x.md", "undeclared_plugin_dependency"),
        (".claude/plugins/cache/mkt/ghost/x.md", "outside_plugin"),
        ("./x/../../../ghost/a.md", "unnormalized_path"),
    ]


def test_absolute_path_is_classified_from_the_inner_root(tmp_path):
    """絶対 path の途中の `plugins/<name>/` は、その root から分類する (飛ばさない)。"""
    plugin, skill = _plugin(tmp_path)
    text = "read /Users/dm/repo/plugins/ghost/x.md\nand `/abs/plugins/demo/references/a.md`\n"
    report = _scan(plugin, skill, text, declared_dependencies=set())
    assert [(r["ref"], r["classification"]) for r in report["refs"]] == [
        ("plugins/ghost/x.md", "undeclared_plugin_dependency"),
        ("plugins/demo/references/a.md", "same_plugin"),
    ]


def test_trailing_japanese_after_an_extension_is_not_part_of_the_ref(tmp_path):
    plugin, skill = _plugin(tmp_path)
    report = _scan(plugin, skill, "references/a.mdを参照し、references/日本語.md も読む\n")
    assert [r["ref"] for r in report["refs"]] == ["references/a.md", "references/日本語.md"]


def test_installed_plugin_cache_is_external_even_under_dot_claude(tmp_path):
    """`.claude/` は allowed prefix でも、`.claude/plugins/` は他の plugin の install 先なので外部に数える。"""
    plugin, skill = _plugin(tmp_path)
    text = "~/.claude/plugins/cache/mkt/ghost/x.md\n.claude/plugins/ghost/y.md\n.claude/settings.json\n"
    report = _scan(plugin, skill, text)
    assert [(r["ref"], r["classification"], r["external"]) for r in report["refs"]] == [
        (".claude/plugins/cache/mkt/ghost/x.md", "outside_plugin", True),
        (".claude/plugins/ghost/y.md", "outside_plugin", True),
        (".claude/settings.json", "allowed_prefix", False),
    ]


# --- owned-vendored: 正本と byte が同じ写しだけを正本に任せる --------------------

def _vendored_layout(tmp_path: Path, *, same_bytes: bool) -> Path:
    plugin, _ = _plugin(tmp_path)
    contract = plugin / "references" / "package-contract.json"
    data = json.loads(contract.read_text(encoding="utf-8"))
    data["runtime_dependencies"] = [{
        "classification": "owned-vendored",
        "owner": "owner-plugin",
        "local_path": "skills/run-shared",
        "owner_route": "skills/run-shared",
    }]
    contract.write_text(json.dumps(data), encoding="utf-8")
    body = "uses doc/owner-only/design.md\n"
    for root, text in ((tmp_path / "plugins" / "owner-plugin", body),
                       (plugin, body if same_bytes else body + "drift\n")):
        target = root / "skills" / "run-shared" / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    (plugin / "skills" / "run-demo" / "SKILL.md").write_text("references/local.md\n", encoding="utf-8")
    return plugin


def test_identical_owned_vendored_copy_delegates_to_owner(tmp_path, capsys):
    plugin = _vendored_layout(tmp_path, same_bytes=True)
    rc = MOD.main(["prog", "--skills-dir", str(plugin / "skills"), "--fail-on-external", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["owned_vendored_ref_count"] == 1
    assert payload["vendored_skills"][0]["status"] == "identical"


def test_diverged_owned_vendored_copy_fails_closed(tmp_path, capsys):
    """写しが正本からずれたら、正本の検査に任せられないので外部参照として数える。"""
    plugin = _vendored_layout(tmp_path, same_bytes=False)
    rc = MOD.main(["prog", "--skills-dir", str(plugin / "skills"), "--fail-on-external", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["vendored_skills"][0]["status"] == "diverged"
    assert payload["owned_vendored_ref_count"] == 0
    assert payload["external_ref_count"] == 1


# --- repo_refs: 宣言ごとに repo の中での実在を確かめる ---------------------------

def _with_repo_refs(tmp_path: Path, repo_refs: list[dict], text: str) -> Path:
    plugin, skill = _plugin(tmp_path)
    contract = plugin / "references" / "package-contract.json"
    data = json.loads(contract.read_text(encoding="utf-8"))
    data["repo_refs"] = repo_refs
    contract.write_text(json.dumps(data), encoding="utf-8")
    skill.write_text(text, encoding="utf-8")
    return plugin


def _run(plugin: Path, capsys) -> tuple[int, dict]:
    rc = MOD.main(["prog", "--skills-dir", str(plugin / "skills"), "--fail-on-external", "--json"])
    return rc, json.loads(capsys.readouterr().out)


def _doc(tmp_path: Path, rel: str) -> None:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n", encoding="utf-8")


def test_existing_prefix_repo_ref_passes(tmp_path, capsys):
    _doc(tmp_path, "doc/design/01-intro.md")
    plugin = _with_repo_refs(
        tmp_path,
        [{"ref": "doc/design/", "match": "prefix", "reason": "設計書"}],
        "read doc/design/01-intro.md\n",
    )
    rc, payload = _run(plugin, capsys)
    assert rc == 0, payload
    assert payload["declared_repo_ref_count"] == 1
    assert payload["repo_root"] == str(tmp_path.resolve())


def test_missing_repo_ref_fails_even_when_declared(tmp_path, capsys):
    """宣言しても、repo に無い path は通さない (宣言は存在の代わりにならない)。"""
    (tmp_path / "doc" / "design").mkdir(parents=True)
    plugin = _with_repo_refs(
        tmp_path,
        [{"ref": "doc/design/", "match": "prefix", "reason": "設計書"}],
        "read doc/design/99-gone.md\n",
    )
    rc, payload = _run(plugin, capsys)
    assert rc == 1
    assert payload["reports"][0]["external_refs"][0]["classification"] == "missing_repo_ref"


def test_exact_repo_ref_checks_target_instead_of_ref(tmp_path, capsys):
    """`../` で始まる ref は起点が読み手で変わるので、target の実在で確かめる。"""
    _doc(tmp_path, "plugins/sibling/scripts/tool.py")
    plugin = _with_repo_refs(
        tmp_path,
        [{"ref": "../../../sibling/scripts/tool.py", "match": "exact",
          "target": "plugins/sibling/scripts/tool.py", "reason": "循環になるので depends_on に入れられない"}],
        "run ../../../sibling/scripts/tool.py\n",
    )
    rc, payload = _run(plugin, capsys)
    assert rc == 0, payload
    assert payload["reports"][0]["refs"][0]["target"] == "plugins/sibling/scripts/tool.py"


def test_exact_parent_repo_ref_does_not_match_a_ref_with_another_base(tmp_path, capsys):
    """`../` の exact 宣言は SKILL.md の dir から読んだ参照のもの。plugin の root から読む同じ文字列には当てない。"""
    _doc(tmp_path, "plugins/sibling/scripts/tool.py")
    plugin = _with_repo_refs(
        tmp_path,
        [{"ref": "../../../sibling/scripts/tool.py", "match": "exact",
          "target": "plugins/sibling/scripts/tool.py", "reason": "循環になるので depends_on に入れられない"}],
        "run $CLAUDE_PLUGIN_ROOT/../../../sibling/scripts/tool.py\n",
    )
    rc, payload = _run(plugin, capsys)
    assert rc == 1
    assert [r["classification"] for r in payload["reports"][0]["external_refs"]] == ["outside_plugin"]
    assert payload["contract_errors"] == ["unused repo_ref (exact): ../../../sibling/scripts/tool.py"]


def test_unused_repo_ref_is_a_contract_error(tmp_path, capsys):
    """使われていない宣言を残すと、後で別の参照を黙って通すので error にする。"""
    _doc(tmp_path, "doc/design/01-intro.md")
    plugin = _with_repo_refs(
        tmp_path,
        [{"ref": "doc/design/", "match": "prefix", "reason": "設計書"}],
        "references/local.md\n",
    )
    rc, payload = _run(plugin, capsys)
    assert rc == 1
    assert payload["contract_errors"] == ["unused repo_ref (prefix): doc/design/"]


def test_newly_added_undeclared_ref_fails_again(tmp_path, capsys):
    """宣言の外の参照を足すと fail に戻る (prefix は宣言した範囲だけを許す)。"""
    _doc(tmp_path, "doc/design/01-intro.md")
    _doc(tmp_path, "doc/other/notes.md")
    plugin = _with_repo_refs(
        tmp_path,
        [{"ref": "doc/design/", "match": "prefix", "reason": "設計書"}],
        "read doc/design/01-intro.md\nand doc/other/notes.md\n",
    )
    rc, payload = _run(plugin, capsys)
    assert rc == 1
    assert [r["ref"] for r in payload["reports"][0]["external_refs"]] == ["doc/other/notes.md"]


def test_repo_ref_is_unverifiable_outside_a_repo_layout(tmp_path, capsys):
    """install 先 (`plugins/<name>` の配置でない) では実在を確かめられないので外部参照のまま数える。"""
    plugin = tmp_path / "installed" / "demo"
    skill = plugin / "skills" / "run-demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    (plugin / "references").mkdir()
    (plugin / "references" / "package-contract.json").write_text(json.dumps({
        "package_mode": "bundle", "entry_points": {}, "depends_on": [],
        "repo_refs": [{"ref": "doc/design/", "match": "prefix", "reason": "設計書"}],
    }), encoding="utf-8")
    skill.write_text("read doc/design/01-intro.md\n", encoding="utf-8")
    rc, payload = _run(plugin, capsys)
    assert rc == 1
    assert payload["repo_root"] is None
    assert payload["reports"][0]["external_refs"][0]["classification"] == "unverifiable_repo_ref"


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({"ref": "../../../x/a.md", "match": "exact", "reason": "r"}, "needs target"),
        ({"ref": "doc/design/", "match": "prefix", "target": "doc/a.md", "reason": "r"},
         "target is only allowed with match=exact"),
        ({"ref": "doc/", "match": "prefix", "reason": "r"}, "at least 2 segments"),
        ({"ref": "doc/design", "match": "prefix", "reason": "r"}, "must end with '/'"),
        ({"ref": "doc/a.md", "match": "exact", "target": "../a.md", "reason": "r"},
         "target must be repo-relative"),
        ({"ref": "/etc/passwd", "match": "exact", "reason": "r"}, "ref must be repo-relative"),
        ({"ref": "doc/a.md", "match": "glob", "reason": "r"}, "match must be one of"),
        ({"ref": "doc/a.md", "match": "exact", "reason": " "}, "reason must be a non-empty string"),
        ({"ref": "doc/a.md", "match": "exact", "reason": "r", "allow": True}, "unknown keys"),
        ({"ref": "doc/a.md", "match": "exact", "target": None, "reason": "r"}, "omit the key instead of null"),
    ],
)
def test_parse_repo_refs_rejects_malformed_entries(entry, message):
    entries, errors = MOD.parse_repo_refs([entry])
    assert entries == []
    assert any(message in error for error in errors), errors


def test_parse_repo_refs_rejects_duplicates():
    entry = {"ref": "doc/design/", "match": "prefix", "reason": "r"}
    entries, errors = MOD.parse_repo_refs([entry, dict(entry)])
    assert len(entries) == 1
    assert errors == ["repo_refs[1]: duplicate repo_ref prefix 'doc/design/'"]


def test_exact_repo_ref_wins_over_longest_prefix():
    entries, errors = MOD.parse_repo_refs([
        {"ref": "doc/design/", "match": "prefix", "reason": "r"},
        {"ref": "doc/design/sub/", "match": "prefix", "reason": "r"},
        {"ref": "doc/design/sub/a.md", "match": "exact", "reason": "r"},
    ])
    assert errors == []
    assert MOD.find_repo_ref("doc/design/sub/a.md", entries)["match"] == "exact"
    assert MOD.find_repo_ref("doc/design/sub/b.md", entries)["ref"] == "doc/design/sub/"
    assert MOD.find_repo_ref("doc/design/x.md", entries)["ref"] == "doc/design/"
    assert MOD.find_repo_ref("scripts/x.py", entries) is None


def test_null_repo_refs_is_a_contract_error(tmp_path, capsys):
    """key があって null なのは宣言の書き損じ。黙って「宣言なし」と読まない。"""
    plugin, skill = _plugin(tmp_path)
    contract = plugin / "references" / "package-contract.json"
    data = json.loads(contract.read_text(encoding="utf-8"))
    data["repo_refs"] = None
    contract.write_text(json.dumps(data), encoding="utf-8")
    skill.write_text("references/local.md\n", encoding="utf-8")
    rc, payload = _run(plugin, capsys)
    assert rc == 1
    assert payload["contract_errors"] == ["package contract repo_refs must be an array"]


# --- どの宣言でも外さない参照: 書いた形と指す先が食い違うもの -------------------

@pytest.mark.parametrize(
    "ref",
    ["references/../../x/a.md", "skills/../../x/a.md", "doc//x.md", "scripts/./x.py", "../../references/../x.md"],
)
def test_unnormalized_path_is_external_even_under_allowed_prefix(tmp_path, ref):
    plugin, skill = _plugin(tmp_path)
    report = _scan(plugin, skill, f"read {ref}\n", repo_refs=[], declared_dependencies=set())
    assert [(r["ref"], r["classification"]) for r in report["external_refs"]] == [(ref, "unnormalized_path")]


def test_unnormalized_path_is_not_released_by_repo_refs(tmp_path, capsys):
    """repo_refs の prefix に当たっても、`..` を含む参照は宣言の範囲の外を指しうるので通さない。"""
    _doc(tmp_path, "doc/design/01-intro.md")
    plugin = _with_repo_refs(
        tmp_path,
        [{"ref": "doc/design/", "match": "prefix", "reason": "設計書"}],
        "read doc/design/01-intro.md\nand doc/design/../../plugins/ghost/x.md\n",
    )
    rc, payload = _run(plugin, capsys)
    assert rc == 1
    assert [r["classification"] for r in payload["reports"][0]["external_refs"]] == ["unnormalized_path"]


def test_parent_only_ref_is_resolved_not_unnormalized(tmp_path):
    """`../../` だけの参照は dir を指す。空の segment と取り違えずに起点から解く。"""
    plugin, skill = _plugin(tmp_path)
    report = _scan(plugin, skill, "the plugin root is ../../\n")
    assert [r["classification"] for r in report["refs"]] == ["same_plugin"]


def test_parent_ref_after_unknown_variable_has_unknown_base(tmp_path):
    plugin, skill = _plugin(tmp_path, depends_on=["x"])
    report = _scan(plugin, skill, "run $WORK/../x/tool.py\n", declared_dependencies={"x"})
    assert [r["classification"] for r in report["external_refs"]] == ["unknown_base"]


@pytest.mark.parametrize("variable", ["$CLAUDE_PLUGIN_ROOT", "${PLUGIN_ROOT}", "{{ PLUGIN_DIR }}"])
def test_parent_ref_after_plugin_root_variable_resolves_from_plugin_root(tmp_path, variable):
    """plugin の root の変数の後ろの `../other/` は兄弟の plugin を指す。"""
    plugin, skill = _plugin(tmp_path)
    undeclared = _scan(plugin, skill, f"{variable}/../other/x.md\n", declared_dependencies=set())
    assert [(r["classification"], r.get("dependency")) for r in undeclared["external_refs"]] == [
        ("undeclared_plugin_dependency", "other")
    ]
    declared = _scan(plugin, skill, f"{variable}/../other/x.md\n", declared_dependencies={"other"})
    assert [r["classification"] for r in declared["refs"]] == ["declared_plugin_dependency"]


@pytest.mark.parametrize("variable", ["${SKILL_DIR}", "$CLAUDE_SKILL_DIR"])
def test_parent_ref_after_skill_dir_variable_resolves_from_skill_md(tmp_path, variable):
    plugin, skill = _plugin(tmp_path)
    report = _scan(plugin, skill, f"{variable}/../../scripts/local.py\n")
    assert [r["classification"] for r in report["refs"]] == ["same_plugin"]


# --- skills/<name>: 自分の plugin に無い skill は持ち主を書かせる -------------------

def test_skills_ref_is_same_plugin_only_when_the_skill_dir_exists(tmp_path):
    plugin, skill = _plugin(tmp_path)
    report = _scan(plugin, skill, "see skills/run-demo/references/a.md\nand skills/run-ghost/SKILL.md\n")
    assert [(r["ref"], r["classification"], r["external"]) for r in report["refs"]] == [
        ("skills/run-demo/references/a.md", "same_plugin", False),
        ("skills/run-ghost/SKILL.md", "foreign_skill_ref", True),
    ]


def test_foreign_skill_ref_is_not_released_by_repo_refs(tmp_path, capsys):
    """持ち主を書かない skill の参照は、repo_refs に書いても通さない (plugins/<owner>/skills/... と書く)。"""
    _doc(tmp_path, "skills/run-ghost/SKILL.md")
    plugin = _with_repo_refs(
        tmp_path,
        [{"ref": "skills/run-ghost/SKILL.md", "match": "exact", "reason": "r"}],
        "see skills/run-ghost/SKILL.md\n",
    )
    rc, payload = _run(plugin, capsys)
    assert rc == 1
    assert payload["reports"][0]["external_refs"][0]["classification"] == "foreign_skill_ref"
    assert payload["contract_errors"] == ["unused repo_ref (exact): skills/run-ghost/SKILL.md"]


def test_owner_qualified_skill_ref_is_judged_by_depends_on(tmp_path):
    plugin, skill = _plugin(tmp_path, depends_on=["owner-plugin"])
    report = _scan(
        plugin, skill, "see plugins/owner-plugin/skills/run-x/SKILL.md\n", declared_dependencies={"owner-plugin"}
    )
    assert [r["classification"] for r in report["refs"]] == ["declared_plugin_dependency"]


# --- owned-vendored の宣言: 任せる先が本当に検査するか・宣言の形 -------------------

def _write_contract(plugin: Path, **fields) -> None:
    path = plugin / "references" / "package-contract.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"package_mode": "bundle", "entry_points": {}, "depends_on": [], **fields}
    path.write_text(json.dumps(data), encoding="utf-8")


def _vendored(owner: str, skill: str = "run-shared") -> dict:
    return {"classification": "owned-vendored", "owner": owner,
            "local_path": f"skills/{skill}", "owner_route": f"skills/{skill}"}


def _skill(plugin: Path, name: str, text: str) -> None:
    target = plugin / "skills" / name / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_identical_vendored_copy_delegates_foreign_skill_ref(tmp_path, capsys):
    """写しの中の `skills/<正本側の skill>` は、正本の plugin では自分の skill なので正本の検査に任せる。"""
    plugins = tmp_path / "plugins"
    body = "see skills/run-owner-only/SKILL.md\n"
    _skill(plugins / "owner-plugin", "run-shared", body)
    _skill(plugins / "owner-plugin", "run-owner-only", "x\n")
    _write_contract(plugins / "owner-plugin")
    _skill(plugins / "demo", "run-shared", body)
    _write_contract(plugins / "demo", runtime_dependencies=[_vendored("owner-plugin")])
    rc, payload = _run(plugins / "demo", capsys)
    assert rc == 0, payload
    assert [r["classification"] for r in payload["reports"][0]["refs"]] == ["owned_vendored"]


@pytest.mark.parametrize("owner_points_at", ["demo", "third-plugin"])
def test_vendored_owner_that_is_itself_a_copy_is_not_trusted(tmp_path, capsys, owner_points_at):
    """正本と書いた plugin もその skill を写しと宣言していれば (任せ合い・連鎖)、そこでは検査されないので任せない。"""
    plugins = tmp_path / "plugins"
    body = "uses doc/owner-only/design.md\n"
    for name in ("demo", "owner-plugin", "third-plugin"):
        _skill(plugins / name, "run-shared", body)
    _write_contract(plugins / "third-plugin")
    _write_contract(plugins / "owner-plugin", runtime_dependencies=[_vendored(owner_points_at)])
    _write_contract(plugins / "demo", runtime_dependencies=[_vendored("owner-plugin")])
    rc, payload = _run(plugins / "demo", capsys)
    assert rc == 1
    assert payload["vendored_skills"][0]["status"] == "owner_not_canonical"
    assert payload["owned_vendored_ref_count"] == 0
    assert payload["external_ref_count"] == 1
    assert any("also declares skills/run-shared as owned-vendored" in e for e in payload["contract_errors"])


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ("skills/run-shared", "runtime_dependencies[0] must be an object"),
        ({**_vendored("owner-plugin"), "local_path": ["skills/run-shared"]},
         "needs string owner, local_path and owner_route"),
        (_vendored("demo"), "owner must be another plugin's name"),
        (_vendored("Owner_Plugin"), "owner must be another plugin's name"),
        ({**_vendored("owner-plugin"), "local_path": "skills/run-shared/sub"}, "must be skills/<name>"),
        ({**_vendored("owner-plugin"), "owner_route": "../owner-plugin/skills/run-shared"}, "must be skills/<name>"),
    ],
)
def test_malformed_owned_vendored_entry_is_a_contract_error(tmp_path, entry, message):
    plugin = tmp_path / "plugins" / "demo"
    _skill(plugin, "run-shared", "references/local.md\n")
    vendored, errors = MOD.owned_vendored_skills({"runtime_dependencies": [entry]}, plugin)
    assert vendored == {}
    assert any(message in error for error in errors), errors


def test_duplicate_owned_vendored_local_path_is_a_contract_error(tmp_path):
    plugins = tmp_path / "plugins"
    _skill(plugins / "owner-plugin", "run-shared", "x\n")
    _skill(plugins / "demo", "run-shared", "x\n")
    vendored, errors = MOD.owned_vendored_skills(
        {"runtime_dependencies": [_vendored("owner-plugin"), _vendored("owner-plugin")]}, plugins / "demo"
    )
    assert list(vendored) == ["run-shared"]
    assert vendored["run-shared"]["status"] == "identical"
    assert errors == ["runtime_dependencies[1]: duplicate owned-vendored local_path 'skills/run-shared'"]


# --- 走査できなかったものを「外部参照 0 件」と読ませない ---------------------------

@pytest.mark.parametrize("fail_on_external", [True, False])
def test_unreadable_skill_md_fails_even_without_gate_flag(tmp_path, capsys, fail_on_external):
    plugin, skill = _plugin(tmp_path)
    skill.write_bytes(b"\xff\xfe not utf-8\n")
    args = ["prog", "--skills-dir", str(plugin / "skills"), "--json"]
    rc = MOD.main(args + (["--fail-on-external"] if fail_on_external else []))
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["skills_scanned"] == 0
    assert len(payload["scan_errors"]) == 1 and "SKILL.md" in payload["scan_errors"][0]


def _scan_errors(plugin: Path, capsys) -> tuple[int, dict]:
    rc = MOD.main(["prog", "--skills-dir", str(plugin / "skills"), "--json"])
    return rc, json.loads(capsys.readouterr().out)


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0, reason="root は権限で止まらない")
def test_unreadable_skill_dir_is_a_scan_error(tmp_path, capsys):
    """読めない skill dir を glob のように黙って飛ばさない (飛ばすと「外部参照 0 件」に見える)。"""
    plugin, _ = _plugin(tmp_path)
    _skill(plugin, "run-locked", "plugins/ghost/x.md\n")
    locked = plugin / "skills" / "run-locked"
    locked.chmod(0)
    try:
        rc, payload = _scan_errors(plugin, capsys)
    finally:
        locked.chmod(0o755)
    assert rc == 1
    assert any("run-locked" in error for error in payload["scan_errors"]), payload["scan_errors"]


@pytest.mark.parametrize("broken", ["dir", "skill_md"])
def test_broken_symlink_is_a_scan_error(tmp_path, capsys, broken):
    plugin, skill = _plugin(tmp_path)
    skill.write_text("references/local.md\n", encoding="utf-8")
    if broken == "dir":
        (plugin / "skills" / "run-gone").symlink_to(tmp_path / "nowhere")
    else:
        (plugin / "skills" / "run-gone").mkdir()
        (plugin / "skills" / "run-gone" / "SKILL.md").symlink_to(tmp_path / "nowhere.md")
    rc, payload = _scan_errors(plugin, capsys)
    assert rc == 1
    assert payload["skills_scanned"] == 1
    assert [error.endswith("broken symlink") for error in payload["scan_errors"]] == [True]


def test_skills_dir_without_any_skill_md_is_a_scan_error(tmp_path, capsys):
    plugin, skill = _plugin(tmp_path)
    skill.parent.rmdir()
    (plugin / "skills" / "_shared").mkdir()
    rc, payload = _scan_errors(plugin, capsys)
    assert rc == 1
    assert payload["skills_scanned"] == 0
    assert payload["scan_errors"] == [f"{plugin / 'skills'}: no <skill>/SKILL.md found"]


def test_dir_without_skill_md_is_skipped_next_to_a_skill(tmp_path, capsys):
    plugin, skill = _plugin(tmp_path)
    skill.write_text("references/local.md\n", encoding="utf-8")
    (plugin / "skills" / "_shared").mkdir()
    rc, payload = _scan_errors(plugin, capsys)
    assert rc == 0, payload
    assert (payload["skills_scanned"], payload["scan_errors"]) == (1, [])


def test_missing_skills_dir_exits_2_without_a_report(tmp_path, capsys):
    rc = MOD.main(["prog", "--skills-dir", str(tmp_path / "nope"), "--fail-on-external", "--json"])
    captured = capsys.readouterr()
    assert rc == 2
    assert captured.out == ""
    assert "--skills-dir is not a directory" in captured.err
