"""Genuine functional tests for plugins/skill-intake/scripts/measure_value_realized.py.

カバレッジ方針:
- 純関数 (score / load_previous_scores / is_declining) を **in-process** で実値検証する。
  axis フィル判定 (>=4 文字 str)、manifest summary.total vs items 長、open-question ペナルティ、
  合成スコアの重み (0.55/0.35/0.10) を境界値込みで検証。
- `main()` の引数パース (位置引数 / --manifest / --history)・usage error・入力 JSON
  読込失敗・正常出力 (stdout JSON) の各分岐を argv を直接渡して駆動する。
- すべての I/O は tmp_path 配下に限定し repo を汚さない。network/keychain/secret 系の
  依存はこのスクリプトには無い (pure compute) ため stub は不要。

ファイル名は他ディレクトリと衝突しないよう `_r4` を付して新規作成 (pytest basename 衝突回避)。
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "measure_value_realized.py"

_SPEC = importlib.util.spec_from_file_location("measure_value_realized_s4", SCRIPT)
MVR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MVR)


# ===================== score(): axis_score =====================

def _full_axes():
    return {k: "answer-text" for k in MVR.AXES}


def test_score_all_axes_filled_no_manifest():
    intake = {"5_axes": _full_axes()}
    r = MVR.score(intake, None)
    assert r["axes_filled"] == len(MVR.AXES)
    assert r["components"]["axisScore"] == 1.0
    # manifest 無し → visScore 0、open_questions 無し → openPenalty 1.0
    assert r["visualization_count"] == 0
    assert r["components"]["visScore"] == 0
    assert r["components"]["openPenalty"] == 1.0
    # total = 0.55*1 + 0.35*0 + 0.10*1 = 0.65
    assert r["score"] == 0.65


def test_score_five_axes_alias_key():
    # '5_axes' 不在時 'five_axes' を使う
    intake = {"five_axes": _full_axes()}
    assert MVR.score(intake, None)["axes_filled"] == len(MVR.AXES)


def test_score_short_axis_not_counted():
    # 3 文字以下 / 非 str は未充足扱い
    axes = {
        "output_destination": "abc",          # 3 文字 < 4 → 未充足
        "info_source": "  abcd  ",            # strip 後 4 文字 → 充足
        "share_target": 123,                  # 非 str → 未充足
        "true_problem": "",                   # 空 → 未充足
        "knowledge_assets": "valid-value",    # 充足
    }
    r = MVR.score({"5_axes": axes}, None)
    assert r["axes_filled"] == 2
    assert r["components"]["axisScore"] == 2 / len(MVR.AXES)


def test_score_missing_axes_object():
    # axes が無ければ全部未充足
    r = MVR.score({}, None)
    assert r["axes_filled"] == 0
    assert r["components"]["axisScore"] == 0.0


# ===================== score(): vis_score (manifest) =====================

def test_score_manifest_summary_total():
    intake = {"5_axes": _full_axes()}
    r = MVR.score(intake, {"summary": {"total": 6}})
    assert r["visualization_count"] == 6
    # 6/12 = 0.5
    assert r["components"]["visScore"] == 0.5


def test_score_manifest_summary_total_caps_at_one():
    # total > 12 でも visScore は 1 に飽和
    r = MVR.score({"5_axes": _full_axes()}, {"summary": {"total": 30}})
    assert r["visualization_count"] == 30
    assert r["components"]["visScore"] == 1


def test_score_manifest_items_fallback():
    # summary 無し / total が数値でない → items の長さを使う
    r = MVR.score({}, {"items": [1, 2, 3, 4]})
    assert r["visualization_count"] == 4


def test_score_manifest_summary_non_numeric_total_falls_to_items():
    # summary.total が文字列 → items にフォールバック
    r = MVR.score({}, {"summary": {"total": "x"}, "items": [1, 2]})
    assert r["visualization_count"] == 2


def test_score_manifest_not_dict():
    # manifest が dict でない → vis_count 0
    r = MVR.score({"5_axes": _full_axes()}, ["not", "a", "dict"])
    assert r["visualization_count"] == 0
    assert r["components"]["visScore"] == 0


def test_score_manifest_summary_total_float():
    r = MVR.score({}, {"summary": {"total": 3.0}})
    assert r["visualization_count"] == 3


# ===================== score(): open-question penalty =====================

def test_score_open_question_penalty():
    intake = {"5_axes": _full_axes(), "open_questions": ["q1", "q2", "q3"]}
    r = MVR.score(intake, None)
    # 3 件 → 1 - 3*0.05 = 0.85
    assert r["components"]["openPenalty"] == pytest.approx(0.85)


def test_score_open_question_penalty_floor_at_zero():
    # 大量の open_questions でもペナルティは 0 で下げ止まる
    intake = {"5_axes": _full_axes(), "open_questions": ["q"] * 100}
    r = MVR.score(intake, None)
    assert r["components"]["openPenalty"] == 0.0


def test_score_open_questions_not_list_ignored():
    # open_questions が list でなければ 0 件扱い
    intake = {"5_axes": _full_axes(), "open_questions": "not-a-list"}
    r = MVR.score(intake, None)
    assert r["components"]["openPenalty"] == 1.0


def test_score_weighted_total_rounding():
    # 全要素が中途半端な値で合成・丸めを検証
    intake = {
        "5_axes": {"output_destination": "abcd", "info_source": "abcd"},  # 2/5 = 0.4
        "open_questions": ["q1", "q2"],                                    # 0.9
    }
    manifest = {"summary": {"total": 6}}                                    # 0.5
    r = MVR.score(intake, manifest)
    # 0.55*0.4 + 0.35*0.5 + 0.10*0.9 = 0.22 + 0.175 + 0.09 = 0.485
    assert r["score"] == 0.485


# ===================== load_previous_scores() =====================

def test_load_previous_none_arg():
    assert MVR.load_previous_scores(None) == []


def test_load_previous_missing_file(tmp_path):
    assert MVR.load_previous_scores(str(tmp_path / "nope.json")) == []


def test_load_previous_scores_list_trims_to_5(tmp_path):
    p = tmp_path / "h.json"
    p.write_text(json.dumps({"previous_scores": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]}),
                 encoding="utf-8")
    # 末尾 5 件だけ
    assert MVR.load_previous_scores(str(p)) == [0.3, 0.4, 0.5, 0.6, 0.7]


def test_load_previous_single_value_field(tmp_path):
    p = tmp_path / "h.json"
    p.write_text(json.dumps({"value_realized_score": 0.42}), encoding="utf-8")
    assert MVR.load_previous_scores(str(p)) == [0.42]


def test_load_previous_dict_without_known_keys(tmp_path):
    p = tmp_path / "h.json"
    p.write_text(json.dumps({"other": 1}), encoding="utf-8")
    assert MVR.load_previous_scores(str(p)) == []


def test_load_previous_non_dict_json(tmp_path):
    p = tmp_path / "h.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert MVR.load_previous_scores(str(p)) == []


def test_load_previous_broken_json_returns_empty(tmp_path):
    p = tmp_path / "h.json"
    p.write_text("{not json", encoding="utf-8")
    # 例外は握りつぶして []
    assert MVR.load_previous_scores(str(p)) == []


# ===================== is_declining() =====================

def test_is_declining_true():
    # prev[-2] > prev[-1] かつ current < prev[-1]
    assert MVR.is_declining([0.5, 0.4], 0.3) is True


def test_is_declining_false_when_current_not_lower():
    assert MVR.is_declining([0.5, 0.4], 0.45) is False


def test_is_declining_false_when_prev_not_descending():
    assert MVR.is_declining([0.3, 0.4], 0.2) is False


def test_is_declining_false_too_short():
    assert MVR.is_declining([0.5], 0.1) is False
    assert MVR.is_declining([], 0.1) is False


def test_is_declining_false_non_list():
    assert MVR.is_declining("not-a-list", 0.1) is False


def test_is_declining_false_non_numeric_entries():
    assert MVR.is_declining(["a", "b"], 0.1) is False


# ===================== main() =====================

def test_main_usage_error_no_intake(capsys):
    rc = MVR.main([])
    assert rc == 2
    assert "usage:" in capsys.readouterr().err


def test_main_input_error_missing_file(tmp_path, capsys):
    rc = MVR.main([str(tmp_path / "nope.json")])
    assert rc == 2
    assert "input error" in capsys.readouterr().err


def test_main_input_error_broken_json(tmp_path, capsys):
    p = tmp_path / "intake.json"
    p.write_text("{broken", encoding="utf-8")
    rc = MVR.main([str(p)])
    assert rc == 2
    assert "input error" in capsys.readouterr().err


def test_main_happy_path_positional(tmp_path, capsys):
    intake = tmp_path / "intake.json"
    intake.write_text(json.dumps({"5_axes": _full_axes()}), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"summary": {"total": 12}}), encoding="utf-8")
    rc = MVR.main([str(intake), str(manifest)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["axes_filled"] == len(MVR.AXES)
    assert out["visualization_count"] == 12
    assert out["components"]["visScore"] == 1
    assert out["previous_scores"] == []
    assert out["declining"] is False


def test_main_manifest_flag(tmp_path, capsys):
    intake = tmp_path / "intake.json"
    intake.write_text(json.dumps({"5_axes": _full_axes()}), encoding="utf-8")
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"items": [1, 2, 3]}), encoding="utf-8")
    rc = MVR.main([str(intake), "--manifest", str(manifest)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["visualization_count"] == 3


def test_main_manifest_path_not_exist_ignored(tmp_path, capsys):
    # --manifest を渡しても存在しなければ manifest=None (vis 0) で処理継続
    intake = tmp_path / "intake.json"
    intake.write_text(json.dumps({"5_axes": _full_axes()}), encoding="utf-8")
    rc = MVR.main([str(intake), "--manifest", str(tmp_path / "absent.json")])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["visualization_count"] == 0


def test_main_history_declining(tmp_path, capsys):
    # history で previous_scores が下降 & current も下降 → declining=True
    intake = tmp_path / "intake.json"
    # axisScore を低めにして score を確実に prev[-1] より小さくする
    intake.write_text(json.dumps({"5_axes": {}, "open_questions": ["q"] * 20}),
                      encoding="utf-8")
    history = tmp_path / "self-update.json"
    history.write_text(json.dumps({"previous_scores": [0.9, 0.8]}), encoding="utf-8")
    rc = MVR.main([str(intake), "--history", str(history)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["previous_scores"] == [0.9, 0.8]
    # score は 0 付近 (< 0.8) なので declining
    assert out["score"] < 0.8
    assert out["declining"] is True


def test_main_history_not_declining(tmp_path, capsys):
    intake = tmp_path / "intake.json"
    intake.write_text(json.dumps({"5_axes": _full_axes()}), encoding="utf-8")
    history = tmp_path / "h.json"
    history.write_text(json.dumps({"previous_scores": [0.1, 0.2]}), encoding="utf-8")
    rc = MVR.main([str(intake), "--history", str(history)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["declining"] is False


def test_main_extra_positional_treated_as_manifest(tmp_path, capsys):
    # intake_file 充足後の 2 番目位置引数は manifest として扱われる
    intake = tmp_path / "intake.json"
    intake.write_text(json.dumps({"5_axes": _full_axes()}), encoding="utf-8")
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"summary": {"total": 2}}), encoding="utf-8")
    extra = tmp_path / "extra.json"
    extra.write_text(json.dumps({"summary": {"total": 99}}), encoding="utf-8")
    # intake, manifest(位置), extra(無視: manifest_file が既に埋まっている)
    rc = MVR.main([str(intake), str(manifest), str(extra)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    # 最初の位置 manifest が採用される
    assert out["visualization_count"] == 2


def test_main_entrypoint_subprocess(tmp_path):
    # __main__ 経路 (sys.exit(main(...))) を subprocess で実起動し exit code を確認
    import subprocess
    intake = tmp_path / "intake.json"
    intake.write_text(json.dumps({"5_axes": _full_axes()}), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(intake)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["axes_filled"] == len(MVR.AXES)

    # usage error 経路
    proc2 = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True,
    )
    assert proc2.returncode == 2
    assert "usage:" in proc2.stderr
