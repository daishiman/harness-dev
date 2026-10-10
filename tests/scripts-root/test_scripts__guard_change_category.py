"""Genuine functional tests for scripts/guard-change-category.py (hyphen module).

git / subprocess / changelog ファイル I/O は monkeypatch・tmp_path で遮断し、
分類ロジック・proposal 判定・cooldown 判定・main の exit code を実入力で検証する。

検査対象:
  - classify_change: plugins/ → P0 / sink adapter → P0 / SKILL.md name 変更 →
    P0 / 新規 SKILL.md(status A) → P1 / P1 doc / plugin.json / rubric.json →
    P1 / .gitignore → P3 / doc・references → P2 / fallback P2
  - needs_proposal: P0/P1 は True, P2/P3 は False
  - has_recent_changelog: 一致/不一致/不正 JSON 行
  - check_cooldown: なし/期間内 False/期間外 True/bypass True
  - load_policy: 不在で exit 2
  - main: --report JSON / 通常出力 + exit code (subprocess)
  - 判定の拠り所 (tmp の git repo): 同じ PR で policy を auto_apply に下げても plugin.json は
    BLOCK / governance-log の行を消すと exit 2 / policy 自身の変更は P1 / P2 の
    --bypass-cooldown は止めない / color.ui=always でも SKILL.md の name 変更を P0 にする
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "guard-change-category.py"
POLICY = ROOT / "plugins" / "skill-governance-config" / "config" / "governance-policy.json"


def _load():
    spec = importlib.util.spec_from_file_location("guard_change_category_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = _load()
PolicyDict = json.loads(POLICY.read_text(encoding="utf-8"))


# --- classify_change (no name-field diff) ------------------------------------
@pytest.fixture
def no_name_change(monkeypatch):
    # _name_field_changed が git を叩かないよう常に False を返させる
    monkeypatch.setattr(G, "_name_field_changed", lambda path: False)


def test_existing_plugin_content_is_p2(no_name_change):
    assert G.classify_change("plugins/foo/skills/bar/SKILL.md") == "P2_content"
    assert G.classify_change("plugins/foo/config/x.json") == "P2_content"

def test_new_plugin_is_p0(no_name_change):
    assert G.classify_change("plugins/newplugin/config/x.json", new_plugin=True) == "P0_breaking"


def test_classify_sink_adapter_is_p0(no_name_change):
    assert G.classify_change("scripts/adapters/sink_notion.py") == "P0_breaking"


def test_classify_p1_doc_paths_is_p1(no_name_change):
    p = "doc/ClaudeCodeスキルの設計書/33-change-governance/policy.md"
    assert G.classify_change(p) == "P1_structural"


def test_classify_plugin_json_is_p1(no_name_change):
    # plugins/ prefix を避けるため別 root を使う
    assert G.classify_change("kit/.claude-plugin/plugin.json") == "P1_structural"


def test_classify_governance_policy_is_p1(no_name_change):
    assert G.classify_change(G.POLICY_REL_PATH) == "P1_structural"


def test_classify_rubric_json_is_p1(no_name_change):
    assert G.classify_change("kit/skills/x/rubric.json") == "P1_structural"


def test_classify_gitignore_is_p3(no_name_change):
    assert G.classify_change(".gitignore") == "P3_cosmetic"
    assert G.classify_change("sub/.editorconfig") == "P3_cosmetic"


def test_classify_doc_body_is_p2(no_name_change):
    assert G.classify_change("doc/readme.md") == "P2_content"


def test_classify_references_is_p2(no_name_change):
    assert G.classify_change("kit/skills/x/references/api.md") == "P2_content"


def test_classify_fallback_is_p2(no_name_change):
    # 既知ルールに当たらない → Goodhart 回避で P2 (P3 にしない)
    assert G.classify_change("some/random/file.py") == "P2_content"


# --- classify_change with name-field diff (SKILL.md under non-plugins root) ---
def test_classify_skill_md_name_change_is_p0(monkeypatch):
    monkeypatch.setattr(G, "_name_field_changed", lambda path: True)
    # 公開nameの変更は既存contentの変更と分離する。
    assert G.classify_change("plugins/p/skills/s/SKILL.md") == "P0_breaking"


@pytest.mark.parametrize("status", ["A", "D", "R100"])
def test_skill_lifecycle_change_is_p1(monkeypatch, status):
    monkeypatch.setattr(G, "_name_field_changed", lambda path: True)
    assert G.classify_change("plugins/p/skills/s/SKILL.md", status=status) == "P1_structural"


# --- needs_proposal ----------------------------------------------------------
def test_needs_proposal_p0_p1_true():
    assert G.needs_proposal("P0_breaking", PolicyDict) is True
    assert G.needs_proposal("P1_structural", PolicyDict) is True


def test_needs_proposal_p2_p3_false():
    assert G.needs_proposal("P2_content", PolicyDict) is False
    assert G.needs_proposal("P3_cosmetic", PolicyDict) is False


def test_needs_proposal_unknown_category_false():
    assert G.needs_proposal("PX_unknown", PolicyDict) is False


# --- has_recent_changelog ----------------------------------------------------
def test_has_recent_changelog_match(tmp_path, monkeypatch):
    log = tmp_path / "governance-log.jsonl"
    log.write_text(
        json.dumps({"target_path": "plugins/foo/skills/bar", "approver": "solo_operator", "proposal_id": "selected"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(G, "CHANGELOG_PATH", log)
    assert not G.has_recent_changelog("plugins/foo/skills/bar/SKILL.md")
    assert G.has_recent_changelog("plugins/foo/skills/bar/SKILL.md", proposal_id="selected")
    # 不正行は黙って飛ばさず ConfigError（main では exit 2）
    log.write_text(log.read_text(encoding="utf-8") + "not-json-line\n", encoding="utf-8")
    with pytest.raises(G.ConfigError, match="2 行目"):
        G.has_recent_changelog("plugins/foo/skills/bar/SKILL.md", proposal_id="selected")


def test_has_recent_changelog_no_match(tmp_path, monkeypatch):
    log = tmp_path / "governance-log.jsonl"
    log.write_text(json.dumps({"target_path": "other/path"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(G, "CHANGELOG_PATH", log)
    assert G.has_recent_changelog("plugins/foo/SKILL.md") is False


def test_has_recent_changelog_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "CHANGELOG_PATH", tmp_path / "absent.jsonl")
    assert G.has_recent_changelog("anything") is False


# --- check_cooldown ----------------------------------------------------------
def test_check_cooldown_bypass(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "CHANGELOG_PATH", tmp_path / "absent.jsonl")
    assert G.check_cooldown("p", "P0_breaking", PolicyDict, bypass=True) is False


def test_check_cooldown_none_rule(tmp_path, monkeypatch):
    # P2_content は cooldown 「なし」→ 常に True（--bypass-cooldown を付けても変わらない）
    monkeypatch.setattr(G, "CHANGELOG_PATH", tmp_path / "absent.jsonl")
    assert G.check_cooldown("p", "P2_content", PolicyDict) is True
    assert G.check_cooldown("p", "P2_content", PolicyDict, bypass=True) is True


def test_check_cooldown_within_period_is_false(tmp_path, monkeypatch):
    import datetime

    log = tmp_path / "governance-log.jsonl"
    recent = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log.write_text(
        json.dumps({"target_path": "plugins/foo/SKILL.md", "timestamp": recent}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(G, "CHANGELOG_PATH", log)
    # P0_breaking は 7日 cooldown。直近変更があるので False (違反)
    assert G.check_cooldown("plugins/foo/SKILL.md", "P0_breaking", PolicyDict) is False


def test_check_cooldown_past_period_is_true(tmp_path, monkeypatch):
    import datetime

    log = tmp_path / "governance-log.jsonl"
    old = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    ).isoformat()
    log.write_text(
        json.dumps({"target_path": "plugins/foo/SKILL.md", "timestamp": old}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(G, "CHANGELOG_PATH", log)
    assert G.check_cooldown("plugins/foo/SKILL.md", "P0_breaking", PolicyDict) is True


def test_check_cooldown_no_log_file_is_true(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "CHANGELOG_PATH", tmp_path / "absent.jsonl")
    assert G.check_cooldown("p", "P0_breaking", PolicyDict) is True


# --- load_policy -------------------------------------------------------------
def test_load_policy_found(monkeypatch):
    # 実ポリシーが repo に存在する前提 (cwd=repo root で呼ぶ)
    monkeypatch.chdir(ROOT)
    pol = G.load_policy()
    assert "change_categories" in pol


def test_load_policy_missing_exits_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # ポリシー不在ディレクトリ
    with pytest.raises(SystemExit) as ei:
        G.load_policy()
    assert ei.value.code == 2


# --- main via subprocess (deterministic: empty git diff) --------------------
def _run_main(tmp_repo: Path, *args):
    """tmp_repo に最小 git repo + policy を用意し guard を走らせる。
    base...HEAD diff が空なので blocked=0 / exit 0 が決定論的。"""
    import os

    env = dict(os.environ)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(tmp_repo),
        env=env,
        capture_output=True,
        text=True,
    )
    return r


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    # policy を相対パスで配置 (POLICY_PATH_CANDIDATES と同じ相対位置)
    pol_dir = repo / "plugins" / "skill-governance-config" / "config"
    pol_dir.mkdir(parents=True)
    (pol_dir / "governance-policy.json").write_text(
        POLICY.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return repo


def test_main_help_via_no_block(tmp_path):
    repo = _init_repo(tmp_path)
    # base=HEAD で diff 空 → blocked 0 / exit 0
    r = _run_main(repo, "--base", "HEAD")
    assert r.returncode == 0, r.stderr
    assert "summary: total=0 blocked=0" in r.stdout


def test_main_report_json(tmp_path):
    repo = _init_repo(tmp_path)
    r = _run_main(repo, "--base", "HEAD", "--report")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["base"] == "HEAD"
    assert payload["changes"] == []
    assert payload["blocked"] == []


def test_main_blocks_unapproved_p0(tmp_path):
    repo = _init_repo(tmp_path)
    # 新規 plugins/ ファイルを作り commit → base(初期commit)...HEAD diff で P0 検出
    newf = repo / "plugins" / "newplug" / "skills" / "s" / "SKILL.md"
    newf.parent.mkdir(parents=True)
    newf.write_text("---\nname: s\n---\nbody\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "add plugin"], cwd=repo, check=True)
    r = _run_main(repo, "--base", "HEAD~1")
    # merge-base に無かった plugins/newplug/ は manifest が無くても新規 plugin (P0)。
    # changelog 未記録 → block → exit 1
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "BLOCK" in r.stderr
    assert "P0_breaking" in r.stderr


def test_main_missing_policy_exits_2(tmp_path):
    # policy を置かない裸の git repo
    repo = tmp_path / "bare"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    r = _run_main(repo, "--base", "HEAD")
    assert r.returncode == 2
    assert "policy not found" in r.stderr


# --- in-process git-wrapper helpers (subprocess monkeypatched) --------------
def test_changed_files_parses_output(monkeypatch):
    monkeypatch.setattr(
        G.subprocess, "check_output", lambda *a, **k: "M\0a.py\0A\0b.md\0"
    )
    assert G.changed_files("base") == ["a.py", "b.md"]


def test_changed_files_git_error_raises(monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(G.subprocess, "check_output", boom)
    with pytest.raises(G.GitDiffError):
        G.changed_files("base")


def test_changed_file_statuses_parses(monkeypatch):
    monkeypatch.setattr(
        G.subprocess,
        "check_output",
        lambda *a, **k: "A\0new.py\0M\0mod.py\0",
    )
    statuses = G.changed_file_statuses("base")
    assert statuses == {"new.py": "A", "mod.py": "M"}


def test_changed_file_statuses_git_error_raises(monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(G.subprocess, "check_output", boom)
    with pytest.raises(G.GitDiffError):
        G.changed_file_statuses("base")


def test_name_field_changed_true(monkeypatch):
    # frontmatter の name が変われば True
    monkeypatch.setattr(
        G.subprocess,
        "check_output",
        lambda *a, **k: "@@ -1,4 +1,4 @@\n ---\n-name: old-skill\n+name: new-skill\n ---\n",
    )
    assert G._name_field_changed("p/SKILL.md") is True


def test_name_field_changed_false_when_no_name_line(monkeypatch):
    monkeypatch.setattr(
        G.subprocess, "check_output",
        lambda *a, **k: "@@ -1,4 +1,4 @@\n ---\n name: s\n+description: x\n ---\n context\n"
    )
    assert G._name_field_changed("p/SKILL.md") is False


def test_name_field_changed_git_error_raises(monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(G.subprocess, "check_output", boom)
    with pytest.raises(G.GitDiffError):
        G._name_field_changed("p/SKILL.md")


# --- check_cooldown additional paths ----------------------------------------
def test_check_cooldown_unparseable_days_fails_closed(tmp_path, monkeypatch):
    # cooldown 文字列に数字が無い → cooldown なしに畳まず ConfigError (main では exit 2)
    pol = {"cooldown_rules": {"P0_breaking": "数字なし"}}
    monkeypatch.setattr(G, "CHANGELOG_PATH", tmp_path / "absent.jsonl")
    with pytest.raises(G.ConfigError):
        G.check_cooldown("p", "P0_breaking", pol)


def test_check_cooldown_skips_missing_ts_but_rejects_bad_json(tmp_path, monkeypatch):
    log = tmp_path / "governance-log.jsonl"
    entry = json.dumps({"target_path": "plugins/foo/SKILL.md"})  # ts 欠落 → skip
    log.write_text(entry + "\n", encoding="utf-8")
    monkeypatch.setattr(G, "CHANGELOG_PATH", log)
    # ts 欠落のみ → cooldown 違反検出されず True
    assert G.check_cooldown("plugins/foo/SKILL.md", "P0_breaking", PolicyDict) is True
    # 不正行は cooldown なしに畳まず ConfigError（以前の変更の行が壊れても素通りさせない）
    log.write_text("not-json\n" + entry + "\n", encoding="utf-8")
    with pytest.raises(G.ConfigError, match="1 行目"):
        G.check_cooldown("plugins/foo/SKILL.md", "P0_breaking", PolicyDict)


def test_check_cooldown_bad_timestamp_format_fails_closed(tmp_path, monkeypatch):
    log = tmp_path / "governance-log.jsonl"
    log.write_text(
        json.dumps({"target_path": "plugins/foo/SKILL.md", "timestamp": "not-a-date"})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(G, "CHANGELOG_PATH", log)
    with pytest.raises(G.ConfigError):
        G.check_cooldown("plugins/foo/SKILL.md", "P0_breaking", PolicyDict)


# --- main() called in-process (deps monkeypatched, no real git) -------------
def _no_merge_base_files(monkeypatch):
    """merge-base の policy と governance-log は無いものとし、実 repo の git に届かせない。"""
    monkeypatch.setattr(G, "_merge_base", lambda base: "MERGE_BASE")
    monkeypatch.setattr(G, "_blob_at", lambda rev, path: None)


def test_main_inprocess_git_failure_exits_2(monkeypatch, capsys):
    # git diff 失敗は「変更なし」ではなく exit 2 (fail-closed)
    def boom(*a, **k):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(G, "load_policy", lambda: PolicyDict)
    monkeypatch.setattr(G.subprocess, "check_output", boom)
    rc = G.main(["prog"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "ERROR: git diff" in captured.err
    assert "blocked=" not in captured.out


def test_main_inprocess_no_changes(monkeypatch, capsys):
    monkeypatch.setattr(G, "load_policy", lambda: PolicyDict)
    monkeypatch.setattr(G, "changed_files", lambda base: [])
    monkeypatch.setattr(G, "changed_file_statuses", lambda base: {})
    rc = G.main(["prog"])
    assert rc == 0
    assert "blocked=0" in capsys.readouterr().out


def test_main_inprocess_blocks_p0(monkeypatch, capsys):
    monkeypatch.setattr(G, "load_policy", lambda: PolicyDict)
    monkeypatch.setattr(G, "changed_files", lambda base: ["plugins/p/skills/s/SKILL.md"])
    monkeypatch.setattr(G, "changed_file_statuses", lambda base: {"plugins/p/skills/s/SKILL.md": "A"})
    monkeypatch.setattr(G, "has_recent_changelog", lambda *a, **k: False)
    monkeypatch.setattr(G, "check_cooldown", lambda *a, **k: True)
    monkeypatch.setattr(G, "_base_plugin_dirs", lambda base: {"plugins/p"})
    _no_merge_base_files(monkeypatch)
    rc = G.main(["prog"])
    assert rc == 1
    assert "BLOCK" in capsys.readouterr().err


def test_main_inprocess_report_json(monkeypatch, capsys):
    monkeypatch.setattr(G, "load_policy", lambda: PolicyDict)
    monkeypatch.setattr(G, "changed_files", lambda base: ["doc/readme.md"])
    monkeypatch.setattr(G, "changed_file_statuses", lambda base: {})
    _no_merge_base_files(monkeypatch)
    rc = G.main(["prog", "--report", "--base", "origin/main"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["changes"][0]["category"] == "P2_content"
    assert payload["changes"][0]["proposal_required"] is False


def test_main_inprocess_cooldown_block(monkeypatch, capsys):
    # proposal 不要だが cooldown 違反で block されるパス
    monkeypatch.setattr(G, "load_policy", lambda: PolicyDict)
    monkeypatch.setattr(G, "changed_files", lambda base: ["doc/x.md"])
    monkeypatch.setattr(G, "changed_file_statuses", lambda base: {})
    monkeypatch.setattr(G, "check_cooldown", lambda *a, **k: False)
    _no_merge_base_files(monkeypatch)
    rc = G.main(["prog"])
    assert rc == 1
    assert "cooldown" in capsys.readouterr().err


def test_approval_targets_are_scoped_and_scalar_list_equivalent(tmp_path, monkeypatch):
    log = tmp_path / "governance-log.jsonl"
    monkeypatch.setattr(G, "CHANGELOG_PATH", log)
    for target in ("plugins/foo/skills/bar", ["plugins/foo/skills/bar"]):
        log.write_text(json.dumps({"target_path": target, "approver": "solo_operator", "proposal_id": "selected"}) + "\n")
        assert G.has_recent_changelog("plugins/foo/skills/bar/SKILL.md", proposal_id="selected")
        assert not G.has_recent_changelog("plugins/foo/skills/bar-extra/SKILL.md", proposal_id="selected")
        assert not G.has_recent_changelog("plugins/unrelated/skills/bar/SKILL.md", proposal_id="selected")


def test_unapproved_record_does_not_authorize(tmp_path, monkeypatch):
    log = tmp_path / "governance-log.jsonl"
    monkeypatch.setattr(G, "CHANGELOG_PATH", log)
    log.write_text(json.dumps({"target_path": "scripts/x.py", "approver": "auto"}) + "\n")
    assert not G.has_recent_changelog("scripts/x.py")


def test_current_proposal_does_not_block_itself_but_prior_change_does(tmp_path, monkeypatch):
    import datetime
    log = tmp_path / "governance-log.jsonl"
    monkeypatch.setattr(G, "CHANGELOG_PATH", log)
    current = {"target_path": ["scripts/x.py"], "approver": "solo_operator",
               "category": "P1_structural", "proposal_id": "current",
               "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    log.write_text(json.dumps(current) + "\n")
    assert G.check_cooldown("scripts/x.py", "P1_structural", PolicyDict, proposal_id="current")
    assert not G.check_cooldown("scripts/x.py", "P1_structural", PolicyDict)
    previous = {**current, "proposal_id": "previous"}
    log.write_text(json.dumps(previous) + "\n" + json.dumps(current) + "\n")
    assert not G.check_cooldown("scripts/x.py", "P1_structural", PolicyDict, proposal_id="current")
    current["incident_fix"] = True
    log.write_text(json.dumps(previous) + "\n" + json.dumps(current) + "\n")
    assert G.check_cooldown("scripts/x.py", "P1_structural", PolicyDict, proposal_id="current")
    current["approver"] = "auto"
    log.write_text(json.dumps(previous) + "\n" + json.dumps(current) + "\n")
    assert not G.check_cooldown("scripts/x.py", "P1_structural", PolicyDict, proposal_id="current")


def test_main_uses_same_base_for_name_diff(monkeypatch):
    monkeypatch.setattr(G, "load_policy", lambda: PolicyDict)
    monkeypatch.setattr(G, "changed_files", lambda base: ["plugins/p/skills/run-x/SKILL.md"])
    monkeypatch.setattr(G, "changed_file_statuses", lambda base: {})
    monkeypatch.setattr(G, "_base_plugin_dirs", lambda base: {"plugins/p"})
    observed = []
    monkeypatch.setattr(G, "_name_field_changed", lambda path, base: observed.append(base) or False)
    merge_bases = []
    monkeypatch.setattr(G, "_merge_base", lambda base: merge_bases.append(base) or "MERGE_BASE")
    monkeypatch.setattr(G, "_blob_at", lambda rev, path: None)
    assert G.main(["prog", "--base", "release-base"]) == 0
    assert observed == ["release-base...HEAD"]
    assert merge_bases == ["release-base"]


def test_current_content_hash_binds_approval_and_self_cooldown(tmp_path, monkeypatch):
    import datetime
    import hashlib
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "rubric.json"
    target.write_text("reviewed content")
    log = tmp_path / "governance-log.jsonl"
    monkeypatch.setattr(G, "CHANGELOG_PATH", log)
    entry = {"target_path": ["rubric.json"], "approver": "solo_operator",
             "category": "P1_structural", "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "target_sha256": {"rubric.json": hashlib.sha256(target.read_bytes()).hexdigest()}}
    log.write_text(json.dumps(entry) + "\n")
    assert G.has_recent_changelog("rubric.json")
    assert G.check_cooldown("rubric.json", "P1_structural", PolicyDict)
    target.write_text("unreviewed content")
    assert not G.has_recent_changelog("rubric.json")
    assert not G.check_cooldown("rubric.json", "P1_structural", PolicyDict)


def test_bypass_flag_requires_current_approved_incident_hash(tmp_path, monkeypatch):
    import hashlib
    monkeypatch.chdir(tmp_path)
    path = Path("guarded.json")
    path.write_text("approved")
    entry = {"target_path": [str(path)], "approver": "independent-reviewer", "status": "approved", "category": "P1_structural", "proposal_id": "current", "target_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest()}}
    log = tmp_path / "log.jsonl"
    monkeypatch.setattr(G, "CHANGELOG_PATH", log)
    log.write_text(json.dumps(entry) + "\n")
    assert not G.check_cooldown(str(path), "P1_structural", PolicyDict, bypass=True, proposal_id="current")
    entry["incident_fix"] = True
    log.write_text(json.dumps(entry) + "\n")
    assert G.check_cooldown(str(path), "P1_structural", PolicyDict, bypass=True, proposal_id="current")
    path.write_text("changed after approval")
    assert not G.check_cooldown(str(path), "P1_structural", PolicyDict, bypass=True, proposal_id="current")


def test_cooldown_applies_across_categories(tmp_path, monkeypatch):
    import datetime
    log = tmp_path / "log.jsonl"
    monkeypatch.setattr(G, "CHANGELOG_PATH", log)
    log.write_text(json.dumps({"target_path": ["same.json"], "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "category": "P0_breaking", "approver": "reviewer"}) + "\n")
    assert not G.check_cooldown("same.json", "P1_structural", PolicyDict)


def test_installed_explicit_policy_from_consumer_cwd(tmp_path, monkeypatch):
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    config = tmp_path / "installed/config/governance-policy.json"
    config.parent.mkdir(parents=True)
    config.write_text(POLICY.read_text())
    monkeypatch.chdir(consumer)
    assert G.load_policy(config)["change_categories"]
    monkeypatch.setattr(G, "changed_files", lambda _base: [])
    monkeypatch.setattr(G, "changed_file_statuses", lambda _base: {})
    assert G.main(["prog", "--policy", str(config), "--report"]) == 0
    assert G.main(["prog", "--help"]) == 0
    assert G.main(["prog", "--policy"]) == 2
    for invalid in [Path("relative.json"), tmp_path / "absent.json"]:
        with pytest.raises(SystemExit) as error:
            G.load_policy(invalid)
        assert error.value.code == 2
    config.write_text("{}")
    with pytest.raises(SystemExit) as error:
        G.load_policy(config)
    assert error.value.code == 2


# --- 判定の拠り所は merge-base（同じ PR の中でゲートを外させない） ---------------
POLICY_REL = "plugins/skill-governance-config/config/governance-policy.json"
LOG_REL = ".claude/changelog/governance-log.jsonl"
MANIFEST_REL = "plugins/demo/.claude-plugin/plugin.json"
SKILL_REL = "plugins/demo/skills/run-x/SKILL.md"


def _governed_repo(tmp_path: Path):
    """policy・plugin.json・SKILL.md・governance-log（2行）・本文を base に commit した repo。

    利用者の global/system の git 設定は読まない（color.ui などは test ごとに repo へ設定する）。
    """
    import os

    empty = tmp_path / "empty.gitconfig"
    empty.write_text("", encoding="utf-8")
    env = dict(os.environ, GIT_CONFIG_GLOBAL=str(empty), GIT_CONFIG_NOSYSTEM="1",
               PYTHONDONTWRITEBYTECODE="1")
    repo = tmp_path / "governed"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                       cwd=repo, env=env, check=True, capture_output=True)

    old = [{"target_path": [t], "approver": "solo_operator", "proposal_id": p,
            "timestamp": "2020-01-01T00:00:00+00:00"} for t, p in (("doc/readme.md", "old-1"),
                                                                  ("plugins/demo", "old-2"))]
    base_files = {
        POLICY_REL: POLICY.read_text(encoding="utf-8"),
        MANIFEST_REL: '{"name": "demo"}\n',
        SKILL_REL: "---\nname: run-x\ndescription: x\n---\n本文\n",
        LOG_REL: "".join(json.dumps(e) + "\n" for e in old),
        "doc/readme.md": "v1\n",
    }
    for rel, text in base_files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    git("tag", "base")

    def commit(changes):
        for rel, text in changes.items():
            (repo / rel).write_text(text, encoding="utf-8")
        git("commit", "-q", "-am", "change")

    def gate(*args):
        return subprocess.run([sys.executable, str(SCRIPT), "--base", "base", *args],
                              cwd=str(repo), env=env, capture_output=True, text=True, encoding="utf-8")

    return repo, git, commit, gate


def test_same_pr_policy_downgrade_still_blocks_plugin_json(tmp_path):
    _, _, commit, gate = _governed_repo(tmp_path)
    head_policy = json.loads(POLICY.read_text(encoding="utf-8"))
    for rule in head_policy["change_categories"].values():
        rule["workflow"], rule["approver"] = "auto_apply", "auto"
    commit({POLICY_REL: json.dumps(head_policy, ensure_ascii=False, indent=2) + "\n",
            MANIFEST_REL: '{"name": "demo", "version": "2.0.0"}\n'})
    r = gate("--report")
    assert r.returncode == 1, r.stderr
    payload = json.loads(r.stdout)
    assert {b["path"]: b["category"] for b in payload["blocked"]} == {
        POLICY_REL: "P1_structural", MANIFEST_REL: "P1_structural"}
    assert all(c["proposal_required"] for c in payload["changes"])


@pytest.mark.parametrize("edit", [
    lambda lines: lines[1:],  # 以前の変更の行を消す
    lambda lines: [lines[0].replace("2020-01-01", "2019-01-01")] + lines[1:],  # 書き換える
    lambda lines: lines[::-1],  # 並べ替える
])
def test_governance_log_must_be_append_only_from_merge_base(tmp_path, edit):
    repo, _, commit, gate = _governed_repo(tmp_path)
    lines = (repo / LOG_REL).read_text(encoding="utf-8").splitlines(keepends=True)
    commit({LOG_REL: "".join(edit(lines)), "doc/readme.md": "v2\n"})
    r = gate()
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "追記以外" in r.stderr
    assert "summary:" not in r.stdout


def test_policy_change_is_p1(tmp_path):
    _, _, commit, gate = _governed_repo(tmp_path)
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    policy["cooldown_rules"]["description"] = "説明だけを変える"
    commit({POLICY_REL: json.dumps(policy, ensure_ascii=False, indent=2) + "\n"})
    r = gate()
    assert r.returncode == 1, r.stderr
    assert f"BLOCK {POLICY_REL} (P1_structural)" in r.stderr


def test_bypass_cooldown_does_not_block_p2(tmp_path):
    _, _, commit, gate = _governed_repo(tmp_path)
    commit({"doc/readme.md": "v2\n"})
    r = gate("--bypass-cooldown")
    assert r.returncode == 0, r.stderr
    assert "summary: total=1 blocked=0" in r.stdout


def test_skill_name_change_is_p0_under_color_and_external_diff(tmp_path):
    _, git, commit, gate = _governed_repo(tmp_path)
    git("config", "color.ui", "always")
    git("config", "diff.external", "true")  # 出力の無い外部 diff
    commit({SKILL_REL: "---\nname: run-y\ndescription: x\n---\n本文\n"})
    r = gate("--report")
    assert r.returncode == 1, r.stderr
    cats = {c["path"]: c["category"] for c in json.loads(r.stdout)["changes"]}
    assert cats == {SKILL_REL: "P0_breaking"}
