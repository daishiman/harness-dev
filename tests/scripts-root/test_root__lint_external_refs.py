"""scripts/lint-external-refs.py の genuine で網羅的な機能テスト (network 不要)。

このスクリプトは SKILL.md 内の外部参照パス (.claude/ creator-kit/ scripts/ doc/
references/ eval-log/ plugins/ で始まるパス断片) を棚卸しし、allowed-prefix で
始まらないものを external として報告する lint。

純関数 scan_skill() を tmp_path の fixture SKILL.md で直接呼び refs / external_refs /
line 番号 を assert し、main(argv) を in-process で駆動して text / JSON 出力・
--fail-on-external の exit code・--allowed-prefix 上書き・空ディレクトリ等の分岐を
網羅する (in-process なので --cov=scripts に直接計上される)。

外部 I/O は一切なし。実 plugins/ は読まず tmp_path に閉じる。
"""
import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-external-refs.py"

_SPEC = importlib.util.spec_from_file_location("lint_external_refs_uut", SCRIPT)
LER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(LER)


# ---------- helpers ----------------------------------------------------------

def _skill(tmp_path: pathlib.Path, name: str, body: str) -> pathlib.Path:
    """plugins/harness-creator/skills/<name>/SKILL.md 風の最小 fixture を作る。"""
    sdir = tmp_path / "skills" / name
    sdir.mkdir(parents=True)
    md = sdir / "SKILL.md"
    md.write_text(body, encoding="utf-8")
    return md


# ---------- scan_skill (純関数) ----------------------------------------------

def test_scan_skill_no_refs(tmp_path):
    md = _skill(tmp_path, "run-a", "# title\n本文に参照パスは無い\n")
    rep = LER.scan_skill(md, LER.DEFAULT_ALLOWED_PREFIXES)
    assert rep["skill"] == "run-a"
    assert rep["path"] == str(md)
    assert rep["refs"] == []
    assert rep["external_refs"] == []


def test_scan_skill_internal_ref_not_external(tmp_path):
    # creator-kit/ は DEFAULT_ALLOWED_PREFIXES に含まれるので external=False
    md = _skill(tmp_path, "run-b", "ref: creator-kit/tools/build.py を使う\n")
    rep = LER.scan_skill(md, LER.DEFAULT_ALLOWED_PREFIXES)
    assert len(rep["refs"]) == 1
    assert rep["refs"][0]["ref"] == "creator-kit/tools/build.py"
    assert rep["refs"][0]["external"] is False
    assert rep["external_refs"] == []


def test_scan_skill_external_ref_flagged(tmp_path):
    # scripts/ は許可前置に無い -> external=True
    md = _skill(tmp_path, "run-c", "実行: scripts/lint-foo.py を叩く\n")
    rep = LER.scan_skill(md, LER.DEFAULT_ALLOWED_PREFIXES)
    assert len(rep["external_refs"]) == 1
    assert rep["external_refs"][0]["ref"] == "scripts/lint-foo.py"
    assert rep["external_refs"][0]["external"] is True


def test_scan_skill_line_number_tracking(tmp_path):
    body = "line1\nline2\nsee plugins/foo/bar.md here\nline4\n"
    md = _skill(tmp_path, "run-d", body)
    rep = LER.scan_skill(md, LER.DEFAULT_ALLOWED_PREFIXES)
    assert rep["refs"][0]["line"] == 3  # plugins/... is on the 3rd line


def test_scan_skill_strips_trailing_punctuation(tmp_path):
    # rstrip(").,`\"'") が末尾の閉じ括弧・カンマ・バッククォート等を落とす
    md = _skill(tmp_path, "run-e", "見よ (`doc/spec.md`).\n")
    rep = LER.scan_skill(md, LER.DEFAULT_ALLOWED_PREFIXES)
    assert rep["refs"][0]["ref"] == "doc/spec.md"


def test_scan_skill_japanese_path_segment(tmp_path):
    # PATH_RE は日本語 (一-龠ぁ-んァ-ンー) を含むパスにマッチする
    md = _skill(tmp_path, "run-f", "doc/契約-ひな形.md を参照\n")
    rep = LER.scan_skill(md, LER.DEFAULT_ALLOWED_PREFIXES)
    assert rep["refs"][0]["ref"].startswith("doc/")
    assert "契約" in rep["refs"][0]["ref"]


def test_scan_skill_custom_allowed_prefix_overrides(tmp_path):
    # allowed に scripts/ を含めれば external=False になる
    md = _skill(tmp_path, "run-g", "exec scripts/x.py now\n")
    rep = LER.scan_skill(md, ("scripts/",))
    assert rep["refs"][0]["external"] is False
    assert rep["external_refs"] == []


def test_scan_skill_multiple_refs_mixed(tmp_path):
    body = (
        "internal creator-kit/a.py\n"
        "external scripts/b.py\n"
        "internal .claude/c.json\n"
        "external doc/d.md\n"
    )
    md = _skill(tmp_path, "run-h", body)
    rep = LER.scan_skill(md, LER.DEFAULT_ALLOWED_PREFIXES)
    assert len(rep["refs"]) == 4
    ext = {r["ref"] for r in rep["external_refs"]}
    assert ext == {"scripts/b.py", "doc/d.md"}


# ---------- main(argv): text / JSON / fail-on-external -----------------------

def test_main_text_no_external_returns_0(tmp_path, capsys):
    _skill(tmp_path, "run-a", "creator-kit/ok.py\n")
    rc = LER.main(["prog", "--skills-dir", str(tmp_path / "skills")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "skills_scanned=1" in out
    assert "external_ref_count=0" in out
    assert "EXTERNAL" not in out


def test_main_text_with_external_lists_lines(tmp_path, capsys):
    _skill(tmp_path, "run-a", "intro\nuse scripts/bad.py here\n")
    rc = LER.main(["prog", "--skills-dir", str(tmp_path / "skills")])
    out = capsys.readouterr().out
    assert rc == 0  # report mode (no --fail-on-external) -> still 0
    assert "external_ref_count=1" in out
    assert "EXTERNAL run-a:2 scripts/bad.py" in out


def test_main_fail_on_external_returns_1(tmp_path):
    _skill(tmp_path, "run-a", "use scripts/bad.py\n")
    rc = LER.main(["prog", "--skills-dir", str(tmp_path / "skills"),
                   "--fail-on-external"])
    assert rc == 1


def test_main_fail_on_external_clean_returns_0(tmp_path):
    _skill(tmp_path, "run-a", "creator-kit/ok.py\n")
    rc = LER.main(["prog", "--skills-dir", str(tmp_path / "skills"),
                   "--fail-on-external"])
    assert rc == 0


def test_main_json_payload_shape(tmp_path, capsys):
    _skill(tmp_path, "run-a", "scripts/x.py\n")
    _skill(tmp_path, "run-b", "creator-kit/y.py\n")
    rc = LER.main(["prog", "--skills-dir", str(tmp_path / "skills"), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["skills_scanned"] == 2
    assert payload["external_ref_count"] == 1
    assert payload["skills_dir"] == str(tmp_path / "skills")
    assert payload["allowed_prefixes"] == list(LER.DEFAULT_ALLOWED_PREFIXES)
    assert len(payload["reports"]) == 2


def test_main_custom_allowed_prefix_via_cli(tmp_path, capsys):
    _skill(tmp_path, "run-a", "scripts/x.py\n")
    rc = LER.main(["prog", "--skills-dir", str(tmp_path / "skills"),
                   "--allowed-prefix", "scripts/", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["external_ref_count"] == 0
    assert payload["allowed_prefixes"] == ["scripts/"]


def test_main_empty_skills_dir_returns_0(tmp_path, capsys):
    (tmp_path / "skills").mkdir()
    rc = LER.main(["prog", "--skills-dir", str(tmp_path / "skills")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "skills_scanned=0" in out


def test_main_nonexistent_skills_dir_returns_0(tmp_path, capsys):
    # glob over a missing dir yields nothing -> 0 scanned, exit 0
    rc = LER.main(["prog", "--skills-dir", str(tmp_path / "absent")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "skills_scanned=0" in out


def test_main_multiple_skills_sorted(tmp_path, capsys):
    _skill(tmp_path, "run-zzz", "scripts/z.py\n")
    _skill(tmp_path, "run-aaa", "scripts/a.py\n")
    rc = LER.main(["prog", "--skills-dir", str(tmp_path / "skills"), "--json"])
    payload = json.loads(capsys.readouterr().out)
    # sorted(glob(...)) -> run-aaa before run-zzz
    assert [r["skill"] for r in payload["reports"]] == ["run-aaa", "run-zzz"]


# ---------- subprocess: entrypoint / argparse exit ---------------------------

def test_entrypoint_subprocess_default_dir(tmp_path):
    # 実 default (plugins/harness-creator/skills) を走らせ exit 0 を確認 (report mode)。
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert "skills_scanned" in payload


def test_entrypoint_unknown_flag_exits_2(tmp_path):
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--no-such-flag"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 2
