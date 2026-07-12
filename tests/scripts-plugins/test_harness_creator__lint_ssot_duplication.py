"""lint-ssot-duplication.py の SSOT 重複検出ロジックを実入力で網羅検証する。

対象 script:
  plugins/harness-creator/skills/run-build-skill/scripts/lint-ssot-duplication.py

方針:
  - 純関数 (parse_json / body_after_frontmatter / check_schemas / substantial_lines /
    check_passages / collect) を実ファイルから importlib でロードして直接呼ぶ。
  - check_schemas / check_passages は tmp_path に「合格 fixture」と「各違反 fixture」
    (DUP-SCHEMA-ID / REDIRECT-FAT-BODY / DUP-REQUIRED-SET / DUP-PASSAGE) を書いて
    実入力で errors/warns を assert する。
  - main は subprocess(sys.executable) で OK / ERROR / WARN(--strict) / usage error の
    全経路を exit code と stdout/stderr で assert する。さらに in-process でも main を叩く。
  - network / keychain / Notion 依存は無い純ローカル lint なので stub 不要。
    全 fixture は tmp_path 配下で repo を汚染しない。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "lint-ssot-duplication.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("lint_ssot_duplication_uut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def MOD():
    return _load()


def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _write_json(parent: Path, name: str, obj) -> Path:
    p = parent / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return p


def _write_md(parent: Path, name: str, text: str) -> Path:
    p = parent / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


# 各行 20 文字以上・PASSAGE_IGNORE_RE に当たらない「実質的」行を WINDOW(6) 行ぶん。
_PASSAGE_LINES = [
    "alpha beta gamma delta epsilon zeta line number one here yes",
    "second meaningful sentence that exceeds twenty characters easily",
    "third distinct paragraph body line with enough length to count",
    "fourth row of substantive prose well past the minimum threshold",
    "fifth statement carrying real semantic weight and many tokens",
    "sixth and final window line also long enough to be substantial",
    "seventh extra line so the window of six can be formed cleanly",
]
_PASSAGE_BLOCK = "\n".join(_PASSAGE_LINES) + "\n"


# ---------------------------------------------------------------------------
# parse_json
# ---------------------------------------------------------------------------
def test_parse_json_valid(MOD, tmp_path):
    p = _write_json(tmp_path, "a.json", {"x": 1})
    assert MOD.parse_json(p) == {"x": 1}


def test_parse_json_invalid_returns_none(MOD, tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    assert MOD.parse_json(p) is None


def test_parse_json_missing_file_returns_none(MOD, tmp_path):
    assert MOD.parse_json(tmp_path / "nope.json") is None


# ---------------------------------------------------------------------------
# body_after_frontmatter
# ---------------------------------------------------------------------------
def test_body_after_frontmatter_strips_fm(MOD):
    # end+4 は "\n---" を読み飛ばすが本文直前の改行 1 つは残る実装
    text = "---\nname: foo\n---\nactual body here\n"
    assert MOD.body_after_frontmatter(text) == "\nactual body here\n"


def test_body_after_frontmatter_no_fm_returns_input(MOD):
    text = "just a body with no frontmatter fence\n"
    assert MOD.body_after_frontmatter(text) == text


def test_body_after_frontmatter_unterminated_fm_returns_input(MOD):
    # 開始 --- はあるが終端 \n--- が無い
    text = "---\nname: foo\nstill in fm\n"
    assert MOD.body_after_frontmatter(text) == text


# ---------------------------------------------------------------------------
# check_schemas — clean / DUP-SCHEMA-ID / REDIRECT-FAT-BODY / DUP-REQUIRED-SET
# ---------------------------------------------------------------------------
def test_check_schemas_clean(MOD, tmp_path):
    a = _write_json(tmp_path, "a.json", {"$id": "id-a", "required": ["w", "x", "y", "z"]})
    b = _write_json(tmp_path, "b.json", {"$id": "id-b", "required": ["p", "q", "r", "s"]})
    errors, warns = MOD.check_schemas([a, b])
    assert errors == []
    assert warns == []


def test_check_schemas_skips_non_dict_json(MOD, tmp_path):
    # JSON だが list (dict でない) はスキップされ何も検出しない
    lst = _write_json(tmp_path, "list.json", [1, 2, 3])
    bad = tmp_path / "bad.json"
    bad.write_text("{broken", encoding="utf-8")  # parse_json -> None もスキップ
    errors, warns = MOD.check_schemas([lst, bad])
    assert errors == []
    assert warns == []


def test_check_schemas_dup_schema_id_is_error(MOD, tmp_path):
    a = _write_json(tmp_path, "a.json", {"$id": "https://x/dup"})
    b = _write_json(tmp_path, "b.json", {"$id": "https://x/dup"})
    errors, warns = MOD.check_schemas([a, b])
    assert len(errors) == 1
    assert "DUP-SCHEMA-ID" in errors[0]
    assert "https://x/dup" in errors[0]
    assert str(a) in errors[0] and str(b) in errors[0]


def test_check_schemas_redirect_with_same_id_not_counted(MOD, tmp_path):
    # redirect 側は by_id に入らないので、正本 1 + redirect では DUP にならない
    canon = _write_json(tmp_path, "canon.json", {"$id": "id-shared"})
    redir = _write_json(
        tmp_path, "redir.json", {"$id": "id-shared", "x-canonical-redirect": "canon.json"}
    )
    errors, warns = MOD.check_schemas([canon, redir])
    assert errors == []
    # redirect 本文に properties が無いので REDIRECT-FAT-BODY も出ない
    assert warns == []


def test_check_schemas_redirect_fat_body_is_warn(MOD, tmp_path):
    redir = _write_json(
        tmp_path,
        "redir.json",
        {"x-canonical-redirect": "canon.json", "properties": {"a": {}, "b": {}}},
    )
    errors, warns = MOD.check_schemas([redir])
    assert errors == []
    assert len(warns) == 1
    assert "REDIRECT-FAT-BODY" in warns[0]
    assert "2 件再掲" in warns[0]


def test_check_schemas_redirect_empty_properties_no_warn(MOD, tmp_path):
    redir = _write_json(
        tmp_path, "redir.json", {"x-canonical-redirect": "c.json", "properties": {}}
    )
    errors, warns = MOD.check_schemas([redir])
    assert errors == []
    assert warns == []


def test_check_schemas_dup_required_set_is_warn(MOD, tmp_path):
    # 4 キー以上の同一 required 集合 (順序違いでも sort で一致) は DUP-REQUIRED-SET
    a = _write_json(tmp_path, "a.json", {"required": ["w", "x", "y", "z"]})
    b = _write_json(tmp_path, "b.json", {"required": ["z", "y", "x", "w"]})
    errors, warns = MOD.check_schemas([a, b])
    assert errors == []
    assert len(warns) == 1
    assert "DUP-REQUIRED-SET" in warns[0]
    assert "w,x,y,z" in warns[0]


def test_check_schemas_required_under_4_keys_ignored(MOD, tmp_path):
    # 3 キーは偶然一致が多いので対象外
    a = _write_json(tmp_path, "a.json", {"required": ["x", "y", "z"]})
    b = _write_json(tmp_path, "b.json", {"required": ["x", "y", "z"]})
    errors, warns = MOD.check_schemas([a, b])
    assert errors == []
    assert warns == []


def test_check_schemas_dup_required_skips_redirect(MOD, tmp_path):
    # redirect は DUP-REQUIRED-SET 集計から除外される
    a = _write_json(tmp_path, "a.json", {"required": ["w", "x", "y", "z"]})
    b = _write_json(
        tmp_path,
        "b.json",
        {"required": ["w", "x", "y", "z"], "x-canonical-redirect": "a.json"},
    )
    errors, warns = MOD.check_schemas([a, b])
    assert errors == []
    assert warns == []


def test_check_schemas_required_not_a_list_ignored(MOD, tmp_path):
    a = _write_json(tmp_path, "a.json", {"required": "not-a-list"})
    errors, warns = MOD.check_schemas([a])
    assert errors == []
    assert warns == []


# ---------------------------------------------------------------------------
# substantial_lines
# ---------------------------------------------------------------------------
def test_substantial_lines_filters_short_and_ignored(MOD):
    text = (
        "---\nname: x\n---\n"
        "short\n"  # 20 文字未満 -> 除外
        "this line is definitely over twenty characters long here\n"  # 採用
        "詳細は references/foo.md を参照すること正本へ寄せる長い行です\n"  # IGNORE_RE -> 除外
        "another sufficiently long substantive line of prose content\n"  # 採用
    )
    out = MOD.substantial_lines(text)
    assert out == [
        "this line is definitely over twenty characters long here",
        "another sufficiently long substantive line of prose content",
    ]


def test_substantial_lines_collapses_whitespace(MOD):
    text = "word   with     many\t\tspaces collapsed into single ones here\n"
    out = MOD.substantial_lines(text)
    assert out == ["word with many spaces collapsed into single ones here"]


# ---------------------------------------------------------------------------
# check_passages — clean / DUP-PASSAGE / templates 例外
# ---------------------------------------------------------------------------
def test_check_passages_clean_distinct(MOD, tmp_path):
    a = _write_md(tmp_path, "a.md", _PASSAGE_BLOCK)
    # b は全く別の長い行群 (重複窓ゼロ)
    b_lines = [f"unique line {i} with plenty of length to count as a row x" for i in range(7)]
    b = _write_md(tmp_path, "b.md", "\n".join(b_lines) + "\n")
    assert MOD.check_passages([a, b]) == []


def test_check_passages_detects_dup(MOD, tmp_path):
    a = _write_md(tmp_path, "a.md", _PASSAGE_BLOCK)
    b = _write_md(tmp_path, "b.md", _PASSAGE_BLOCK)
    warns = MOD.check_passages([a, b])
    assert len(warns) == 1
    assert "DUP-PASSAGE" in warns[0]
    assert str(a) in warns[0] and str(b) in warns[0]
    assert "2 ファイルに点在" in warns[0]


def test_check_passages_dedups_same_fileset(MOD, tmp_path):
    # 同一 2 ファイル間で複数の重複窓があっても fileset 単位で 1 件に集約される
    big = _PASSAGE_BLOCK + "\n".join(
        f"extra shared paragraph row number {i} long enough to be kept here" for i in range(7)
    ) + "\n"
    a = _write_md(tmp_path, "a.md", big)
    b = _write_md(tmp_path, "b.md", big)
    warns = MOD.check_passages([a, b])
    assert len(warns) == 1


def test_check_passages_templates_excluded(MOD, tmp_path):
    # templates/ 配下は伝搬例外 (意図的コピー) なので重複でも検出しない
    a = _write_md(tmp_path, "templates/a.md", _PASSAGE_BLOCK)
    b = _write_md(tmp_path, "templates/b.md", _PASSAGE_BLOCK)
    assert MOD.check_passages([a, b]) == []


def test_check_passages_single_file_no_dup(MOD, tmp_path):
    a = _write_md(tmp_path, "a.md", _PASSAGE_BLOCK)
    assert MOD.check_passages([a]) == []


def test_check_passages_skips_unreadable(MOD, tmp_path):
    # ディレクトリを .md として渡すと read_text が OSError -> continue
    d = tmp_path / "weird.md"
    d.mkdir()
    ok = _write_md(tmp_path, "ok.md", _PASSAGE_BLOCK)
    # OSError 経路を踏んでも例外を投げず通常処理を続ける
    assert MOD.check_passages([d, ok]) == []


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------
def test_collect_plain_files_and_strict(MOD, tmp_path):
    f1 = _write_json(tmp_path, "a.json", {})
    f2 = _write_md(tmp_path, "b.md", "x")
    files, strict = MOD.collect([str(f1), str(f2), "--strict"])
    assert files == [f1, f2]
    assert strict is True


def test_collect_no_strict_default(MOD, tmp_path):
    f1 = _write_json(tmp_path, "a.json", {})
    files, strict = MOD.collect([str(f1)])
    assert strict is False


def test_collect_plugin_dir_globs_md_json(MOD, tmp_path):
    _write_json(tmp_path, "sub/a.json", {})
    _write_md(tmp_path, "sub/b.md", "x")
    _write_md(tmp_path, "c.txt", "ignored")  # 対象外拡張子
    files, strict = MOD.collect(["--plugin-dir", str(tmp_path)])
    suffixes = {p.suffix for p in files}
    assert suffixes == {".json", ".md"}
    assert len(files) == 2


def test_collect_plugin_dir_missing_value(MOD):
    files, strict = MOD.collect(["--plugin-dir"])
    assert files == []


def test_collect_plugin_dir_not_a_dir(MOD, tmp_path):
    files, strict = MOD.collect(["--plugin-dir", str(tmp_path / "nope")])
    assert files == []


def test_collect_empty_argv(MOD):
    files, strict = MOD.collect([])
    assert files == []
    assert strict is False


# ---------------------------------------------------------------------------
# main (subprocess) — exit code / 出力契約
# ---------------------------------------------------------------------------
def test_main_no_args_usage_error(MOD):
    r = _run([])
    assert r.returncode == 2
    assert "usage: lint-ssot-duplication.py" in r.stderr


def test_main_plugin_dir_no_value_usage_error(MOD):
    r = _run(["--plugin-dir"])
    assert r.returncode == 2
    assert "usage:" in r.stderr


def test_main_clean_ok(MOD, tmp_path):
    _write_json(tmp_path, "a.json", {"$id": "id-a"})
    _write_md(tmp_path, "b.md", "short body that is fine\n")
    r = _run(["--plugin-dir", str(tmp_path)])
    assert r.returncode == 0
    assert "OK: SSOT 重複チェック通過" in r.stdout
    assert "schemas=1" in r.stdout
    assert "md=1" in r.stdout


def test_main_dup_schema_id_exits_1(MOD, tmp_path):
    a = _write_json(tmp_path, "a.json", {"$id": "id-dup"})
    b = _write_json(tmp_path, "b.json", {"$id": "id-dup"})
    r = _run([str(a), str(b)])
    assert r.returncode == 1
    assert "ERROR DUP-SCHEMA-ID" in r.stderr


def test_main_warn_without_strict_exits_0(MOD, tmp_path):
    # DUP-REQUIRED-SET は smell。--strict 無しなら exit 0 だが summary に件数が出る
    a = _write_json(tmp_path, "a.json", {"required": ["w", "x", "y", "z"]})
    b = _write_json(tmp_path, "b.json", {"required": ["w", "x", "y", "z"]})
    r = _run([str(a), str(b)])
    assert r.returncode == 0
    assert "WARN  DUP-REQUIRED-SET" in r.stderr
    assert "warnings=1 件は smell" in r.stdout


def test_main_warn_with_strict_exits_1(MOD, tmp_path):
    a = _write_json(tmp_path, "a.json", {"required": ["w", "x", "y", "z"]})
    b = _write_json(tmp_path, "b.json", {"required": ["w", "x", "y", "z"]})
    r = _run([str(a), str(b), "--strict"])
    assert r.returncode == 1
    assert "WARN  DUP-REQUIRED-SET" in r.stderr


def test_main_passage_dup_warn(MOD, tmp_path):
    a = _write_md(tmp_path, "a.md", _PASSAGE_BLOCK)
    b = _write_md(tmp_path, "b.md", _PASSAGE_BLOCK)
    r = _run([str(a), str(b), "--strict"])
    assert r.returncode == 1
    assert "WARN  DUP-PASSAGE" in r.stderr


def test_main_in_process_clean(MOD, tmp_path, capsys):
    # main を in-process でも叩き return code / stdout を直接検証
    p = _write_json(tmp_path, "a.json", {"$id": "x"})
    assert MOD.main([str(p)]) == 0
    out = capsys.readouterr().out
    assert "OK: SSOT 重複チェック通過" in out


def test_main_in_process_usage_error(MOD, capsys):
    assert MOD.main([]) == 2
    assert "usage:" in capsys.readouterr().err


def test_main_in_process_error_branch(MOD, tmp_path, capsys):
    # ERROR (DUP-SCHEMA-ID) で stderr に ERROR 行が書かれ exit 1
    a = _write_json(tmp_path, "a.json", {"$id": "dup"})
    b = _write_json(tmp_path, "b.json", {"$id": "dup"})
    assert MOD.main([str(a), str(b)]) == 1
    assert "ERROR DUP-SCHEMA-ID" in capsys.readouterr().err


def test_main_in_process_warn_summary_branch(MOD, tmp_path, capsys):
    # WARN だが --strict 無し -> exit 0、summary に件数、stderr に WARN 行
    a = _write_json(tmp_path, "a.json", {"required": ["w", "x", "y", "z"]})
    b = _write_json(tmp_path, "b.json", {"required": ["w", "x", "y", "z"]})
    assert MOD.main([str(a), str(b)]) == 0
    cap = capsys.readouterr()
    assert "WARN  DUP-REQUIRED-SET" in cap.err
    assert "warnings=1 件は smell" in cap.out


def test_main_in_process_strict_warn_exit_1(MOD, tmp_path, capsys):
    a = _write_json(tmp_path, "a.json", {"required": ["w", "x", "y", "z"]})
    b = _write_json(tmp_path, "b.json", {"required": ["w", "x", "y", "z"]})
    assert MOD.main([str(a), str(b), "--strict"]) == 1
    assert "WARN  DUP-REQUIRED-SET" in capsys.readouterr().err
