"""scripts/lint-live-trial-verdict.py の機械検査を合成 fixture で固定する。

正: schema 適合 + sha 一致 + PASS + tier=live 非降格 → exit 0
負: DEGRADED / downgrade / schema 違反 / denylist 被験体 →
    存在する verdict の違反は record-only 中 (--enforce なし) でも exit 1
古い: stale-sha は既定で要再実走 WARN (exit 0)。--enforce か
      LIVE_TRIAL_ENFORCE_FRESHNESS=1 で exit 1。
不在: verify_by: live-trial 宣言 skill の verdict 欠落は D13 パイロットゲート中
      record-only WARN (exit 0)、--enforce で exit 1。
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LINT_PATH = ROOT / "scripts" / "lint-live-trial-verdict.py"


def _load():
    spec = importlib.util.spec_from_file_location("lint_live_trial_verdict", LINT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load()

SKILL_MD_DECLARING = """---
name: {name}
description: demo
kind: run
version: 0.1.0
owner: team-platform
feedback_contract:
  criteria:
    - id: OUT1
      loop_scope: outer
      text: 実走 acceptance が PASS する
      verify_by: live-trial
---
body
"""

SKILL_MD_PLAIN = """---
name: {name}
description: demo
kind: run
version: 0.1.0
owner: team-platform
---
body
"""


@pytest.fixture()
def lint(monkeypatch, tmp_path):
    # 実行環境の鮮度強制 env が既定挙動の検査へ漏れないようにする
    monkeypatch.delenv("LIVE_TRIAL_ENFORCE_FRESHNESS", raising=False)
    monkeypatch.setattr(_MOD, "PLUGINS_DIR", tmp_path / "plugins")
    monkeypatch.setattr(_MOD, "EVAL_LOG", tmp_path / "eval-log")
    return _MOD


def _make_skill(lint, skill="run-demo", template=SKILL_MD_DECLARING):
    skill_dir = lint.PLUGINS_DIR / "demo-plugin" / "skills" / skill
    (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(template.format(name=skill), encoding="utf-8")
    (skill_dir / "scripts" / "x.py").write_text("print('x')\n", encoding="utf-8")
    return skill_dir


def _valid_doc(lint, skill_dir, skill="run-demo"):
    verdict_mod, _, _ = lint.load_harness()
    return {
        "target_skill": f"demo-plugin:{skill}",
        "args": "",
        "requested_model": "",
        "actual_model": ["claude-sonnet-5"],
        "nudge_count": 0,
        "gate_response_count": 0,
        "gate_kind": "rescue",
        "goal_verdict": {"result": "PASS", "blockers": []},
        "overall": {"launch": "PASS", "completion": "PASS", "goal_fit": "PASS", "verdict": "PASS"},
        "skill_dir_tree_sha": verdict_mod.skill_dir_tree_sha(skill_dir),
        "transcript_sha256": None,
        "scenario_origin": "synthetic",
        "environment": {
            "claude_version": "2.0.0",
            "tmux": True,
            "transcript_layer": "jsonl",
            "permissions_mode": "bypassPermissions",
        },
        "tier": "live",
        "downgrade_reason": None,
        "timeline": {"boot_s": 3.0, "poll_exit": "DONE", "wall_clock_s": 60.0},
    }


def _write_verdict(lint, doc, skill="run-demo", run_id="20260702T000000"):
    vdir = lint.EVAL_LOG / "demo-plugin" / skill / "live-trial" / run_id
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "verdict.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return vdir / "verdict.json"


# --- 正 fixture -------------------------------------------------------------

def test_valid_pass_verdict_exit0(lint, capsys):
    skill_dir = _make_skill(lint)
    _write_verdict(lint, _valid_doc(lint, skill_dir))
    assert lint.run_lint() == 0
    assert "[OK]" in capsys.readouterr().out


def test_codex_lint_uses_native_runtime_guard(lint, monkeypatch):
    """runtimeのラベルとPASSの自己申告だけでは合格させない。"""
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["environment"]["runtime"] = "codex"
    path = _write_verdict(lint, doc)
    verdict_mod, backend_mod, schema = lint.load_harness()
    # schema/closureは別の単体テストで検証。この境界ではnative検査への委譲を測る。
    monkeypatch.setattr(verdict_mod, "validate_schema", lambda *_: [])
    seen = []

    def digest(source, runtime="claude"):
        seen.append(runtime)
        return doc["skill_dir_tree_sha"]

    monkeypatch.setattr(verdict_mod, "skill_dir_tree_sha", digest)
    monkeypatch.setattr(
        verdict_mod, "validate_runtime_evidence",
        lambda *_: ["native activation missing"], raising=False,
    )
    errors = lint.check_verdict(path, "demo-plugin", "run-demo", verdict_mod, backend_mod, schema)
    assert seen == ["codex"]
    assert any("runtime-evidence: native activation missing" in item for item in errors)


def test_contractual_gate_exemption_is_surfaced(lint, capsys):
    """契約 gate 免除は合格だが黙って通さない — [NOTE] で必ず可視化されること。"""
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["gate_response_count"] = 1
    doc["gate_kind"] = "contractual"
    doc["gate_contract_evidence"] = ["frontmatter.external_mutation_guard"]
    _write_verdict(lint, doc)
    assert lint.run_lint() == 0
    out = capsys.readouterr().out
    assert "[NOTE]" in out
    assert "gate_kind=contractual" in out
    assert "frontmatter.external_mutation_guard" in out


def test_contractual_without_evidence_is_a_violation(lint, capsys):
    """接地根拠なき contractual は手書き verdict でも通さないこと (CLI 迂回の封鎖)。"""
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["gate_response_count"] = 1
    doc["gate_kind"] = "contractual"
    _write_verdict(lint, doc)
    assert lint.run_lint() == 1
    assert "gate_contract_evidence が空" in capsys.readouterr().out


def test_rescue_gate_is_not_reported_as_exemption(lint, capsys):
    """rescue の gate 応答は免除ではない (降格側で裁かれる) — NOTE を出さないこと。"""
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["gate_response_count"] = 1
    _write_verdict(lint, doc)
    lint.run_lint()
    assert "[NOTE]" not in capsys.readouterr().out


def test_verdict_without_gate_kind_stays_valid(lint):
    """gate_kind 導入前の verdict (gate=0) を schema 違反にしないこと。"""
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    del doc["gate_kind"]
    _write_verdict(lint, doc)
    assert lint.run_lint() == 0


def test_missing_gate_kind_is_not_an_exemption(lint, capsys):
    """gate_kind 欠落は fail-closed に rescue — 免除として扱わないこと。"""
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    del doc["gate_kind"]
    doc["gate_response_count"] = 1
    _write_verdict(lint, doc)
    lint.run_lint()
    assert "[NOTE]" not in capsys.readouterr().out


def test_valid_pass_verdict_exit0_with_enforce(lint):
    skill_dir = _make_skill(lint)
    _write_verdict(lint, _valid_doc(lint, skill_dir))
    assert lint.run_lint(enforce=True) == 0


# --- 不在 fixture (D13 record-only) ------------------------------------------

def test_missing_verdict_is_record_only_warn(lint, capsys):
    _make_skill(lint)
    assert lint.run_lint() == 0
    out = capsys.readouterr().out
    assert "WARN" in out and "record-only" in out


def test_missing_verdict_fails_with_enforce(lint):
    _make_skill(lint)
    assert lint.run_lint(enforce=True) == 1


def test_missing_not_required_without_declaration(lint, capsys):
    _make_skill(lint, template=SKILL_MD_PLAIN)
    assert lint.run_lint(enforce=True) == 0
    assert "0 missing" in capsys.readouterr().out


def test_denylisted_engine_skill_exempt_from_presence(lint):
    # run-skill-iter-improve は verify_by: live-trial を宣言するが被験 denylist
    # (再帰遮断) につき presence 要求から除外される
    _make_skill(lint, skill="run-skill-iter-improve")
    assert lint.run_lint(enforce=True) == 0


# --- 負 fixture (存在する verdict の違反は record-only 中も exit 1) -----------

def test_degraded_verdict_hard_fails(lint, capsys):
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["overall"]["verdict"] = "DEGRADED"
    _write_verdict(lint, doc)
    assert lint.run_lint() == 1
    assert "verdict=DEGRADED" in capsys.readouterr().out


def _make_stale(lint):
    skill_dir = _make_skill(lint)
    _write_verdict(lint, _valid_doc(lint, skill_dir))
    # verdict 後に挙動面 (SKILL.md) を変更 → tree sha 不一致
    (skill_dir / "SKILL.md").write_text(
        SKILL_MD_DECLARING.format(name="run-demo") + "\nchanged\n", encoding="utf-8"
    )
    return skill_dir


def test_stale_sha_warns_by_default(lint, capsys):
    """CI で実走できない以上、古い PASS は要再実走の WARN に留め、再実走ループを起こさない。"""
    _make_stale(lint)
    assert lint.run_lint() == 0
    out = capsys.readouterr().out
    assert "[WARN] live-trial verdict 要再実走: 1 verdict(s)" in out
    assert "stale-sha" in out
    assert "1 stale (re-trial advised)" in out


def test_stale_sha_fails_with_enforce(lint, capsys):
    _make_stale(lint)
    assert lint.run_lint(enforce=True) == 1
    out = capsys.readouterr().out
    assert "[FAIL]" in out and "stale-sha" in out


def test_stale_sha_fails_with_freshness_env(lint, monkeypatch, capsys):
    """release 前の再取得では env だけで FAIL に戻せること (不在の扱いは変えない)。"""
    _make_stale(lint)
    monkeypatch.setenv("LIVE_TRIAL_ENFORCE_FRESHNESS", "1")
    assert lint.run_lint() == 1
    assert "stale-sha" in capsys.readouterr().out


def test_stale_sha_does_not_hide_other_violations(lint, capsys):
    """古いうえに FAIL の verdict は、WARN 扱いの陰で FAIL を消さないこと。"""
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["skill_dir_tree_sha"] = "0" * 64
    doc["overall"]["verdict"] = "FAIL"
    _write_verdict(lint, doc)
    assert lint.run_lint() == 1
    out = capsys.readouterr().out
    assert "verdict=FAIL" in out and "stale-sha" in out


def test_stale_sha_names_drifted_skill_and_skips_manifest_version(lint, monkeypatch, tmp_path, capsys):
    """未追跡の合成 fixture はファイル名を足さない。git 上の受領ツリーなら挙動ファイルだけ足す。"""
    monkeypatch.setattr(lint, "ROOT", tmp_path)
    plugin = tmp_path / "plugins" / "demo-plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "demo-plugin", "version": "0.0.1", "dependencies": []}),
        encoding="utf-8",
    )
    skill_dir = _make_skill(lint)
    verdict_path = _write_verdict(lint, _valid_doc(lint, skill_dir))
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    })
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=tmp_path, check=True, env=env)
    manifest = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    manifest["version"] = "9.9.9"
    (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        SKILL_MD_DECLARING.format(name="run-demo") + "\nchanged\n", encoding="utf-8"
    )
    assert lint.run_lint() == 0
    out = capsys.readouterr().out
    assert "stale-sha" in out
    assert "plugins/demo-plugin/skills/run-demo/SKILL.md" in out
    assert "plugin.json" not in out
    assert verdict_path.name == "verdict.json"


# --- Codex の本文照合と古い閉包 ------------------------------------------------

SOURCE_ERRORS = [
    "native-skill-activation-unproven",
    "native-skill-source-unproven:demo-plugin:run-demo",
]
_GIT_ENV = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def _git(cwd, *args):
    env = os.environ.copy()
    env.update(_GIT_ENV)
    subprocess.run(["git", *args], cwd=cwd, check=True, env=env)


def _source_check(skill_dir):
    """本文照合の代役。今の本文 (changed 入り) とだけ合わない。"""
    body = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    return list(SOURCE_ERRORS) if "changed" in body else []


def _codex_fixture(
    lint, monkeypatch, tmp_path, runtime_evidence, *,
    commit=True, recorded_sha=None, removed_after_commit=None,
):
    """Codex verdict を受領 commit に載せ、その後に SKILL.md を変える。

    runtime_evidence(skill_dir) の戻り値を validate_runtime_evidence の結果にする。
    transcript の形は extract-codex-transcript の単体テストが固定するので、ここでは
    「どのツリーを基準に照合するか」だけを測る。
    commit="tree-only" は、閉包だけを commit して verdict を未追跡のまま置く。
    removed_after_commit は、受領 commit の閉包にあって今は消えた skill 内のファイル。
    """
    monkeypatch.setattr(lint, "ROOT", tmp_path)
    plugin = tmp_path / "plugins" / "demo-plugin"
    for manifest_dir in (".claude-plugin", ".codex-plugin"):
        (plugin / manifest_dir).mkdir(parents=True)
        (plugin / manifest_dir / "plugin.json").write_text(
            json.dumps({"name": "demo-plugin", "version": "0.0.1", "dependencies": []}),
            encoding="utf-8",
        )
    skill_dir = _make_skill(lint)
    if removed_after_commit:
        (skill_dir / removed_after_commit).write_text("print('old')\n", encoding="utf-8")
    verdict_mod, backend_mod, schema = lint.load_harness()
    monkeypatch.setattr(verdict_mod, "validate_schema", lambda *_: [])
    monkeypatch.setattr(
        verdict_mod, "validate_runtime_evidence",
        lambda _doc, _transcript, checked_dir: runtime_evidence(checked_dir),
    )
    monkeypatch.setattr(lint, "load_harness", lambda: (verdict_mod, backend_mod, schema))
    doc = _valid_doc(lint, skill_dir)
    doc["environment"]["runtime"] = "codex"
    doc["skill_dir_tree_sha"] = recorded_sha or verdict_mod.skill_dir_tree_sha(skill_dir, runtime="codex")
    if commit != "tree-only":
        _write_verdict(lint, doc)
    if commit:
        _git(tmp_path, "init", "-q", "-b", "main")
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", "baseline")
    if commit == "tree-only":
        _write_verdict(lint, doc)
    if removed_after_commit:
        (skill_dir / removed_after_commit).unlink()
    (skill_dir / "SKILL.md").write_text(
        SKILL_MD_DECLARING.format(name="run-demo") + "\nchanged\n", encoding="utf-8"
    )
    return skill_dir


def test_stale_codex_source_mismatch_is_folded_into_stale_warn(lint, monkeypatch, tmp_path, capsys):
    """受領 commit の本文で通る本文照合の誤りは古さなので、stale-sha の 1 行に畳んで WARN にする。"""
    _codex_fixture(lint, monkeypatch, tmp_path, _source_check)
    assert lint.run_lint() == 0
    out = capsys.readouterr().out
    assert "1 stale (re-trial advised)" in out
    assert "本文照合 native-skill-activation-unproven" in out and "受領 commit" in out
    assert "runtime-evidence" not in out
    # 鮮度強制 (release 前) では、畳んだ行ごと FAIL に戻る
    assert lint.run_lint(enforce=True) == 1
    assert "本文照合" in capsys.readouterr().out


def test_stale_codex_source_mismatch_fails_when_baseline_body_also_mismatches(
    lint, monkeypatch, tmp_path, capsys,
):
    """受領 commit の本文でも合わないなら起動の証明が無いので、古さの陰に隠さない。"""
    _codex_fixture(lint, monkeypatch, tmp_path, lambda _dir: list(SOURCE_ERRORS))
    assert lint.run_lint() == 1
    out = capsys.readouterr().out
    assert "runtime-evidence: native-skill-source-unproven" in out
    assert "本文照合" not in out


def test_stale_codex_source_mismatch_fails_for_untracked_verdict(lint, monkeypatch, tmp_path, capsys):
    """受領 commit が無い (未追跡の) verdict は基準の本文が無いので FAIL のまま。"""
    _codex_fixture(lint, monkeypatch, tmp_path, _source_check, commit=False)
    assert lint.run_lint() == 1
    assert "runtime-evidence: native-skill-activation-unproven" in capsys.readouterr().out


def test_untracked_verdict_is_not_rechecked_against_head(lint, monkeypatch, tmp_path, capsys):
    """閉包は commit 済みでも verdict が未追跡なら、HEAD を受領 commit の代わりにしない。

    HEAD には記録と同じ閉包があるので、HEAD で照合し直すと畳めてしまう。
    """
    _codex_fixture(lint, monkeypatch, tmp_path, _source_check, commit="tree-only")
    assert lint.run_lint() == 1
    out = capsys.readouterr().out
    assert "runtime-evidence: native-skill-activation-unproven" in out
    assert "本文照合" not in out


def test_fold_keeps_runtime_errors_that_are_not_source_errors(lint, monkeypatch, tmp_path, capsys):
    """畳むのは本文照合の誤りだけ。受領 commit でも出る他の誤りは FAIL に残す。"""
    def check(skill_dir):
        return _source_check(skill_dir) + ["native-cli-version-mismatch"]

    _codex_fixture(lint, monkeypatch, tmp_path, check)
    assert lint.run_lint() == 1
    out = capsys.readouterr().out
    assert "本文照合 native-skill-activation-unproven" in out
    assert "runtime-evidence: native-cli-version-mismatch" in out
    assert "runtime-evidence: native-skill" not in out


def test_fold_extracts_files_removed_since_the_baseline(lint, monkeypatch, tmp_path, capsys):
    """受領 commit の閉包にあって今は消えたファイルも、plugin 単位の展開で取り戻す。"""
    _codex_fixture(
        lint, monkeypatch, tmp_path, _source_check, removed_after_commit="scripts/old.py",
    )
    assert lint.run_lint() == 0
    assert "本文照合 native-skill-activation-unproven" in capsys.readouterr().out


def test_closure_roots_groups_plugin_files_by_plugin(lint):
    """plugins/ の下は plugin dir 単位、それ以外は label のまま展開単位にする。"""
    labels = [
        "plugins/a/skills/s/SKILL.md",
        "plugins/a/.codex-plugin/plugin.json",
        "plugins/b/lib/y.py",
        "scripts/x.py",
        "plugins/top.md",
    ]
    assert lint._closure_roots(labels) == ["plugins/a", "plugins/b", "plugins/top.md", "scripts/x.py"]


def test_extract_baseline_refuses_commit_with_escaping_symlink(lint, monkeypatch, tmp_path):
    """受領 commit の閉包に外を指す symlink があれば、展開せずに False を返す。"""
    repo = tmp_path / "repo"
    scripts = repo / "plugins" / "demo-plugin" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "x.py").write_text("x\n", encoding="utf-8")
    (scripts / "evil").symlink_to("../../../../outside")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline")
    monkeypatch.setattr(lint, "ROOT", repo)
    dest = tmp_path / "dest"
    dest.mkdir()
    assert lint._extract_baseline("HEAD", ["plugins/demo-plugin"], dest) is False
    assert not (dest / "plugins" / "demo-plugin" / "scripts" / "evil").is_symlink()
    # 受領 commit に展開する対象が 1 つも無いときも、展開できたことにしない
    assert lint._extract_baseline("HEAD", ["plugins/missing"], dest) is False


def test_extract_baseline_without_git_is_false(lint, monkeypatch, tmp_path):
    """git の実行ファイルが無い環境は、例外を漏らさず False にする。"""
    def missing(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(lint.subprocess, "run", missing)
    assert lint._extract_baseline("HEAD", ["plugins/demo-plugin"], tmp_path) is False


def test_symlink_loop_in_baseline_is_not_explained(lint, monkeypatch, tmp_path, capsys):
    """受領 commit の閉包に symlink の輪がある (3.11/3.12 は RuntimeError) なら FAIL のまま。"""
    _codex_fixture(lint, monkeypatch, tmp_path, _source_check)
    verdict_mod, _, _ = lint.load_harness()
    current = verdict_mod.skill_dir_tree_sha

    def looping(skill_dir, runtime="claude"):
        if str(skill_dir).startswith(str(tmp_path / "plugins")):
            return current(skill_dir, runtime=runtime)
        raise RuntimeError("Symlink loop from 'scripts/a'")

    monkeypatch.setattr(verdict_mod, "skill_dir_tree_sha", looping)
    assert lint.run_lint() == 1
    assert "runtime-evidence: native-skill-activation-unproven" in capsys.readouterr().out


def test_stale_codex_source_mismatch_fails_when_recorded_digest_is_not_the_baseline(
    lint, monkeypatch, tmp_path, capsys,
):
    """受領 commit の閉包 digest が記録と違えば、その commit は verdict の基準ではない。"""
    _codex_fixture(lint, monkeypatch, tmp_path, _source_check, recorded_sha="0" * 64)
    assert lint.run_lint() == 1
    assert "runtime-evidence: native-skill-source-unproven" in capsys.readouterr().out


def test_stale_codex_baseline_recheck_must_not_add_errors(lint, monkeypatch, tmp_path, capsys):
    """受領 commit で照合し直したときに新しい誤りが出るなら、畳まずに FAIL のまま。"""
    def check(skill_dir):
        return _source_check(skill_dir) or ["native-cli-version-mismatch"]

    _codex_fixture(lint, monkeypatch, tmp_path, check)
    assert lint.run_lint() == 1
    assert "runtime-evidence: native-skill-source-unproven" in capsys.readouterr().out


def _symlink_archive(*members):
    """(name, linkname) の symlink だけを並べた tar。"""
    import io
    import tarfile

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as archive:
        for name, linkname in members:
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = linkname
            archive.addfile(info)
    buf.seek(0)
    return tarfile.open(fileobj=buf)


# 自前の検査 (gh-107845 を抱える版の経路) と stdlib の検査の両方を、どの版でも通す
@pytest.fixture(params=["patched", "stdlib"])
def link_check(request, lint, monkeypatch):
    monkeypatch.setattr(lint, "_STDLIB_LINK_CHECK_SOUND", request.param == "stdlib")
    return request.param


def test_member_filter_accepts_inner_relative_symlink(lint, tmp_path, monkeypatch):
    """下位 dir の相対 symlink が中を指すなら通す (3.11.4 の data filter は誤って拒む)。"""
    monkeypatch.setattr(lint, "_STDLIB_LINK_CHECK_SOUND", False)
    with _symlink_archive(("p/hooks/x.py", "../scripts/x.py")) as archive:
        archive.extractall(tmp_path, filter=lint._member_filter)
    assert (tmp_path / "p" / "hooks" / "x.py").is_symlink()


@pytest.mark.parametrize("linkname, error", [
    ("../../../outside.py", "LinkOutsideDestinationError"),
    ("/etc/passwd", "AbsoluteLinkError"),
    # 絶対 path は展開先の中を指していても拒む (行き先の検査では止まらない場合)
    ("{dest}/p/scripts/x.py", "AbsoluteLinkError"),
])
def test_member_filter_rejects_escaping_symlink(lint, tmp_path, linkname, error, link_check):
    """展開先の外を指す symlink と絶対 path の symlink は拒む。"""
    import tarfile

    linkname = linkname.format(dest=tmp_path)
    with _symlink_archive(("p/hooks/y.py", linkname)) as archive:
        with pytest.raises(getattr(tarfile, error)):
            archive.extractall(tmp_path, filter=lint._member_filter)
    assert not (tmp_path / "p" / "hooks" / "y.py").exists()


def test_member_filter_rejects_escape_chained_through_earlier_link(lint, tmp_path, link_check):
    """先に置いた link を経由して外へ出る連鎖 (p/x -> . の後の p/x/y -> ../..) を拒む。"""
    import tarfile

    with _symlink_archive(("p/x", "."), ("p/x/y", "../..")) as archive:
        with pytest.raises(tarfile.FilterError):
            archive.extractall(tmp_path, filter=lint._member_filter)


def test_member_filter_rejects_case_folded_chain(lint, tmp_path, link_check):
    """大文字小文字を区別しない FS では、p/X -> . の後の p/x/y -> ../.. も外へ出る連鎖になる。"""
    import tarfile

    probe = tmp_path / "CaseProbe"
    probe.mkdir()
    if not (tmp_path / "caseprobe").exists():
        pytest.skip("大文字小文字を区別する FS では p/X と p/x は別のもので、連鎖にならない")
    dest = tmp_path / "dest"
    dest.mkdir()
    with _symlink_archive(("p/X", "."), ("p/x/y", "../..")) as archive:
        with pytest.raises(tarfile.FilterError):
            archive.extractall(dest, filter=lint._member_filter)


def test_member_filter_delegates_to_stdlib_when_its_link_check_is_sound(lint, monkeypatch):
    """stdlib の検査が正しい版では、symlink も stdlib の data filter に任せる。"""
    import tarfile

    seen = []
    monkeypatch.setattr(lint, "_STDLIB_LINK_CHECK_SOUND", True)
    monkeypatch.setattr(tarfile, "data_filter", lambda member, dest: seen.append(member.name) or member)
    info = tarfile.TarInfo("p/hooks/x.py")
    info.type = tarfile.SYMTYPE
    info.linkname = "../scripts/x.py"
    lint._member_filter(info, "/unused")
    assert seen == ["p/hooks/x.py"]


def test_stdlib_link_check_probe_matches_stdlib_behaviour(lint, monkeypatch, tmp_path):
    """判定は、下位 dir の中を指す相対 link を stdlib が受け入れるかどうかと一致する。"""
    import tarfile

    monkeypatch.setattr(lint, "_STDLIB_LINK_CHECK_SOUND", None)
    info = tarfile.TarInfo("a/b")
    info.type = tarfile.SYMTYPE
    info.linkname = "../c"
    try:
        tarfile.data_filter(info, str(tmp_path))
        expected = True
    except tarfile.LinkOutsideDestinationError:
        expected = False
    assert lint._stdlib_link_check_sound() is expected


def test_downgraded_tier_hard_fails(lint, capsys):
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["tier"] = "fork"
    doc["downgrade_reason"] = "tmux 不在"
    _write_verdict(lint, doc)
    assert lint.run_lint() == 1
    assert "downgraded" in capsys.readouterr().out


def test_schema_extra_key_hard_fails(lint, capsys):
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["score"] = 95  # additionalProperties false 違反 (点数出力の混入を遮断)
    _write_verdict(lint, doc)
    assert lint.run_lint() == 1
    assert "schema" in capsys.readouterr().out


def test_invalid_json_hard_fails(lint):
    skill_dir = _make_skill(lint)
    path = _write_verdict(lint, _valid_doc(lint, skill_dir))
    path.write_text("{broken", encoding="utf-8")
    assert lint.run_lint() == 1


def test_denylist_subject_detected_in_check(lint):
    skill_dir = _make_skill(lint)
    doc = _valid_doc(lint, skill_dir)
    doc["target_skill"] = "demo-plugin:run-skill-live-trial"
    path = _write_verdict(lint, doc)
    verdict_mod, backend_mod, schema = lint.load_harness()
    errs = lint.check_verdict(path, "demo-plugin", "run-demo", verdict_mod, backend_mod, schema)
    assert any("denylist-subject" in e for e in errs)


# --- 最新 run-id 選択 ---------------------------------------------------------

def test_latest_run_id_wins_newer_fail(lint):
    skill_dir = _make_skill(lint)
    good = _valid_doc(lint, skill_dir)
    bad = _valid_doc(lint, skill_dir)
    bad["overall"]["verdict"] = "FAIL"
    _write_verdict(lint, good, run_id="20260701T000000")
    _write_verdict(lint, bad, run_id="20260702T000000")
    assert lint.run_lint() == 1


def _receipt(lint, ref, skill="run-demo"):
    path = lint.EVAL_LOG / "demo-plugin" / skill / "criteria-test" / "scenario-verdict.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "criteria_results": {
            "OUT1": {"verify_by": "live-trial", "live_trial_verdict_ref": ref},
        },
    }), encoding="utf-8")
    return path


def test_criteria_receipt_pass_beats_newer_non_pass(lint):
    """辞書順で新しい失敗 run は、receipt が採用した current PASS を受理証跡にしない。"""
    skill_dir = _make_skill(lint)
    good = _valid_doc(lint, skill_dir)
    bad = _valid_doc(lint, skill_dir)
    bad["overall"]["verdict"] = "BLOCKED"
    bad["downgrade_reason"] = "tmux 不在 / HARD_CAP 超過等の fail-closed"
    _write_verdict(lint, good, run_id="20260701T000000")
    _write_verdict(lint, bad, run_id="20260702T000000")
    _receipt(lint, "eval-log/demo-plugin/run-demo/live-trial/20260701T000000/verdict.json")
    assert lint.run_lint() == 0


def test_corrupt_criteria_receipt_does_not_fall_through(lint, capsys):
    skill_dir = _make_skill(lint)
    _write_verdict(lint, _valid_doc(lint, skill_dir), run_id="20260702T000000")
    path = _receipt(lint, "eval-log/demo-plugin/run-demo/live-trial/20260702T000000/verdict.json")
    path.write_text("{", encoding="utf-8")
    assert lint.run_lint() == 1
    assert "criteria-receipt-invalid-json" in capsys.readouterr().out


def test_stale_receipt_verdict_is_reported_instead_of_newer_fail(lint, capsys):
    skill_dir = _make_skill(lint)
    good = _valid_doc(lint, skill_dir)
    good["skill_dir_tree_sha"] = "0" * 64
    bad = _valid_doc(lint, skill_dir)
    bad["overall"]["verdict"] = "FAIL"
    _write_verdict(lint, good, run_id="20260701T000000")
    _write_verdict(lint, bad, run_id="20260702T000000")
    _receipt(lint, "eval-log/demo-plugin/run-demo/live-trial/20260701T000000/verdict.json")
    assert lint.run_lint() == 0
    out = capsys.readouterr().out
    assert "20260701T000000/verdict.json stale-sha" in out
    assert "verdict=FAIL" not in out


def test_latest_run_id_wins_newer_pass(lint):
    skill_dir = _make_skill(lint)
    good = _valid_doc(lint, skill_dir)
    bad = _valid_doc(lint, skill_dir)
    bad["overall"]["verdict"] = "FAIL"
    _write_verdict(lint, bad, run_id="20260701T000000")
    _write_verdict(lint, good, run_id="20260702T000000")
    assert lint.run_lint() == 0


# --- self-test 経路 -----------------------------------------------------------

def test_self_test_passes():
    assert _load().self_test() == 0
