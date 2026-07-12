"""measure_value_realized.py の純関数 + main CLI 契約を network 無しで網羅する。

measure_value_realized は intake.json (5軸 + open_questions) と任意の visual manifest から
value-realized スコア (0.55*axis + 0.35*vis + 0.10*open_penalty) を算出し、--history で
過去スコア列を読んで declining 判定を付ける純計算スクリプト。実通信・keychain は一切叩かない。

本テストは:
  - score(): axis filled カウント (>=4 文字判定 / 空 / 短すぎ / 非 str)、five_axes 別名、
    visScore (summary.total / items 長 / 上限 1.0 への clamp)、open_penalty (0 件 / 多数で 0 下限)
  - load_previous_scores(): None / 不存在 / previous_scores 列 (末尾5件) / value_realized_score 単発 /
    不正 JSON / dict 以外 / 空 dict
  - is_declining(): 列が短い / 2 連続下降 + current 継続下降 / 非数値混入 / 反発上昇
  - main(): 位置引数のみ / --manifest / --history / 欠落 intake / 不正 JSON / manifest 不存在は無視 /
    usage (exit 2)
を実入力で genuine に assert する。すべて tmp_path を使い repo を汚さない。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "measure_value_realized.py"

_SPEC = importlib.util.spec_from_file_location("measure_value_realized_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


FULL_AXES = {
    "output_destination": "Notion DB",
    "info_source": "Slack ログ",
    "share_target": "経理チーム",
    "true_problem": "発行漏れ検知が手作業",
    "knowledge_assets": "過去の請求一覧",
}


# --------------------------------------------------------------------------
# score(): 5 軸の filled カウント
# --------------------------------------------------------------------------

def test_score_all_axes_filled_gives_full_axis_score():
    r = MOD.score({"5_axes": FULL_AXES}, None)
    assert r["axes_filled"] == 5
    assert r["components"]["axisScore"] == 1.0


def test_score_uses_five_axes_alias():
    # '5_axes' が無く 'five_axes' がある場合も同じく解釈される。
    r = MOD.score({"five_axes": FULL_AXES}, None)
    assert r["axes_filled"] == 5


def test_score_short_or_empty_axis_not_counted():
    axes = dict(FULL_AXES)
    axes["info_source"] = "abc"        # 3 文字 (< 4) は未充足
    axes["share_target"] = "   "       # 空白のみ strip 後 0 文字
    axes["true_problem"] = ""          # 空
    r = MOD.score({"5_axes": axes}, None)
    assert r["axes_filled"] == 2       # output_destination + knowledge_assets のみ
    assert r["components"]["axisScore"] == 2 / 5


def test_score_non_str_axis_not_counted():
    axes = dict(FULL_AXES)
    axes["info_source"] = 12345        # 非 str は未充足
    axes["share_target"] = None
    r = MOD.score({"5_axes": axes}, None)
    assert r["axes_filled"] == 3


def test_score_no_axes_key_gives_zero():
    r = MOD.score({}, None)
    assert r["axes_filled"] == 0
    assert r["components"]["axisScore"] == 0.0


# --------------------------------------------------------------------------
# score(): visualization count (manifest)
# --------------------------------------------------------------------------

def test_score_vis_from_summary_total():
    r = MOD.score({"5_axes": FULL_AXES}, {"summary": {"total": 6}})
    assert r["visualization_count"] == 6
    assert r["components"]["visScore"] == 0.5   # 6/12


def test_score_vis_from_items_length_when_no_summary_total():
    r = MOD.score({"5_axes": FULL_AXES}, {"items": ["a", "b", "c"]})
    assert r["visualization_count"] == 3
    assert r["components"]["visScore"] == 0.25


def test_score_vis_clamped_to_one():
    # 12 を超える可視化数でも visScore は 1.0 で頭打ち。
    r = MOD.score({"5_axes": FULL_AXES}, {"summary": {"total": 30}})
    assert r["visualization_count"] == 30
    assert r["components"]["visScore"] == 1

def test_score_vis_float_total_coerced_to_int():
    r = MOD.score({"5_axes": FULL_AXES}, {"summary": {"total": 4.0}})
    assert r["visualization_count"] == 4


def test_score_vis_zero_when_manifest_none():
    r = MOD.score({"5_axes": FULL_AXES}, None)
    assert r["visualization_count"] == 0
    assert r["components"]["visScore"] == 0


def test_score_vis_zero_when_manifest_not_dict():
    r = MOD.score({"5_axes": FULL_AXES}, ["not", "a", "dict"])
    assert r["visualization_count"] == 0


def test_score_vis_summary_without_total_falls_through_to_zero():
    # summary はあるが total が無く items も無い → 0。
    r = MOD.score({"5_axes": FULL_AXES}, {"summary": {"foo": 1}})
    assert r["visualization_count"] == 0


# --------------------------------------------------------------------------
# score(): open_questions penalty
# --------------------------------------------------------------------------

def test_score_open_penalty_no_questions_is_one():
    r = MOD.score({"5_axes": FULL_AXES, "open_questions": []}, None)
    assert r["components"]["openPenalty"] == 1.0


def test_score_open_penalty_decreases_with_count():
    r = MOD.score({"5_axes": FULL_AXES, "open_questions": ["q1", "q2", "q3"]}, None)
    assert r["components"]["openPenalty"] == pytest.approx(1 - 3 * 0.05)


def test_score_open_penalty_floored_at_zero():
    # 0.05 * 21 = 1.05 → max(0, 1-1.05) = 0。
    r = MOD.score({"5_axes": FULL_AXES, "open_questions": ["q"] * 21}, None)
    assert r["components"]["openPenalty"] == 0.0


def test_score_open_questions_non_list_treated_as_zero():
    r = MOD.score({"5_axes": FULL_AXES, "open_questions": "not-a-list"}, None)
    assert r["components"]["openPenalty"] == 1.0


def test_score_total_weighting_is_exact():
    # 全充足 axis(1.0) + vis 6/12(0.5) + open 2件(0.9):
    # 0.55*1 + 0.35*0.5 + 0.10*0.9 = 0.55 + 0.175 + 0.09 = 0.815
    r = MOD.score(
        {"5_axes": FULL_AXES, "open_questions": ["q1", "q2"]},
        {"summary": {"total": 6}},
    )
    assert r["score"] == 0.815


# --------------------------------------------------------------------------
# load_previous_scores()
# --------------------------------------------------------------------------

def test_load_previous_none_arg_returns_empty():
    assert MOD.load_previous_scores(None) == []


def test_load_previous_missing_file_returns_empty(tmp_path):
    assert MOD.load_previous_scores(str(tmp_path / "nope.json")) == []


def test_load_previous_scores_list_keeps_last_five(tmp_path):
    p = tmp_path / "self-update.json"
    p.write_text(json.dumps({"previous_scores": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]}), encoding="utf-8")
    assert MOD.load_previous_scores(str(p)) == [0.3, 0.4, 0.5, 0.6, 0.7]


def test_load_previous_single_value_realized_score(tmp_path):
    p = tmp_path / "self-update.json"
    p.write_text(json.dumps({"value_realized_score": 0.42}), encoding="utf-8")
    assert MOD.load_previous_scores(str(p)) == [0.42]


def test_load_previous_dict_without_known_keys_returns_empty(tmp_path):
    p = tmp_path / "self-update.json"
    p.write_text(json.dumps({"unrelated": 1}), encoding="utf-8")
    assert MOD.load_previous_scores(str(p)) == []


def test_load_previous_non_dict_json_returns_empty(tmp_path):
    p = tmp_path / "self-update.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert MOD.load_previous_scores(str(p)) == []


def test_load_previous_invalid_json_returns_empty(tmp_path):
    p = tmp_path / "self-update.json"
    p.write_text("{ broken json", encoding="utf-8")
    assert MOD.load_previous_scores(str(p)) == []


# --------------------------------------------------------------------------
# is_declining()
# --------------------------------------------------------------------------

def test_is_declining_needs_at_least_two_prev():
    assert MOD.is_declining([], 0.5) is False
    assert MOD.is_declining([0.9], 0.5) is False


def test_is_declining_non_list_prev():
    assert MOD.is_declining("nope", 0.5) is False


def test_is_declining_true_when_continuous_descent():
    # prev[-2]=0.8 > prev[-1]=0.7 かつ current 0.6 < 0.7 → 連続下降。
    assert MOD.is_declining([0.9, 0.8, 0.7], 0.6) is True


def test_is_declining_false_when_current_rebounds():
    assert MOD.is_declining([0.9, 0.8, 0.7], 0.75) is False


def test_is_declining_false_when_prev_was_rising():
    # prev[-2]=0.6 < prev[-1]=0.7 → そもそも下降していない。
    assert MOD.is_declining([0.5, 0.6, 0.7], 0.4) is False


def test_is_declining_false_when_prev_contains_non_number():
    assert MOD.is_declining([0.8, "x"], 0.5) is False


# --------------------------------------------------------------------------
# main(argv) in-process 契約 (subprocess の子は素の --cov で計上されないため直接呼ぶ)
# --------------------------------------------------------------------------

def _write_intake(tmp_path, **kw):
    p = tmp_path / "intake.json"
    obj = {"5_axes": FULL_AXES, "open_questions": []}
    obj.update(kw)
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return p


def test_main_positional_intake_only(tmp_path, capsys):
    intake = _write_intake(tmp_path)
    rc = MOD.main([str(intake)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["axes_filled"] == 5
    assert out["visualization_count"] == 0
    assert out["previous_scores"] == []
    assert out["declining"] is False


def test_main_positional_manifest(tmp_path, capsys):
    intake = _write_intake(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"summary": {"total": 12}}), encoding="utf-8")
    rc = MOD.main([str(intake), str(manifest)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["visualization_count"] == 12
    assert out["components"]["visScore"] == 1


def test_main_opt_manifest_flag(tmp_path, capsys):
    intake = _write_intake(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"items": ["a", "b"]}), encoding="utf-8")
    rc = MOD.main([str(intake), "--manifest", str(manifest)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["visualization_count"] == 2


def test_main_history_flag_marks_declining(tmp_path, capsys):
    intake = _write_intake(tmp_path, open_questions=["q"] * 21)  # penalty 0
    # 全充足 axis(1) vis 0 open 0 → 0.55*1 = 0.55。
    hist = tmp_path / "self-update.json"
    hist.write_text(json.dumps({"previous_scores": [0.9, 0.7]}), encoding="utf-8")
    rc = MOD.main([str(intake), "--history", str(hist)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["score"] == 0.55
    assert out["previous_scores"] == [0.9, 0.7]
    # prev 0.9>0.7 かつ current 0.55<0.7 → declining。
    assert out["declining"] is True


def test_main_history_not_declining_when_rebound(tmp_path, capsys):
    intake = _write_intake(tmp_path)  # score 高め (0.55)
    hist = tmp_path / "self-update.json"
    hist.write_text(json.dumps({"previous_scores": [0.9, 0.1]}), encoding="utf-8")
    rc = MOD.main([str(intake), "--history", str(hist)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    # current 0.55 > prev[-1] 0.1 → 反発で declining でない。
    assert out["declining"] is False


def test_main_manifest_missing_is_silently_ignored(tmp_path, capsys):
    intake = _write_intake(tmp_path)
    rc = MOD.main([str(intake), "--manifest", str(tmp_path / "absent.json")])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    # 不存在 manifest は無視 → vis 0。
    assert out["visualization_count"] == 0


def test_main_no_intake_returns_usage_2(capsys):
    rc = MOD.main([])
    assert rc == 2
    assert "usage:" in capsys.readouterr().err


def test_main_invalid_json_returns_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    rc = MOD.main([str(bad)])
    assert rc == 2
    assert "input error" in capsys.readouterr().err


def test_main_missing_intake_file_returns_2(tmp_path, capsys):
    rc = MOD.main([str(tmp_path / "nope.json")])
    assert rc == 2
    assert "input error" in capsys.readouterr().err


# --------------------------------------------------------------------------
# subprocess 契約 (CLI 統合: argv 解釈 + stdout JSON + exit code)
# --------------------------------------------------------------------------

def _run(args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd,
    )


def test_cli_positional_to_stdout(tmp_path):
    intake = _write_intake(tmp_path)
    proc = _run([str(intake)], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["axes_filled"] == 5


def test_cli_usage_exit2(tmp_path):
    proc = _run([], cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "usage:" in proc.stderr


def test_cli_invalid_json_exit2(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ broken", encoding="utf-8")
    proc = _run([str(bad)], cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "input error" in proc.stderr


def test_module_guard_runs_main_via_runpy(tmp_path, capsys):
    # if __name__ == "__main__": sys.exit(main(sys.argv[1:])) の末尾ガードを踏む。
    import runpy
    intake = _write_intake(tmp_path)
    sys.argv = ["measure_value_realized.py", str(intake)]
    with pytest.raises(SystemExit) as ei:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert ei.value.code == 0
    assert json.loads(capsys.readouterr().out)["axes_filled"] == 5
