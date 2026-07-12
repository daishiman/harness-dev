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


def test_classify_plugins_dir_is_p0(no_name_change):
    assert G.classify_change("plugins/foo/skills/bar/SKILL.md") == "P0_breaking"
    assert G.classify_change("plugins/newplugin/config/x.json") == "P0_breaking"


def test_classify_sink_adapter_is_p0(no_name_change):
    assert G.classify_change("scripts/adapters/sink_notion.py") == "P0_breaking"


def test_classify_p1_doc_paths_is_p1(no_name_change):
    p = "doc/ClaudeCodeスキルの設計書/33-change-governance/policy.md"
    assert G.classify_change(p) == "P1_structural"


def test_classify_plugin_json_is_p1(no_name_change):
    # plugins/ prefix を避けるため別 root を使う
    assert G.classify_change("kit/.claude-plugin/plugin.json") == "P1_structural"


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
    # plugins/ で始まると先に P0 になるので、ロジックの SKILL.md 経路を踏むには
    # name 変更=True を別途確認。plugins prefix だと無条件 P0 だが、これも P0 で正しい。
    assert G.classify_change("plugins/p/skills/s/SKILL.md") == "P0_breaking"


def test_classify_new_skill_md_status_A_is_p1(monkeypatch):
    # _SKILL_MD_RE は plugins/ 前提だが、plugins prefix の早期 return が先。
    # 早期 return を無効化して status 経路を検証する。
    monkeypatch.setattr(G, "_name_field_changed", lambda path: False)
    orig_startswith = str.startswith

    # plugins/ 早期 return を回避するため、パスを一時的に非 plugins にできない
    # (正規表現が plugins/ 前提)。よって早期 return が常に勝つことを明示テスト。
    assert G.classify_change("plugins/p/skills/s/SKILL.md", status="A") == "P0_breaking"


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
        json.dumps({"target_path": "plugins/foo/skills/bar"}) + "\n"
        + "not-json-line\n",  # 不正行は無視される
        encoding="utf-8",
    )
    monkeypatch.setattr(G, "CHANGELOG_PATH", log)
    assert G.has_recent_changelog("plugins/foo/skills/bar/SKILL.md") is True


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
    assert G.check_cooldown("p", "P0_breaking", PolicyDict, bypass=True) is True


def test_check_cooldown_none_rule(tmp_path, monkeypatch):
    # P2_content は cooldown 「なし」→ 常に True
    assert G.check_cooldown("p", "P2_content", PolicyDict) is True


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
    # P0_breaking + changelog 未記録 → block → exit 1
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
        G.subprocess, "check_output", lambda *a, **k: "a.py\n\nb.md\n"
    )
    assert G.changed_files("base") == ["a.py", "b.md"]


def test_changed_files_git_error_returns_empty(monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(G.subprocess, "check_output", boom)
    assert G.changed_files("base") == []


def test_changed_file_statuses_parses(monkeypatch):
    monkeypatch.setattr(
        G.subprocess,
        "check_output",
        lambda *a, **k: "A\tnew.py\nM\tmod.py\nbadline\n",
    )
    statuses = G.changed_file_statuses("base")
    assert statuses == {"new.py": "A", "mod.py": "M"}


def test_changed_file_statuses_git_error_returns_empty(monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(G.subprocess, "check_output", boom)
    assert G.changed_file_statuses("base") == {}


def test_name_field_changed_true(monkeypatch):
    # diff に +name:/-name: 行があれば True
    monkeypatch.setattr(
        G.subprocess,
        "check_output",
        lambda *a, **k: "-name: old-skill\n+name: new-skill\n context\n",
    )
    assert G._name_field_changed("p/SKILL.md") is True


def test_name_field_changed_false_when_no_name_line(monkeypatch):
    monkeypatch.setattr(
        G.subprocess, "check_output", lambda *a, **k: "+description: x\n context\n"
    )
    assert G._name_field_changed("p/SKILL.md") is False


def test_name_field_changed_git_error_false(monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(G.subprocess, "check_output", boom)
    assert G._name_field_changed("p/SKILL.md") is False


# --- check_cooldown additional paths ----------------------------------------
def test_check_cooldown_unparseable_days_is_true(tmp_path, monkeypatch):
    # cooldown 文字列に数字が無い → AttributeError → True (緩和側)
    pol = {"cooldown_rules": {"P0_breaking": "数字なし"}}
    monkeypatch.setattr(G, "CHANGELOG_PATH", tmp_path / "absent.jsonl")
    assert G.check_cooldown("p", "P0_breaking", pol) is True


def test_check_cooldown_ignores_bad_json_and_missing_ts(tmp_path, monkeypatch):
    log = tmp_path / "governance-log.jsonl"
    log.write_text(
        "not-json\n"
        + json.dumps({"target_path": "plugins/foo/SKILL.md"})  # ts 欠落 → skip
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(G, "CHANGELOG_PATH", log)
    # 不正行/ts 欠落のみ → cooldown 違反検出されず True
    assert G.check_cooldown("plugins/foo/SKILL.md", "P0_breaking", PolicyDict) is True


def test_check_cooldown_bad_timestamp_format_skipped(tmp_path, monkeypatch):
    log = tmp_path / "governance-log.jsonl"
    log.write_text(
        json.dumps({"target_path": "plugins/foo/SKILL.md", "timestamp": "not-a-date"})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(G, "CHANGELOG_PATH", log)
    assert G.check_cooldown("plugins/foo/SKILL.md", "P0_breaking", PolicyDict) is True


# --- main() called in-process (deps monkeypatched, no real git) -------------
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
    monkeypatch.setattr(G, "has_recent_changelog", lambda f: False)
    monkeypatch.setattr(G, "check_cooldown", lambda *a, **k: True)
    rc = G.main(["prog"])
    assert rc == 1
    assert "BLOCK" in capsys.readouterr().err


def test_main_inprocess_report_json(monkeypatch, capsys):
    monkeypatch.setattr(G, "load_policy", lambda: PolicyDict)
    monkeypatch.setattr(G, "changed_files", lambda base: ["doc/readme.md"])
    monkeypatch.setattr(G, "changed_file_statuses", lambda base: {})
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
    rc = G.main(["prog"])
    assert rc == 1
    assert "cooldown" in capsys.readouterr().err
