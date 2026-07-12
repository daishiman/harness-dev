# /// script
# name: test_config_value_fill
# purpose: 既知値から config を一発生成する value-fill 経路 (build_config / write_skeleton(values=) / doctor --init 値フラグ) を検証する。SSOT(CONFIG_SKELETON)不変・実値の git 追跡ファイル非混入・部分指定の fail-closed 維持を機構的に固定する。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: ["pytest"]
# requires-python: ">=3.9"
# ///
"""config value-fill のテスト。

config 不在→初回 dry-run 到達のオンボーディングで、既知の DB ID/送信元から config を 1 ステップで
満たせること(対話ループの解消)、かつその際に SSOT を汚さず実値を git 追跡ファイルへ漏らさず、
未指定キーは placeholder のまま fail-closed を維持することを固定する。"""
import copy
import json
from pathlib import Path

import pytest

from lib import notion_config as nc
from lib import setup_doctor

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = PLUGIN_ROOT / ".notion-config.example.json"

# 明らかに偽の (しかし placeholder ではない) 実値。git 追跡ファイルへ漏れてはならない。
FAKE = {
    "body_db": "0000000000body0000000000bodydb01",
    "recipient_db": "1111111111recip1111111111recpdb1",
    "log_db": "2222222222logdb2222222222logdb01",
    "impersonate": "no-reply@example.test",
}


def test_build_config_none_equals_skeleton_but_is_a_copy():
    cfg = nc.build_config(None)
    assert cfg == nc.CONFIG_SKELETON
    assert cfg is not nc.CONFIG_SKELETON                       # deepcopy (別オブジェクト)
    assert cfg["databases"] is not nc.CONFIG_SKELETON["databases"]


def test_build_config_overlays_real_values():
    cfg = nc.build_config(FAKE)
    assert cfg["databases"]["gmail-send-log"]["db_id"] == FAKE["log_db"]
    assert cfg["notion_gmail_send"]["source"]["body_db"] == FAKE["body_db"]
    assert cfg["notion_gmail_send"]["source"]["recipient_db"] == FAKE["recipient_db"]
    assert cfg["notion_gmail_send"]["sender"]["impersonate"] == FAKE["impersonate"]


def test_build_config_does_not_mutate_ssot():
    before = copy.deepcopy(nc.CONFIG_SKELETON)
    nc.build_config(FAKE)
    assert nc.CONFIG_SKELETON == before, "build_config が SSOT(CONFIG_SKELETON)を破壊している"
    # SSOT は placeholder のまま (git 追跡ファイルへ実値が回り込まない)
    assert nc.CONFIG_SKELETON["notion_gmail_send"]["source"]["body_db"].startswith("<")


def test_build_config_does_not_touch_example_file():
    before = EXAMPLE.read_text(encoding="utf-8")
    nc.build_config(FAKE)
    assert EXAMPLE.read_text(encoding="utf-8") == before, "example(git 追跡)が書き換わった"
    for v in FAKE.values():
        assert v not in before                                # 実値は example に存在しない


def test_full_values_resolve_without_error():
    cfg = nc.build_config(FAKE)
    assert nc.get_db_id("gmail-send-log", cfg) == FAKE["log_db"]
    assert nc.get_source_db_ids(cfg) == (FAKE["body_db"], FAKE["recipient_db"])
    assert nc.get_sender(cfg)["impersonate"] == FAKE["impersonate"]


def test_partial_values_keep_fail_closed_for_unfilled():
    # source だけ埋め、送信ログDB は placeholder のまま → 該当キーは依然 ConfigError (fail-closed)
    cfg = nc.build_config({"body_db": FAKE["body_db"], "recipient_db": FAKE["recipient_db"]})
    assert nc.get_source_db_ids(cfg) == (FAKE["body_db"], FAKE["recipient_db"])  # 埋めた分は解決
    with pytest.raises(nc.ConfigError, match="placeholder"):
        nc.get_db_id("gmail-send-log", cfg)                   # 未指定分は placeholder 拒否


def test_write_skeleton_with_values_writes_filled_resolvable_config(tmp_path):
    dest = tmp_path / ".notion-config.json"
    nc.write_skeleton(dest, values=FAKE)
    cfg = nc.load_config(str(dest))
    assert nc.get_source_db_ids(cfg) == (FAKE["body_db"], FAKE["recipient_db"])
    assert nc.get_db_id("gmail-send-log", cfg) == FAKE["log_db"]


def test_write_skeleton_with_values_refuses_overwrite_without_flag(tmp_path):
    dest = tmp_path / ".notion-config.json"
    nc.write_skeleton(dest, values=FAKE)
    with pytest.raises(nc.ConfigError):
        nc.write_skeleton(dest, values={"body_db": "x"})      # 既存実値を黙って潰さない
    nc.write_skeleton(dest, values={"body_db": "x"}, overwrite=True)  # 明示時のみ許可


def test_doctor_init_with_value_flags_creates_resolvable_config(tmp_path, capsys):
    dest = tmp_path / ".notion-config.json"
    rc = setup_doctor._do_init(str(dest), values=FAKE)
    assert rc == 0 and dest.is_file()
    cfg = nc.load_config(str(dest))
    assert nc.get_source_db_ids(cfg) == (FAKE["body_db"], FAKE["recipient_db"])
    out = capsys.readouterr().out
    assert "必須項目が揃いました" in out                       # 全値充足を案内


def test_doctor_init_partial_lists_remaining_placeholders(tmp_path, capsys):
    dest = tmp_path / ".notion-config.json"
    setup_doctor._do_init(str(dest), values={"body_db": FAKE["body_db"]})
    out = capsys.readouterr().out
    assert "まだ実値が必要な項目" in out
    assert "notion_gmail_send.source.recipient_db" in out      # 未指定キーを名指しで提示
    assert "fail-closed" in out


def test_unresolved_keys_empty_when_fully_filled():
    assert setup_doctor._unresolved_keys(nc.build_config(FAKE)) == []
    assert len(setup_doctor._unresolved_keys(nc.build_config(None))) == 4  # 全 placeholder
