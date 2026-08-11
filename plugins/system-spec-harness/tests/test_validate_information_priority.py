# /// script
# name: test-validate-information-priority
# version: 0.1.0
# purpose: validate-information-priority.py の決定論ゲートを正例=OK・負例=各違反・usage=exit2 で網羅検証する pytest。特に「順位確定より先に装飾している」順序違反を捕まえられることを固定する。
# inputs:
#   - argv: pytest 経由 (直接 argv は取らない)
# outputs:
#   - stdout: pytest 結果
#   - exit: 0=all pass / 1=failure
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""information priority map gate の検証。

正例 = OK / 負例 = 各違反 / usage = exit2。ハイフン名モジュールを importlib で
in-process ロードし validate()/main() を直接呼ぶ。
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "information-priority-map.schema.json"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vip = _load("vip", "validate-information-priority.py")


def _valid() -> dict:
    return {
        "artifact_id": "member-training-view",
        "artifact_kind": "screen",
        "context_of_use": {
            "audience": "フィットネストレーナー",
            "primary_tasks": [
                {"task": "会員と会話しながら本人確認する", "frequency": "high", "failure_cost": "medium"},
                {"task": "次回予約を確定する", "frequency": "high", "failure_cost": "high"},
            ],
            "environment": "トレーニングルームでタブレットを片手持ち",
            "expertise": "occasional",
        },
        "inventory": [
            {
                "element_id": "name-kana",
                "source_value": "氏名かな",
                "disposition": "keep",
                "group_id": "identity",
            },
            {
                "element_id": "birthday",
                "source_value": "生年月日 1990-04-02",
                "disposition": "transform",
                "display_value": "36歳",
                "reason": "会話では年齢の方が話題に繋がる",
                "group_id": "identity",
            },
            {
                "element_id": "label-tel",
                "source_value": "ラベル『電話番号』",
                "disposition": "drop",
                "reason": "アイコンで伝わるためラベルは不要",
            },
            {
                "element_id": "next-reservation",
                "source_value": "次回予約日時 2026-08-18T10:00",
                "disposition": "transform",
                "display_value": "1週間後",
                "reason": "会話では相対表現の方が理解が速い",
                "group_id": "reservation",
            },
        ],
        "groups": [
            {
                "group_id": "reservation",
                "label": "予約状況",
                "rank": 1,
                "rank_rationale": "高頻度かつ失敗コスト高の task (次回予約確定) に直結",
                "member_order": ["next-reservation"],
            },
            {
                "group_id": "identity",
                "label": "本人識別",
                "rank": 2,
                "rank_rationale": "高頻度だが失敗コストは中 (呼びかけの誤りは即時に訂正できる)",
                "member_order": ["name-kana", "birthday"],
            },
        ],
        "form_selection": {
            "chosen": "card",
            "candidates_considered": [
                {"form": "table", "why_not": "会話中の一瞥では行の走査コストが高い"},
                {"form": "list", "why_not": "予約状態のバッジなど機能を足しにくい"},
            ],
            "rationale": "視覚要素とテキストを併置でき機能追加もしやすい",
        },
        "emphasis": [
            {"target": "reservation", "channel": ["position", "size"], "expresses_rank": 1},
            {"target": "identity", "channel": ["position"], "expresses_rank": 2},
        ],
        "styling": [
            {"target": "next-reservation", "decoration": "塗りバッジ", "semantic_intent": "status"},
        ],
        "outcome_metrics": ["予約確定までのタップ数", "初見トレーナーの到達率"],
    }


# ── 正例 ───────────────────────────────────────────────────────────────
def test_valid_map_passes():
    assert vip.validate(_valid()) == []


def test_schema_file_is_loadable_json():
    doc = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert doc["$id"] == "information-priority-map.schema.json"


def test_optional_blocks_may_be_absent():
    doc = _valid()
    del doc["emphasis"]
    del doc["styling"]
    del doc["outcome_metrics"]
    assert vip.validate(doc) == []


# ── 負例: 手順の順序制約 ───────────────────────────────────────────────
def test_styling_without_any_rank_is_order_violation():
    doc = _valid()
    for g in doc["groups"]:
        del g["rank"]
    errors = vip.validate(doc)
    assert any("順位付けが装飾に先行" in e for e in errors)


def test_emphasis_not_matching_rank_is_rejected():
    doc = _valid()
    doc["emphasis"][0]["expresses_rank"] = 2
    errors = vip.validate(doc)
    assert any("強弱が順位の写像になっていない" in e for e in errors)


def test_emphasis_on_element_inherits_group_rank():
    doc = _valid()
    doc["emphasis"].append({"target": "birthday", "channel": ["size"], "expresses_rank": 1})
    errors = vip.validate(doc)
    assert any("birthday" in e and "所属 group の rank は 2" in e for e in errors)


# ── 負例: 順位そのものの健全性 ────────────────────────────────────────
def test_tied_ranks_are_rejected():
    doc = _valid()
    doc["groups"][1]["rank"] = 1
    doc["emphasis"][1]["expresses_rank"] = 1
    errors = vip.validate(doc)
    assert any("連番でない" in e for e in errors)


def test_empty_rank_rationale_is_rejected():
    doc = _valid()
    doc["groups"][0]["rank_rationale"] = "   "
    assert any("rank_rationale" in e for e in vip.validate(doc))


def test_group_without_members_is_rejected():
    doc = _valid()
    doc["groups"].append(
        {"group_id": "ghost", "label": "空の束", "rank": 3, "rank_rationale": "根拠らしきもの"}
    )
    assert any("空の束" in e for e in vip.validate(doc))


# ── 負例: 削除・加工の説明責任 ────────────────────────────────────────
def test_drop_without_reason_is_rejected():
    doc = _valid()
    del doc["inventory"][2]["reason"]
    errors = vip.validate(doc)
    assert any("理由なき削除/加工" in e for e in errors)


def test_transform_without_display_value_is_rejected():
    doc = _valid()
    del doc["inventory"][1]["display_value"]
    assert any("display_value が無い" in e for e in vip.validate(doc))


def test_keep_with_display_value_is_rejected():
    doc = _valid()
    doc["inventory"][0]["display_value"] = "ヤマダ タロウ"
    assert any("disposition=transform" in e for e in vip.validate(doc))


def test_displayed_element_without_group_is_rejected():
    doc = _valid()
    del doc["inventory"][0]["group_id"]
    assert any("意味の束に属さなければならない" in e for e in vip.validate(doc))


def test_all_dropped_is_rejected():
    doc = _valid()
    for e in doc["inventory"]:
        e["disposition"] = "drop"
        e["reason"] = "全部消した"
        e.pop("display_value", None)
        e.pop("group_id", None)
    assert any("表示する情報が残っていない" in e for e in vip.validate(doc))


def test_member_order_referencing_other_group_is_rejected():
    doc = _valid()
    doc["groups"][0]["member_order"] = ["next-reservation", "name-kana"]
    assert any("は group 'identity' の要素" in e for e in vip.validate(doc))


# ── 負例: 早期形式固定 ─────────────────────────────────────────────────
def test_single_candidate_form_is_rejected():
    doc = _valid()
    doc["form_selection"]["candidates_considered"] = [{"form": "table", "why_not": "n/a"}]
    errors = vip.validate(doc)
    assert any("いきなり表を作る" in e for e in errors)


# ── 負例: 装飾の意味 / アクセシビリティ ───────────────────────────────
def test_decorative_only_styling_is_rejected():
    doc = _valid()
    doc["styling"][0]["semantic_intent"] = "今風にする"
    assert any("意味の列挙に無い" in e for e in vip.validate(doc))


def test_color_only_emphasis_requires_accessibility_declaration():
    doc = _valid()
    doc["emphasis"][0]["channel"] = ["color"]
    errors = vip.validate(doc)
    assert any("色覚特性" in e for e in errors)

    doc["accessibility"] = {"color_not_sole_channel": True, "notes": "位置でも順位を表している"}
    assert vip.validate(doc) == []


def test_unknown_visual_channel_is_rejected():
    doc = _valid()
    doc["emphasis"][0]["channel"] = ["glitter"]
    assert any("未知の視覚変数" in e for e in vip.validate(doc))


# ── 負例: 文脈欠落 ─────────────────────────────────────────────────────
def test_missing_context_of_use_keys():
    doc = _valid()
    del doc["context_of_use"]["expertise"]
    assert any("context_of_use: 必須キー欠落" in e for e in vip.validate(doc))


def test_no_primary_tasks_is_rejected():
    doc = _valid()
    doc["context_of_use"]["primary_tasks"] = []
    assert any("順位は決められない" in e for e in vip.validate(doc))


def test_missing_root_key_short_circuits():
    doc = _valid()
    del doc["groups"]
    errors = vip.validate(doc)
    assert len(errors) == 1 and "root: 必須キー欠落" in errors[0]


def test_non_object_root():
    assert vip.validate([]) == ["ルートが object でない"]


# ── CLI ────────────────────────────────────────────────────────────────
def _write(tmp_path: Path, obj) -> str:
    p = tmp_path / "map.json"
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_main_ok(tmp_path, capsys):
    assert vip.main([_write(tmp_path, _valid())]) == 0
    assert "OK information priority map" in capsys.readouterr().out


def test_main_violation(tmp_path, capsys):
    doc = _valid()
    doc["styling"][0]["semantic_intent"] = "かっこいいから"
    assert vip.main([_write(tmp_path, doc)]) == 1
    assert "VIOLATION" in capsys.readouterr().err


def test_main_missing_file_is_usage_error(tmp_path, capsys):
    assert vip.main([str(tmp_path / "nope.json")]) == 2
    assert "USAGE ERROR" in capsys.readouterr().err


def test_main_broken_json_is_usage_error(tmp_path, capsys):
    p = tmp_path / "broken.json"
    p.write_text("{not json", encoding="utf-8")
    assert vip.main([str(p)]) == 2
    assert "USAGE ERROR" in capsys.readouterr().err


def test_main_requires_argument():
    with pytest.raises(SystemExit):
        vip.main([])


def test_exemption_requires_reason_and_approver():
    doc = copy.deepcopy(_valid())
    doc["exemption"] = {"reason": "熟練者専用の高密度一覧のため効率性を優先する"}
    assert any("exemption: 必須キー欠落" in e for e in vip.validate(doc))
