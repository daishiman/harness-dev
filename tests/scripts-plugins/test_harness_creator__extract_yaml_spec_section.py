"""extract-yaml-spec-section.py: kind ごとの節を索引で引き、cache と食い違えば止まる。"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUN_BUILD = ROOT / "plugins/harness-creator/skills/run-build-skill"
SCRIPT = RUN_BUILD / "scripts/extract-yaml-spec-section.py"
BUILDER = ROOT / "scripts/build-yaml-spec-cache.py"
FLAGS_SCHEMA = RUN_BUILD / "schemas/build-flags.schema.json"
REFERENCES = ROOT / "plugins/harness-creator/skills/ref-yaml-spec-fetcher/references"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


MOD = _load(SCRIPT, "extract_yaml_spec_section")
BUILD = _load(BUILDER, "build_yaml_spec_cache_for_reader")


def _sample_cache() -> str:
    return "\n".join([
        "# YAML Spec Cache", "", "last_fetched: 2026-11-14T00:00:00Z",
        "fetcher: scripts/build-yaml-spec-cache.py", "",
        "## Source (skills): https://x/skills", "",
        "#### Configure", "intro", "##### Frontmatter reference", "name: x", "##### Other", "o",
        "#### Next", "n", "",
        "## Source (subagents): https://x/sub-agents", "",
        "#### Frontmatter reference", "tools: Read", "#### Control subagent capabilities", "c",
        "#### Dup", "a", "#### Dup", "b", "",
        "## Source (hooks): https://x/hooks", "",
        "FETCH_FAILED: URLError: down", "",
        "## Source (plugins-reference): https://x/plugins-reference", "",
        "#### Manifest file", "m", "",
        "## Source (changelog): https://x/CHANGELOG.md", "",
        "### Changelog", "#### 2.0.1", "- a", "",
        "[truncated: kept 10 of 99 chars at a heading boundary; newest-first changelog]", "",
    ])


@pytest.fixture
def fixture(tmp_path: Path) -> tuple[Path, Path]:
    cache = tmp_path / "yaml-spec-cache.md"
    cache.write_text(_sample_cache(), encoding="utf-8")
    index = tmp_path / "yaml-spec-index.json"
    index.write_text(BUILD.render_index(BUILD.build_index(cache.read_bytes())), encoding="utf-8")
    return cache, index


def _run(capsys, *argv: str) -> tuple[int, str, str]:
    code = MOD.main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def _evidence(out: str) -> dict:
    first = out.split("\n", 1)[0]
    assert first.startswith("yaml-spec-source: ")
    return json.loads(first[len("yaml-spec-source: "):])


def test_kind_table_covers_every_capability_kind_and_skill_subtype():
    schema = json.loads(FLAGS_SCHEMA.read_text(encoding="utf-8"))
    assert set(MOD.KIND_SECTIONS) == set(schema["properties"]["capability_kind"]["enum"])
    assert MOD.SKILL_SUBTYPES == set(schema["properties"]["kind"]["enum"])
    # 公式 docs に節の無い kind は、空の対応と理由の両方を持つ (黙って空にしない)
    assert {k for k, v in MOD.KIND_SECTIONS.items() if not v} == set(MOD.NOT_APPLICABLE)


@pytest.mark.parametrize("kind", sorted(MOD.KIND_SECTIONS) + sorted(MOD.SKILL_SUBTYPES))
def test_every_kind_resolves_against_the_committed_cache(kind, capsys):
    """公式 docs の見出しが改名されたら、ここで落ちる (空の出力で正常終了させない)。"""
    code, out, err = _run(capsys, "--kind", kind)
    assert code == 0, err
    evidence = _evidence(out)
    index = json.loads((REFERENCES / "yaml-spec-index.json").read_text(encoding="utf-8"))
    assert evidence["cache_sha256"] == hashlib.sha256((REFERENCES / "yaml-spec-cache.md").read_bytes()).hexdigest()
    assert evidence["cache_sha256"] == index["cache_sha256"]
    assert evidence["last_fetched"] == index["last_fetched"]
    normalized = "skill" if kind in MOD.SKILL_SUBTYPES else kind
    assert evidence["kind"] == normalized
    assert [tuple(s[:2]) for s in evidence["sections"]] == list(MOD.KIND_SECTIONS[normalized])
    if not MOD.KIND_SECTIONS[normalized]:
        assert evidence["not_applicable"] == MOD.NOT_APPLICABLE[normalized]


def test_evidence_line_and_read_ranges_point_at_the_heading(fixture, capsys):
    cache, index = fixture
    code, out, _ = _run(capsys, "--kind", "agent", "--cache", str(cache), "--index", str(index))
    assert code == 0
    evidence = _evidence(out)
    assert evidence["sections"] == [
        ["subagents", "Frontmatter reference", 19, 20],
        ["subagents", "Control subagent capabilities", 21, 22],
    ]
    lines = _sample_cache().split("\n")
    assert lines[19 - 1] == "#### Frontmatter reference"
    assert "offset=19 limit=2 " in out


def test_print_emits_exactly_the_indexed_lines(fixture, capsys):
    cache, index = fixture
    code, out, _ = _run(capsys, "--section", "skills:Frontmatter reference", "--print",
                        "--cache", str(cache), "--index", str(index))
    assert code == 0
    assert out.endswith("--- skills:Frontmatter reference L10-11 ---\n##### Frontmatter reference\nname: x\n")


def test_extra_section_is_appended_once_and_whole_section_works(fixture, capsys):
    cache, index = fixture
    code, out, _ = _run(capsys, "--kind", "plugin-composition", "--section", "plugins-reference",
                        "--section", "skills:Next", "--cache", str(cache), "--index", str(index))
    assert code == 0
    sections = _evidence(out)["sections"]
    assert sections[0][:2] == ["plugins-reference", None] and sections[1][:2] == ["skills", "Next"]
    assert len(sections) == 2


def test_not_applicable_kind_exits_zero_with_reason(fixture, capsys):
    cache, index = fixture
    code, out, _ = _run(capsys, "--kind", "prompt", "--cache", str(cache), "--index", str(index))
    assert code == 0
    assert _evidence(out)["sections"] == []
    assert "read: 不要" in out


def test_sha_mismatch_stops_with_exit_2(fixture, capsys):
    cache, index = fixture
    cache.write_bytes(cache.read_bytes() + b"edited by hand\n")
    code, out, err = _run(capsys, "--kind", "skill", "--cache", str(cache), "--index", str(index))
    assert code == 2 and out == ""
    assert "--reindex" in err


@pytest.mark.parametrize("broken", ["missing", "not-json", "schema"])
def test_missing_or_unreadable_index_is_exit_2(fixture, capsys, broken):
    cache, index = fixture
    if broken == "missing":
        index.unlink()
    elif broken == "not-json":
        index.write_text("{", encoding="utf-8")
    else:
        data = json.loads(index.read_text(encoding="utf-8"))
        data["schema_version"] = 99
        index.write_text(json.dumps(data), encoding="utf-8")
    code, _, _ = _run(capsys, "--kind", "skill", "--cache", str(cache), "--index", str(index))
    assert code == 2


def test_index_range_that_does_not_land_on_the_heading_is_exit_2(fixture, capsys):
    cache, index = fixture
    data = json.loads(index.read_text(encoding="utf-8"))
    row = next(r for r in data["headings"]["skills"] if r[4] == "Frontmatter reference")
    row[1] += 1  # sha は合うまま行範囲だけずらす
    index.write_text(json.dumps(data), encoding="utf-8")
    code, _, err = _run(capsys, "--kind", "skill", "--cache", str(cache), "--index", str(index))
    assert code == 2 and "合わない" in err


def test_fetch_failed_section_is_exit_2(fixture, capsys):
    cache, index = fixture
    code, _, err = _run(capsys, "--kind", "hook", "--cache", str(cache), "--index", str(index))
    assert code == 2 and "FETCH_FAILED" in err


@pytest.mark.parametrize("argv, needle", [
    (["--section", "skills:Frontmater reference"], "近い見出し: Frontmatter reference"),
    (["--section", "nope"], "索引に節が無い"),
    (["--section", "subagents:Dup"], "見出しが 2 個ある"),
    (["--kind", "nope"], "未知の kind"),
    (["--section", "skills:"], "見出しが空"),
    ([], "--kind か --section"),
])
def test_lookup_errors_are_exit_1(fixture, capsys, argv, needle):
    cache, index = fixture
    code, out, err = _run(capsys, *argv, "--cache", str(cache), "--index", str(index))
    assert code == 1 and out == ""
    assert needle in err


def test_truncated_section_warns_on_stderr(fixture, capsys):
    cache, index = fixture
    code, _, err = _run(capsys, "--section", "changelog", "--cache", str(cache), "--index", str(index))
    assert code == 0 and "切り詰められている" in err


def test_list_shows_sections_and_headings(fixture, capsys):
    cache, index = fixture
    code, out, _ = _run(capsys, "--list", "--cache", str(cache), "--index", str(index))
    assert code == 0 and "hooks\tL" in out and "fetch_failed" in out
    code, out, _ = _run(capsys, "--list", "skills", "--cache", str(cache), "--index", str(index))
    assert code == 0 and "  Frontmatter reference\tL10-11" in out


def test_cli_usage_error_is_exit_1_not_2():
    """exit 2 は cache の問題のために空けておく (argparse の既定の 2 を使わない)。"""
    proc = subprocess.run([sys.executable, str(SCRIPT), "--bogus"], capture_output=True, text=True)
    assert proc.returncode == 1


def test_default_paths_are_relative_to_the_script_not_the_cwd():
    assert MOD.DEFAULT_CACHE == REFERENCES.resolve() / "yaml-spec-cache.md"
    assert MOD.DEFAULT_INDEX == REFERENCES.resolve() / "yaml-spec-index.json"


# --- 索引は sha256 で縛られない。形と節の境界も確かめる ---
def _edit_index(index: Path, edit) -> None:
    data = json.loads(index.read_text(encoding="utf-8"))
    edit(data)
    index.write_text(json.dumps(data), encoding="utf-8")


def test_non_utf8_index_is_exit_2(fixture, capsys):
    cache, index = fixture
    index.write_bytes(b"\xff\xfe{}")
    code, out, err = _run(capsys, "--kind", "skill", "--cache", str(cache), "--index", str(index))
    assert code == 2 and out == "" and "UTF-8" in err


def test_non_utf8_cache_with_matching_sha_is_exit_2(fixture, capsys):
    cache, index = fixture
    raw = cache.read_bytes().replace(b"name: x", b"name: \xff")
    cache.write_bytes(raw)
    _edit_index(index, lambda d: d.update(cache_sha256=hashlib.sha256(raw).hexdigest()))
    code, out, err = _run(capsys, "--kind", "skill", "--cache", str(cache), "--index", str(index))
    assert code == 2 and out == "" and "UTF-8" in err


@pytest.mark.parametrize("breakage", [
    lambda d: d.update(sections={"skills": {}}),
    lambda d: d["sections"][0].update(start_line="6"),
    lambda d: d["sections"][0].pop("end_line"),
    lambda d: d["sections"][0].update(start_line=True),
    lambda d: d.update(headings=[]),
    lambda d: d["headings"]["skills"].__setitem__(0, [2, 8, 9, 10]),
    lambda d: d["headings"]["skills"].__setitem__(0, [2, "8", 9, 10, "Configure"]),
])
def test_malformed_index_is_exit_2_not_a_traceback(fixture, capsys, breakage):
    cache, index = fixture
    _edit_index(index, breakage)
    code, out, err = _run(capsys, "--kind", "skill", "--cache", str(cache), "--index", str(index))
    assert code == 2 and out == "" and "索引の形が壊れている" in err


def _section(data: dict, name: str) -> dict:
    return next(s for s in data["sections"] if s["name"] == name)


@pytest.mark.parametrize("edit, needle", [
    (lambda d: _section(d, "plugins-reference").update(start_line=10**6, end_line=10**6), "cache の外"),
    (lambda d: _section(d, "plugins-reference").update(end_line=_section(d, "plugins-reference")["end_line"] + 3), "はみ出す"),
    (lambda d: _section(d, "plugins-reference").update(end_line=_section(d, "plugins-reference")["end_line"] - 1), "境界"),
])
def test_whole_section_range_must_match_the_section_boundary(fixture, capsys, edit, needle):
    cache, index = fixture
    _edit_index(index, edit)
    code, out, err = _run(capsys, "--section", "plugins-reference", "--cache", str(cache), "--index", str(index))
    assert code == 2 and out == "" and needle in err


def test_heading_range_running_past_its_section_is_exit_2(fixture, capsys):
    cache, index = fixture

    def edit(d):
        row = next(r for r in d["headings"]["skills"] if r[4] == "Frontmatter reference")
        row[2] = _section(d, "skills")["end_line"] + 2  # 隣の節 (subagents) へはみ出す

    _edit_index(index, edit)
    code, out, err = _run(capsys, "--kind", "skill", "--print", "--cache", str(cache), "--index", str(index))
    assert code == 2 and out == "" and "の外" in err


def test_trailing_newline_does_not_count_as_a_line(fixture, capsys):
    """読む側の行数は索引を作る側と同じ (末尾の改行は行を作らない)。最後の節は cache の最終行で終わる。"""
    cache, index = fixture
    cache.write_bytes(cache.read_bytes().rstrip(b"\n") + b"\n")
    index.write_text(BUILD.render_index(BUILD.build_index(cache.read_bytes())), encoding="utf-8")
    code, out, _ = _run(capsys, "--section", "changelog", "--print", "--cache", str(cache), "--index", str(index))
    assert code == 0
    assert out.rstrip("\n").endswith("[truncated: kept 10 of 99 chars at a heading boundary; newest-first changelog]")
