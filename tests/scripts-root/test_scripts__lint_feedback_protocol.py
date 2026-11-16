"""genuine 機能テスト: scripts/lint-feedback-protocol.py

純関数 (_target_plugins / check_plugin_awareness / check_plugin_deployment) を
tmp_path 上に組んだ実 plugin ツリーで呼び実出力を assert。
main() は (a) subprocess で実 repo 緑 / --strict / --help、(b) module 内 path を
tmp の合成 schema に monkeypatch して R1-R5 の FAIL/PASS 経路を SystemExit で検証。
network/NOTION は元々不要 (オフライン lint) なので遮断不要。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-feedback-protocol.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("lint_feedback_protocol_uut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


# ---------- _target_plugins ----------
def test_target_plugins_picks_manifest_holders_and_excludes_harness_creator(tmp_path, monkeypatch):
    pdir = tmp_path / "plugins"
    # manifest 保持 plugin
    (pdir / "alpha" / ".claude-plugin").mkdir(parents=True)
    (pdir / "alpha" / ".claude-plugin" / "plugin.json").write_text("{}")
    # harness-creator は除外対象
    (pdir / "harness-creator").mkdir(parents=True)
    (pdir / "harness-creator" / "plugin.json").write_text("{}")
    # manifest 無し plugin は無視
    (pdir / "no-manifest").mkdir(parents=True)
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    names = [p.name for p in MOD._target_plugins()]
    assert names == ["alpha"]


def test_target_plugins_empty_when_dir_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "PLUGINS_DIR", tmp_path / "absent")
    assert MOD._target_plugins() == []


# ---------- check_plugin_awareness (R6) ----------
def _make_plugin(pdir, name, manifest=True, awareness_text=""):
    d = pdir / name
    d.mkdir(parents=True, exist_ok=True)
    if manifest:
        (d / "plugin.json").write_text("{}")
    if awareness_text:
        (d / "README.md").write_text(awareness_text)
    return d


def test_awareness_warns_when_keyword_absent(tmp_path, monkeypatch):
    pdir = tmp_path / "plugins"
    _make_plugin(pdir, "beta", awareness_text="このプラグインの説明")
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    warns = MOD.check_plugin_awareness()
    assert len(warns) == 1
    assert "beta" in warns[0] and "R6" in warns[0]


def test_awareness_clean_when_keyword_present(tmp_path, monkeypatch):
    pdir = tmp_path / "plugins"
    _make_plugin(pdir, "gamma", awareness_text="発火: run-skill-feedback を使う")
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    assert MOD.check_plugin_awareness() == []


def test_awareness_reads_commands_and_agents_md(tmp_path, monkeypatch):
    pdir = tmp_path / "plugins"
    d = _make_plugin(pdir, "delta", awareness_text="無関係本文")
    (d / "commands").mkdir()
    (d / "commands" / "cmd.md").write_text("here we mention run-skill-feedback path")
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    # README に無くても commands/*.md に在れば clean。
    assert MOD.check_plugin_awareness() == []


# ---------- check_plugin_deployment (R7) ----------
def test_deployment_warns_when_skill_absent(tmp_path, monkeypatch):
    pdir = tmp_path / "plugins"
    _make_plugin(pdir, "eps")
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    warns = MOD.check_plugin_deployment()
    assert len(warns) == 1
    assert "配備なし" in warns[0]


def test_deployment_clean_when_real_dir_present(tmp_path, monkeypatch):
    pdir = tmp_path / "plugins"
    d = _make_plugin(pdir, "zeta")
    (d / "skills" / "run-skill-feedback").mkdir(parents=True)
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    assert MOD.check_plugin_deployment() == []


def test_deployment_detects_broken_symlink(tmp_path, monkeypatch):
    pdir = tmp_path / "plugins"
    d = _make_plugin(pdir, "eta")
    (d / "skills").mkdir(parents=True)
    (d / "skills" / "run-skill-feedback").symlink_to(tmp_path / "does-not-exist")
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    warns = MOD.check_plugin_deployment()
    assert len(warns) == 1
    assert "broken symlink" in warns[0]


# ---------- main() FAIL 経路 (合成 schema を monkeypatch) ----------
def _good_schema():
    return {
        "feedback_protocol": {
            "command": "/run-skill-feedback",
            "firing_conditions": [],
            "intake_fields": [],
            "status_lifecycle": [],
            "open_statuses": [],
            "promise_to_reporter": "",
            "callout_summary": "",
        },
        "page_body_sections": [{"id": "feedback", "renderer_ref": "feedback_protocol"}],
    }


def _patch_paths(monkeypatch, tmp_path, schema, skill_md_text, upsert_src, plugins=None):
    sp = tmp_path / "skill-list.schema.json"
    sp.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
    repo, md, _, _, _ = _build_validation_fixture(tmp_path, skill_md_text)
    up = tmp_path / "notion-upsert-plugin.py"
    up.write_text(upsert_src, encoding="utf-8")
    monkeypatch.setattr(MOD, "SCHEMA", sp)
    monkeypatch.setattr(MOD, "ROOT", repo)
    monkeypatch.setattr(MOD, "SKILL_MD", md)
    monkeypatch.setattr(MOD, "UPSERT", up)
    monkeypatch.setattr(MOD, "PLUGINS_DIR", plugins or (tmp_path / "noplugins"))
    monkeypatch.setattr(sys, "argv", ["lint-feedback-protocol.py"])


_GOOD_MD = (
    "feedback_protocol を skill-list.schema.json で参照。\n"
    "triggers:\n"
    "  - 分かりにくい\n"
    "  - 直してほしい\n"
    "  - バグ\n"
    "  - 改善\n"
    "  - 要望\n"
)
_GOOD_UPSERT = "def x():\n    _load_feedback_protocol()\n"


def test_main_passes_with_synthetic_good_inputs(tmp_path, monkeypatch, capsys):
    _patch_paths(monkeypatch, tmp_path, _good_schema(), _GOOD_MD, _GOOD_UPSERT)
    # plugins dir 不在 => R6/R7 warn ゼロ。全 PASS で exit せず正常 return。
    MOD.main()
    out = capsys.readouterr().out
    assert "all checks passed" in out


def test_main_fails_on_missing_feedback_protocol_R1(tmp_path, monkeypatch, capsys):
    schema = _good_schema()
    del schema["feedback_protocol"]
    _patch_paths(monkeypatch, tmp_path, schema, _GOOD_MD, _GOOD_UPSERT)
    with pytest.raises(SystemExit) as e:
        MOD.main()
    assert e.value.code == 1
    out = capsys.readouterr().out
    assert "R1" in out and "FAIL" in out


def test_main_fails_on_R2_R3_R4_R5_together(tmp_path, monkeypatch, capsys):
    schema = _good_schema()
    schema["page_body_sections"] = []  # R2 違反
    bad_md = "本文に何も参照無し triggers:\n  - 無関係\n"  # R3/R4 違反
    bad_upsert = "def x():\n    pass\n"  # R5 違反
    _patch_paths(monkeypatch, tmp_path, schema, bad_md, bad_upsert)
    with pytest.raises(SystemExit) as e:
        MOD.main()
    assert e.value.code == 1
    out = capsys.readouterr().out
    for rid in ("R2", "R3", "R4", "R5"):
        assert rid in out


def test_main_strict_fails_on_R6_R7_warnings(tmp_path, monkeypatch, capsys):
    pdir = tmp_path / "plugins"
    # awareness 無し & deployment 無しの plugin => R6+R7 warn。--strict で exit 1。
    (pdir / "needy").mkdir(parents=True)
    (pdir / "needy" / "plugin.json").write_text("{}")
    (pdir / "needy" / "README.md").write_text("関係ない本文")
    _patch_paths(monkeypatch, tmp_path, _good_schema(), _GOOD_MD, _GOOD_UPSERT, plugins=pdir)
    monkeypatch.setattr(sys, "argv", ["lint-feedback-protocol.py", "--strict"])
    with pytest.raises(SystemExit) as e:
        MOD.main()
    assert e.value.code == 1
    out = capsys.readouterr().out
    assert "R6" in out and "R7" in out
    assert "FAIL" in out  # strict ラベル


def test_main_nonstrict_warns_but_passes_on_R6_R7(tmp_path, monkeypatch, capsys):
    pdir = tmp_path / "plugins"
    (pdir / "needy").mkdir(parents=True)
    (pdir / "needy" / "plugin.json").write_text("{}")
    (pdir / "needy" / "README.md").write_text("関係ない本文")
    _patch_paths(monkeypatch, tmp_path, _good_schema(), _GOOD_MD, _GOOD_UPSERT, plugins=pdir)
    MOD.main()  # default = warn のみ、exit せず
    out = capsys.readouterr().out
    assert "WARN" in out
    assert "all checks passed" in out


# ---------- main() via subprocess (実 repo + CLI) ----------
def test_subprocess_default_on_real_repo_passes():
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 0
    assert "all checks passed" in r.stdout


def test_subprocess_help_exits_zero():
    r = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "--strict" in r.stdout


def _build_validation_fixture(tmp_path, body=""):
    repo = tmp_path / "build-repo"
    skill = repo / "plugins" / "demo" / "skills" / "run-skill-feedback"
    (skill / "scripts").mkdir(parents=True)
    (skill / "scripts" / "submit.py").write_text("#!/usr/bin/env python3\n")
    lint = repo / "scripts" / "lint-feedback-protocol.py"
    lint.parent.mkdir()
    lint.write_text("#!/usr/bin/env python3\nraise RuntimeError('must not execute')\n")
    lint.chmod(0o755)
    md = skill / "SKILL.md"
    md.write_text(
        "---\nscript_refs: [scripts/submit.py]\nfeedback_contract:\n  criteria:\n"
        "    - {id: IN1, verify_by: lint, text: lint-feedback-protocol SSOT}\n"
        "    - {id: IN2, verify_by: lint, text: lint-feedback-protocol secrets}\n---\n" + body)
    manifest = {
        "resources": [{"type": "script", "path": "scripts/submit.py"}],
        "build_validation": {"lint_feedback_protocol": {
            "role": "build-lint", "scope": "repo", "path": "scripts/lint-feedback-protocol.py",
            "argv": ["python3", "scripts/lint-feedback-protocol.py", "--strict"],
            "criteria": ["IN1", "IN2"], "attributes": {"shebang": True, "executable": True},
        }},
    }
    manifest_path = skill / "workflow-manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return repo, md, manifest_path, manifest, lint


def _r9(monkeypatch, repo, md):
    monkeypatch.setattr(MOD, "ROOT", repo)
    monkeypatch.setattr(MOD, "SKILL_MD", md)
    return MOD.check_build_validation()


def test_build_validation_accepts_explicit_development_contract_without_running_it(tmp_path, monkeypatch):
    repo, md, _, _, _ = _build_validation_fixture(tmp_path)
    assert _r9(monkeypatch, repo, md) == []


@pytest.mark.parametrize("field,value", [
    ("role", "runtime"), ("scope", "plugin"), ("path", "scripts/other.py"),
    ("argv", ["python3", "scripts/lint-feedback-protocol.py"]), ("argv", "python3 lint --strict"),
    ("criteria", ["IN1"]), ("criteria", ["IN1", "IN1"]), ("criteria", "IN1 IN2"),
    ("attributes", {"shebang": True, "executable": False}),
    ("attributes", {"shebang": "true", "executable": True}),
])
def test_build_validation_rejects_contract_drift_and_type_errors(tmp_path, monkeypatch, field, value):
    repo, md, path, data, _ = _build_validation_fixture(tmp_path)
    data["build_validation"]["lint_feedback_protocol"][field] = value
    path.write_text(json.dumps(data))
    assert _r9(monkeypatch, repo, md)


@pytest.mark.parametrize("value", [None, [], {}, {"lint_feedback_protocol": []}])
def test_build_validation_cannot_be_evaded_by_removing_runtime_lint_refs(tmp_path, monkeypatch, value):
    repo, md, path, data, _ = _build_validation_fixture(tmp_path)
    data["build_validation"] = value
    path.write_text(json.dumps(data))
    assert _r9(monkeypatch, repo, md)


@pytest.mark.parametrize("fault", ["missing", "shebang", "mode", "external"])
def test_build_validation_verifies_real_lint_file_before_distribution(tmp_path, monkeypatch, fault):
    repo, md, _, _, lint = _build_validation_fixture(tmp_path)
    if fault == "missing":
        lint.rename(lint.with_suffix(".missing"))
    elif fault == "shebang":
        lint.write_text("print('not an entrypoint')\n")
    elif fault == "mode":
        lint.chmod(0o644)
    else:
        external = tmp_path / "external.py"
        external.write_text("#!/usr/bin/env python3\n")
        external.chmod(0o755)
        lint.rename(lint.with_suffix(".original"))
        lint.symlink_to(external)
    assert _r9(monkeypatch, repo, md)


@pytest.mark.parametrize("fault", ["runtime-lint", "outside-resource", "missing-resource", "bad-criteria", "bad-ref-type"])
def test_build_validation_runtime_boundary_and_criteria_remain_enforced(tmp_path, monkeypatch, fault):
    repo, md, path, data, _ = _build_validation_fixture(tmp_path)
    if fault == "runtime-lint":
        md.write_text(md.read_text().replace("scripts/submit.py", "scripts/lint-feedback-protocol.py"))
    elif fault in {"outside-resource", "missing-resource"}:
        data["resources"][0]["path"] = "../../outside.py" if fault == "outside-resource" else "missing.py"
    elif fault == "bad-criteria":
        md.write_text(md.read_text().replace("id: IN2, verify_by: lint", "id: IN2, verify_by: script"))
    else:
        md.write_text(md.read_text().replace("script_refs: [scripts/submit.py]", "script_refs: 3"))
    path.write_text(json.dumps(data))
    assert _r9(monkeypatch, repo, md)
