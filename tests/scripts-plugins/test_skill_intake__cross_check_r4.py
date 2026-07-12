"""Genuine functional tests for plugins/skill-intake/scripts/cross_check.py.

対象は intake.md と intake.json の 5 軸 answer 一致を Jaccard 類似度で検査する
純粋なローカル処理スクリプト (network/keychain/secret 一切なし)。

カバレッジ方針:
- 純関数 (parse_sections / pick_axis / extract_frontmatter / convert_md /
  norm / similarity / cross) を **in-process** で実値検証する。
- `main()` の引数不足・入力エラー (欠落ファイル / 不正 JSON) ・一致 (exit 0) /
  不一致 (exit 1) の各分岐を subprocess ではなく argv 差し替えで genuine に駆動。
- すべての I/O は tmp_path に限定し repo を汚さない。

ファイル名は他ディレクトリの cross 系と衝突しないよう `_r4` を付して新規作成
(pytest basename 衝突回避)。
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "cross_check.py"

_SPEC = importlib.util.spec_from_file_location("cross_check_s4", SCRIPT)
CC = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(CC)


# ===================== parse_sections =====================

def test_parse_sections_basic():
    md = "# 出力先\nNotion に保存\n## 情報源\nSlack ログ"
    sec = CC.parse_sections(md)
    assert sec["出力先"] == "Notion に保存"
    assert sec["情報源"] == "Slack ログ"


def test_parse_sections_multiline_body_stripped():
    md = "## 真の課題\n\n複数行\n本文\n\n"
    sec = CC.parse_sections(md)
    assert sec["真の課題"] == "複数行\n本文"


def test_parse_sections_no_heading_returns_empty():
    # 見出しが一切無ければ current が None のまま → 空 dict
    assert CC.parse_sections("本文のみ\nもう一行") == {}


def test_parse_sections_heading_levels_1_to_4():
    md = "#### 共有相手\nチーム全員"
    sec = CC.parse_sections(md)
    assert sec["共有相手"] == "チーム全員"


def test_parse_sections_trailing_section_flushed():
    # ループ末尾の current フラッシュ経路を踏む (最終見出しに本文)
    md = "# A\nfirst\n# B\nlast line"
    sec = CC.parse_sections(md)
    assert sec["A"] == "first"
    assert sec["B"] == "last line"


# ===================== pick_axis =====================

def test_pick_axis_matches_by_substring():
    sections = {"出力先 (Output Destination)": "Notion"}
    assert CC.pick_axis(sections, ["出力先", "Output Destination"]) == "Notion"


def test_pick_axis_returns_empty_when_no_match():
    assert CC.pick_axis({"無関係": "x"}, ["出力先"]) == ""


def test_pick_axis_first_matching_value():
    # needle のいずれかが見出しに含まれれば採用
    sections = {"その他 Information Source": "Slack"}
    assert CC.pick_axis(sections, ["情報源", "Information Source"]) == "Slack"


# ===================== extract_frontmatter =====================

def test_extract_frontmatter_parses_kv_and_strips_quotes():
    md = "---\ntitle: 'クオート付き'\nslug: my-skill\n---\n本文ここから"
    meta, body = CC.extract_frontmatter(md)
    assert meta["title"] == "クオート付き"
    assert meta["slug"] == "my-skill"
    assert body == "本文ここから"


def test_extract_frontmatter_double_quote_stripped():
    md = '---\nname: "値"\n---\nbody'
    meta, _ = CC.extract_frontmatter(md)
    assert meta["name"] == "値"


def test_extract_frontmatter_absent_returns_empty_and_full():
    md = "# 見出し\n本文"
    meta, body = CC.extract_frontmatter(md)
    assert meta == {}
    assert body == md


def test_extract_frontmatter_ignores_non_kv_lines():
    md = "---\nvalid_key: ok\nこれはキーでない行\n---\nbody"
    meta, _ = CC.extract_frontmatter(md)
    assert meta == {"valid_key": "ok"}


# ===================== convert_md =====================

def test_convert_md_maps_all_axes():
    md = (
        "---\nslug: x\n---\n"
        "# 出力先\nNotion\n"
        "# 情報源\nSlack\n"
        "# 共有相手\nチーム\n"
        "# 真の課題\n属人化\n"
        "# ナレッジ資産\n手順書"
    )
    out = CC.convert_md(md)
    axes = out["5_axes"]
    assert axes["output_target"] == "Notion"
    assert axes["info_source"] == "Slack"
    assert axes["share_target"] == "チーム"
    assert axes["true_problem"] == "属人化"
    assert axes["knowledge_assets"] == "手順書"


def test_convert_md_missing_axis_is_empty_string():
    md = "# 出力先\nNotion"
    out = CC.convert_md(md)
    assert out["5_axes"]["info_source"] == ""


def test_convert_md_english_headings():
    md = "# Output Destination\nNotion\n# Information Source\nSlack"
    out = CC.convert_md(md)
    assert out["5_axes"]["output_target"] == "Notion"
    assert out["5_axes"]["info_source"] == "Slack"


# ===================== norm =====================

def test_norm_collapses_whitespace():
    assert CC.norm("  a\t\nb   c ") == "a b c"


def test_norm_none_and_number():
    assert CC.norm(None) == ""
    assert CC.norm(123) == "123"


# ===================== similarity =====================

def test_similarity_both_empty_is_one():
    assert CC.similarity("", "") == 1
    assert CC.similarity(None, None) == 1


def test_similarity_one_empty_is_zero():
    assert CC.similarity("text", "") == 0
    assert CC.similarity("", "text") == 0


def test_similarity_identical_is_one():
    assert CC.similarity("Notion に保存", "Notion に保存") == 1


def test_similarity_partial_jaccard():
    # トークン {a,b} と {b,c} → 共通1 / 和集合3
    assert CC.similarity("a b", "b c") == pytest.approx(1 / 3)


def test_similarity_splits_on_japanese_punct():
    # 「、」「。」でも分割される
    s = CC.similarity("出力、情報。共有", "出力、情報。共有")
    assert s == 1


def test_similarity_disjoint_is_zero():
    assert CC.similarity("foo", "bar") == 0


# ===================== cross =====================

def _md_all_axes(**vals):
    headings = {
        "output_target": "出力先",
        "info_source": "情報源",
        "share_target": "共有相手",
        "true_problem": "真の課題",
        "knowledge_assets": "ナレッジ資産",
    }
    parts = []
    for axis, head in headings.items():
        parts.append(f"# {head}\n{vals.get(axis, '')}")
    return "\n".join(parts)


def test_cross_all_match_ok():
    vals = dict(
        output_target="Notion データベース",
        info_source="Slack の会話ログ",
        share_target="開発チーム全員",
        true_problem="知識の属人化問題",
        knowledge_assets="運用手順書 一式",
    )
    md = _md_all_axes(**vals)
    js = {"5_axes": vals}
    r = CC.cross(md, js)
    assert r["ok"] is True
    assert r["mismatches"] == []


def test_cross_detects_mismatch_below_threshold():
    md = _md_all_axes(output_target="Notion に保存する")
    js = {"5_axes": {"output_target": "全く異なる Google Drive へ"}}
    r = CC.cross(md, js)
    assert r["ok"] is False
    axes_flagged = {m["axis"] for m in r["mismatches"]}
    assert "output_target" in axes_flagged
    mm = next(m for m in r["mismatches"] if m["axis"] == "output_target")
    assert mm["similarity"] < 0.4
    assert "Notion" in mm["md_excerpt"]
    assert "Google Drive" in mm["json_excerpt"]


def test_cross_accepts_five_axes_alias_key():
    # json 側が five_axes キーでも拾う
    vals = dict(output_target="Notion")
    md = _md_all_axes(**vals)
    js = {"five_axes": {"output_target": "Notion"}}
    r = CC.cross(md, js)
    # 他軸は両方空 → similarity 1 で一致、output も一致
    assert r["ok"] is True


def test_cross_excerpt_truncated_to_60_chars():
    long = "語" * 100
    md = _md_all_axes(output_target=long)
    js = {"5_axes": {"output_target": "別物" * 50}}
    r = CC.cross(md, js)
    mm = next(m for m in r["mismatches"] if m["axis"] == "output_target")
    assert len(mm["md_excerpt"]) == 60


def test_cross_empty_both_sides_all_ok():
    # md も json も空 → 各軸 similarity 1 → ok
    r = CC.cross("", {})
    assert r["ok"] is True


# ===================== main() =====================

def _set_argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["cross_check.py", *args])


def _write(tmp_path, name, content):
    p = tmp_path / name
    if isinstance(content, (dict, list)):
        p.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    else:
        p.write_text(content, encoding="utf-8")
    return str(p)


def test_main_usage_when_too_few_args(monkeypatch, capsys):
    _set_argv(monkeypatch, "only-one.md")
    assert CC.main(sys.argv) == 2
    assert "usage:" in capsys.readouterr().err


def test_main_input_error_missing_md(monkeypatch, capsys, tmp_path):
    js = _write(tmp_path, "intake.json", {"5_axes": {}})
    argv = ["cross_check.py", str(tmp_path / "missing.md"), js]
    assert CC.main(argv) == 2
    assert "input error:" in capsys.readouterr().err


def test_main_input_error_bad_json(monkeypatch, capsys, tmp_path):
    md = _write(tmp_path, "intake.md", "# 出力先\nNotion")
    bad = _write(tmp_path, "intake.json", "{not valid json")
    argv = ["cross_check.py", md, bad]
    assert CC.main(argv) == 2
    assert "input error:" in capsys.readouterr().err


def test_main_ok_returns_0_and_prints_json(monkeypatch, capsys, tmp_path):
    vals = dict(
        output_target="Notion データベース 保存",
        info_source="Slack 会話 ログ",
        share_target="開発 チーム 全員",
        true_problem="知識 属人化 問題",
        knowledge_assets="運用 手順書 一式",
    )
    md = _write(tmp_path, "intake.md", _md_all_axes(**vals))
    js = _write(tmp_path, "intake.json", {"5_axes": vals})
    argv = ["cross_check.py", md, js]
    assert CC.main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["mismatches"] == []


def test_main_mismatch_returns_1(monkeypatch, capsys, tmp_path):
    md = _write(tmp_path, "intake.md", _md_all_axes(output_target="Notion へ保存"))
    js = _write(tmp_path, "intake.json",
                {"5_axes": {"output_target": "完全に違う Google Drive 行き"}})
    argv = ["cross_check.py", md, js]
    assert CC.main(argv) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert any(m["axis"] == "output_target" for m in out["mismatches"])


def test_main_subprocess_smoke(tmp_path):
    # subprocess(sys.executable) 経由で CLI 起動も genuine に確認 (__main__ ガード経路)
    import subprocess
    vals = dict(output_target="Notion 保存 先")
    md = _write(tmp_path, "intake.md", _md_all_axes(**vals))
    js = _write(tmp_path, "intake.json", {"5_axes": vals})
    r = subprocess.run([sys.executable, str(SCRIPT), md, js],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert json.loads(r.stdout)["ok"] is True
