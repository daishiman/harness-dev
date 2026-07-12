"""Genuine functional tests for
plugins/harness-creator/skills/run-build-skill/scripts/lint-knowledge-loop.py

The script is a stateless lint over a skill directory: every check reads files
under <skill_dir>/knowledge|scripts|references and emits findings. All tests
build complete pass-fixtures and per-rule violation-fixtures under tmp_path, so
the repository is never touched. Pure functions are imported via
importlib.util.spec_from_file_location; the CLI is exercised via
subprocess(sys.executable) to cover argparse / exit-code / main() branches.

No network, no keychain, no secrets. --self-test is run against the real
script location because it deliberately validates the repo's own
schema<->constants drift and lint<->CI wiring (both present in this repo).
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO_ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "lint-knowledge-loop.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("lint_knowledge_loop_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()


# ── fixture builders ─────────────────────────────────────────────────────
def _entry(i: int) -> dict:
    return {
        "id": f"t_{i:03d}",
        "title": f"タイトル{i}",
        "intent": f"意図{i}",
        "background": f"背景{i}",
        "keywords": [f"kw{i}"],
        "source": "test.md",
    }


def _make_pass_skill(tmp_path: Path, store_only: bool = False) -> Path:
    """A skill dir that passes every KL rule for the given loop kind."""
    skill = tmp_path / "skill"
    kdir = skill / "knowledge"
    sdir = skill / "scripts"
    kdir.mkdir(parents=True)
    sdir.mkdir(parents=True)

    if not store_only:
        for name in ("search_knowledge.py", "record_usage.py", "add_entry.py"):
            (sdir / name).write_text("# stub", encoding="utf-8")

    (skill / "SKILL.md").write_text("# t\n分割閾値: 500行/25エントリ", encoding="utf-8")

    cat = {
        "category": "test",
        "label": "テスト",
        "version": "1.0.0",
        "items": [_entry(i) for i in range(1, 4)],
    }
    (kdir / "knowledge-test.json").write_text(json.dumps(cat), encoding="utf-8")

    index = {
        "version": "1.0.0",
        "consult_at": ["build-time"] if store_only else ["runtime"],
        "categories": [
            {"id": "test", "label": "テスト", "file": "knowledge-test.json", "keywords": []}
        ],
        "global_keywords": {},
    }
    (kdir / "knowledge-index.json").write_text(json.dumps(index), encoding="utf-8")
    return skill


def _rule(findings, rule):
    return [f for f in findings if f["rule"] == rule]


# ── pure helper functions ────────────────────────────────────────────────
def test_find_knowledge_dir_present_and_absent(tmp_path):
    skill = tmp_path / "s"
    skill.mkdir()
    assert MOD.find_knowledge_dir(skill) is None
    (skill / "knowledge").mkdir()
    assert MOD.find_knowledge_dir(skill) == skill / "knowledge"


def test_load_json_safe_ok(tmp_path):
    p = tmp_path / "a.json"
    p.write_text('{"x": 1}', encoding="utf-8")
    data, err = MOD.load_json_safe(p)
    assert err is None and data == {"x": 1}


def test_load_json_safe_decode_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    data, err = MOD.load_json_safe(p)
    assert data is None and "JSON解析失敗" in err


def test_load_json_safe_os_error(tmp_path):
    data, err = MOD.load_json_safe(tmp_path / "missing.json")
    assert data is None and "ファイル読み込みエラー" in err


def test_collect_entries_items_and_list_and_bad(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    # items-shaped
    (kdir / "a.json").write_text(json.dumps({"items": [_entry(1), _entry(2)]}), encoding="utf-8")
    # bare list shaped
    (kdir / "b.json").write_text(json.dumps([_entry(3)]), encoding="utf-8")
    # reserved files are skipped even if malformed
    (kdir / "knowledge-index.json").write_text("{broken", encoding="utf-8")
    (kdir / "router.json").write_text("{broken", encoding="utf-8")
    (kdir / "schema.json").write_text("{broken", encoding="utf-8")
    (kdir / "registry.json").write_text("{broken", encoding="utf-8")
    # a malformed data file reports an error but does not crash
    (kdir / "c.json").write_text("{broken", encoding="utf-8")

    entries, errors = MOD.collect_entries(kdir)
    assert len(entries) == 3
    assert any("c.json" in e for e in errors)
    # reserved malformed files must NOT appear in errors
    assert not any("router.json" in e or "schema.json" in e for e in errors)


def test_extract_anyof_required_nested():
    node = {
        "allOf": [
            {"anyOf": [{"required": ["title"]}, {"required": ["content"]}]},
            {"properties": {"x": {"anyOf": [{"required": ["intent"]}, {"required": ["purpose"]}]}}},
        ]
    }
    groups = MOD._extract_anyof_required(node)
    assert {"title", "content"} in groups
    assert {"intent", "purpose"} in groups


# ── KL-001 ───────────────────────────────────────────────────────────────
def test_kl001_missing_index_and_router(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    findings = MOD.check_kl001(kdir)
    assert findings and findings[0]["severity"] == "error"
    assert "knowledge-index.json" in findings[0]["message"]


def test_kl001_too_few_entries(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "knowledge-index.json").write_text(json.dumps({"consult_at": ["runtime"]}), encoding="utf-8")
    (kdir / "data.json").write_text(json.dumps({"items": [_entry(1), _entry(2)]}), encoding="utf-8")
    findings = MOD.check_kl001(kdir)
    assert findings and "3件未満" in findings[0]["message"]


def test_kl001_router_satisfies_existence(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "router.json").write_text(json.dumps({"consult_at": ["runtime"]}), encoding="utf-8")
    (kdir / "data.json").write_text(json.dumps({"items": [_entry(i) for i in range(1, 4)]}), encoding="utf-8")
    assert MOD.check_kl001(kdir) == []


# ── KL-002 ───────────────────────────────────────────────────────────────
def test_kl002_pass(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "data.json").write_text(json.dumps({"items": [_entry(i) for i in range(1, 4)]}), encoding="utf-8")
    assert MOD.check_kl002(kdir) == []


def test_kl002_missing_each_field_class(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    bad = {
        "id": "x1",
        # missing background + source (ALWAYS), title/content, intent/purpose, keywords/tags
    }
    (kdir / "data.json").write_text(json.dumps({"items": [bad]}), encoding="utf-8")
    findings = MOD.check_kl002(kdir)
    msgs = " ".join(f["message"] for f in findings)
    assert "必須フィールドがない" in msgs
    assert "title または content がない" in msgs
    assert "intent または purpose がない" in msgs
    assert "keywords または tags がない" in msgs
    assert all(f["severity"] == "error" for f in findings)


def test_kl002_accepts_alias_fields(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    # use the alternate names: content/purpose/tags
    alias = {
        "id": "a1",
        "content": "c",
        "purpose": "p",
        "tags": ["t"],
        "background": "b",
        "source": "s",
    }
    (kdir / "data.json").write_text(json.dumps({"items": [alias]}), encoding="utf-8")
    assert MOD.check_kl002(kdir) == []


def test_kl002_reports_json_error(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "data.json").write_text("{broken", encoding="utf-8")
    findings = MOD.check_kl002(kdir)
    assert any(f["rule"] == "KL-002" and "JSON解析失敗" in f["message"] for f in findings)


def test_kl002_ignores_non_dict_items(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "data.json").write_text(json.dumps({"items": ["not-a-dict", 42]}), encoding="utf-8")
    # non-dict items are skipped, no field findings
    assert MOD.check_kl002(kdir) == []


# ── KL-003 / KL-004 / KL-006 ─────────────────────────────────────────────
def test_kl003_kl004_missing_then_present(tmp_path):
    skill = tmp_path / "s"
    (skill / "scripts").mkdir(parents=True)
    assert MOD.check_kl003(skill) and MOD.check_kl003(skill)[0]["rule"] == "KL-003"
    assert MOD.check_kl004(skill) and MOD.check_kl004(skill)[0]["rule"] == "KL-004"
    (skill / "scripts" / "search_knowledge.py").write_text("#", encoding="utf-8")
    (skill / "scripts" / "record_usage.py").write_text("#", encoding="utf-8")
    assert MOD.check_kl003(skill) == []
    assert MOD.check_kl004(skill) == []


def test_kl006_warn_then_present(tmp_path):
    skill = tmp_path / "s"
    (skill / "scripts").mkdir(parents=True)
    out = MOD.check_kl006(skill)
    assert out and out[0]["severity"] == "warn"
    (skill / "scripts" / "add_entry.py").write_text("#", encoding="utf-8")
    assert MOD.check_kl006(skill) == []


# ── KL-005 ───────────────────────────────────────────────────────────────
def test_kl005_found_in_skill_md(tmp_path):
    skill = tmp_path / "s"
    kdir = skill / "knowledge"
    kdir.mkdir(parents=True)
    (skill / "SKILL.md").write_text("split 分割 of files", encoding="utf-8")
    assert MOD.check_kl005(skill, kdir) == []


def test_kl005_found_in_index_lifecycle(tmp_path):
    skill = tmp_path / "s"
    kdir = skill / "knowledge"
    kdir.mkdir(parents=True)
    (kdir / "knowledge-index.json").write_text(
        json.dumps({"lifecycle": {"split_threshold_entries": 25}}), encoding="utf-8"
    )
    assert MOD.check_kl005(skill, kdir) == []


def test_kl005_warn_when_absent(tmp_path):
    skill = tmp_path / "s"
    kdir = skill / "knowledge"
    kdir.mkdir(parents=True)
    out = MOD.check_kl005(skill, kdir)
    assert out and out[0]["severity"] == "warn" and out[0]["rule"] == "KL-005"


def test_kl005_found_in_reference_doc(tmp_path):
    skill = tmp_path / "s"
    kdir = skill / "knowledge"
    refs = skill / "references"
    kdir.mkdir(parents=True)
    refs.mkdir(parents=True)
    (refs / "knowledge-construction.md").write_text("threshold 500 lines", encoding="utf-8")
    assert MOD.check_kl005(skill, kdir) == []


# ── KL-007 ───────────────────────────────────────────────────────────────
def _kdir_with_index(tmp_path, index: dict) -> Path:
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "knowledge-index.json").write_text(json.dumps(index), encoding="utf-8")
    return kdir


def test_kl007_loop_a_runtime_pass(tmp_path):
    kdir = _kdir_with_index(tmp_path, {"consult_at": ["runtime"]})
    assert MOD.check_kl007(kdir, store_only=False) == []


def test_kl007_loop_b_buildtime_pass(tmp_path):
    kdir = _kdir_with_index(tmp_path, {"consult_at": ["build-time"]})
    assert MOD.check_kl007(kdir, store_only=True) == []


def test_kl007_undeclared(tmp_path):
    kdir = _kdir_with_index(tmp_path, {})
    out = MOD.check_kl007(kdir, store_only=False)
    assert out and "未宣言" in out[0]["message"]


def test_kl007_empty_list(tmp_path):
    kdir = _kdir_with_index(tmp_path, {"consult_at": []})
    out = MOD.check_kl007(kdir, store_only=False)
    assert out and "未宣言" in out[0]["message"]


def test_kl007_not_a_list(tmp_path):
    kdir = _kdir_with_index(tmp_path, {"consult_at": "runtime"})
    out = MOD.check_kl007(kdir, store_only=False)
    assert out and "配列である必要" in out[0]["message"]


def test_kl007_invalid_value(tmp_path):
    kdir = _kdir_with_index(tmp_path, {"consult_at": ["sometime"]})
    out = MOD.check_kl007(kdir, store_only=False)
    assert out and "不正な値" in out[0]["message"]


def test_kl007_mismatch_loop_a_buildtime(tmp_path):
    kdir = _kdir_with_index(tmp_path, {"consult_at": ["build-time"]})
    out = MOD.check_kl007(kdir, store_only=False)
    assert out and "不一致" in out[0]["message"] and "runtime" in out[0]["message"]


def test_kl007_mismatch_loop_b_runtime(tmp_path):
    kdir = _kdir_with_index(tmp_path, {"consult_at": ["runtime"]})
    out = MOD.check_kl007(kdir, store_only=True)
    assert out and "不一致" in out[0]["message"] and "build-time" in out[0]["message"]


def test_kl007_no_decl_file_returns_empty(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    # neither index nor router → KL-001 handles it; KL-007 returns empty
    assert MOD.check_kl007(kdir, store_only=False) == []


def test_kl007_router_used_when_no_index(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "router.json").write_text(json.dumps({"consult_at": ["runtime"]}), encoding="utf-8")
    assert MOD.check_kl007(kdir, store_only=False) == []


def test_kl007_decl_json_error(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "knowledge-index.json").write_text("{broken", encoding="utf-8")
    out = MOD.check_kl007(kdir, store_only=False)
    assert out and "JSON 解析に失敗" in out[0]["message"]


# ── run_lint orchestration ───────────────────────────────────────────────
def test_run_lint_skip_when_no_knowledge(tmp_path):
    skill = tmp_path / "s"
    skill.mkdir()
    res = MOD.run_lint(skill, strict=False)
    assert res["status"] == "skip"


def test_run_lint_full_pass(tmp_path):
    skill = _make_pass_skill(tmp_path)
    res = MOD.run_lint(skill, strict=True)
    assert res["status"] == "pass", res
    assert res["error_count"] == 0 and res["warn_count"] == 0


def test_run_lint_strict_fail_vs_warn(tmp_path):
    skill = _make_pass_skill(tmp_path)
    (skill / "scripts" / "search_knowledge.py").unlink()  # introduces a KL-003 error
    assert MOD.run_lint(skill, strict=True)["status"] == "fail"
    assert MOD.run_lint(skill, strict=False)["status"] == "warn"


def test_run_lint_warn_only(tmp_path):
    skill = _make_pass_skill(tmp_path)
    (skill / "scripts" / "add_entry.py").unlink()  # only a warn-level KL-006
    res = MOD.run_lint(skill, strict=True)
    assert res["status"] == "warn" and res["error_count"] == 0 and res["warn_count"] >= 1


def test_run_lint_store_only_info_path(tmp_path):
    skill = _make_pass_skill(tmp_path, store_only=True)
    # scripts dir is empty for store-only but KL-003/004/006 must not error
    res = MOD.run_lint(skill, strict=True, store_only=True)
    assert res["status"] == "pass", res
    info = _rule(res["findings"], "KL-003/004/006")
    assert info and info[0]["severity"] == "info"
    assert _rule(res["findings"], "KL-006") == []


# ── CLI via subprocess ───────────────────────────────────────────────────
def _run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True)


def test_cli_pass_exit0(tmp_path):
    skill = _make_pass_skill(tmp_path)
    r = _run(str(skill), "--strict")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["status"] == "pass"


def test_cli_strict_fail_exit1(tmp_path):
    skill = _make_pass_skill(tmp_path)
    (skill / "scripts" / "record_usage.py").unlink()
    r = _run(str(skill), "--strict")
    assert r.returncode == 1
    assert json.loads(r.stdout)["status"] == "fail"


def test_cli_store_only_flag(tmp_path):
    skill = _make_pass_skill(tmp_path, store_only=True)
    r = _run(str(skill), "--strict", "--store-only")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["status"] == "pass"


def test_cli_missing_dir_exit1(tmp_path):
    r = _run(str(tmp_path / "does-not-exist"))
    assert r.returncode == 1
    # error is emitted as JSON on stderr (ensure_ascii default → escaped unicode)
    err = json.loads(r.stderr)
    assert "error" in err and "does-not-exist" in err["error"]


def test_cli_no_skill_dir_arg_errors():
    r = _run()  # no positional, no flag
    assert r.returncode != 0
    assert "skill_dir" in (r.stderr + r.stdout)


def test_cli_skip_exit0(tmp_path):
    skill = tmp_path / "empty"
    skill.mkdir()
    r = _run(str(skill))
    assert r.returncode == 0
    assert json.loads(r.stdout)["status"] == "skip"


def test_cli_self_test_passes():
    # --self-test validates the real repo's schema<->constants + lint<->CI wiring,
    # both of which are present in this repository.
    r = _run("--self-test")
    assert r.returncode == 0, f"self-test failed: {r.stdout}\n{r.stderr}"
    assert "PASS" in r.stdout


# ── self-test internal meta-checks (import path, real repo) ───────────────
def test_check_schema_drift_passes_real_repo(capsys):
    MOD.check_schema_drift()
    out = capsys.readouterr().out
    assert "PASS" in out or "スキップ" in out


def test_check_ci_wiring_passes_real_repo(capsys):
    MOD.check_ci_wiring()
    out = capsys.readouterr().out
    assert "PASS" in out or "スキップ" in out


def test_check_schema_drift_skips_when_schema_missing(tmp_path, monkeypatch, capsys):
    # Point the module's __file__ at a layout where ../schemas/ does not exist.
    fake = tmp_path / "skills" / "run-build-skill" / "scripts" / "lint-knowledge-loop.py"
    fake.parent.mkdir(parents=True)
    fake.write_text("#", encoding="utf-8")
    monkeypatch.setattr(MOD, "__file__", str(fake))
    MOD.check_schema_drift()
    assert "スキップ" in capsys.readouterr().out


def test_check_schema_drift_skips_on_malformed_schema(tmp_path, monkeypatch, capsys):
    base = tmp_path / "run-build-skill"
    (base / "scripts").mkdir(parents=True)
    (base / "schemas").mkdir(parents=True)
    (base / "schemas" / "knowledge-loop.schema.json").write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(MOD, "__file__", str(base / "scripts" / "lint-knowledge-loop.py"))
    MOD.check_schema_drift()
    assert "読み込み失敗" in capsys.readouterr().out


def test_check_ci_wiring_skips_when_ci_missing(tmp_path, monkeypatch, capsys):
    # A short path so parents[5] resolves to a dir lacking .github/workflows.
    deep = tmp_path / "a" / "b" / "c" / "d" / "e" / "f" / "lint-knowledge-loop.py"
    deep.parent.mkdir(parents=True)
    deep.write_text("#", encoding="utf-8")
    monkeypatch.setattr(MOD, "__file__", str(deep))
    MOD.check_ci_wiring()
    assert "スキップ" in capsys.readouterr().out
