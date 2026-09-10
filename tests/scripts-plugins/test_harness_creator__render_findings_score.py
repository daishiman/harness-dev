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


# ============================================================================
# 被覆率の申告と fail-closed
#
# 「検査していない」が「合格」へ吸い込まれる経路が塞がっているかを見る。
# ここが緩むと threshold 80 が「未実装なら満たされる」へ静かに反転する。
# ============================================================================

def test_rule_applies_wildcard_and_explicit():
    assert RFS.rule_applies({"id": "X"}, "skill") is True          # 既定は '*'
    assert RFS.rule_applies({"applies_to_kinds": ["*"]}, "hook") is True
    assert RFS.rule_applies({"applies_to_kinds": ["agent"]}, "skill") is False
    assert RFS.rule_applies({"applies_to_kinds": ["agent"]}, "agent") is True


def test_main_not_applicable_rule_excluded_from_coverage(monkeypatch, tmp_path, capsys):
    """対象種別が違う rule は減点もせず、被覆率の分母にも入らない。"""
    rp = tmp_path / "rubric.json"
    rule = {"id": "AG-002", "severity": "high", "area": "agent", "check": "",
            "applies_to_kinds": ["agent"]}
    rp.write_text(json.dumps(_rubric([rule])), encoding="utf-8")
    d, _ = _write_skill_dir(tmp_path)
    _stub_compose(monkeypatch, _rubric([rule]))
    _run_main(monkeypatch, ["--rubric", str(rp), "--target", str(d)])
    out = json.loads(capsys.readouterr().out)
    assert out["passed"] is True
    assert out["coverage"]["applicable_rules"] == 0
    assert out["coverage"]["not_applicable"] == 1
    assert out["not_applicable"][0]["id"] == "AG-002"


def test_main_unscored_high_rule_blocks_pass(monkeypatch, tmp_path, capsys):
    """適用対象なのに判定実装が無い high rule は、満点でも合格にしない。"""
    rp = tmp_path / "rubric.json"
    rule = {"id": "ZZ-999", "severity": "high", "area": "future", "check": "",
            "applies_to_kinds": ["skill"]}
    rp.write_text(json.dumps(_rubric([rule])), encoding="utf-8")
    d, _ = _write_skill_dir(tmp_path)
    _stub_compose(monkeypatch, _rubric([rule]))
    _run_main(monkeypatch, ["--rubric", str(rp), "--target", str(d)])
    out = json.loads(capsys.readouterr().out)
    assert out["score"] == 100          # 減点は発生しない (違反を捏造しない)
    assert out["passed"] is False       # が、合格とも言わない
    assert out["unscored"][0]["id"] == "ZZ-999"
    assert "ZZ-999" in out["blocking_reason"]


def test_main_unscored_low_rule_does_not_block_but_is_declared(monkeypatch, tmp_path, capsys):
    rp = tmp_path / "rubric.json"
    rule = {"id": "ZZ-001", "severity": "low", "area": "future", "check": ""}
    rp.write_text(json.dumps(_rubric([rule])), encoding="utf-8")
    d, _ = _write_skill_dir(tmp_path)
    _stub_compose(monkeypatch, _rubric([rule]))
    _run_main(monkeypatch, ["--rubric", str(rp), "--target", str(d)])
    out = json.loads(capsys.readouterr().out)
    assert out["passed"] is True
    assert out["coverage"]["unscored"] == 1
    assert "blocking_reason" not in out


def test_main_llm_judge_rule_goes_to_pending_not_scored(monkeypatch, tmp_path, capsys):
    rp = tmp_path / "rubric.json"
    rule = {"id": "BD-004", "severity": "high", "area": "body", "check": ""}
    rp.write_text(json.dumps(_rubric([rule])), encoding="utf-8")
    d, _ = _write_skill_dir(tmp_path)
    _stub_compose(monkeypatch, _rubric([rule]))
    _run_main(monkeypatch, ["--rubric", str(rp), "--target", str(d)])
    out = json.loads(capsys.readouterr().out)
    assert [p["id"] for p in out["pending_human"]] == ["BD-004"]
    assert out["coverage"]["scored"] == 0
    assert out["passed"] is True


def test_main_rubric_blocked_rule_declares_blocked_on(monkeypatch, tmp_path, capsys):
    """rule 文が実態と食い違う PG-001/REG-001 は silent pass にしない。"""
    rp = tmp_path / "rubric.json"
    rule = {"id": "PG-001", "severity": "high", "area": "prompt", "check": ""}
    rp.write_text(json.dumps(_rubric([rule])), encoding="utf-8")
    d, _ = _write_skill_dir(tmp_path)
    _stub_compose(monkeypatch, _rubric([rule]))
    _run_main(monkeypatch, ["--rubric", str(rp), "--target", str(d)])
    out = json.loads(capsys.readouterr().out)
    assert out["pending_human"][0]["blocked_on"] == "rubric-text"


def test_main_emits_plugin_and_skill_for_eval_log_routing(monkeypatch, tmp_path, capsys):
    """eval-log/<plugin>/ の振り分けキーを出す (出さないと全件 core/ に落ちる)。"""
    plugin = tmp_path / "plugins" / "demo-plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "demo-plugin"}), encoding="utf-8")
    (plugin / "skills").mkdir()
    d, _ = _write_skill_dir(plugin / "skills")
    rp = tmp_path / "rubric.json"
    rp.write_text(json.dumps(_rubric([])), encoding="utf-8")
    _stub_compose(monkeypatch, _rubric([]))
    _run_main(monkeypatch, ["--rubric", str(rp), "--target", str(d)])
    out = json.loads(capsys.readouterr().out)
    assert out["plugin"] == "demo-plugin"
    assert out["skill"] == "run-do-thing"
    assert out["target_kind"] == "skill"


# ============================================================================
# 新規実装 rule
# ============================================================================

def test_pd002_pass_with_key_rules_heading():
    body = "\n# t\n\n## Purpose & Output Contract\nx\n\n## Key Rules\n1. a\n"
    assert RFS.check_rule(_rule("PD-002"), {}, body, Path(".")) is None


def test_pd002_fail_missing_heading():
    body = "\n# t\n\n## 概要\nMUST do x\n"
    f = RFS.check_rule(_rule("PD-002"), {}, body, Path("."))
    assert f is not None and "## Purpose" in f["message"]


def test_pd002_fail_missing_prohibition():
    body = "\n# t\n\n## Purpose & Output Contract\nただの説明。\n"
    f = RFS.check_rule(_rule("PD-002"), {}, body, Path("."))
    assert f is not None and "Key Rule" in f["message"]


def test_pd002_ignores_content_past_line_30():
    body = "\n## Purpose\n" + "\n".join(f"line {i}" for i in range(40)) + "\nMUST x\n"
    f = RFS.check_rule(_rule("PD-002"), {}, body, Path("."))
    assert f is not None  # 30 行より後の禁則では救済しない


def _knowledge_skill(tmp_path, entries, *, plugin_scope=False, declare=True):
    """knowledge loop を持つ skill を組み立てる。"""
    plugin = tmp_path / "plugins" / "kb-plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "kb-plugin"}), encoding="utf-8")
    (plugin / "skills").mkdir()
    d, _ = _write_skill_dir(plugin / "skills", name="run-kb")
    kdir = (plugin if plugin_scope else d) / "knowledge"
    kdir.mkdir()
    (kdir / "router.json").write_text(json.dumps({"categories": {}}), encoding="utf-8")
    (kdir / "cat.json").write_text(json.dumps(entries), encoding="utf-8")
    return d, kdir


FULL_ENTRY = {"id": "K-1", "title": "t", "intent": "x すること",
              "background": "b", "keywords": ["a"], "source": "s.md"}


def test_kl001_skips_when_no_knowledge_loop(tmp_path):
    d, _ = _write_skill_dir(tmp_path)
    assert RFS.check_rule(_rule("KL-001", "high"), {}, "", d) is None


def test_kl001_pass_with_router_and_three_entries(tmp_path):
    d, _ = _knowledge_skill(tmp_path, [FULL_ENTRY] * 3)
    assert RFS.check_rule(_rule("KL-001", "high"), {}, "", d) is None


def test_kl001_fail_too_few_entries(tmp_path):
    d, _ = _knowledge_skill(tmp_path, [FULL_ENTRY] * 2)
    f = RFS.check_rule(_rule("KL-001", "high"), {}, "", d)
    assert f is not None and "< 3" in f["message"]


def test_kl001_declared_but_missing_dir_fails(tmp_path):
    d, _ = _write_skill_dir(tmp_path)
    f = RFS.check_rule(_rule("KL-001", "high"), {"knowledge_loop": "true"}, "", d)
    assert f is not None and "knowledge/ が無い" in f["message"]


def test_kl_others_silent_when_dir_missing(tmp_path):
    """同じ 1 つの欠落で KL-002..005 まで重ねて減点しない。"""
    d, _ = _write_skill_dir(tmp_path)
    for rid in ("KL-002", "KL-003", "KL-004", "KL-005"):
        assert RFS.check_rule(_rule(rid), {"knowledge_loop": "true"}, "", d) is None


def test_kl002_reports_scale_not_just_first_violation(tmp_path):
    bad = {"id": "K-9", "intent": "x すること", "background": "b",
           "keywords": ["a"], "source": "s.md"}   # title/content 欠落
    d, _ = _knowledge_skill(tmp_path, [FULL_ENTRY, bad, dict(bad, id="K-10")])
    f = RFS.check_rule(_rule("KL-002"), {}, "", d)
    assert f is not None
    assert "2/3 entry" in f["message"] and "title|content" in f["message"]


def test_kl003_fail_without_deterministic_search(tmp_path):
    d, _ = _knowledge_skill(tmp_path, [FULL_ENTRY] * 3)
    f = RFS.check_rule(_rule("KL-003"), {}, "", d)
    assert f is not None and "AI 意味検索のみは FAIL" in f["message"]


def test_kl003_pass_with_weighted_search_script(tmp_path):
    d, _ = _knowledge_skill(tmp_path, [FULL_ENTRY] * 3)
    (d / "scripts").mkdir()
    (d / "scripts" / "search_knowledge.py").write_text(
        "FIELD_WEIGHTS = {'title': 3}\n", encoding="utf-8")
    assert RFS.check_rule(_rule("KL-003"), {}, "", d) is None


def test_kl003_fail_when_search_script_has_no_weighting(tmp_path):
    """ファイル名を合わせただけでは通さない (全文一致のみは FAIL)。"""
    d, _ = _knowledge_skill(tmp_path, [FULL_ENTRY] * 3)
    (d / "scripts").mkdir()
    (d / "scripts" / "search_knowledge.py").write_text(
        "def search(q, items):\n    return [i for i in items if q in i]\n", encoding="utf-8")
    f = RFS.check_rule(_rule("KL-003"), {}, "", d)
    assert f is not None and "weight" in f["message"]


def test_kl004_fail_without_usage_recording(tmp_path):
    d, _ = _knowledge_skill(tmp_path, [FULL_ENTRY] * 3)
    f = RFS.check_rule(_rule("KL-004"), {}, "", d)
    assert f is not None and "feedback loop 未配線" in f["message"]


def test_kl004_fail_when_recorder_omits_fields(tmp_path):
    d, _ = _knowledge_skill(tmp_path, [FULL_ENTRY] * 3)
    (d / "scripts").mkdir()
    (d / "scripts" / "record_usage.py").write_text(
        "LOG = 'usage-log.jsonl'\nmatched_ids = []\n", encoding="utf-8")
    f = RFS.check_rule(_rule("KL-004"), {}, "", d)
    assert f is not None and "used_ids" in f["message"]


def test_kl004_pass_with_full_recorder(tmp_path):
    d, _ = _knowledge_skill(tmp_path, [FULL_ENTRY] * 3)
    (d / "scripts").mkdir()
    (d / "scripts" / "record_usage.py").write_text(
        "LOG='usage-log.jsonl'\nmatched_ids=[]\nused_ids=[]\nsatisfaction=0\n",
        encoding="utf-8")
    assert RFS.check_rule(_rule("KL-004"), {}, "", d) is None


def test_kl_plugin_scope_requires_declaration(tmp_path):
    """plugin 直下の knowledge/ を、宣言していない sibling skill へ波及させない。"""
    d, _ = _knowledge_skill(tmp_path, [FULL_ENTRY] * 3, plugin_scope=True)
    assert RFS.check_rule(_rule("KL-001", "high"), {}, "", d) is None   # 宣言なし → skip
    assert RFS.check_rule(_rule("KL-001", "high"), {"knowledge_loop": "y"}, "", d) is None


def test_kl005_fail_without_documented_thresholds(tmp_path):
    d, _ = _knowledge_skill(tmp_path, [FULL_ENTRY] * 3)
    f = RFS.check_rule(_rule("KL-005", "low"), {}, "", d)
    assert f is not None and "分割閾値" in f["message"]


def _bundle_repo(tmp_path, *, distributable=None, sidecar=None, bundled=False):
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    (root / ".claude-plugin").mkdir()
    (root / ".claude-plugin" / "bundles.json").write_text(
        json.dumps({"bundles": [{"name": "b", "plugins": ["p1"] if bundled else []}]}),
        encoding="utf-8")
    plugin = root / "plugins" / "p1"
    (plugin / ".claude-plugin").mkdir(parents=True)
    manifest = {"name": "p1"}
    if distributable is not None:
        manifest["distributable"] = distributable
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(manifest), encoding="utf-8")
    if sidecar is not None:
        (plugin / "references").mkdir()
        (plugin / "references" / "package-contract.json").write_text(
            json.dumps({"distribution": {"distributable": sidecar}}), encoding="utf-8")
    (plugin / "skills").mkdir()
    d, _ = _write_skill_dir(plugin / "skills")
    return d


def test_bnd001_fail_when_distributable_plugin_unbundled(tmp_path):
    d = _bundle_repo(tmp_path, bundled=False)
    f = RFS.check_rule(_rule("BND-001", "high"), {}, "", d)
    assert f is not None and "bundles.json" in f["message"]


def test_bnd001_pass_when_bundled(tmp_path):
    d = _bundle_repo(tmp_path, bundled=True)
    assert RFS.check_rule(_rule("BND-001", "high"), {}, "", d) is None


def test_bnd001_skips_non_distributable_manifest(tmp_path):
    d = _bundle_repo(tmp_path, distributable=False, bundled=False)
    assert RFS.check_rule(_rule("BND-001", "high"), {}, "", d) is None


def test_bnd001_sidecar_overrides_manifest(tmp_path):
    """配布可否の SSOT は sidecar package-contract.json が優先 (dev-graph の形)。"""
    d = _bundle_repo(tmp_path, distributable=None, sidecar=False, bundled=False)
    assert RFS.check_rule(_rule("BND-001", "high"), {}, "", d) is None


def _prompt_repo(tmp_path, anchor):
    plugin = tmp_path / "plugins" / "p1"
    (plugin / "agents").mkdir(parents=True)
    (plugin / "agents" / "worker.md").write_text(
        f"---\nname: worker\n---\n{anchor}\nbody\n", encoding="utf-8")
    (plugin / "skills").mkdir()
    d, _ = _write_skill_dir(plugin / "skills")
    (d / "prompts").mkdir()
    (d / "prompts" / "R1-agent-worker.md").write_text("x", encoding="utf-8")
    return d


def test_pg002_pass_with_bare_r_id_anchor(tmp_path):
    d = _prompt_repo(tmp_path, "<!-- responsibility: R1 -->")
    assert RFS.check_rule(_rule("PG-002"), {}, "", d) is None


def test_pg002_pass_with_full_stem_anchor(tmp_path):
    d = _prompt_repo(tmp_path, "<!-- responsibility: R1-agent-worker -->")
    assert RFS.check_rule(_rule("PG-002"), {}, "", d) is None


def test_pg002_fail_on_cross_wired_stem(tmp_path):
    """R 番号が合っていても別 agent の stem なら交差配線として落とす。"""
    d = _prompt_repo(tmp_path, "<!-- responsibility: R1-agent-other -->")
    f = RFS.check_rule(_rule("PG-002"), {}, "", d)
    assert f is not None and "一致しない" in f["message"]


def test_pg002_fail_when_anchor_absent(tmp_path):
    d = _prompt_repo(tmp_path, "no anchor here")
    f = RFS.check_rule(_rule("PG-002"), {}, "", d)
    assert f is not None and "アンカーが無い" in f["message"]


def test_pg002_skips_skill_without_prompts(tmp_path):
    d, _ = _write_skill_dir(tmp_path)
    assert RFS.check_rule(_rule("PG-002"), {}, "", d) is None
