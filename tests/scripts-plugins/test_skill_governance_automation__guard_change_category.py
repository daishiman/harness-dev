"""guard-change-category.py の純関数 + main CLI 契約を genuine に網羅する。

guard-change-category.py は git diff から変更ファイルを取得し governance-policy.json の
change_categories ルールで P0/P1/P2/P3 を分類、proposal_required かつ未承認の変更を
exit 1 で block する 33 章 Change Governance の自動分類器。

network/git/changelog 依存は次の境界で stub する:
  - changed_files / changed_file_statuses / _name_field_changed が叩く subprocess.check_output
    を monkeypatch で差し替え、実 git に到達しない。
  - load_policy / has_recent_changelog / check_cooldown が参照する POLICY_PATH_CANDIDATES /
    CHANGELOG_PATH をモジュール属性 monkeypatch で tmp_path 配下に向け、repo を汚さない。
  - main の in-process テストは _merge_base / _blob_at も差し替え、merge-base の policy と
    governance-log の追記だけの確認を実 git に届かせない（その確認は tmp の git repo で行う）。

被覆方針:
  - classify_change の全分岐 (新規plugin → P0, sink adapter, SKILL.md name diff, A/D/R status,
    既存 SKILL.md name 変更 / content, P1 doc paths, plugin.json, rubric.json, P3 suffix,
    doc/ references/ examples/ templates, fallback)
  - load_policy (found / not found → exit 2)
  - needs_proposal (proposal_required あり / なし / 未知 category)
  - has_recent_changelog (ファイル無し / 一致 / 不一致 / 不正 JSON 行)
  - check_cooldown (bypass / なし / 数値抽出失敗 / changelog 無し / 期間内違反 / 期間外OK /
    不正 timestamp / target 不一致)
  - main (report 経路 / block 検出で exit 1 / 全承認で exit 0 / cooldown 違反 block /
    --base 引数 / --bypass-cooldown / git 失敗で exit 2)
  - 判定の拠り所 (tmp の git repo): 同じ PR で policy を auto_apply に下げても plugin.json は
    BLOCK / governance-log の行を消すと exit 2 / policy 自身の変更は P1
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

def test_classify_plugin_content_and_new_plugin_distinct():
    assert G.classify_change("plugins/foo/skills/bar/SKILL.md", name_changed=False) == "P2_content"
    assert G.classify_change("plugins/new-plugin/anything.txt", new_plugin=True) == "P0_breaking"


def test_classify_sink_adapter_is_p0():
    assert G.classify_change("scripts/adapters/sink_notion.py") == "P0_breaking"
    assert G.classify_change(
        "plugins/skill-governance-adapters/scripts/adapters/sink_slack.py"
    ) == "P0_breaking"


def test_classify_p1_doc_paths_are_structural():
    assert G.classify_change(
        "doc/ClaudeCodeスキルの設計書/33-change-governance/README.md"
    ) == "P1_structural"
    assert G.classify_change(
        "doc/ClaudeCodeスキルの設計書/06-classification-and-naming/x.md"
    ) == "P1_structural"


def test_classify_plugin_json_is_structural():
    # 既存 plugin manifest の変更は構造変更。
    assert G.classify_change("kits/foo/.claude-plugin/plugin.json") == "P1_structural"


def test_classify_rubric_json_is_structural():
    assert G.classify_change("kits/foo/rubric.json") == "P1_structural"


def test_classify_governance_policy_is_structural():
    # ゲート自身の判定の拠り所。fallback の P2（auto_apply）に落とさない。
    assert G.classify_change(G.POLICY_REL_PATH) == "P1_structural"
    assert G.classify_change("plugins/skill-governance-config/config/other.json") == "P2_content"


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
    monkeypatch.setattr(G, "_name_field_changed", lambda p: True)
    assert G.classify_change("plugins/p/skills/s/SKILL.md") == "P0_breaking"


def test_classify_non_plugin_skill_md_is_fallback():
    assert G.classify_change("kits/p/skills/s/SKILL.md", status="A") == "P2_content"


def test_classify_skill_lifecycle_and_name_changes(monkeypatch):
    monkeypatch.setattr(G, "_name_field_changed", lambda p: False)
    path = "plugins/p/skills/s/SKILL.md"
    for status in ("A", "D", "R100"):
        assert G.classify_change(path, status=status) == "P1_structural"
    assert G.classify_change(path, name_changed=False) == "P2_content"
    assert G.classify_change(path, name_changed=True) == "P0_breaking"


# ===========================================================================
# _name_field_changed (subprocess stub)
# ===========================================================================

_DIFF_HEAD = (
    "diff --git a/p/SKILL.md b/p/SKILL.md\nindex 1..2 100644\n"
    "--- a/p/SKILL.md\n+++ b/p/SKILL.md\n@@ -1,6 +1,6 @@\n"
)


def test_name_field_changed_detects_name_line(monkeypatch):
    monkeypatch.setattr(
        G.subprocess, "check_output",
        lambda *a, **k: _DIFF_HEAD + " ---\n-name: old-skill\n+name: new-skill\n description: x\n ---\n body\n",
    )
    assert G._name_field_changed("p/SKILL.md") is True


def test_name_field_changed_no_name_line(monkeypatch):
    monkeypatch.setattr(
        G.subprocess, "check_output",
        lambda *a, **k: _DIFF_HEAD + " ---\n name: s\n-description: x\n+description: y\n ---\n",
    )
    assert G._name_field_changed("p/SKILL.md") is False


def test_name_field_changed_ignores_name_lines_outside_frontmatter(monkeypatch):
    # 本文のコードブロックにある name: 行の変更は公開名の変更ではない（P0 にしない）。
    monkeypatch.setattr(
        G.subprocess, "check_output",
        lambda *a, **k: _DIFF_HEAD + " ---\n name: s\n ---\n ```yaml\n-name: old-example\n+name: new-example\n ```\n",
    )
    assert G._name_field_changed("p/SKILL.md") is False


def test_name_field_changed_ignores_color_and_external_diff(monkeypatch):
    # 手元の color.ui=always や diff.external で hunk を読み違えないよう、git diff に明示して渡す。
    seen = []
    monkeypatch.setattr(G.subprocess, "check_output", lambda cmd, **k: seen.append(cmd) or "")
    G._name_field_changed("p/SKILL.md", "base...HEAD")
    assert {"--no-color", "--no-ext-diff", "--no-textconv"} <= set(seen[0])
    assert seen[0][-3:] == ["base...HEAD", "--", "p/SKILL.md"]


def test_name_field_changed_no_hunk_is_false(monkeypatch):
    monkeypatch.setattr(G.subprocess, "check_output", lambda *a, **k: "")
    assert G._name_field_changed("p/SKILL.md") is False


def test_name_field_changed_git_error_raises(monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "git")
    monkeypatch.setattr(G.subprocess, "check_output", boom)
    with pytest.raises(G.GitDiffError):
        G._name_field_changed("p/SKILL.md")


# ===========================================================================
# changed_files / changed_file_statuses (subprocess stub)
# ===========================================================================

def test_changed_files_parses_lines(monkeypatch):
    calls = []

    def fake(cmd, **k):
        calls.append(cmd)
        return "M\0a.py\0A\0doc/日本語 の名前.md\0D\0c.md\0"
    monkeypatch.setattr(G.subprocess, "check_output", fake)
    # -z で読むので、空白や非 ASCII のパスも quote されずにそのまま返る。
    assert G.changed_files("origin/main") == ["a.py", "doc/日本語 の名前.md", "c.md"]
    assert "-z" in calls[0]


def test_changed_files_git_error_raises(monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "git")
    monkeypatch.setattr(G.subprocess, "check_output", boom)
    with pytest.raises(G.GitDiffError):
        G.changed_files("origin/main")


def test_changed_file_statuses_parses(monkeypatch):
    monkeypatch.setattr(
        G.subprocess, "check_output",
        lambda *a, **k: "A\0new.py\0M\0mod.py\0R100\0old.py\0renamed.py\0C75\0src.py\0copy.py\0",
    )
    st = G.changed_file_statuses("origin/main")
    assert st["new.py"] == "A"
    assert st["mod.py"] == "M"
    # rename は元のパスも変更に数える（元のパスは消えている）。copy の元は変わらないので数えない。
    assert st["renamed.py"] == "R100"
    assert st["old.py"] == "R100"
    assert st["copy.py"] == "C75"
    assert "src.py" not in st


def test_changed_file_statuses_malformed_output_raises(monkeypatch):
    # パスの欠けた出力を空の差分として読まない。
    monkeypatch.setattr(G.subprocess, "check_output", lambda *a, **k: "M\0a.py\0R100\0only-old.py\0")
    with pytest.raises(G.GitDiffError):
        G.changed_file_statuses("origin/main")


def test_changed_file_statuses_git_error_raises(monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "git")
    monkeypatch.setattr(G.subprocess, "check_output", boom)
    with pytest.raises(G.GitDiffError):
        G.changed_file_statuses("origin/main")


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
    changelog_file.write_text(json.dumps({"target_path": "plugins/foo/skills/bar", "approver": "reviewer", "proposal_id": "selected"}) + "\n", encoding="utf-8")
    assert not G.has_recent_changelog("plugins/foo/skills/bar/SKILL.md")
    assert G.has_recent_changelog("plugins/foo/skills/bar/SKILL.md", proposal_id="selected")
    assert not G.has_recent_changelog("plugins/foo/skills/bar-extra/SKILL.md", proposal_id="selected")


def test_has_recent_changelog_no_match(changelog_file):
    changelog_file.write_text(
        json.dumps({"target_path": "kits/other"}) + "\n",
        encoding="utf-8",
    )
    assert G.has_recent_changelog("plugins/foo/x.py") is False


def test_has_recent_changelog_skips_blank_lines_and_rejects_bad_lines(changelog_file):
    entry = json.dumps({"target_path": "plugins/y", "approver": "reviewer", "proposal_id": "selected"})
    changelog_file.write_text("\n   \n" + entry + "\n", encoding="utf-8")
    assert G.has_recent_changelog("plugins/y/x.py", proposal_id="selected")
    assert not G.has_recent_changelog("plugins/z/x.py", proposal_id="selected")
    # 壊れた行は黙って飛ばさない（以前の変更の行が壊れると cooldown が素通りになる）
    changelog_file.write_text("\n   \n{ not json\n" + entry + "\n", encoding="utf-8")
    with pytest.raises(G.ConfigError, match="3 行目"):
        G.has_recent_changelog("plugins/y/x.py", proposal_id="selected")


# ===========================================================================
# check_cooldown
# ===========================================================================

def test_check_cooldown_bypass_has_no_effect_without_cooldown(changelog_file):
    # cooldown「なし」の分類では --bypass-cooldown の有無で結果を変えない。
    assert G.check_cooldown("doc/readme.md", "P2_content", VALID_POLICY, bypass=True)
    assert G.check_cooldown("x/.gitignore", "P3_cosmetic", VALID_POLICY, bypass=True)
    assert not G.check_cooldown("doc/readme.md", "P1_structural", VALID_POLICY, bypass=True)


def test_check_cooldown_bypass_requires_approved_incident(changelog_file):
    assert not G.check_cooldown("any", "P0_breaking", VALID_POLICY, bypass=True)
    entry = {"target_path": "any", "approver": "reviewer", "proposal_id": "selected", "incident_fix": True}
    changelog_file.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    assert G.check_cooldown("any", "P0_breaking", VALID_POLICY, bypass=True, proposal_id="selected")
    entry["incident_fix"] = False
    changelog_file.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    assert not G.check_cooldown("any", "P0_breaking", VALID_POLICY, bypass=True, proposal_id="selected")


def test_check_cooldown_category_none_ok(changelog_file):
    # P2_content は cooldown "なし" → True。
    assert G.check_cooldown("any", "P2_content", VALID_POLICY) is True


def test_check_cooldown_unknown_category_defaults_nashi(changelog_file):
    # cooldown_rules に無い category → days_str 既定 "なし" → True。
    assert G.check_cooldown("any", "UNKNOWN", VALID_POLICY) is True


def test_check_cooldown_no_digit_in_days_fails_closed(changelog_file):
    pol = {"cooldown_rules": {"P0_breaking": "ながい期間"}}
    # 日数を読めない値を cooldown なしに畳まない。
    with pytest.raises(G.ConfigError):
        G.check_cooldown("any", "P0_breaking", pol)


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


@pytest.mark.parametrize("bad", ["not-a-date", 20261010])
def test_check_cooldown_bad_timestamp_fails_closed(changelog_file, bad):
    changelog_file.write_text(
        json.dumps({"target_path": "plugins/foo/x.py", "timestamp": bad}) + "\n",
        encoding="utf-8",
    )
    # 読めない timestamp を「以前の変更なし」に畳まない。
    with pytest.raises(G.ConfigError):
        G.check_cooldown("plugins/foo/x.py", "P0_breaking", VALID_POLICY)


def test_check_cooldown_skips_blank_lines_and_rejects_bad_jsonlines(changelog_file):
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    recent = json.dumps({"target_path": "plugins/foo/x.py",
                         "timestamp": (now - datetime.timedelta(days=1)).isoformat()})
    changelog_file.write_text("\n  \n" + recent + "\n", encoding="utf-8")
    assert G.check_cooldown("plugins/foo/x.py", "P0_breaking", VALID_POLICY) is False
    for bad in ("{ broken json", "[1, 2]", '"text"'):
        changelog_file.write_text("\n  \n" + bad + "\n" + recent + "\n", encoding="utf-8")
        with pytest.raises(G.ConfigError, match="3 行目"):
            G.check_cooldown("plugins/foo/x.py", "P0_breaking", VALID_POLICY)


def test_entries_do_not_split_json_on_unicode_line_separators(changelog_file):
    # splitlines だと U+2028 で行が割れて、正しい行を壊れた行と取り違える。
    entry = {"target_path": "plugins/y", "approver": "reviewer", "proposal_id": "p",
             "note": "a\u2028b\u0085c"}
    changelog_file.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")
    assert G.has_recent_changelog("plugins/y/x.py", proposal_id="p")


# ===========================================================================
# main (in-process, all externals stubbed)
# ===========================================================================

def _stub_git(monkeypatch, files, statuses):
    monkeypatch.setattr(G, "changed_files", lambda base: files)
    monkeypatch.setattr(G, "changed_file_statuses", lambda base: statuses)
    # merge-base の policy と governance-log は無いものとして、tmp の file で判定させる
    monkeypatch.setattr(G, "_merge_base", lambda base: "MERGE_BASE")
    monkeypatch.setattr(G, "_blob_at", lambda rev, path: None)


def test_main_clean_p2_only_exit0(policy_file, changelog_file, monkeypatch, capsys):
    _stub_git(monkeypatch, ["doc/readme.md"], {"doc/readme.md": "M"})
    rc = G.main(["prog"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "summary: total=1 blocked=0" in out


def test_main_p0_unapproved_blocks_exit1(policy_file, changelog_file, monkeypatch, capsys):
    # sink adapter interface → P0_breaking、承認なしで block。
    _stub_git(monkeypatch, ["scripts/adapters/sink_new.py"], {"scripts/adapters/sink_new.py": "A"})
    rc = G.main(["prog"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "BLOCK scripts/adapters/sink_new.py (P0_breaking)" in err
    assert "未記録" in err


def test_main_p0_approved_passes_exit0(policy_file, changelog_file, monkeypatch, capsys):
    # 明示的に選んだ承認済みproposalに束縛し、以前のcooldownを保持する。
    import datetime
    old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)).isoformat()
    changelog_file.write_text(
        json.dumps({"target_path": "scripts/adapters/sink_new.py", "timestamp": old, "approver": "reviewer", "proposal_id": "selected"}) + "\n",
        encoding="utf-8",
    )
    _stub_git(monkeypatch, ["scripts/adapters/sink_new.py"], {"scripts/adapters/sink_new.py": "A"})
    rc = G.main(["prog", "--proposal-id", "selected"])
    assert rc == 0
    assert "blocked=0" in capsys.readouterr().out


def test_main_cooldown_violation_blocks(policy_file, changelog_file, monkeypatch, capsys):
    # approved (changelog に一致) だが cooldown 期間内 → cooldown 違反で block。
    import datetime
    recent = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
    changelog_file.write_text(
        json.dumps({"target_path": "scripts/adapters/sink_new.py", "timestamp": recent, "approver": "reviewer", "proposal_id": "previous"}) + "\n" + json.dumps({"target_path": "scripts/adapters/sink_new.py", "approver": "reviewer", "proposal_id": "selected"}) + "\n",
        encoding="utf-8",
    )
    _stub_git(monkeypatch, ["scripts/adapters/sink_new.py"], {"scripts/adapters/sink_new.py": "A"})
    rc = G.main(["prog", "--proposal-id", "selected"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "cooldown 違反" in err


def test_main_bypass_cooldown_passes(policy_file, changelog_file, monkeypatch, capsys):
    import datetime
    recent = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
    target = "scripts/adapters/sink_new.py"
    previous = {"target_path": target, "timestamp": recent}
    current = {"target_path": target, "timestamp": recent, "proposal_id": "selected", "approver": "reviewer", "incident_fix": True}
    changelog_file.write_text(json.dumps(previous) + "\n" + json.dumps(current) + "\n", encoding="utf-8")
    _stub_git(monkeypatch, [target], {target: "M"})
    assert G.main(["prog", "--proposal-id", "selected", "--bypass-cooldown"]) == 0
    assert "blocked=0" in capsys.readouterr().out


def test_main_bypass_cooldown_on_p2_passes(policy_file, changelog_file, monkeypatch, capsys):
    # cooldown の無い P2 では、incident_fix の承認が無くても --bypass-cooldown で止めない。
    _stub_git(monkeypatch, ["doc/readme.md"], {"doc/readme.md": "M"})
    assert G.main(["prog", "--bypass-cooldown"]) == 0
    assert "blocked=0" in capsys.readouterr().out


def test_main_bypass_without_incident_names_the_flag(policy_file, changelog_file, monkeypatch, capsys):
    target = "scripts/adapters/sink_new.py"
    changelog_file.write_text(json.dumps(
        {"target_path": target, "approver": ["a", "b"], "proposal_id": "selected"}) + "\n", encoding="utf-8")
    _stub_git(monkeypatch, [target], {target: "M"})
    assert G.main(["prog", "--proposal-id", "selected", "--bypass-cooldown"]) == 1
    err = capsys.readouterr().err
    assert "--bypass-cooldown を使えない" in err and "incident_fix" in err


def test_main_broken_changelog_line_exits_2(policy_file, changelog_file, monkeypatch, capsys):
    _stub_git(monkeypatch, ["doc/readme.md"], {"doc/readme.md": "M"})
    changelog_file.write_text('{"target_path": "doc/readme.md"}\n{ broken\n', encoding="utf-8")
    assert G.main(["prog"]) == 2
    captured = capsys.readouterr()
    assert "2 行目が JSON として読めない" in captured.err
    assert "summary:" not in captured.out


def test_main_report_mode_emits_json(policy_file, changelog_file, monkeypatch, capsys):
    _stub_git(monkeypatch, ["scripts/adapters/sink_new.py", "doc/readme.md"],
              {"scripts/adapters/sink_new.py": "A", "doc/readme.md": "M"})
    rc = G.main(["prog", "--report"])
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    assert data["base"] == "origin/main"
    cats = {c["path"]: c["category"] for c in data["changes"]}
    assert cats["scripts/adapters/sink_new.py"] == "P0_breaking"
    assert cats["doc/readme.md"] == "P2_content"
    assert len(data["blocked"]) == 1
    assert data["blocked"][0]["path"] == "scripts/adapters/sink_new.py"


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


def test_main_git_failure_exits_2_not_empty_pass(policy_file, changelog_file, monkeypatch, capsys):
    """base が解決できない等で git diff が落ちたら、空の差分として exit 0 にしない。"""
    def boom(*a, **k):
        raise subprocess.CalledProcessError(128, "git")
    monkeypatch.setattr(G.subprocess, "check_output", boom)
    rc = G.main(["prog", "--base", "no-such-ref"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "ERROR: git diff" in captured.err
    assert "summary:" not in captured.out


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


# ===========================================================================
# review A の指摘への回帰テスト
# ===========================================================================

def _git_env(tmp_path):
    """利用者の global 設定（core.quotePath=false など）を読まない git 環境。"""
    empty = tmp_path / "empty.gitconfig"
    empty.write_text("", encoding="utf-8")
    env = dict(__import__("os").environ, GIT_CONFIG_GLOBAL=str(empty), GIT_CONFIG_NOSYSTEM="1",
               PYTHONDONTWRITEBYTECODE="1")
    return env


def test_cli_classifies_non_ascii_paths_without_user_git_config(tmp_path):
    """core.quotePath が既定 (true) でも、日本語のパスを quote された文字列として P2 に落とさない。"""
    env = _git_env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                       cwd=repo, env=env, check=True, capture_output=True)

    git("init", "-q")
    git("config", "core.quotePath", "true")
    doc33 = repo / "doc" / "ClaudeCodeスキルの設計書" / "33-change-governance"
    doc27 = repo / "doc" / "ClaudeCodeスキルの設計書" / "27-rubric-governance-runbook"
    doc33.mkdir(parents=True)
    doc27.mkdir(parents=True)
    (doc33 / "README.md").write_text("v1\n", encoding="utf-8")
    (doc27 / "旧い手順.md").write_text("手順の本文\n" * 20, encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    git("tag", "base")
    (doc33 / "README.md").write_text("v2\n", encoding="utf-8")
    git("mv", "doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook/旧い手順.md",
        "doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook/新しい手順.md")
    git("commit", "-q", "-am", "change")

    policy = ROOT / "plugins" / "skill-governance-config" / "config" / "governance-policy.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "base", "--report", "--policy", str(policy)],
        capture_output=True, text=True, encoding="utf-8", cwd=str(repo), env=env,
    )
    assert proc.returncode == 1, proc.stderr  # 承認の記録が無いので P1 は block
    cats = {c["path"]: c["category"] for c in json.loads(proc.stdout)["changes"]}
    base = "doc/ClaudeCodeスキルの設計書/"
    assert cats == {
        base + "33-change-governance/README.md": "P1_structural",
        # リネームは元のパス（削除と同じ扱い）と新しいパスの両方を P1 として照合する。
        base + "27-rubric-governance-runbook/旧い手順.md": "P1_structural",
        base + "27-rubric-governance-runbook/新しい手順.md": "P1_structural",
    }


# --- 削除の承認 (target_sha256 の値が null) ---------------------------------

def _deletion_entry(target, sha, ts="2026-01-01T00:00:00+00:00"):
    return {"target_path": [target], "approver": "solo_operator", "status": "approved",
            "proposal_id": "PROP-del", "timestamp": ts, "target_sha256": {target: sha}}


def test_deletion_approval_requires_absent_file(changelog_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = "kits/foo/rubric.json"
    changelog_file.write_text(json.dumps(_deletion_entry(target, None)) + "\n", encoding="utf-8")
    assert G.has_recent_changelog(target) is True
    # 承認の後でファイルを戻したら、削除の承認では通さない。
    (tmp_path / "kits" / "foo").mkdir(parents=True)
    (tmp_path / target).write_text("{}", encoding="utf-8")
    assert G.has_recent_changelog(target) is False
    assert G.has_recent_changelog(target, "PROP-del") is False


def test_deletion_needs_explicit_null_not_missing_or_string(changelog_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = "kits/foo/rubric.json"
    entries = [
        _deletion_entry(target, "0" * 64),  # 消えたファイルに sha の文字列は一致しない
        {**_deletion_entry(target, None), "target_sha256": {"other.json": None}},  # 対象のキーが無い
        {**_deletion_entry(target, None), "target_sha256": None},
    ]
    changelog_file.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    assert G.has_recent_changelog(target) is False


def test_main_passes_approved_deletion_of_p1(policy_file, changelog_file, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    target = "kits/foo/rubric.json"
    _stub_git(monkeypatch, [target], {target: "D"})
    assert G.main(["prog"]) == 1
    changelog_file.write_text(json.dumps(_deletion_entry(target, None)) + "\n", encoding="utf-8")
    assert G.main(["prog"]) == 0
    assert "blocked=0" in capsys.readouterr().out


# --- 承認者の人数と auto の拒否 ---------------------------------------------

P0_TWO_APPROVERS = {
    **VALID_POLICY,
    "change_categories": {
        **VALID_POLICY["change_categories"],
        "P0_breaking": {"workflow": "proposal_required + human_approval + cooldown_7d",
                        "approver": "team-skills + solo_operator (両方)"},
        "P1_structural": {"workflow": "proposal_required + human_approval + cooldown_3d",
                          "approver": "solo_operator"},
    },
}


def test_required_approver_count_follows_policy():
    assert G.required_approver_count("P0_breaking", P0_TWO_APPROVERS) == 2
    assert G.required_approver_count("P1_structural", P0_TWO_APPROVERS) == 1
    assert G.required_approver_count("P0_breaking", VALID_POLICY) == 1  # approver の記載が無い policy


@pytest.mark.parametrize("approver, count", [
    ("solo_operator", 1),
    ("team-skills + solo_operator", 2),
    (["team-skills", "solo_operator"], 2),
    (["solo_operator", "Solo_Operator"], 1),  # 同じ人を2度数えない
    ("/root (independent technical review + 承認)", 1),  # 括弧の中の + は区切りではない
])
def test_approver_names_counts_distinct_people(approver, count):
    assert len(G._approver_names(approver)) == count


@pytest.mark.parametrize("approver", [
    "Auto", "AUTO (x)", "pending", ["solo_operator", "auto"], "solo_operator + Auto",
    "", "  ", ["solo_operator", ""], ["solo_operator", 3], 3, None,
])
def test_auto_pending_and_unreadable_approvers_are_rejected(approver):
    assert G._approved({"approver": approver}) is False


def test_p0_requires_two_distinct_approvers(changelog_file):
    target = "scripts/adapters/sink_new.py"
    one = {"target_path": target, "approver": "solo_operator", "proposal_id": "p"}
    changelog_file.write_text(json.dumps(one) + "\n", encoding="utf-8")
    assert G.has_recent_changelog(target, "p", 2) is False
    two = {**one, "approver": ["team-skills", "solo_operator"]}
    changelog_file.write_text(json.dumps(two) + "\n", encoding="utf-8")
    assert G.has_recent_changelog(target, "p", 2) is True


def test_main_blocks_p0_with_single_approver(tmp_path, changelog_file, monkeypatch, capsys):
    p = tmp_path / "policy.json"
    p.write_text(json.dumps(P0_TWO_APPROVERS, ensure_ascii=False), encoding="utf-8")
    target = "scripts/adapters/sink_new.py"
    changelog_file.write_text(json.dumps(
        {"target_path": target, "approver": "solo_operator", "proposal_id": "p"}) + "\n", encoding="utf-8")
    _stub_git(monkeypatch, [target], {target: "M"})
    assert G.main(["prog", "--policy", str(p), "--proposal-id", "p"]) == 1
    assert "承認者 2 名以上が要る" in capsys.readouterr().err


# --- 引数の検証 ---------------------------------------------------------------

@pytest.mark.parametrize("args", [
    ["--unknown"], ["--base", ""], ["--base=--output=x"], ["--base", "a..b"],
    ["--base", "main HEAD"], ["--proposal-id", " "], ["--repor"], ["extra"],
])
def test_main_rejects_bad_arguments_without_running_git(policy_file, changelog_file, tmp_path,
                                                         monkeypatch, capsys, args):
    monkeypatch.chdir(tmp_path)
    before = sorted(tmp_path.iterdir())

    def never(*a, **k):
        raise AssertionError("git must not run")
    monkeypatch.setattr(G.subprocess, "check_output", never)
    assert G.main(["prog", *args]) == 2
    assert "summary:" not in capsys.readouterr().out
    assert sorted(tmp_path.iterdir()) == before  # git diff --output= でファイルを書かせない


def test_main_help_exits_0(capsys):
    assert G.main(["prog", "--help"]) == 0
    out = capsys.readouterr().out
    assert "--policy" in out and "--bypass-cooldown" in out


# --- 設定を読めないときは exit 2 -------------------------------------------

def _p0_change(monkeypatch):
    target = "scripts/adapters/sink_new.py"
    _stub_git(monkeypatch, [target], {target: "M"})
    return target


def test_main_unreadable_changelog_exits_2(policy_file, changelog_file, monkeypatch, capsys):
    _p0_change(monkeypatch)
    changelog_file.write_bytes(b"\xff\xfe broken\n")
    assert G.main(["prog"]) == 2
    assert "ERROR:" in capsys.readouterr().err


def test_main_changelog_directory_exits_2(policy_file, changelog_file, monkeypatch, capsys):
    _p0_change(monkeypatch)
    changelog_file.mkdir()
    assert G.main(["prog"]) == 2
    assert "ERROR:" in capsys.readouterr().err


def test_main_numeric_timestamp_exits_2(policy_file, changelog_file, monkeypatch, capsys):
    target = _p0_change(monkeypatch)
    entries = [{"target_path": target, "timestamp": 20261010},
               {"target_path": target, "approver": "reviewer", "proposal_id": "selected"}]
    changelog_file.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    assert G.main(["prog", "--proposal-id", "selected"]) == 2
    assert "timestamp" in capsys.readouterr().err


@pytest.mark.parametrize("mutate", [
    lambda p: p["change_categories"].__setitem__("P0_breaking", "proposal_required"),
    lambda p: p["change_categories"]["P0_breaking"].__setitem__("workflow", 7),
    lambda p: p["change_categories"]["P0_breaking"].__setitem__("approver", ["a", "b"]),
    lambda p: p["cooldown_rules"].__setitem__("P1_structural", "ながい期間"),
    lambda p: p["cooldown_rules"].__setitem__("P1_structural", 3),
])
def test_load_policy_rejects_invalid_rules(tmp_path, monkeypatch, capsys, mutate):
    policy = json.loads(json.dumps(VALID_POLICY))
    mutate(policy)
    p = tmp_path / "policy.json"
    p.write_text(json.dumps(policy, ensure_ascii=False), encoding="utf-8")
    _p0_change(monkeypatch)
    with pytest.raises(SystemExit) as ei:  # load_policy は従来どおり SystemExit(2) で止める
        G.main(["prog", "--policy", str(p)])
    assert ei.value.code == 2
    assert "policy category/cooldown contract is invalid" in capsys.readouterr().err


def test_load_policy_non_utf8_exits_2(tmp_path, monkeypatch, capsys):
    p = tmp_path / "policy.json"
    p.write_bytes(b"\xff\xfe{}")
    _p0_change(monkeypatch)
    with pytest.raises(SystemExit) as ei:
        G.main(["prog", "--policy", str(p)])
    assert ei.value.code == 2
    assert "policy cannot be read" in capsys.readouterr().err


# --- 新規 plugin の判定 -----------------------------------------------------

def test_main_new_plugin_directory_without_manifest_is_p0(policy_file, changelog_file, monkeypatch, capsys):
    files = ["plugins/brand-new/skills/x/SKILL.md", "plugins/existing/notes.md"]
    _stub_git(monkeypatch, files, {files[0]: "A", files[1]: "M"})
    monkeypatch.setattr(G, "_base_plugin_dirs", lambda base: {"plugins/existing"})
    assert G.main(["prog", "--report"]) == 1
    cats = {c["path"]: c["category"] for c in json.loads(capsys.readouterr().out)["changes"]}
    assert cats == {files[0]: "P0_breaking", files[1]: "P2_content"}


# --- requires-python ">=3.9" -----------------------------------------------

def test_cli_runs_on_python39_if_available():
    py39 = Path("/usr/bin/python3")
    if not py39.exists():
        pytest.skip("/usr/bin/python3 が無い")
    version = subprocess.run([str(py39), "-c", "import sys; print(sys.version_info[:2] == (3, 9))"],
                             capture_output=True, text=True)
    if version.stdout.strip() != "True":
        pytest.skip("/usr/bin/python3 が 3.9 でない")
    env = dict(__import__("os").environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([str(py39), str(SCRIPT), "--help"], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    # 実 repo の governance-log の timestamp も 3.9 の fromisoformat で読める。
    proc = subprocess.run([str(py39), str(SCRIPT), "--base", "HEAD", "--report"],
                          capture_output=True, text=True, cwd=str(ROOT), env=env)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["changes"] == []


# --- 判定の拠り所は merge-base（同じ PR の中でゲートを外させない） ---------------

POLICY_REL = "plugins/skill-governance-config/config/governance-policy.json"
LOG_REL = ".claude/changelog/governance-log.jsonl"
MANIFEST_REL = "plugins/demo/.claude-plugin/plugin.json"
REAL_POLICY = ROOT / POLICY_REL


def _governed_repo(tmp_path):
    """policy・plugin.json・governance-log（2行）・本文を base に commit した repo を作る。"""
    env = _git_env(tmp_path)
    repo = tmp_path / "governed"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                       cwd=repo, env=env, check=True, capture_output=True)

    old = [{"target_path": [t], "approver": "solo_operator", "proposal_id": p,
            "timestamp": "2020-01-01T00:00:00+00:00"} for t, p in (("doc/readme.md", "old-1"),
                                                                  ("plugins/demo", "old-2"))]
    base_files = {
        POLICY_REL: REAL_POLICY.read_text(encoding="utf-8"),
        MANIFEST_REL: '{"name": "demo"}\n',
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
                              capture_output=True, text=True, encoding="utf-8", cwd=str(repo), env=env)

    return repo, commit, gate


def test_cli_same_pr_policy_downgrade_still_blocks_plugin_json(tmp_path):
    repo, commit, gate = _governed_repo(tmp_path)
    head_policy = json.loads(REAL_POLICY.read_text(encoding="utf-8"))
    for rule in head_policy["change_categories"].values():
        rule["workflow"], rule["approver"] = "auto_apply", "auto"
    commit({POLICY_REL: json.dumps(head_policy, ensure_ascii=False, indent=2) + "\n",
            MANIFEST_REL: '{"name": "demo", "version": "2.0.0"}\n'})
    proc = gate("--report")
    assert proc.returncode == 1, proc.stderr
    blocked = {b["path"]: b["category"] for b in json.loads(proc.stdout)["blocked"]}
    assert blocked == {POLICY_REL: "P1_structural", MANIFEST_REL: "P1_structural"}


def test_cli_deleting_governance_log_line_exits_2(tmp_path):
    repo, commit, gate = _governed_repo(tmp_path)
    lines = (repo / LOG_REL).read_text(encoding="utf-8").splitlines(keepends=True)
    commit({LOG_REL: "".join(lines[1:]), "doc/readme.md": "v2\n"})
    proc = gate()
    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    assert "追記以外" in proc.stderr
    assert "summary:" not in proc.stdout


def test_cli_appending_governance_log_line_passes(tmp_path):
    repo, commit, gate = _governed_repo(tmp_path)
    log = (repo / LOG_REL).read_text(encoding="utf-8")
    added = json.dumps({"target_path": ["doc/readme.md"], "approver": "auto", "proposal_id": "new",
                        "timestamp": "2020-02-01T00:00:00+00:00"})
    commit({LOG_REL: log + added + "\n", "doc/readme.md": "v2\n"})
    proc = gate()
    assert proc.returncode == 0, proc.stderr
    assert "summary: total=2 blocked=0" in proc.stdout


def test_cli_policy_change_is_p1(tmp_path):
    repo, commit, gate = _governed_repo(tmp_path)
    policy = json.loads(REAL_POLICY.read_text(encoding="utf-8"))
    policy["cooldown_rules"]["description"] = "説明だけを変える"
    commit({POLICY_REL: json.dumps(policy, ensure_ascii=False, indent=2) + "\n"})
    proc = gate()
    assert proc.returncode == 1, proc.stderr
    assert f"BLOCK {POLICY_REL} (P1_structural)" in proc.stderr


def test_changelog_append_only_compares_bytes_with_merge_base(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(G, "CHANGELOG_PATH", Path(LOG_REL))
    (tmp_path / LOG_REL).parent.mkdir(parents=True)
    (tmp_path / LOG_REL).write_bytes(b'{"a": 1}\n{"b": 2}\n')
    for base, ok in ((None, True), (b'{"a": 1}\n', True), (b'{"a": 1}\n{"b": 2}\n', True),
                     (b'{"a": 1}\r\n', False), (b'{"z": 0}\n{"a": 1}\n', False)):
        monkeypatch.setattr(G, "_blob_at", lambda rev, path, base=base: base)
        if ok:
            G.check_changelog_append_only("MB")
        else:
            with pytest.raises(G.ConfigError, match="追記以外"):
                G.check_changelog_append_only("MB")


def test_load_base_policy_rejects_broken_policy_at_merge_base(monkeypatch):
    monkeypatch.setattr(G, "POLICY_PATH_CANDIDATES", (Path(POLICY_REL),))
    monkeypatch.setattr(G, "_blob_at", lambda rev, path: None)
    assert G.load_base_policy("MB") is None  # 初めて入れる PR は作業ツリーの policy
    monkeypatch.setattr(G, "_blob_at", lambda rev, path: json.dumps(VALID_POLICY).encode())
    assert G.load_base_policy("MB") == VALID_POLICY
    for raw in (b"{ broken", b"\xff\xfe{}", b'{"change_categories": {}}'):
        monkeypatch.setattr(G, "_blob_at", lambda rev, path, raw=raw: raw)
        with pytest.raises(G.ConfigError, match="merge-base"):
            G.load_base_policy("MB")
