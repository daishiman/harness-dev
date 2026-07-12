# /// script
# name: test_config_scaffold
# purpose: config の placeholder SSOT (CONFIG_SKELETON) と scaffold (write_skeleton/--init 相当) を検証する。実 DB ID/送信元の git 追跡ファイルへの再混入(再leak)を機構的に遮断する。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: ["pytest"]
# requires-python: ">=3.9"
# ///
"""config scaffold / placeholder SSOT のテスト。

example ファイル・write_skeleton・ConfigError 文言がすべて単一 SSOT (CONFIG_SKELETON) から
導かれ、実値が git 追跡ファイルへ混入しないことを固定する。config 不在のオンボーディング破綻と
実値漏洩の回帰を防ぐ。"""
import json
from pathlib import Path

import pytest

from lib import notion_config as nc

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = PLUGIN_ROOT / ".notion-config.example.json"
LEGACY_EXAMPLE = PLUGIN_ROOT / ".notion-config.json.example"

# 過去に example へ焼き込まれていた実値の痕跡。git 追跡ファイルに二度と現れてはならない。
REAL_VALUE_MARKERS = ["38807a0c", "77777777", "example.invalid"]


def test_example_follows_repo_naming_convention():
    # repo 規約は <name>.example.json (skill-intake / mf-kessai と一致し .gitignore negation が効く)。
    assert EXAMPLE.is_file(), ".notion-config.example.json が存在しません"
    assert not LEGACY_EXAMPLE.exists(), "旧命名 .notion-config.json.example が残っています"


def test_example_matches_skeleton_ssot():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert data == nc.CONFIG_SKELETON, "example が CONFIG_SKELETON (SSOT) と一致しません"


def test_no_real_values_in_skeleton_or_example():
    blobs = {
        "CONFIG_SKELETON": json.dumps(nc.CONFIG_SKELETON, ensure_ascii=False),
        "example file": EXAMPLE.read_text(encoding="utf-8"),
    }
    for where, blob in blobs.items():
        for marker in REAL_VALUE_MARKERS:
            assert marker not in blob, f"{where} に実値 {marker} が混入しています (git に実値を載せない)"


def test_skeleton_values_are_placeholders():
    src = nc.CONFIG_SKELETON["notion_gmail_send"]["source"]
    sender = nc.CONFIG_SKELETON["notion_gmail_send"]["sender"]
    assert src["body_db"].startswith("<") and src["body_db"].endswith(">")
    assert src["recipient_db"].startswith("<") and src["recipient_db"].endswith(">")
    assert sender["impersonate"].startswith("<"), "送信元は placeholder でなければならない (git に実値を載せない)"
    assert nc.CONFIG_SKELETON["databases"]["gmail-send-log"]["db_id"].startswith("<")


def test_placeholder_values_are_rejected_as_unresolved_config():
    with pytest.raises(nc.ConfigError, match="placeholder"):
        nc.require_resolved_value("<メール本文DBのid>", "notion_gmail_send.source.body_db")
    with pytest.raises(nc.ConfigError, match="placeholder"):
        nc.get_db_id("gmail-send-log", nc.CONFIG_SKELETON)
    with pytest.raises(nc.ConfigError, match="placeholder"):
        nc.get_source_db_ids(nc.CONFIG_SKELETON)


def test_skeleton_uses_canonical_db_name():
    note = nc.CONFIG_SKELETON["notion_gmail_send"]["source"]["_note"]
    assert "メール送信先_DB" in note
    assert "メール送信対象者DB" not in note, "宛先DB名称のドリフトが再発しています"


def test_write_skeleton_creates_placeholder_config(tmp_path):
    dest = tmp_path / "sub" / ".notion-config.json"
    written = nc.write_skeleton(dest)
    assert written == dest and dest.is_file()
    assert json.loads(dest.read_text(encoding="utf-8")) == nc.CONFIG_SKELETON


def test_write_skeleton_refuses_overwrite_then_allows_with_flag(tmp_path):
    dest = tmp_path / ".notion-config.json"
    nc.write_skeleton(dest)
    with pytest.raises(nc.ConfigError):
        nc.write_skeleton(dest)            # 既存を黙って潰さない
    nc.write_skeleton(dest, overwrite=True)  # 明示時のみ許可


def test_scaffold_target_prefers_claude_project_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert nc.scaffold_target_path() == tmp_path / nc.CONFIG_FILENAME


def test_config_missing_error_points_to_init_not_dead_end(monkeypatch):
    # config 不在のエラーは scaffold (doctor --init) と placeholder 例を指し、デッドエンドにしない。
    monkeypatch.setattr(nc, "find_config_path", lambda path=None: None)
    with pytest.raises(nc.ConfigError) as ei:
        nc.load_config()
    msg = str(ei.value)
    assert "doctor --init" in msg
    assert ".notion-config.example.json" in msg


def test_tenant_global_notion_config_path_is_supported(monkeypatch, tmp_path):
    config = tmp_path / "tenant-notion.json"
    config.write_text(json.dumps({"databases": {"gmail-send-log": {"db_id": "tenant-db"}}}))
    monkeypatch.delenv("NOTION_GMAIL_CONFIG", raising=False)
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(config))
    assert nc.find_config_path() == config
    assert nc.get_db_id("gmail-send-log") == "tenant-db"
