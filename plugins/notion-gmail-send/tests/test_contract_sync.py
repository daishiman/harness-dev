# /// script
# name: test_contract_sync
# purpose: 実装とスキル契約の同期を検証する。冪等キー定義、reason_code enum、verdict schema が drift しないことを固定する。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: ["pytest"]
# requires-python: ">=3.9"
# ///
"""実装とスキル契約の同期テスト。"""
import importlib.util
import json
from pathlib import Path

from lib import idempotent_log as ilog
from lib import notion_client as nc

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SETUP_PATH = PLUGIN_ROOT / "skills" / "run-notion-gmail-sendlog-setup" / "scripts" / "setup-send-log-db.py"
SCHEMA_PATH = PLUGIN_ROOT / "skills" / "run-notion-gmail-send" / "schemas" / "send-verdict.schema.json"
REF_SKILL = PLUGIN_ROOT / "skills" / "ref-notion-gmail-send-spec" / "SKILL.md"
SPEC_DETAIL = PLUGIN_ROOT / "skills" / "ref-notion-gmail-send-spec" / "references" / "spec-detail.md"
SENDLOG_SKILL = PLUGIN_ROOT / "skills" / "run-notion-gmail-sendlog-setup" / "SKILL.md"
ROOT_SSOT = PLUGIN_ROOT.parents[1] / "doc" / "run-notion-gmail-send-仕様と検証メモ.md"


def _load_setup():
    spec = importlib.util.spec_from_file_location("setup_send_log_db_under_test", SETUP_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_send_log_setup_reason_options_follow_idempotent_log_ssot():
    setup = _load_setup()
    assert setup.REASON_OPTIONS is ilog.REASON_CODES
    expected = {o["name"] for o in setup.EXPECTED["reason_code"]["select"]["options"]}
    assert expected == set(ilog.REASON_CODES)


def test_send_verdict_schema_allows_verify_plan_nonce_fields():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    props = schema["properties"]
    assert props["approval_nonce_unit"]["type"] == ["integer", "null"]
    assert props["approval_nonce"]["type"] == "string"
    assert schema["additionalProperties"] is False


def test_docs_use_campaign_independent_dedup_key():
    for path in [REF_SKILL, SPEC_DETAIL, SENDLOG_SKILL, ROOT_SSOT]:
        text = path.read_text(encoding="utf-8")
        assert "{本文page_id}:{宛先page_id}:{content_hash}" in text
        assert "{campaign_id}:{本文page_id}:{宛先page_id}:{content_hash}" not in text


def test_recipient_contract_mentions_current_filters_and_dedup_tiebreak():
    for path in [REF_SKILL, SPEC_DETAIL, ROOT_SSOT]:
        text = path.read_text(encoding="utf-8")
        assert "メール（プロ人材）" in text
        assert "メール（cc秘書）" in text
        assert "メールを送らない=false" in text
        assert "created_time" in text and "page_id" in text
        assert "`部署名` は廃止" in text


def test_docs_clarify_secretary_cc_optional_and_overlap_suppression():
    # F2/F5/F1/F8: 秘書CC任意・To重複CC除外・created_time一次キー・送信対象false扱いの明文化が drift しないよう固定
    for path in [SPEC_DETAIL, ROOT_SSOT]:
        text = path.read_text(encoding="utf-8")
        # 秘書CC は必須でない (空なら To のみ送信)
        assert "秘書" in text and ("必須では" in text or "必須でない" in text)
        # To 重複 CC 除外の可視化メタ名 (コード message_assemble.cc_suppressed_by_to と整合)
        assert "cc_suppressed_due_to_to_overlap" in text
        # 送信対象=false は dry-run 母集団外 / 承認後 false 化のみ send_suppressed
        assert "send_suppressed" in text
        # dedup 一次キー = created_time 降順 (page_id は tie-break のみ)
        assert "一次キー" in text


def test_spec_has_user_to_impl_glossary():
    # 用語対応表 (ユーザー語彙 ↔ 実装語彙) が spec に存在し主要対応を含む (F2)
    text = SPEC_DETAIL.read_text(encoding="utf-8")
    assert "用語対応表" in text
    for pair in ["プロ人材", "秘書", "content_hash", "cc_suppressed_due_to_to_overlap"]:
        assert pair in text


def test_source_db_property_contract_matches_current_notion_schema():
    assert nc.P_SUBJECT == "件名"
    assert nc.P_FROM == "メールの送り主"
    assert nc.P_CC == "CC"
    assert nc.P_MSG_TARGET == "メッセージ対象"
    assert nc.P_NAME == "担当者様名"
    assert nc.P_COMPANY == "会社名"
    assert nc.P_EMAIL_PRO == "メール（プロ人材）"
    assert nc.P_EMAIL_HISHO == "メール（cc秘書）"
    assert nc.P_DO_NOT_SEND == "メールを送らない"
    assert nc.P_SEND_TARGET == "送信対象"
    assert "部署" not in {
        nc.P_SUBJECT, nc.P_FROM, nc.P_CC, nc.P_MSG_TARGET,
        nc.P_NAME, nc.P_COMPANY, nc.P_EMAIL_PRO, nc.P_EMAIL_HISHO,
        nc.P_DO_NOT_SEND, nc.P_SEND_TARGET,
    }


def test_values_for_recipient_excludes_department_token():
    values = nc.values_for_recipient({"name": "田中", "company": "X社", "department": "営業部"})
    assert values == {"担当者様名": "田中", "会社名": "X社"}
    assert "部署名" not in values


def test_public_contract_has_no_legacy_recipient_filter_wording():
    for path in [REF_SKILL, SPEC_DETAIL, ROOT_SSOT]:
        text = path.read_text(encoding="utf-8")
        assert "送信対象=✅ かつ メール非空" not in text
        assert "メール(To) が非空" not in text
        assert "メールを送らない☐" in text or "メールを送らない=false" in text


def test_gmail_sent_history_contract_is_documented_and_endpoint_bound():
    docs = "\n".join(path.read_text(encoding="utf-8") for path in [REF_SKILL, SPEC_DETAIL, ROOT_SSOT])
    assert "users.messages.send" in docs
    assert "送信済み" in docs


# 二重送信防止の中核 lib は専用ユニットテストの存在を CI で必須化する。
# (過去に「test を追加した」と報告されながら実体が無く中核が未保護だった回帰の再発防止)
TESTS_DIR = Path(__file__).resolve().parent
CORE_LIBS_REQUIRING_UNIT_TESTS = ["idempotent_log"]


def test_core_libs_have_dedicated_unit_tests():
    for lib_name in CORE_LIBS_REQUIRING_UNIT_TESTS:
        test_file = TESTS_DIR / f"test_{lib_name}.py"
        assert test_file.exists(), (
            f"中核 lib '{lib_name}' のユニットテスト tests/{test_file.name} が存在しません。"
            " 二重送信防止の回帰を防ぐため専用テストファイルを必須とします。"
        )
        text = test_file.read_text(encoding="utf-8")
        # 空ファイル/幻影での偽装防止: 中核 lib を import し reserve を検証する実テストを要求する
        assert "from lib import idempotent_log" in text, (
            f"tests/{test_file.name} が中核 lib を import していません。"
        )
        assert "reserve" in text and "def test_" in text, (
            f"tests/{test_file.name} に reserve を検証する実テストがありません。"
        )
