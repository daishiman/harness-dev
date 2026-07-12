"""render-findings-score.py の genuine な機能テスト。

対象:
  plugins/harness-creator/skills/assign-skill-design-evaluator/scripts/render-findings-score.py

方針:
- 純関数 (load_rubric / split_frontmatter / check_rule) を実ファイルから importlib で
  ロードし、実入力で全ルール ID の合格/違反/エッジ分岐を assert。
- compose_rubrics は外部 plugin (skill-governance-automation) への subprocess 依存なので
  monkeypatch.setattr で subprocess.run を stub し、コマンド構築/成功 parse/失敗→SystemExit(2)
  の各経路を genuine に検証する(実 plugin を実行しない)。
- main は (a) compose_rubrics を stub して in-process で正常系/各 exit path を直接呼び、
  (b) argparse の usage error は subprocess(sys.executable) で exit code を assert する。
すべて tmp_path に閉じ、repo を汚さない。
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
    / "plugins/harness-creator/skills/assign-skill-design-evaluator/scripts/render-findings-score.py"
)

_SPEC = importlib.util.spec_from_file_location("render_findings_score", SCRIPT)
RFS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(RFS)


# ---------- helpers ----------------------------------------------------------

def _rule(rid, severity="medium", area="frontmatter", check=""):
    return {"id": rid, "severity": severity, "area": area, "check": check}


def _rubric(rules, threshold=80, **extra):
    d = {
        "rubric_id": "skill-design",
        "rubric_version": "1.0.0",
        "threshold": threshold,
        "rules": rules,
    }
    d.update(extra)
    return d


GOOD_FM = {
    "name": "run-do-thing",
    "description": "Score things. Use when X, or Y.",
}

GOOD_BODY = (
    "\n## Purpose & Output Contract\nx\n## Gotchas\ny\n"
)


# ============================================================================
# load_rubric
# ============================================================================

def test_load_rubric_reads_json(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"rubric_id": "z", "rules": []}), encoding="utf-8")
    assert RFS.load_rubric(p) == {"rubric_id": "z", "rules": []}


def test_load_rubric_raises_on_bad_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        RFS.load_rubric(p)


# ============================================================================
# split_frontmatter
# ============================================================================

def test_split_frontmatter_no_leading_dashes_returns_empty():
    fm, body = RFS.split_frontmatter("no frontmatter here")
    assert fm == {}
    assert body == "no frontmatter here"


def test_split_frontmatter_incomplete_delimiters():
    # only one --- -> parts < 3 -> empty fm
    fm, body = RFS.split_frontmatter("---\nname: x\nno closing")
    assert fm == {}
    assert body == "---\nname: x\nno closing"


def test_split_frontmatter_parses_keys():
    text = "---\nname: run-x\ndescription: hello world\ninvalid line without colon\n---\n## Body\n"
    fm, body = RFS.split_frontmatter(text)
    assert fm["name"] == "run-x"
    assert fm["description"] == "hello world"
    assert "## Body" in body
    # 不正行は無視される
    assert "invalid line without colon" not in fm


# ============================================================================
# check_rule — FM-001 (name prefix/kebab/len)
# ============================================================================

def test_fm001_pass_valid_name():
    assert RFS.check_rule(_rule("FM-001", "high"), {"name": "run-foo-bar"}, "", Path(".")) is None


def test_fm001_fail_bad_prefix():
    f = RFS.check_rule(_rule("FM-001", "high"), {"name": "do-foo"}, "", Path("."))
    assert f["id"] == "FM-001"
    assert f["severity"] == "high"
    assert "prefix/kebab" in f["message"]


def test_fm001_fail_too_long():
    long_name = "run-" + ("a" * 60)
    f = RFS.check_rule(_rule("FM-001", "high"), {"name": long_name}, "", Path("."))
    assert f is not None
    assert f["loc"] == "frontmatter.name"


def test_fm001_fail_uppercase():
    f = RFS.check_rule(_rule("FM-001", "high"), {"name": "run-Foo"}, "", Path("."))
    assert f is not None


# ============================================================================
# check_rule — FM-002 (trigger phrase presence)
# ============================================================================

def test_fm002_pass_english():
    assert RFS.check_rule(_rule("FM-002"), {"description": "Use when foo."}, "", Path(".")) is None


def test_fm002_pass_japanese():
    assert RFS.check_rule(_rule("FM-002"), {"description": "これをするとき動く"}, "", Path(".")) is None


def test_fm002_fail_no_trigger():
    f = RFS.check_rule(_rule("FM-002"), {"description": "Does a thing always"}, "", Path("."))
    assert f is not None
    assert "trigger phrase" in f["message"]


# ============================================================================
# check_rule — FM-003 (trigger count 2..3)
# ============================================================================

def test_fm003_pass_english_two_clauses():
    # "Use when A, or B." -> 2 clauses
    assert RFS.check_rule(_rule("FM-003"), {"description": "Use when A, or B."}, "", Path(".")) is None


def test_fm003_fail_english_one_clause():
    f = RFS.check_rule(_rule("FM-003"), {"description": "Use when A."}, "", Path("."))
    assert f is not None
    assert "trigger count = 1" in f["message"]


def test_fm003_fail_english_too_many():
    f = RFS.check_rule(
        _rule("FM-003"), {"description": "Use when A, B, C, or D."}, "", Path(".")
    )
    assert f is not None
    assert "expected 2..3" in f["message"]


def test_fm003_pass_japanese_two_clauses():
    # 読点で 2 clause + とき
    f = RFS.check_rule(_rule("FM-003"), {"description": "Aする、Bするとき"}, "", Path("."))
    assert f is None


def test_fm003_fail_japanese_one_clause():
    f = RFS.check_rule(_rule("FM-003"), {"description": "Aするとき"}, "", Path("."))
    assert f is not None


# ============================================================================
# check_rule — FM-004 (no action detail)
# ============================================================================

def test_fm004_pass_clean():
    assert RFS.check_rule(_rule("FM-004"), {"description": "Use when foo."}, "", Path(".")) is None


def test_fm004_fail_contains_action():
    f = RFS.check_rule(
        _rule("FM-004"), {"description": "採点する。JSONで返す。"}, "", Path(".")
    )
    assert f is not None
    assert "action detail" in f["message"]
    assert "採点する" in f["message"]


# ============================================================================
# check_rule — FM-005 (first phrase must be verb)
# ============================================================================

def test_fm005_pass_english_verb():
    assert RFS.check_rule(_rule("FM-005"), {"description": "Score the skill."}, "", Path(".")) is None


def test_fm005_pass_japanese_verb_in_head():
    assert RFS.check_rule(_rule("FM-005"), {"description": "スキルを採点する。"}, "", Path(".")) is None


def test_fm005_fail_non_verb():
    f = RFS.check_rule(_rule("FM-005"), {"description": "Thing happens here."}, "", Path("."))
    assert f is not None
    assert "not a verb" in f["message"]


def test_fm005_empty_desc_no_finding():
    # desc 空なら finding 無し
    assert RFS.check_rule(_rule("FM-005"), {"description": ""}, "", Path(".")) is None


# ============================================================================
# check_rule — BD-001 / BD-002 / BD-003
# ============================================================================

def test_bd001_pass_has_purpose():
    assert RFS.check_rule(_rule("BD-001"), {}, "## Purpose & Output Contract\n", Path(".")) is None


def test_bd001_fail_missing_purpose():
    f = RFS.check_rule(_rule("BD-001"), {}, "## Other\n", Path("."))
    assert f is not None
    assert "Purpose & Output Contract" in f["message"]


def test_bd002_fail_missing_gotchas():
    f = RFS.check_rule(_rule("BD-002"), {}, "## Purpose & Output Contract\n", Path("."))
    assert f is not None
    assert "Gotchas" in f["message"]


def test_bd003_pass_under_300():
    body = "\n".join(["line"] * 10)
    assert RFS.check_rule(_rule("BD-003"), {}, body, Path(".")) is None


def test_bd003_fail_over_300():
    body = "\n".join(["line"] * 301)
    f = RFS.check_rule(_rule("BD-003"), {}, body, Path("."))
    assert f is not None
    assert "> 300" in f["message"]


def test_bd004_always_none():
    assert RFS.check_rule(_rule("BD-004"), {}, "", Path(".")) is None


# ============================================================================
# check_rule — NM-001 / NM-002 / NM-003
# ============================================================================

def test_nm001_pass_dirname_matches(tmp_path):
    d = tmp_path / "run-x"
    d.mkdir()
    assert RFS.check_rule(_rule("NM-001"), {"name": "run-x"}, "", d) is None


def test_nm001_fail_dirname_mismatch(tmp_path):
    d = tmp_path / "run-y"
    d.mkdir()
    f = RFS.check_rule(_rule("NM-001"), {"name": "run-x"}, "", d)
    assert f is not None
    assert "!=" in f["message"]


def test_nm002_pass_has_prefix():
    assert RFS.check_rule(_rule("NM-002"), {"name": "assign-x"}, "", Path(".")) is None


def test_nm002_fail_no_prefix():
    f = RFS.check_rule(_rule("NM-002"), {"name": "foobar"}, "", Path("."))
    assert f is not None
    assert "prefix" in f["message"]


def test_nm003_pass_all_py(tmp_path):
    d = tmp_path / "run-x"
    (d / "scripts").mkdir(parents=True)
    (d / "scripts" / "a.py").write_text("x", encoding="utf-8")
    assert RFS.check_rule(_rule("NM-003"), {"name": "run-x"}, "", d) is None


def test_nm003_fail_non_py(tmp_path):
    d = tmp_path / "run-x"
    (d / "scripts").mkdir(parents=True)
    (d / "scripts" / "a.sh").write_text("x", encoding="utf-8")
    f = RFS.check_rule(_rule("NM-003"), {"name": "run-x"}, "", d)
    assert f is not None
    assert "non-py" in f["message"]


# ============================================================================
# check_rule — PD-001 (progressive disclosure)
# ============================================================================

def test_pd001_pass_short_body(tmp_path):
    body = "\n".join(["l"] * 50)
    assert RFS.check_rule(_rule("PD-001"), {}, body, tmp_path) is None


def test_pd001_fail_long_body_empty_refs(tmp_path):
    body = "\n".join(["l"] * 150)
    f = RFS.check_rule(_rule("PD-001"), {}, body, tmp_path)
    assert f is not None
    assert "references/ empty" in f["message"]


def test_pd001_pass_long_body_with_refs(tmp_path):
    body = "\n".join(["l"] * 150)
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "doc.md").write_text("x", encoding="utf-8")
    assert RFS.check_rule(_rule("PD-001"), {}, body, tmp_path) is None


# ============================================================================
# check_rule — RG-001 and unknown rule
# ============================================================================

def test_rg001_always_none():
    assert RFS.check_rule(_rule("RG-001"), {}, "", Path(".")) is None


def test_unknown_rule_returns_none():
    assert RFS.check_rule(_rule("ZZ-999"), {}, "", Path(".")) is None


def test_check_rule_severity_default_low():
    # severity 未指定 -> low が使われる
    rule = {"id": "FM-001"}
    f = RFS.check_rule(rule, {"name": "bad name"}, "", Path("."))
    assert f["severity"] == "low"


# ============================================================================
# compose_rubrics — subprocess stub
# ============================================================================

def test_compose_rubrics_success(monkeypatch, tmp_path):
    captured = {}

    class FakeResult:
        returncode = 0
        stdout = json.dumps({"rules": [], "_composition_hash": "abc"})
        stderr = ""

    def fake_run(cmd, capture_output, text):
        captured["cmd"] = cmd
        return FakeResult()

    monkeypatch.setattr(RFS.subprocess, "run", fake_run)
    refs = [tmp_path / "r1.json", tmp_path / "r2.json"]
    out = RFS.compose_rubrics(refs, "deep-merge", "most-specific-wins")
    assert out["_composition_hash"] == "abc"
    # コマンドに sys.executable / strategy / policy / refs が含まれる
    assert RFS.sys.executable in captured["cmd"]
    assert "deep-merge" in captured["cmd"]
    assert "most-specific-wins" in captured["cmd"]
    assert str(refs[0]) in captured["cmd"]
    assert str(refs[1]) in captured["cmd"]


def test_compose_rubrics_failure_raises_systemexit(monkeypatch, tmp_path, capsys):
    class FakeResult:
        returncode = 2
        stdout = ""
        stderr = "boom error"

    monkeypatch.setattr(RFS.subprocess, "run", lambda cmd, capture_output, text: FakeResult())
    with pytest.raises(SystemExit) as ei:
        RFS.compose_rubrics([tmp_path / "r.json"], "deep-merge", "error")
    assert ei.value.code == 2
    assert "boom error" in capsys.readouterr().err


def test_compose_rubrics_failure_fallback_to_stdout(monkeypatch, tmp_path, capsys):
    # stderr 空なら stdout を出す分岐
    class FakeResult:
        returncode = 1
        stdout = "stdout message"
        stderr = "   "

    monkeypatch.setattr(RFS.subprocess, "run", lambda cmd, capture_output, text: FakeResult())
    with pytest.raises(SystemExit):
        RFS.compose_rubrics([tmp_path / "r.json"], "strict", "warn-and-merge")
    assert "stdout message" in capsys.readouterr().err


# ============================================================================
# main — in-process with compose_rubrics stubbed
# ============================================================================

def _write_skill_dir(tmp_path, name="run-do-thing", body=None, desc=None):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    desc = desc or "Score things. Use when A, or B."
    body = body if body is not None else "\n## Purpose & Output Contract\nx\n## Gotchas\ny\n"
    md = d / "SKILL.md"
    md.write_text(f"---\nname: {name}\ndescription: {desc}\n---{body}", encoding="utf-8")
    return d, md


def _stub_compose(monkeypatch, rubric):
    monkeypatch.setattr(RFS, "compose_rubrics", lambda refs, strat, pol: rubric)


def _run_main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["render-findings-score.py", *argv])
    return RFS.main()


def test_main_perfect_score_passes(monkeypatch, tmp_path, capsys):
    rp = tmp_path / "rubric.json"
    rp.write_text(json.dumps(_rubric([])), encoding="utf-8")
    d, _ = _write_skill_dir(tmp_path)
    _stub_compose(monkeypatch, _rubric([], threshold=80))
    rc = _run_main(monkeypatch, ["--rubric", str(rp), "--target", str(d)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["score"] == 100
    assert out["passed"] is True
    assert out["findings"] == []
    assert out["rubric_hash"].startswith("sha256:")


def test_main_high_severity_blocks_pass(monkeypatch, tmp_path, capsys):
    rp = tmp_path / "rubric.json"
    rp.write_text(json.dumps(_rubric([])), encoding="utf-8")
    # NM-001 high -> dirname mismatch
    d = tmp_path / "wrong-dir"
    d.mkdir()
    md = d / "SKILL.md"
    md.write_text(
        "---\nname: run-do-thing\ndescription: Score things. Use when A, or B.\n---"
        "\n## Purpose & Output Contract\nx\n## Gotchas\ny\n",
        encoding="utf-8",
    )
    _stub_compose(monkeypatch, _rubric([_rule("NM-001", "high", "naming")]))
    rc = _run_main(monkeypatch, ["--rubric", str(rp), "--target", str(d)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["passed"] is False
    assert any(f["id"] == "NM-001" for f in out["required_fixes"])
    assert out["score"] == 80  # 100 - 20


def test_main_score_floors_at_zero(monkeypatch, tmp_path, capsys):
    rp = tmp_path / "rubric.json"
    rp.write_text(json.dumps(_rubric([])), encoding="utf-8")
    # dirname=wrong-dir != name=bad-name; desc/body も多数違反させる
    d = tmp_path / "wrong-dir"
    d.mkdir()
    md = d / "SKILL.md"
    md.write_text(
        "---\nname: bad-name\ndescription: thing happens always\n---\n## Other\n",
        encoding="utf-8",
    )
    # 全 high で違反: FM-001(bad prefix) FM-002(no trigger) FM-005(non-verb)
    # BD-001(no purpose) BD-002(no gotchas) NM-001(dirname) NM-002(no prefix)
    rules = [
        _rule("FM-001", "high"),
        _rule("FM-002", "high"),
        _rule("FM-005", "high"),
        _rule("BD-001", "high", "body"),
        _rule("BD-002", "high", "body"),
        _rule("NM-001", "high", "naming"),
        _rule("NM-002", "high", "naming"),
    ]
    _stub_compose(monkeypatch, _rubric(rules))
    rc = _run_main(monkeypatch, ["--rubric", str(rp), "--target", str(d)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    # 7 件 * -20 = -140 -> 0 にクランプ
    assert out["score"] == 0
    assert out["passed"] is False


def test_main_target_is_file(monkeypatch, tmp_path, capsys):
    rp = tmp_path / "rubric.json"
    rp.write_text(json.dumps(_rubric([])), encoding="utf-8")
    d, md = _write_skill_dir(tmp_path)
    _stub_compose(monkeypatch, _rubric([]))
    # target を SKILL.md 直接指定
    rc = _run_main(monkeypatch, ["--rubric", str(rp), "--target", str(md)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["target"] == str(md)


def test_main_emit_hash_flag(monkeypatch, tmp_path, capsys):
    rp = tmp_path / "rubric.json"
    rp.write_text(json.dumps(_rubric([])), encoding="utf-8")
    d, _ = _write_skill_dir(tmp_path)
    _stub_compose(monkeypatch, _rubric([]))
    rc = _run_main(monkeypatch, ["--rubric", str(rp), "--target", str(d), "--emit-hash"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["rubric_hash"]


def test_main_todo_human_rule_goes_to_pending(monkeypatch, tmp_path, capsys):
    rp = tmp_path / "rubric.json"
    rp.write_text(json.dumps(_rubric([])), encoding="utf-8")
    d, _ = _write_skill_dir(tmp_path)
    rule = _rule("FM-001", "high", check="something TODO(human) here")
    _stub_compose(monkeypatch, _rubric([rule]))
    rc = _run_main(monkeypatch, ["--rubric", str(rp), "--target", str(d)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["pending_human"][0]["id"] == "FM-001"
    assert out["findings"] == []  # TODO ルールは findings に入らない


def test_main_rubric_refs_path(monkeypatch, tmp_path, capsys):
    r1 = tmp_path / "r1.json"
    r2 = tmp_path / "r2.json"
    # refs[0] は L0 正本でなければ main() が fail-fast (return 1) する契約。
    # 合成順序 L0→L1→L2 を満たすため先頭レイヤに layer="L0" を付与する。
    r1.write_text(json.dumps(_rubric([], layer="L0")), encoding="utf-8")
    r2.write_text(json.dumps(_rubric([])), encoding="utf-8")
    d, _ = _write_skill_dir(tmp_path)
    _stub_compose(monkeypatch, _rubric([], _composition_hash="hh"))
    rc = _run_main(monkeypatch, ["--rubric-refs", str(r1), str(r2), "--target", str(d)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["composition_hash"] == "hh"
    assert len(out["rubric_refs"]) == 2


def test_main_no_rubric_arg_returns_2(monkeypatch, tmp_path, capsys):
    d, _ = _write_skill_dir(tmp_path)
    rc = _run_main(monkeypatch, ["--target", str(d)])
    assert rc == 2
    assert "either --rubric or --rubric-refs required" in capsys.readouterr().err


def test_main_rubric_not_found_returns_2(monkeypatch, tmp_path, capsys):
    d, _ = _write_skill_dir(tmp_path)
    missing = tmp_path / "nope.json"
    rc = _run_main(monkeypatch, ["--rubric", str(missing), "--target", str(d)])
    assert rc == 2
    assert "rubric not found" in capsys.readouterr().err


def test_main_skill_md_not_found_returns_2(monkeypatch, tmp_path, capsys):
    rp = tmp_path / "rubric.json"
    rp.write_text(json.dumps(_rubric([])), encoding="utf-8")
    empty_dir = tmp_path / "empty-skill"
    empty_dir.mkdir()
    _stub_compose(monkeypatch, _rubric([]))
    rc = _run_main(monkeypatch, ["--rubric", str(rp), "--target", str(empty_dir)])
    assert rc == 2
    assert "SKILL.md not found" in capsys.readouterr().err


# ============================================================================
# main — argparse usage error via subprocess
# ============================================================================

def test_main_missing_target_argparse_error():
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--rubric", "x.json"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 2
    assert "--target" in r.stderr or "required" in r.stderr
