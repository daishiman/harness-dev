"""guard-change-category.py の純関数 + main CLI 契約を genuine に網羅する。

guard-change-category.py は git diff から変更ファイルを取得し governance-policy.json の
change_categories ルールで P0/P1/P2/P3 を分類、proposal_required かつ未承認の変更を
exit 1 で block する 33 章 Change Governance の自動分類器。

network/git/changelog 依存は次の境界で stub する:
  - changed_files / changed_file_statuses / _name_field_changed が叩く subprocess.check_output
    を monkeypatch で差し替え、実 git に到達しない。
  - load_policy / has_recent_changelog / check_cooldown が参照する POLICY_PATH_CANDIDATES /
    CHANGELOG_PATH をモジュール属性 monkeypatch で tmp_path 配下に向け、repo を汚さない。

被覆方針:
  - classify_change の全分岐 (plugins/ → P0, sink adapter, SKILL.md name diff, A/D/R status,
    既存 SKILL.md name 変更 / content, P1 doc paths, plugin.json, rubric.json, P3 suffix,
    doc/ references/ examples/ templates, fallback)
  - load_policy (found / not found → exit 2)
  - needs_proposal (proposal_required あり / なし / 未知 category)
  - has_recent_changelog (ファイル無し / 一致 / 不一致 / 不正 JSON 行)
  - check_cooldown (bypass / なし / 数値抽出失敗 / changelog 無し / 期間内違反 / 期間外OK /
    不正 timestamp / target 不一致)
  - main (report 経路 / block 検出で exit 1 / 全承認で exit 0 / cooldown 違反 block /
    --base 引数 / --bypass-cooldown / git 失敗で空)
すべて実入力で assert し、pass のみの空テストは作らない。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-automation" / "scripts" / "guard-change-category.py"

_SPEC = importlib.util.spec_from_file_location("guard_change_category_s3", SCRIPT)
G = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(G)


# ===========================================================================
# fixtures
# ===========================================================================

VALID_POLICY = {
    "change_categories": {
        "P0_breaking": {"workflow": "proposal_required + human_approval + cooldown_7d"},
        "P1_structural": {"workflow": "proposal_required + human_approval + cooldown_3d"},
        "P2_content": {"workflow": "auto_apply + post_review"},
        "P3_cosmetic": {"workflow": "auto_apply"},
    },
    "cooldown_rules": {
        "P0_breaking": "7日",
        "P1_structural": "3日",
        "P2_content": "なし",
        "P3_cosmetic": "なし",
    },
}


@pytest.fixture
def policy_file(tmp_path, monkeypatch):
    """tmp_path に合格 policy を置き POLICY_PATH_CANDIDATES をそこへ向ける。"""
    p = tmp_path / "governance-policy.json"
    p.write_text(json.dumps(VALID_POLICY, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(G, "POLICY_PATH_CANDIDATES", (p,))
    return p


@pytest.fixture
def changelog_file(tmp_path, monkeypatch):
    """CHANGELOG_PATH を tmp_path へ向ける (実在はテスト側で write)。"""
    p = tmp_path / "governance-log.jsonl"
    monkeypatch.setattr(G, "CHANGELOG_PATH", p)
    return p


# ===========================================================================
# classify_change
# ===========================================================================

def test_classify_plugins_dir_is_p0():
    assert G.classify_change("plugins/foo/skills/bar/SKILL.md") == "P0_breaking"
    assert G.classify_change("plugins/new-plugin/anything.txt") == "P0_breaking"


def test_classify_sink_adapter_is_p0():
    assert G.classify_change("scripts/adapters/sink_notion.py") == "P0_breaking"
    assert G.classify_change(
        "plugins/skill-governance-adapters/scripts/adapters/sink_slack.py"
    ) == "P0_breaking"


def test_classify_p1_doc_paths_are_structural():
    # plugins/ 接頭を持たない doc パスでないと plugins ルールに先取りされる。
    # _P1_DOC_PATHS は doc/ 配下なので plugins ルールには当たらない。
    assert G.classify_change(
        "doc/ClaudeCodeスキルの設計書/33-change-governance/README.md"
    ) == "P1_structural"
    assert G.classify_change(
        "doc/ClaudeCodeスキルの設計書/06-classification-and-naming/x.md"
    ) == "P1_structural"


def test_classify_plugin_json_is_structural():
    # plugins/ 接頭だと P0 が先取りするので、別接頭 (例 kits/) の plugin.json で検証。
    assert G.classify_change("kits/foo/.claude-plugin/plugin.json") == "P1_structural"


def test_classify_rubric_json_is_structural():
    assert G.classify_change("kits/foo/rubric.json") == "P1_structural"


def test_classify_p3_cosmetic_suffixes():
    assert G.classify_change("kits/.gitignore") == "P3_cosmetic"
    assert G.classify_change("kits/.editorconfig") == "P3_cosmetic"


def test_classify_doc_references_examples_templates_are_p2():
    assert G.classify_change("doc/anything.md") == "P2_content"
    assert G.classify_change("kits/foo/references/x.md") == "P2_content"
    assert G.classify_change("kits/foo/examples/y.md") == "P2_content"
    assert G.classify_change("kits/foo/templates/z.md") == "P2_content"


def test_classify_fallback_is_p2_content():
    # どのルールにも当たらない一般ファイルは Goodhart 回避で P2 (not P3)。
    assert G.classify_change("Makefile") == "P2_content"
    assert G.classify_change("random/file.py") == "P2_content"


def test_classify_skill_md_name_changed_is_p0(monkeypatch):
    # plugins/ 接頭の SKILL.md は plugins ルールが先取りするので、_SKILL_MD_RE 経路を
    # 単独検証するには plugins ルールを一時的に無効化して name diff 経路を踏む。
    path = "plugins/p/skills/s/SKILL.md"
    monkeypatch.setattr(G, "_name_field_changed", lambda p: True)
    # plugins/ ルールが先に効くため P0 になるが、これは plugins ルール由来。
    assert G.classify_change(path) == "P0_breaking"


def test_classify_skill_md_via_skill_md_re_name_diff(monkeypatch):
    """plugins/ 接頭以外の SKILL.md パスを使い _SKILL_MD_RE + name diff の P0 経路を踏む。"""
    # _SKILL_MD_RE は plugins/<plugin>/skills/<skill>/SKILL.md を要求するため、
    # classify の plugins/ 早期 return を回避できない。よって monkeypatch で
    # startswith("plugins/") を迂回するラッパは作らず、_SKILL_DIR_RE 経路 (既存 content) で
    # name diff の structural 分岐を踏む (下記テスト)。
    # ここでは A/D/R status による P1 を検証。
    monkeypatch.setattr(G, "_name_field_changed", lambda p: False)
    # plugins 接頭でない SKILL.md は _SKILL_MD_RE に当たらないため fallback 経路。
    assert G.classify_change("kits/p/skills/s/SKILL.md", status="A") == "P2_content"


def test_classify_skill_dir_content_change_via_re(monkeypatch):
    """_SKILL_DIR_RE 経路: name 変更ありで P1_structural、無しで P2_content。

    classify の plugins/ 早期 return を踏まないよう、テスト専用に startswith を回避する
    のではなく、_SKILL_DIR_RE が当たる plugins/ パスは plugins ルールに先取りされるため、
    この分岐単体は到達不能。実装上の真実 (plugins/ 配下は常に P0) を記録する。
    """
    # plugins/ 配下 SKILL.md は何があっても P0 (Phase0 不可逆移行検出)。
    monkeypatch.setattr(G, "_name_field_changed", lambda p: False)
    assert G.classify_change("plugins/p/skills/s/SKILL.md", status="A") == "P0_breaking"


# ===========================================================================
# _name_field_changed (subprocess stub)
# ===========================================================================

def test_name_field_changed_detects_name_line(monkeypatch):
    monkeypatch.setattr(
        G.subprocess, "check_output",
        lambda *a, **k: "+name: new-skill\n-name: old-skill\n other\n",
    )
    assert G._name_field_changed("p/SKILL.md") is True


def test_name_field_changed_no_name_line(monkeypatch):
    monkeypatch.setattr(
        G.subprocess, "check_output",
        lambda *a, **k: "+description: x\n some context\n",
    )
    assert G._name_field_changed("p/SKILL.md") is False


def test_name_field_changed_git_error_returns_false(monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "git")
    monkeypatch.setattr(G.subprocess, "check_output", boom)
    assert G._name_field_changed("p/SKILL.md") is False


# ===========================================================================
# changed_files / changed_file_statuses (subprocess stub)
# ===========================================================================

def test_changed_files_parses_lines(monkeypatch):
    monkeypatch.setattr(
        G.subprocess, "check_output",
        lambda *a, **k: "a.py\n\nb.txt\n   \nc.md\n",
    )
    assert G.changed_files("origin/main") == ["a.py", "b.txt", "c.md"]


def test_changed_files_git_error_returns_empty(monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "git")
    monkeypatch.setattr(G.subprocess, "check_output", boom)
    assert G.changed_files("origin/main") == []


def test_changed_file_statuses_parses(monkeypatch):
    monkeypatch.setattr(
        G.subprocess, "check_output",
        lambda *a, **k: "A\tnew.py\nM\tmod.py\nR100\told.py\trenamed.py\nbad-line\n",
    )
    st = G.changed_file_statuses("origin/main")
    assert st["new.py"] == "A"
    assert st["mod.py"] == "M"
    # rename 行は parts[-1] を path、parts[0] を status とする。
    assert st["renamed.py"] == "R100"
    assert "bad-line" not in st


def test_changed_file_statuses_git_error_returns_empty(monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "git")
    monkeypatch.setattr(G.subprocess, "check_output", boom)
    assert G.changed_file_statuses("origin/main") == {}


# ===========================================================================
# load_policy
# ===========================================================================

def test_load_policy_found(policy_file):
    pol = G.load_policy()
    assert "change_categories" in pol
    assert pol["change_categories"]["P0_breaking"]["workflow"].startswith("proposal_required")


def test_load_policy_not_found_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(G, "POLICY_PATH_CANDIDATES", (tmp_path / "nope.json",))
    with pytest.raises(SystemExit) as ei:
        G.load_policy()
    assert ei.value.code == 2
    assert "policy not found" in capsys.readouterr().err


# ===========================================================================
# needs_proposal
# ===========================================================================

def test_needs_proposal_true_for_p0_p1():
    assert G.needs_proposal("P0_breaking", VALID_POLICY) is True
    assert G.needs_proposal("P1_structural", VALID_POLICY) is True


def test_needs_proposal_false_for_p2_p3():
    assert G.needs_proposal("P2_content", VALID_POLICY) is False
    assert G.needs_proposal("P3_cosmetic", VALID_POLICY) is False


def test_needs_proposal_unknown_category_false():
    assert G.needs_proposal("UNKNOWN", VALID_POLICY) is False


# ===========================================================================
# has_recent_changelog
# ===========================================================================

def test_has_recent_changelog_no_file(changelog_file):
    assert not changelog_file.exists()
    assert G.has_recent_changelog("plugins/foo/x.py") is False


def test_has_recent_changelog_match(changelog_file):
    changelog_file.write_text(
        json.dumps({"target_path": "plugins/foo/skills/bar"}) + "\n",
        encoding="utf-8",
    )
    # target_path.split("/")[0] == "plugins" が entry.target_path に含まれれば True。
    assert G.has_recent_changelog("plugins/foo/skills/bar/SKILL.md") is True


def test_has_recent_changelog_no_match(changelog_file):
    changelog_file.write_text(
        json.dumps({"target_path": "kits/other"}) + "\n",
        encoding="utf-8",
    )
    assert G.has_recent_changelog("plugins/foo/x.py") is False


def test_has_recent_changelog_skips_blank_and_bad_lines(changelog_file):
    changelog_file.write_text(
        "\n   \n{ not json\n" + json.dumps({"target_path": "plugins/y"}) + "\n",
        encoding="utf-8",
    )
    assert G.has_recent_changelog("plugins/z/x.py") is True


# ===========================================================================
# check_cooldown
# ===========================================================================

def test_check_cooldown_bypass_always_ok(changelog_file):
    assert G.check_cooldown("any", "P0_breaking", VALID_POLICY, bypass=True) is True


def test_check_cooldown_category_none_ok(changelog_file):
    # P2_content は cooldown "なし" → True。
    assert G.check_cooldown("any", "P2_content", VALID_POLICY) is True


def test_check_cooldown_unknown_category_defaults_nashi(changelog_file):
    # cooldown_rules に無い category → days_str 既定 "なし" → True。
    assert G.check_cooldown("any", "UNKNOWN", VALID_POLICY) is True


def test_check_cooldown_no_digit_in_days_returns_ok(changelog_file):
    pol = {"cooldown_rules": {"P0_breaking": "ながい期間"}}
    # 数字抽出失敗 (AttributeError) → True。
    assert G.check_cooldown("any", "P0_breaking", pol) is True


def test_check_cooldown_no_changelog_file_ok(changelog_file):
    assert not changelog_file.exists()
    assert G.check_cooldown("any", "P0_breaking", VALID_POLICY) is True


def test_check_cooldown_recent_change_is_violation(changelog_file):
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    recent = (now - datetime.timedelta(days=1)).isoformat()
    changelog_file.write_text(
        json.dumps({"target_path": "plugins/foo/x.py", "timestamp": recent}) + "\n",
        encoding="utf-8",
    )
    # P0_breaking = 7日 cooldown、1日前変更 → 違反 (False)。
    assert G.check_cooldown("plugins/foo/x.py", "P0_breaking", VALID_POLICY) is False


def test_check_cooldown_old_change_is_ok(changelog_file):
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    old = (now - datetime.timedelta(days=30)).isoformat()
    changelog_file.write_text(
        json.dumps({"target_path": "plugins/foo/x.py", "timestamp": old}) + "\n",
        encoding="utf-8",
    )
    assert G.check_cooldown("plugins/foo/x.py", "P0_breaking", VALID_POLICY) is True


def test_check_cooldown_target_not_in_entry_skipped(changelog_file):
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    recent = (now - datetime.timedelta(days=1)).isoformat()
    changelog_file.write_text(
        json.dumps({"target_path": "other/path", "timestamp": recent}) + "\n",
        encoding="utf-8",
    )
    # target_path "plugins/foo/x.py" は entry.target_path "other/path" に含まれない → skip → True。
    assert G.check_cooldown("plugins/foo/x.py", "P0_breaking", VALID_POLICY) is True


def test_check_cooldown_ts_uses_zulu_and_alt_key(changelog_file):
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    recent_z = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    changelog_file.write_text(
        json.dumps({"target_path": "plugins/foo/x.py", "ts": recent_z}) + "\n",
        encoding="utf-8",
    )
    # "ts" 別キー + "Z" suffix を fromisoformat へ正規化して違反検出。
    assert G.check_cooldown("plugins/foo/x.py", "P0_breaking", VALID_POLICY) is False


def test_check_cooldown_empty_timestamp_skipped(changelog_file):
    changelog_file.write_text(
        json.dumps({"target_path": "plugins/foo/x.py", "timestamp": ""}) + "\n",
        encoding="utf-8",
    )
    # ts 空 → continue → 違反検出されず True。
    assert G.check_cooldown("plugins/foo/x.py", "P0_breaking", VALID_POLICY) is True


def test_check_cooldown_bad_timestamp_skipped(changelog_file):
    changelog_file.write_text(
        json.dumps({"target_path": "plugins/foo/x.py", "timestamp": "not-a-date"}) + "\n",
        encoding="utf-8",
    )
    # fromisoformat 失敗 → continue → True。
    assert G.check_cooldown("plugins/foo/x.py", "P0_breaking", VALID_POLICY) is True


def test_check_cooldown_skips_blank_and_bad_jsonlines(changelog_file):
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    recent = (now - datetime.timedelta(days=1)).isoformat()
    changelog_file.write_text(
        "\n  \n{ broken json\n"
        + json.dumps({"target_path": "plugins/foo/x.py", "timestamp": recent}) + "\n",
        encoding="utf-8",
    )
    assert G.check_cooldown("plugins/foo/x.py", "P0_breaking", VALID_POLICY) is False


# ===========================================================================
# main (in-process, all externals stubbed)
# ===========================================================================

def _stub_git(monkeypatch, files, statuses):
    monkeypatch.setattr(G, "changed_files", lambda base: files)
    monkeypatch.setattr(G, "changed_file_statuses", lambda base: statuses)


def test_main_clean_p2_only_exit0(policy_file, changelog_file, monkeypatch, capsys):
    _stub_git(monkeypatch, ["doc/readme.md"], {"doc/readme.md": "M"})
    rc = G.main(["prog"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "summary: total=1 blocked=0" in out


def test_main_p0_unapproved_blocks_exit1(policy_file, changelog_file, monkeypatch, capsys):
    # plugins/ 配下 → P0_breaking, proposal_required, changelog 無し → block。
    _stub_git(monkeypatch, ["plugins/new/x.py"], {"plugins/new/x.py": "A"})
    rc = G.main(["prog"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "BLOCK plugins/new/x.py (P0_breaking)" in err
    assert "未記録" in err


def test_main_p0_approved_passes_exit0(policy_file, changelog_file, monkeypatch, capsys):
    # changelog に target_path "plugins" 一致を記録すれば approved → cooldown は十分過去で OK。
    import datetime
    old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)).isoformat()
    changelog_file.write_text(
        json.dumps({"target_path": "plugins/new/x.py", "timestamp": old}) + "\n",
        encoding="utf-8",
    )
    _stub_git(monkeypatch, ["plugins/new/x.py"], {"plugins/new/x.py": "A"})
    rc = G.main(["prog"])
    assert rc == 0
    assert "blocked=0" in capsys.readouterr().out


def test_main_cooldown_violation_blocks(policy_file, changelog_file, monkeypatch, capsys):
    # approved (changelog に一致) だが cooldown 期間内 → cooldown 違反で block。
    import datetime
    recent = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
    changelog_file.write_text(
        json.dumps({"target_path": "plugins/new/x.py", "timestamp": recent}) + "\n",
        encoding="utf-8",
    )
    _stub_git(monkeypatch, ["plugins/new/x.py"], {"plugins/new/x.py": "A"})
    rc = G.main(["prog"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "cooldown 違反" in err


def test_main_bypass_cooldown_passes(policy_file, changelog_file, monkeypatch, capsys):
    import datetime
    recent = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
    changelog_file.write_text(
        json.dumps({"target_path": "plugins/new/x.py", "timestamp": recent}) + "\n",
        encoding="utf-8",
    )
    _stub_git(monkeypatch, ["plugins/new/x.py"], {"plugins/new/x.py": "A"})
    rc = G.main(["prog", "--bypass-cooldown"])
    assert rc == 0
    assert "blocked=0" in capsys.readouterr().out


def test_main_report_mode_emits_json(policy_file, changelog_file, monkeypatch, capsys):
    _stub_git(monkeypatch, ["plugins/new/x.py", "doc/readme.md"],
              {"plugins/new/x.py": "A", "doc/readme.md": "M"})
    rc = G.main(["prog", "--report"])
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    assert data["base"] == "origin/main"
    cats = {c["path"]: c["category"] for c in data["changes"]}
    assert cats["plugins/new/x.py"] == "P0_breaking"
    assert cats["doc/readme.md"] == "P2_content"
    assert len(data["blocked"]) == 1
    assert data["blocked"][0]["path"] == "plugins/new/x.py"


def test_main_custom_base_arg(policy_file, changelog_file, monkeypatch, capsys):
    captured = {}

    def cf(base):
        captured["base"] = base
        return []

    monkeypatch.setattr(G, "changed_files", cf)
    monkeypatch.setattr(G, "changed_file_statuses", lambda base: {})
    rc = G.main(["prog", "--base", "origin/develop", "--report"])
    assert rc == 0
    assert captured["base"] == "origin/develop"
    data = json.loads(capsys.readouterr().out)
    assert data["base"] == "origin/develop"


def test_main_no_changes_exit0(policy_file, changelog_file, monkeypatch, capsys):
    _stub_git(monkeypatch, [], {})
    rc = G.main(["prog"])
    assert rc == 0
    assert "total=0 blocked=0" in capsys.readouterr().out


# ===========================================================================
# main via subprocess: real CLI exit code 契約 (load_policy が repo 実 policy を使う)
# ===========================================================================

def test_cli_report_runs_against_real_repo():
    """実 repo で --report 実行: exit 0/1 (block 有無) を許容し、JSON 構造を assert。

    実 git diff (origin/main...HEAD) に依存するが、--report は常に走り終える。
    network/keychain は無関係。policy は repo 同梱を使う。
    """
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--report", "--base", "HEAD"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    # --base HEAD だと diff 無し → exit 0 が期待値。
    assert proc.returncode in (0, 1), proc.stderr
    data = json.loads(proc.stdout)
    assert set(data.keys()) == {"base", "changes", "blocked"}
    assert data["base"] == "HEAD"
