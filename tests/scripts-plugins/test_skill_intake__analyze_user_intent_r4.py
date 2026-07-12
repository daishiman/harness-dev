"""analyze_user_intent.py の genuine 機能テスト (scripts4 / 独立計測用)。

対象: plugins/skill-intake/scripts/analyze_user_intent.py

挙動の要約:
  output/<hint>/ 配下の全 phase JSON (kickoff/assumption/.../summary/next-action) を
  読み込み、抽象動詞・曖昧語シグナル検出 / true_intent 抽出 (重み付き最頻) /
  5軸ごとの最適解選定 (文字密度) を内部解析し internal-analysis.json を書き出す裏処理。
  引数不足/非ディレクトリは exit 2、正常は exit 0。

検証方針:
  - 純関数 (load_json_safely / detect_signals / extract_true_intent /
    select_optimal_per_axis) を importlib で実ファイルからロードし、
    正常系・各異常系・エッジ (空 dict / 不正 JSON / 欠落ファイル / ネスト dict/list /
    非 dict true_purpose / 候補ゼロ / None 軸 / dict 軸の JSON 化 / 重み最大選択) を
    実入力で assert。
  - main は tmp_path に phase JSON を実配置し in-process 実行、戻り値・stdout・
    生成 internal-analysis.json の中身 (signals / signal_summary / true_intent /
    per_axis_optimal / hidden_from_user / consumed_by) を assert。
    引数不足 (exit 2) / 非ディレクトリ (exit 2) も網羅。
  - CLI 経路 (__main__ guard 経由 sys.exit) は subprocess(sys.executable) で
    exit code と生成ファイルを実測。

network: false / keychain: なし / 実 repo 書換: なし (tmp_path のみ)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "analyze_user_intent.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("analyze_user_intent_uut_r4", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


def _wj(p: Path, data) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


# ── load_json_safely ─────────────────────────────────────────────────────────
def test_load_json_safely_reads_valid(tmp_path):
    p = _wj(tmp_path / "a.json", {"k": "v"})
    assert MOD.load_json_safely(p) == {"k": "v"}


def test_load_json_safely_returns_none_on_corrupt(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{ not json ]", encoding="utf-8")
    assert MOD.load_json_safely(p) is None


def test_load_json_safely_returns_none_on_missing(tmp_path):
    assert MOD.load_json_safely(tmp_path / "nope.json") is None


# ── detect_signals ───────────────────────────────────────────────────────────
def test_detect_signals_abstract_verb_in_string():
    sig = MOD.detect_signals("業務を効率化したい", prefix="purpose")
    assert len(sig) == 1
    assert sig[0]["kind"] == "abstract_verb"
    assert sig[0]["token"] == "効率化"
    assert sig[0]["field"] == "purpose"
    assert "効率化" in sig[0]["text"]


def test_detect_signals_vague_token_in_string():
    sig = MOD.detect_signals("なんとなくいい感じにして", prefix="free")
    kinds = {(s["kind"], s["token"]) for s in sig}
    assert ("vague_token", "なんとなく") in kinds
    assert ("vague_token", "いい感じ") in kinds


def test_detect_signals_recurses_dict_and_builds_path():
    obj = {"outer": {"inner": "もっと自動化したい"}}
    sig = MOD.detect_signals(obj)
    assert len(sig) == 1
    assert sig[0]["field"] == "outer.inner"
    assert sig[0]["token"] == "自動化"


def test_detect_signals_recurses_list_with_index_path():
    obj = {"items": ["改善したい", "no-signal", "強化する"]}
    sig = MOD.detect_signals(obj)
    fields = sorted(s["field"] for s in sig)
    assert fields == ["items[0]", "items[2]"]


def test_detect_signals_truncates_text_to_80_chars():
    long = "効率化" + "あ" * 200
    sig = MOD.detect_signals(long)
    assert len(sig[0]["text"]) == 80


def test_detect_signals_no_match_returns_empty():
    assert MOD.detect_signals("普通の説明文です") == []
    assert MOD.detect_signals(12345) == []
    assert MOD.detect_signals(None) == []


def test_detect_signals_multiple_tokens_in_one_string():
    # 1 文に複数の抽象動詞 → それぞれ別シグナル
    sig = MOD.detect_signals("最適化と自動化を同時に")
    tokens = sorted(s["token"] for s in sig)
    assert tokens == ["最適化", "自動化"]


# ── extract_true_intent ──────────────────────────────────────────────────────
def test_extract_true_intent_picks_highest_weight():
    phase = {
        "purpose": {
            "true_purpose": {"verb_object": "請求書を発行する", "underlying_motivation": "ミス削減"},
        },
        "summary": {"five_axes": {"true_problem": "発行漏れの検知"}},
        "assumption": {"confirmed_deep_problem": "属人化"},
    }
    res = MOD.extract_true_intent(phase)
    # weight 3 が 2 件 (verb_object, true_problem) → max は最初の weight 3
    assert res["best_pick"]["weight"] == 3
    sources = {c["source"] for c in res["candidates"]}
    assert "purpose.json/true_purpose.verb_object" in sources
    assert "summary.json/five_axes.true_problem" in sources
    assert "assumption.json/confirmed_deep_problem" in sources
    assert "purpose.json/underlying_motivation" in sources
    assert len(res["candidates"]) == 4


def test_extract_true_intent_empty_when_no_candidates():
    res = MOD.extract_true_intent({})
    assert res["candidates"] == []
    assert res["best_pick"] is None


def test_extract_true_intent_handles_non_dict_true_purpose():
    # true_purpose が dict でない (str) → tp は {} 扱いで例外を出さない
    phase = {"purpose": {"true_purpose": "just a string"}}
    res = MOD.extract_true_intent(phase)
    assert res["candidates"] == []
    assert res["best_pick"] is None


def test_extract_true_intent_partial_only_motivation():
    phase = {"purpose": {"true_purpose": {"underlying_motivation": "理由"}}}
    res = MOD.extract_true_intent(phase)
    assert len(res["candidates"]) == 1
    assert res["best_pick"]["source"] == "purpose.json/underlying_motivation"
    assert res["best_pick"]["weight"] == 2


def test_extract_true_intent_handles_null_subobjects():
    # purpose / summary / assumption が None → "or {}" で安全に処理
    phase = {"purpose": None, "summary": None, "assumption": None}
    res = MOD.extract_true_intent(phase)
    assert res["candidates"] == []


# ── select_optimal_per_axis ──────────────────────────────────────────────────
def test_select_optimal_per_axis_all_axes_present():
    phase = {
        "summary": {
            "five_axes": {
                "output_target": "Notion ページ",
                "info_source": "MF 取引データ",
                "share_target": "経理チーム",
                "true_problem": "発行漏れ",
                "knowledge_assets": "過去の請求履歴",
            }
        }
    }
    axes = MOD.select_optimal_per_axis(phase)
    assert set(axes) == {
        "output_target",
        "info_source",
        "share_target",
        "true_problem",
        "knowledge_assets",
    }
    out = axes["output_target"]
    assert out["selected"] == "Notion ページ"
    # 空白除去後の文字数 = specificity
    assert out["specificity_score"] == len("Notion ページ".replace(" ", ""))
    assert "文字密度" in out["reason"]


def test_select_optimal_per_axis_missing_axis_marks_unfilled():
    axes = MOD.select_optimal_per_axis({"summary": {"five_axes": {"output_target": "x"}}})
    assert axes["info_source"]["selected"] is None
    assert axes["info_source"]["reason"] == "summary.json 未充足"
    assert axes["info_source"]["alternatives"] == []
    # specificity_score は未充足軸には付かない
    assert "specificity_score" not in axes["info_source"]


def test_select_optimal_per_axis_dict_value_is_json_serialized():
    # 軸の値が dict → json.dumps で文字密度を測る
    val = {"format": "pdf", "dest": "drive"}
    axes = MOD.select_optimal_per_axis({"summary": {"five_axes": {"output_target": val}}})
    out = axes["output_target"]
    assert out["selected"] == val
    expected = len(json.dumps(val, ensure_ascii=False).replace(" ", ""))
    # json.dumps 結果の空白除去長 (\s+ は半角空白含む)
    import re

    expected = len(re.sub(r"\s+", "", json.dumps(val, ensure_ascii=False)))
    assert out["specificity_score"] == expected


def test_select_optimal_per_axis_empty_summary_all_unfilled():
    axes = MOD.select_optimal_per_axis({})
    assert all(a["selected"] is None for a in axes.values())
    assert all(a["reason"] == "summary.json 未充足" for a in axes.values())


# ── main: in-process ─────────────────────────────────────────────────────────
def test_main_arg_missing_returns_2(capsys):
    rc = MOD.main(["analyze_user_intent.py"])
    assert rc == 2
    assert "usage" in capsys.readouterr().err


def test_main_not_a_directory_returns_2(tmp_path, capsys):
    f = tmp_path / "afile.txt"
    f.write_text("x", encoding="utf-8")
    rc = MOD.main(["prog", str(f)])
    assert rc == 2
    assert "not a directory" in capsys.readouterr().err


def test_main_writes_internal_analysis_full(tmp_path, capsys):
    hint = tmp_path / "hint-acme"
    hint.mkdir()
    _wj(
        hint / "purpose.json",
        {"true_purpose": {"verb_object": "請求書を自動発行する", "underlying_motivation": "属人化を効率化"}},
    )
    _wj(
        hint / "summary.json",
        {
            "five_axes": {
                "output_target": "Notion",
                "info_source": "MF",
                "share_target": "経理",
                "true_problem": "発行漏れをなんとかしたい",
                "knowledge_assets": "履歴",
            }
        },
    )
    _wj(hint / "assumption.json", {"confirmed_deep_problem": "手作業のミス"})

    rc = MOD.main(["prog", str(hint)])
    assert rc == 0
    assert "wrote" in capsys.readouterr().out

    out_path = hint / "internal-analysis.json"
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))

    assert data["produced_by"] == "analyze_user_intent.py"
    assert data["hint_dir"] == str(hint.resolve())
    assert data["hidden_from_user"] is True
    assert data["consumed_by"] == ["render_notion_page.py", "render-intake-final.py"]
    assert "timestamp" in data

    # true_intent: verb_object (weight 3) が最有力
    assert data["true_intent"]["best_pick"]["weight"] == 3

    # signals: 効率化 (abstract) + なんとなく? -> "効率化" は underlying_motivation に含まれる
    tokens = {s["token"] for s in data["signals"]}
    assert "効率化" in tokens
    assert "自動発行" not in tokens  # 自動化 ではない (部分一致しない)

    # per_axis: 全 5 軸
    assert set(data["per_axis_optimal"]) == {
        "output_target",
        "info_source",
        "share_target",
        "true_problem",
        "knowledge_assets",
    }

    # signal_summary は count 降順の most_common 形式
    assert all({"kind", "token", "count"} <= set(item) for item in data["signal_summary"])


def test_main_empty_dir_produces_minimal_analysis(tmp_path, capsys):
    # phase JSON が一切無い → 全 load None → {} 扱いで例外なく完走
    hint = tmp_path / "empty-hint"
    hint.mkdir()
    rc = MOD.main(["prog", str(hint)])
    assert rc == 0
    data = json.loads((hint / "internal-analysis.json").read_text(encoding="utf-8"))
    assert data["signals"] == []
    assert data["signal_summary"] == []
    assert data["true_intent"]["best_pick"] is None
    # 全軸未充足
    assert all(a["selected"] is None for a in data["per_axis_optimal"].values())


def test_main_corrupt_phase_file_is_tolerated(tmp_path):
    hint = tmp_path / "hint-corrupt"
    hint.mkdir()
    (hint / "summary.json").write_text("{ broken json ]", encoding="utf-8")
    _wj(hint / "purpose.json", {"true_purpose": {"verb_object": "X を最適化"}})
    rc = MOD.main(["prog", str(hint)])
    assert rc == 0
    data = json.loads((hint / "internal-analysis.json").read_text(encoding="utf-8"))
    # 壊れた summary は {} 扱い → 軸は全未充足だが purpose の候補は残る
    assert data["true_intent"]["best_pick"]["text"] == "X を最適化"
    assert all(a["selected"] is None for a in data["per_axis_optimal"].values())


def test_main_signal_summary_counts_aggregate(tmp_path):
    hint = tmp_path / "hint-counts"
    hint.mkdir()
    # 同一トークン "効率化" を複数 phase に散らす → count 集計を検証
    _wj(hint / "purpose.json", {"a": "効率化", "b": "効率化したい"})
    _wj(hint / "kickoff.json", {"c": "効率化"})
    rc = MOD.main(["prog", str(hint)])
    assert rc == 0
    data = json.loads((hint / "internal-analysis.json").read_text(encoding="utf-8"))
    summary = {(i["kind"], i["token"]): i["count"] for i in data["signal_summary"]}
    assert summary[("abstract_verb", "効率化")] == 3


# ── CLI subprocess (exit code 実測 / __main__ guard) ─────────────────────────
def test_cli_subprocess_runs_and_writes(tmp_path):
    hint = tmp_path / "cli-hint"
    hint.mkdir()
    _wj(hint / "purpose.json", {"true_purpose": {"verb_object": "自動化したい"}})
    res = subprocess.run(
        [sys.executable, str(SCRIPT), str(hint)], text=True, capture_output=True
    )
    assert res.returncode == 0, res.stderr
    assert "wrote" in res.stdout
    assert (hint / "internal-analysis.json").exists()


def test_cli_subprocess_missing_arg_exit_2():
    res = subprocess.run([sys.executable, str(SCRIPT)], text=True, capture_output=True)
    assert res.returncode == 2
    assert "usage" in res.stderr
