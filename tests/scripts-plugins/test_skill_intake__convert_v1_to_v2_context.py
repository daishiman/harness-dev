"""plugins/skill-intake/scripts/convert_v1_to_v2_context.py の genuine 機能テスト。

v1 intake.json (sections-based) を v2 render_notion_page context へ変換する純関数 convert() と
main(argv) の全分岐を tmp_path fixture で網羅する。network/keychain/Notion への依存は無い
(純粋なデータ変換スクリプト)。

カバー分岐:
- _str: None / list / scalar
- convert (空 v1 / フル v1):
    skill_name の正規化(規約一致そのまま / 32文字超切詰め+末尾ハイフン除去)
    handoff_mode 正規化(許可外→standard、standard→es は human-review)
    candidates / dimensions(confidence map)/ output_priority(mandatory→is_top)
    options groups(option id 正規化 既存形 / Q4-A→prefix連番 / 数字prefix→Oフォールバック、weight 正規化、adopted マッピング)
    figures(mermaid_source→mermaid rename + setdefault)
    rules_check(dict 形 / list of dict / list of scalar / その他型)
    five_axes(update enum 正規化、axis_name_map、depth_norm、pipeline)
    design_decisions output_priority(dict/str 混在)
    open_questions / handoff(recommended_next)/ self_update / artifacts
    notion_db_properties(output_dest/sharing/knowledge_tags のデフォルト & 抽出、depth enum)
    legacy 互換(5_axes flat / user_profile)
- main: 引数不足 exit2 / src 不在 exit2 / 正常変換 exit0(dst 書込)

network: false, keychain: なし, 実 repo 書換: なし(全 tmp_path)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "convert_v1_to_v2_context.py"

SPEC = importlib.util.spec_from_file_location("convert_v1_to_v2_context_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# ── _str ─────────────────────────────────────────────────────────────────────
def test_str_none():
    assert MOD._str(None) == ""


def test_str_list_joins():
    assert MOD._str(["a", "b", 3]) == "a, b, 3"


def test_str_scalar():
    assert MOD._str(42) == "42"


# ── convert: 空 v1(全 setdefault / デフォルト経路) ──────────────────────────
def test_convert_empty_v1_defaults():
    out = MOD.convert({})
    # meta デフォルト
    assert out["meta"]["pattern_code"] == "A"
    assert out["meta"]["pattern_label"] == "新規"
    assert out["meta"]["depth"] == "standard"
    assert out["meta"]["depth_minutes"] == 30
    # executive_summary handoff_mode: 空 handoff_mode_raw=standard → es は human-review
    assert out["executive_summary"]["handoff_mode"] == "human-review"
    # notion_db_properties デフォルト
    nd = out["notion_db_properties"]
    assert nd["出力先"] == ["Slack"]
    assert nd["共有相手"] == ["クライアント"]
    assert nd["ナレッジ資産タグ"] == ["思考プロセス", "判断基準"]
    assert nd["深度"] == "standard"
    # legacy
    assert out["5_axes"] == {}
    assert out["user_profile"] == {}
    # 全トップレベルキー存在
    for k in (
        "meta",
        "executive_summary",
        "assumption",
        "profile",
        "purpose",
        "options",
        "figures",
        "five_axes",
        "design_decisions",
        "open_questions",
        "handoff",
        "self_update",
        "artifacts",
        "section_diagrams",
        "notion_db_properties",
    ):
        assert k in out


# ── convert: skill_name 正規化 ──────────────────────────────────────────────
def test_convert_skill_name_already_valid_kept():
    out = MOD.convert({"skill_name_hint": "build-foo-bar"})
    assert out["meta"]["skill_name_hint"] == "build-foo-bar"


def test_convert_skill_name_too_long_truncated_and_trimmed():
    # 32文字超 + 33文字目以降切詰めで末尾ハイフン → 除去
    long = "abcdefghij-klmnopqrst-uvwxyz0123-extra"
    out = MOD.convert({"skill_name_hint": long})
    name = out["meta"]["skill_name_hint"]
    assert len(name) <= 32
    assert not name.endswith("-")


def test_convert_skill_name_uppercase_invalid_truncated():
    # 規約非一致(大文字) → truncate 経路
    out = MOD.convert({"skill_name_hint": "Foo"})
    assert out["meta"]["skill_name_hint"] == "Foo"  # 3文字、切詰め後そのまま


# ── convert: handoff_mode 正規化 ────────────────────────────────────────────
def test_convert_handoff_mode_fast_track_preserved():
    out = MOD.convert({"sections": {"0_executive_summary": {"handoff_mode": "fast-track"}}})
    assert out["notion_db_properties"]["引き渡しモード"] == "fast-track"
    assert out["executive_summary"]["handoff_mode"] == "fast-track"


def test_convert_handoff_mode_invalid_to_standard():
    out = MOD.convert({"sections": {"0_executive_summary": {"handoff_mode": "bogus"}}})
    assert out["notion_db_properties"]["引き渡しモード"] == "standard"
    assert out["executive_summary"]["handoff_mode"] == "human-review"


# ── convert: assumption candidates / blind_spots ────────────────────────────
def test_convert_candidates_id_and_adopted():
    v1 = {
        "sections": {
            "1_assumption_challenger": {
                "surface_request": "sr",
                "adopted_deep_problem": "deep",
                "deep_candidates": [
                    {"label": "L1", "adopted": True},  # id 欠落 → D1
                    {"id": "X9", "text": "T2"},  # label 欠落 → text 採用
                ],
                "blindspots": ["bs1"],
            }
        }
    }
    out = MOD.convert(v1)
    cands = out["assumption"]["candidates"]
    assert cands[0]["id"] == "D1"
    assert cands[0]["label"] == "L1"
    assert cands[0]["adopted"] is True
    assert cands[1]["id"] == "X9"
    assert cands[1]["label"] == "T2"
    assert out["assumption"]["deep_problem"] == "deep"
    assert out["assumption"]["blind_spots"] == ["bs1"]


# ── convert: profile dimensions(confidence map)/ user_profile legacy ────────
def test_convert_dimensions_confidence_map_and_user_profile():
    v1 = {
        "sections": {
            "2_user_profile": {
                "dimensions": [
                    {"dim": "skill_level", "value": "上級", "confidence": "mid", "evidence": "e"},
                    {"name": "tooling", "value": "vscode", "confidence": "high"},
                    {"dim": "unknown", "value": "v", "confidence": "weird"},  # 未知→medium
                ]
            }
        }
    }
    out = MOD.convert(v1)
    dims = out["profile"]["dimensions"]
    assert dims[0]["name"] == "skill_level"
    assert dims[0]["confidence"] == "medium"  # mid→medium
    assert dims[1]["confidence"] == "high"
    assert dims[2]["confidence"] == "medium"  # 未知→medium
    # legacy user_profile は name->value
    assert out["user_profile"]["skill_level"] == "上級"
    assert out["user_profile"]["tooling"] == "vscode"


# ── convert: purpose techniques / output_priority ───────────────────────────
def test_convert_purpose_techniques_and_output_priority():
    v1 = {
        "sections": {
            "3_purpose_excavator": {
                "true_purpose": "tp",
                "rounds": 3,
                "techniques_used": ["t1", "t2"],
                "differentiation": "diff",
                "output_priority": [
                    {"output": "report", "mandatory": True},
                    {"text": "log", "is_top": False},
                ],
            }
        }
    }
    out = MOD.convert(v1)
    p = out["purpose"]
    assert p["true_purpose"] == "tp"
    assert p["rounds"] == 3
    assert p["techniques_used_str"] == "t1 -> t2"
    assert p["differentiation_text"] == "diff"
    assert p["output_priority"][0] == {"text": "report", "is_top": True}
    assert p["output_priority"][1] == {"text": "log", "is_top": False}


# ── convert: options(option id 正規化 / weight / adopted) ───────────────────
def test_convert_options_id_normalization_and_weight():
    v1 = {
        "sections": {
            "4_option_presenter": {
                "connectors": {
                    "input_sources": ["a", "b"],
                    "knowledge_assets": "ka",
                    "outputs": "o",
                    # scheduler 欠落 → on-demand
                },
                "decision_tables": [
                    {
                        "axis": "AxisOne",
                        "adopted_id": "Q4-A",
                        "options": [
                            {"id": "A1", "label": "keep", "weight": "重"},  # 既に規約一致
                            {"id": "Q4-A", "label": "norm", "weight": "bad"},  # →prefix連番 Q2, weight→中
                            {"id": "9x", "label": "fallback"},  # alpha upper なし →O3
                        ],
                    }
                ],
            }
        }
    }
    out = MOD.convert(v1)
    grp = out["options"]["groups"][0]
    assert grp["title"] == "AxisOne"
    opts = grp["options"]
    assert opts[0]["id"] == "A1"
    assert opts[0]["weight"] == "重"
    assert opts[1]["id"] == "Q2"  # Q4-A → prefix Q + idx2
    assert opts[1]["weight"] == "中"  # 不正 weight 正規化
    assert opts[2]["id"] == "O3"  # upper alpha なし → O + idx3
    # adopted_raw="Q4-A" は id_map で Q2 へ
    assert grp["adopted"] == "Q2"
    # connectors
    conn = out["options"]["connectors"]
    assert conn["input_sources"] == "a, b"
    assert conn["scheduler"] == "on-demand"


# ── convert: figures(mermaid_source rename / rules_check 各形) ──────────────
def test_convert_figures_dict_rules_check():
    v1 = {
        "sections": {
            "5_visualizer": {
                "figures": [
                    {"title": "F1", "mermaid_source": "graph TD"},
                    {"title": "F2", "mermaid": "graph LR"},
                ],
                "rules_check": {"rule-a": True, "rule-b": False},
            }
        }
    }
    out = MOD.convert(v1)
    entries = out["figures"]["entries"]
    assert entries[0]["mermaid"] == "graph TD"  # rename された
    assert "mermaid_source" not in entries[0]
    assert entries[0]["one_liner"] == ""  # setdefault
    assert entries[1]["mermaid"] == "graph LR"
    rc = out["figures"]["mandatory_rules_check"]
    assert {"text": "rule-a", "passed": True} in rc
    assert {"text": "rule-b", "passed": False} in rc


def test_convert_figures_list_rules_check():
    v1 = {
        "sections": {
            "5_visualizer": {
                "rules_check": [
                    {"rule": "r1", "result": False},
                    {"text": "r2", "passed": True},
                    "bare-string-rule",
                ],
            }
        }
    }
    out = MOD.convert(v1)
    rc = out["figures"]["mandatory_rules_check"]
    assert {"text": "r1", "passed": False} in rc
    assert {"text": "r2", "passed": True} in rc
    assert {"text": "bare-string-rule", "passed": True} in rc


def test_convert_figures_other_rules_check_type():
    # rules_check が dict でも list でもない型 → 空リスト
    v1 = {"sections": {"5_visualizer": {"rules_check": "scalar"}}}
    out = MOD.convert(v1)
    assert out["figures"]["mandatory_rules_check"] == []


# ── convert: five_axes(axis_name_map / depth_norm / pipeline / update enum) ─
def test_convert_five_axes_mapping_and_pipeline():
    v1 = {
        "sections": {
            "6_five_axes_summary": {
                "axes": [
                    {"axis_id": "output_to", "answer": "Notion に出力", "depth": "detailed"},
                    {"axis": "input_from", "content": "src", "depth": "light"},
                    {"axis_id": "share_target", "answer": "チームへ"},
                    {"axis_id": "real_problem", "answer": "課題"},
                    {"axis_id": "knowledge_asset", "answer": "暗黙知あり"},
                ],
                "knowledge_pipeline": {
                    "ingest": "i",
                    "analysis": "an",
                    "storage": "st",
                    "retrieval": "re",
                    "update": "weekly",
                },
            }
        }
    }
    out = MOD.convert(v1)
    rows = out["five_axes"]["rows"]
    names = {r["name"] for r in rows}
    assert "出力先" in names
    assert "情報源" in names
    # depth 正規化
    out_row = next(r for r in rows if r["name"] == "出力先")
    assert out_row["depth"] == "deep"  # detailed→deep
    in_row = next(r for r in rows if r["name"] == "情報源")
    assert in_row["depth"] == "shallow"  # light→shallow
    # pipeline update enum 保持
    assert out["five_axes"]["pipeline"]["update"] == "weekly"
    # legacy 5_axes flat: 出力先→output_target 等
    assert out["5_axes"]["output_target"] == "Notion に出力"
    assert out["5_axes"]["share_target"] == "チームへ"
    # notion_db_properties 出力先抽出(Notion を検出)
    assert "Notion" in out["notion_db_properties"]["出力先"]


def test_convert_five_axes_update_invalid_to_on_demand():
    v1 = {
        "sections": {
            "6_five_axes_summary": {
                "knowledge_pipeline": {"update": "hourly"}  # enum 外
            }
        }
    }
    out = MOD.convert(v1)
    assert out["five_axes"]["pipeline"]["update"] == "on-demand"


# ── convert: design_decisions output_priority(dict/str 混在) ────────────────
def test_convert_design_decisions_dict_output_priority():
    # output_priority_finalized は dict items のみが正常変換される
    # (output / text キーを引く)。adoptions は adopted_id / reason_one_liner を読む。
    v1 = {
        "sections": {
            "7_design_decisions": {
                "adoptions": [
                    {"axis": "ax", "adopted_id": "A1", "reason_one_liner": "why"},
                    {"axis": "ax2", "adopted": "B1", "reason": "alt"},  # legacy キー
                ],
                "output_priority_finalized": [
                    {"output": "first"},
                    {"text": "third"},
                    {"nothing": "x"},  # output/text 欠落 → "" (dict なので str 分岐は通らない)
                ],
            }
        }
    }
    out = MOD.convert(v1)
    dd = out["design_decisions"]
    assert dd["rows"][0] == {"axis": "ax", "adopted": "A1", "reason": "why"}
    assert dd["rows"][1] == {"axis": "ax2", "adopted": "B1", "reason": "alt"}
    assert dd["output_priority"] == ["first", "third", ""]


def test_convert_design_decisions_falls_back_to_purpose_output_priority():
    # output_priority_finalized 欠落時は purpose の output_priority_raw を流用
    v1 = {
        "sections": {
            "3_purpose_excavator": {
                "output_priority": [{"output": "rep"}, {"text": "log"}]
            },
            "7_design_decisions": {},
        }
    }
    out = MOD.convert(v1)
    assert out["design_decisions"]["output_priority"] == ["rep", "log"]


def test_convert_design_decisions_string_item_raises_known_limitation():
    # 既知の限界: output_priority_finalized に bare string を入れると item.get で
    # AttributeError(script の `item if isinstance(item, str)` フォールバックは
    # 外側の .get が先に評価されるため到達しない)。genuine な振る舞いを固定。
    v1 = {
        "sections": {
            "7_design_decisions": {"output_priority_finalized": ["bare-string"]}
        }
    }
    with pytest.raises(AttributeError):
        MOD.convert(v1)


# ── convert: open_questions / handoff ────────────────────────────────────────
def test_convert_open_questions_and_handoff():
    v1 = {
        "sections": {
            "8_open_questions": {
                "questions": [
                    {"q": "Q1?", "blocking": True, "defer_to": "phase2"},
                    {"question": "Q2?"},
                ]
            },
            "9_handoff_contract": {
                "recommended_next": {"mode": "fast-track", "skip_to_phase": "Phase 2", "reason": "r"},
                "intake_json_path": "/p/intake.json",
                "starting_command": "/build",
            },
        }
    }
    out = MOD.convert(v1)
    oq = out["open_questions"]
    assert oq[0] == {"question": "Q1?", "blocking": True, "defer_to": "phase2"}
    assert oq[1]["question"] == "Q2?"
    h = out["handoff"]
    assert h["recommended_mode"] == "fast-track"
    assert h["skip_to_phase"] == "Phase 2"
    assert h["intake_json_path"] == "/p/intake.json"
    assert h["starting_command"] == "/build"


# ── convert: self_update / artifacts ─────────────────────────────────────────
def test_convert_self_update_and_artifacts():
    v1 = {
        "sections": {
            "0_executive_summary": {"value_realized_score": 7},
            "10_self_updater": {
                "metrics": {
                    "candidates_detected": 5,
                    "candidates_applied": 3,
                    "skipped_duplicates": 2,
                    # value_realized_score_estimate 欠落 → es score=7
                },
                "score_rationale": "ok",
                "deductions": ["d1"],
            },
            "11_artifact_index": {
                "base_path": "/base",
                "artifacts": [
                    {"path": "a.md", "role_one_liner": "role"},
                    {"path": "b.md", "description": "desc"},
                ],
            },
        }
    }
    out = MOD.convert(v1)
    su = out["self_update"]
    assert su["candidates_detected"] == 5
    assert su["candidates_applied"] == 3
    assert su["skipped_duplicates"] == 2
    assert su["value_realized_score"] == 7  # estimate 欠落 → es score
    assert su["deductions"] == ["d1"]
    art = out["artifacts"]
    assert art["base_path"] == "/base"
    assert art["files"][0] == {"path": "a.md", "description": "role"}
    assert art["files"][1] == {"path": "b.md", "description": "desc"}


# ── convert: notion_db_properties 抽出(sharing / knowledge_tags) ────────────
def test_convert_notion_props_sharing_and_tags_extracted():
    v1 = {
        "sections": {
            "1_assumption_challenger": {"adopted_deep_problem": "X" * 300},  # 200 で切詰め
            "2_user_profile": {
                "dimensions": [{"dim": "sharing_intent", "value": "チームと受講生へ共有"}]
            },
            "6_five_axes_summary": {
                "knowledge_pipeline": {"ingest": "判断基準とチェックリストを蓄積"}
            },
        }
    }
    out = MOD.convert(v1)
    nd = out["notion_db_properties"]
    # sharing から チーム / 受講生 抽出
    assert "チーム" in nd["共有相手"]
    assert "受講生" in nd["共有相手"]
    # knowledge_tags: 判断基準 / チェックリスト 抽出
    assert "判断基準" in nd["ナレッジ資産タグ"]
    assert "チェックリスト" in nd["ナレッジ資産タグ"]
    # true_problem 200 文字切詰め
    assert len(nd["真の課題"]) == 200


# ── main(argv) ───────────────────────────────────────────────────────────────
def test_main_insufficient_args_returns_2(capsys):
    rc = MOD.main(["prog"])
    assert rc == 2
    assert "Usage" in capsys.readouterr().err


def test_main_src_missing_returns_2(tmp_path, capsys):
    src = tmp_path / "nope.json"
    dst = tmp_path / "out.json"
    rc = MOD.main(["prog", str(src), str(dst)])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_main_converts_and_writes(tmp_path, capsys):
    src = tmp_path / "v1.json"
    src.write_text(
        json.dumps({"skill_name_hint": "build-thing", "sections": {}}),
        encoding="utf-8",
    )
    dst = tmp_path / "sub" / "v2.json"  # parent 未作成 → mkdir(parents) 経路
    rc = MOD.main(["prog", str(src), str(dst)])
    assert rc == 0
    assert dst.exists()
    data = json.loads(dst.read_text(encoding="utf-8"))
    assert data["meta"]["skill_name_hint"] == "build-thing"
    assert "OK: v2 context written" in capsys.readouterr().err


# ── CLI subprocess: 実 main を起動(tmp 入出力のみ。repo 非汚染) ──────────────
def test_cli_subprocess_full_roundtrip(tmp_path):
    src = tmp_path / "v1.json"
    v1 = {
        "skill_name_hint": "summarize-notes",
        "sections": {
            "0_executive_summary": {"pattern": "B", "depth": "detailed", "handoff_mode": "fast-track"},
            "6_five_axes_summary": {
                "axes": [{"axis_id": "output_to", "answer": "Slack へ"}],
                "knowledge_pipeline": {"update": "daily"},
            },
        },
    }
    src.write_text(json.dumps(v1), encoding="utf-8")
    dst = tmp_path / "v2.json"
    res = subprocess.run(
        [sys.executable, str(SCRIPT), str(src), str(dst)],
        text=True,
        capture_output=True,
    )
    assert res.returncode == 0, res.stderr
    data = json.loads(dst.read_text(encoding="utf-8"))
    assert data["meta"]["pattern_code"] == "B"
    assert data["meta"]["pattern_label"] == "改修"
    assert data["five_axes"]["pipeline"]["update"] == "daily"
    assert "Slack" in data["notion_db_properties"]["出力先"]


def test_cli_subprocess_usage_exit_2():
    res = subprocess.run([sys.executable, str(SCRIPT)], text=True, capture_output=True)
    assert res.returncode == 2
    assert "Usage" in res.stderr
