"""validate-report-visual.py の網羅テスト。

関数 (analyze_report / check_report) の import 経路と、CLI の exit code 規約
(0=PASS / 1=崩れ検出 / 2=usage・ファイル不在 / --strict 昇格) の subprocess 経路の
両方を検証する。fixture HTML は tests 内にインライン生成する (tmp_path・node 非依存)。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# scripts/validate-report-visual.py はハイフン入りファイル名のため importlib で読み込む。
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "validate-report-visual.py"
_PLUGIN_ROOT = _SCRIPT.parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_report_visual_mod", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()


def _load_postgen_hook():
    path = _PLUGIN_ROOT / "hooks" / "hook-postgen-eval.py"
    spec = importlib.util.spec_from_file_location("hook_postgen_eval_mod", path)
    assert spec and spec.loader
    hook_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook_mod)
    return hook_mod


# --- fixture 生成 (render-report.js が出す class 規約を最小再現) -------------

def _section(sec_id, heading, paragraphs=None, visuals_html="", extra=""):
    paras = "\n".join(f"  <p>{p}</p>" for p in (paragraphs or ["本文段落です。"]))
    return (
        f'<section class="report-section" id="{sec_id}" data-role="body" '
        f'style="--section-accent: var(--accent-blue-vivid);">\n'
        f"  <h2>{heading}</h2>\n{paras}\n{extra}\n  {visuals_html}\n</section>"
    )


_SVG_FIGURE = (
    '<figure class="report-visual report-visual--svg" role="img">\n'
    '  <svg viewBox="0 0 960 320"><rect x="0" y="0" width="10" height="10"/>'
    '<text>ノード</text></svg>\n  <figcaption>図</figcaption>\n</figure>'
)
_FALLBACK_FIGURE = (
    '<figure class="report-visual report-visual--fallback">\n'
    '  <svg viewBox="0 0 960 200"><text>未対応の svg variant</text></svg>\n</figure>'
)


def _doc(sections_html, style="", head_extra="", h1="レポート表題"):
    default_style = (
        "<style>\n.report{max-width:190mm;}\n"
        "@page { size: A4 portrait; margin: 18mm; }\n"
        "@media print { .report-section { break-inside: avoid-page; } }\n"
        "</style>"
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"ja\">\n<head>\n<meta charset=\"UTF-8\">\n"
        '<meta name="generator" content="slide-report-generator/render-report">\n'
        f"{style or default_style}\n{head_extra}\n</head>\n"
        '<body style="--report-accent: var(--accent-blue-vivid);">\n'
        '<main class="report">\n'
        f'  <header class="report-header">\n    <h1 class="report-title">{h1}</h1>\n'
        '    <p class="report-keymessage">要点</p>\n  </header>\n'
        f"{sections_html}\n"
        '  <footer class="report-footer">report mode</footer>\n'
        "</main>\n</body>\n</html>\n"
    )


def _valid_html():
    secs = "\n".join(
        [
            _section("section-intro", "はじめに", ["**導入**の段落。", "続きの段落。"]),
            _section("section-flow", "流れ", ["本文。"], visuals_html=_SVG_FIGURE),
        ]
    )
    return _doc(secs)


VALID_STRUCTURE = {
    "meta": {"title": "T", "reportType": "internal-analysis", "audience": "a", "keyMessage": "k"},
    "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
    "sections": [
        {"id": "section-intro", "heading": "はじめに", "paragraphs": ["x"]},
        {"id": "section-flow", "heading": "流れ", "paragraphs": ["y"]},
    ],
}


# --- analyze_report ---------------------------------------------------------

def test_analyze_extracts_h1_and_sections():
    facts = mod.analyze_report(_valid_html())
    assert facts["h1_texts"] == ["レポート表題"]
    assert [s["id"] for s in facts["sections"]] == ["section-intro", "section-flow"]
    assert facts["sections"][1]["figure_count"] == 1
    assert facts["sections"][0]["heading"] == "はじめに"


def test_analyze_counts_paragraphs_and_text_len():
    facts = mod.analyze_report(_valid_html())
    intro = facts["sections"][0]
    assert intro["p_count"] == 2
    assert intro["text_len"] > 0
    assert facts["placeholders"] == []


def test_analyze_extracts_print_css():
    facts = mod.analyze_report(_valid_html())
    assert "break-inside" in facts["print_css"]


def test_analyze_toc_presence_comes_from_nav_dom_not_css_selector():
    css_only = _doc(_section("section-a", "A"), style="<style>.report-toc--sidebar{position:sticky}</style>")
    assert mod.analyze_report(css_only)["toc_sidebar_count"] == 0

    with_nav = css_only.replace(
        '<main class="report">',
        '<main class="report"><nav class="report-toc report-toc--sidebar" aria-label="目次"></nav>',
    )
    assert mod.analyze_report(with_nav)["toc_sidebar_count"] == 1


# --- 正常系 (PASS) ----------------------------------------------------------

def test_valid_report_passes():
    r = mod.check_report(_valid_html())
    assert r["passed"] is True, r["findings"]
    assert r["summary"]["fail"] == 0


def test_valid_report_passes_with_structure():
    r = mod.check_report(_valid_html(), structure=VALID_STRUCTURE)
    assert r["passed"] is True, r["findings"]


def test_valid_report_passes_strict():
    r = mod.check_report(_valid_html(), structure=VALID_STRUCTURE, strict=True)
    assert r["passed"] is True, r["findings"]


# --- C1: section 構造欠落 (fail-closed) -------------------------------------

def test_missing_h1_is_fail():
    html = _valid_html().replace('<h1 class="report-title">レポート表題</h1>', "")
    r = mod.check_report(html)
    assert r["passed"] is False
    assert any(f["check"] == "section-structure" and "h1" in f["message"] for f in r["findings"])


def test_no_sections_is_fail():
    html = _doc("")  # section 皆無
    r = mod.check_report(html)
    assert r["passed"] is False
    assert any("section 構造欠落" in f["message"] for f in r["findings"])


def test_section_without_h2_is_fail():
    sec = (
        '<section class="report-section" id="section-x">\n  <p>本文</p>\n  \n</section>'
    )
    r = mod.check_report(_doc(sec))
    assert r["passed"] is False
    assert any("h2 見出しが無い" in f["message"] for f in r["findings"])


def test_structure_section_missing_from_html_is_fail():
    # html には section-intro しか無いのに structure は2節を要求 → 欠落 fail。
    secs = _section("section-intro", "はじめに")
    r = mod.check_report(_doc(secs), structure=VALID_STRUCTURE)
    assert r["passed"] is False
    assert any("section-flow" in f["message"] and "欠落" in f["message"] for f in r["findings"])


def test_structure_heading_mismatch_is_warn_only():
    secs = "\n".join(
        [
            _section("section-intro", "別の見出し"),
            _section("section-flow", "流れ"),
        ]
    )
    r = mod.check_report(_doc(secs), structure=VALID_STRUCTURE)
    # 見出し不一致は warn のみ → 非 strict では passed。
    assert r["passed"] is True
    assert any(f["severity"] == "warn" and "見出し不一致" in f["message"] for f in r["findings"])
    # strict では昇格して fail。
    r2 = mod.check_report(_doc(secs), structure=VALID_STRUCTURE, strict=True)
    assert r2["passed"] is False


# --- C2: 1項目多ビジュアル (fail-closed) ------------------------------------

def test_excess_visuals_is_fail():
    # 3ビジュアル (fail_bound=3) → 過剰重複 fail。
    triple = _SVG_FIGURE + "\n  " + _SVG_FIGURE + "\n  " + _SVG_FIGURE
    secs = "\n".join(
        [
            _section("section-intro", "はじめに"),
            _section("section-flow", "流れ", visuals_html=triple),
        ]
    )
    r = mod.check_report(_doc(secs))
    assert r["passed"] is False
    assert any(f["check"] == "one-visual" and "過剰重複" in f["message"] for f in r["findings"])


def test_two_visuals_is_warn_only():
    double = _SVG_FIGURE + "\n  " + _SVG_FIGURE
    secs = "\n".join(
        [
            _section("section-intro", "はじめに"),
            _section("section-flow", "流れ", visuals_html=double),
        ]
    )
    r = mod.check_report(_doc(secs))
    assert r["passed"] is True  # 逸脱は warn 止まり
    assert any(f["severity"] == "warn" and "逸脱" in f["message"] for f in r["findings"])
    assert mod.check_report(_doc(secs), strict=True)["passed"] is False


def test_render_fallback_is_warn():
    secs = "\n".join(
        [
            _section("section-intro", "はじめに"),
            _section("section-flow", "流れ", visuals_html=_FALLBACK_FIGURE),
        ]
    )
    r = mod.check_report(_doc(secs))
    assert r["passed"] is True
    assert any("フォールバック" in f["message"] for f in r["findings"])


def test_standalone_img_counts_as_visual_but_table_does_not():
    # 1.1.0+ 設計: 表(table)は body ブロック=構造化本文であり hero visual に数えない。
    # img(1) + figure(1) = hero 2個 → warn 止まり (table は加算しない)。
    extra = '<img src="a.png" alt="x">\n  <table><tr><td>1</td></tr></table>\n  ' + _SVG_FIGURE
    secs = "\n".join(
        [
            _section("section-intro", "はじめに"),
            _section("section-flow", "流れ", visuals_html=extra),
        ]
    )
    r = mod.check_report(_doc(secs))
    assert r["passed"] is True, r["findings"]  # hero 2個は warn 止まり
    assert any(f["check"] == "one-visual" and "逸脱" in f["message"] for f in r["findings"])
    assert mod.check_report(_doc(secs), strict=True)["passed"] is False


def test_diagram_plus_table_is_not_over_visual():
    # 図解 1 + データ表 1 の正当な節は『1項目1ビジュアル逸脱』に誤爆しない (表は本文扱い)。
    table_html = '<figure class="report-table-wrap"><table class="report-table"><tbody><tr><td>v</td></tr></tbody></figure>'
    secs = "\n".join(
        [
            _section("section-intro", "はじめに"),
            _section("section-flow", "流れ", visuals_html=_SVG_FIGURE + "\n  " + table_html),
        ]
    )
    r = mod.check_report(_doc(secs), strict=True)
    assert r["passed"] is True, r["findings"]
    assert not any(f["check"] == "one-visual" for f in r["findings"])


# --- C3: 段落過密 / オーバーフロー ------------------------------------------

def test_extremely_long_paragraph_is_fail():
    long_p = "あ" * 4000
    secs = "\n".join(
        [
            _section("section-intro", "はじめに"),
            _section("section-flow", "流れ", [long_p]),
        ]
    )
    r = mod.check_report(_doc(secs))
    assert r["passed"] is False
    assert any(f["check"] == "paragraph-density" and "極端に長い" in f["message"] for f in r["findings"])


def test_moderately_long_paragraph_is_warn():
    mid_p = "い" * 2500
    secs = "\n".join(
        [
            _section("section-intro", "はじめに"),
            _section("section-flow", "流れ", [mid_p]),
        ]
    )
    r = mod.check_report(_doc(secs))
    assert r["passed"] is True
    assert any(f["severity"] == "warn" and "段落が長い" in f["message"] for f in r["findings"])


def test_too_many_paragraphs_is_warn():
    many = ["段落" for _ in range(16)]
    secs = "\n".join(
        [
            _section("section-intro", "はじめに"),
            _section("section-flow", "流れ", many),
        ]
    )
    r = mod.check_report(_doc(secs))
    assert any("段落数過密" in f["message"] for f in r["findings"])


def test_threshold_override():
    mid_p = "う" * 500
    secs = "\n".join(
        [_section("section-intro", "はじめに"), _section("section-flow", "流れ", [mid_p])]
    )
    r = mod.check_report(_doc(secs), thresholds={"para_len_fail": 400})
    assert r["passed"] is False


# --- C4: プレースホルダ残存 / 空セクション (fail-closed) --------------------

def test_unresolved_placeholder_is_fail():
    secs = "\n".join(
        [
            _section("section-intro", "はじめに", ["未解決 {{ title }} が残っている。"]),
            _section("section-flow", "流れ"),
        ]
    )
    r = mod.check_report(_doc(secs))
    assert r["passed"] is False
    assert any(f["check"] == "placeholder" and "{{ title }}" in f["message"] for f in r["findings"])


def test_empty_placeholder_braces_detected():
    secs = _section("section-intro", "はじめに", ["空 {{}} プレースホルダ。"])
    r = mod.check_report(_doc(secs))
    assert any(f["check"] == "placeholder" for f in r["findings"])


def test_placeholder_inside_code_is_not_flagged():
    # インライン code 内の {{}} は誤検出しない (テンプレ例示の可能性)。
    secs = _section("section-intro", "はじめに", ["コード例です。"],
                    extra='  <p><code>{{ jinja }}</code></p>')
    r = mod.check_report(_doc(secs))
    assert not any(f["check"] == "placeholder" for f in r["findings"])


def test_empty_section_is_fail():
    sec = '<section class="report-section" id="section-empty">\n  <h2>空節</h2>\n  \n</section>'
    r = mod.check_report(_doc(sec))
    assert r["passed"] is False
    assert any("空セクション" in f["message"] for f in r["findings"])


# --- C5: 印刷 letterbox / cover 兆候 (warn) ----------------------------------

def test_print_cover_is_warn():
    style = (
        "<style>\n@media print { .report-visual img { object-fit: cover; } }\n</style>"
    )
    secs = "\n".join([_section("section-intro", "はじめに"), _section("section-flow", "流れ")])
    r = mod.check_report(_doc(secs, style=style))
    assert r["passed"] is True
    assert any(f["check"] == "print-letterbox" and "cover" in f["message"] for f in r["findings"])
    assert mod.check_report(_doc(secs, style=style), strict=True)["passed"] is False


def test_print_letterbox_aspect_ratio_is_warn():
    style = "<style>\n@media print { .report { aspect-ratio: 16 / 9; } }\n</style>"
    secs = _section("section-intro", "はじめに")
    r = mod.check_report(_doc(secs, style=style))
    assert any("letterbox" in f["message"] for f in r["findings"])


def test_page_landscape_is_warn():
    style = "<style>\n@page { size: A4 landscape; }\n</style>"
    secs = _section("section-intro", "はじめに")
    r = mod.check_report(_doc(secs, style=style))
    assert any("landscape" in f["message"] for f in r["findings"])


# --- CLI exit code 規約 (subprocess) ----------------------------------------

def _run_cli(*args):
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_cli_valid_exit_0(tmp_path):
    html = _write(tmp_path, "report.html", _valid_html())
    proc = _run_cli(str(html))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["passed"] is True


def test_cli_with_structure_exit_0(tmp_path):
    html = _write(tmp_path, "report.html", _valid_html())
    struct = _write(tmp_path, "s.json", json.dumps(VALID_STRUCTURE, ensure_ascii=False))
    proc = _run_cli(str(html), "--structure", str(struct))
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["passed"] is True


def test_cli_required_structure_with_structure_exit_0(tmp_path):
    html = _write(tmp_path, "report.html", _valid_html())
    struct = _write(tmp_path, "report-structure.json", json.dumps(VALID_STRUCTURE, ensure_ascii=False))
    proc = _run_cli(
        str(html), "--structure", str(struct), "--require-structure", "--json"
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["passed"] is True


def test_cli_defect_exit_1(tmp_path):
    bad = _valid_html().replace("<h2>はじめに</h2>", "<h2>{{TITLE}}</h2>")
    html = _write(tmp_path, "report.html", bad)
    proc = _run_cli(str(html))
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["passed"] is False


def test_cli_strict_promotes_warn_to_exit_1(tmp_path):
    double = _SVG_FIGURE + "\n  " + _SVG_FIGURE
    secs = "\n".join([_section("section-intro", "はじめに"),
                      _section("section-flow", "流れ", visuals_html=double)])
    html = _write(tmp_path, "report.html", _doc(secs))
    assert _run_cli(str(html)).returncode == 0
    assert _run_cli(str(html), "--strict").returncode == 1


def test_cli_missing_report_exit_2(tmp_path):
    proc = _run_cli(str(tmp_path / "nope.html"))
    assert proc.returncode == 2
    assert "not found" in proc.stderr


def test_cli_missing_structure_exit_2(tmp_path):
    html = _write(tmp_path, "report.html", _valid_html())
    proc = _run_cli(str(html), "--structure", str(tmp_path / "nope.json"))
    assert proc.returncode == 2


def test_cli_bad_structure_json_exit_2(tmp_path):
    html = _write(tmp_path, "report.html", _valid_html())
    struct = _write(tmp_path, "s.json", "{ not json ")
    proc = _run_cli(str(html), "--structure", str(struct))
    assert proc.returncode == 2


def test_cli_no_args_exit_2():
    # 必須 positional 欠落は argparse が usage error (exit 2)。
    proc = _run_cli()
    assert proc.returncode == 2


def test_cli_help_exit_0():
    proc = _run_cli("--help")
    assert proc.returncode == 0
    assert "report.html" in proc.stdout


# --- main() in-process (exit code + JSON stdout の直接検証) ------------------

def test_main_valid_returns_0(tmp_path, capsys):
    html = _write(tmp_path, "report.html", _valid_html())
    rc = mod.main([str(html)])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["passed"] is True


def test_main_with_structure_returns_0(tmp_path, capsys):
    html = _write(tmp_path, "report.html", _valid_html())
    struct = _write(tmp_path, "s.json", json.dumps(VALID_STRUCTURE, ensure_ascii=False))
    rc = mod.main([str(html), "--structure", str(struct)])
    assert rc == 0
    capsys.readouterr()


def test_main_required_structure_with_structure_returns_0(tmp_path, capsys):
    html = _write(tmp_path, "report.html", _valid_html())
    struct = _write(tmp_path, "report-structure.json", json.dumps(VALID_STRUCTURE, ensure_ascii=False))
    rc = mod.main([
        str(html), "--structure", str(struct), "--require-structure", "--json"
    ])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["passed"] is True


def test_main_defect_returns_1(tmp_path, capsys):
    bad = _valid_html().replace("<h2>はじめに</h2>", "<h2>{{X}}</h2>")
    html = _write(tmp_path, "report.html", bad)
    rc = mod.main([str(html)])
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["passed"] is False


def test_main_strict_returns_1(tmp_path, capsys):
    double = _SVG_FIGURE + "\n  " + _SVG_FIGURE
    secs = "\n".join([_section("section-intro", "はじめに"),
                      _section("section-flow", "流れ", visuals_html=double)])
    html = _write(tmp_path, "report.html", _doc(secs))
    assert mod.main([str(html)]) == 0
    capsys.readouterr()
    assert mod.main([str(html), "--strict"]) == 1
    capsys.readouterr()


def test_main_missing_report_returns_2(tmp_path, capsys):
    rc = mod.main([str(tmp_path / "nope.html")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_main_missing_structure_returns_2(tmp_path, capsys):
    html = _write(tmp_path, "report.html", _valid_html())
    rc = mod.main([str(html), "--structure", str(tmp_path / "nope.json")])
    assert rc == 2
    capsys.readouterr()


def test_main_bad_structure_json_returns_2(tmp_path, capsys):
    html = _write(tmp_path, "report.html", _valid_html())
    struct = _write(tmp_path, "s.json", "{ not json ")
    rc = mod.main([str(html), "--structure", str(struct)])
    assert rc == 2
    assert "JSON" in capsys.readouterr().err


# ===== C6: 1.1.0 構造化ゲート (羅列←→過剰構造化 の双方向) =====

def _sec_html(sec_id, heading, inner):
    return f'<section class="report-section" id="{sec_id}"><h2 data-secnum="01">{heading}</h2>{inner}</section>'


def test_110_all_paragraphs_warns_raretsu():
    """1.1.0 宣言だが全節 paragraph-only (body[] 不使用) は羅列の兆候として warn。"""
    struct = {"meta": {"title": "t", "reportType": "internal-analysis", "audience": "a", "keyMessage": "k", "schemaVersion": "1.1.0"},
              "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "paragraphs": ["x。y。"]},
                           {"id": "section-b", "heading": "B", "paragraphs": ["z。"]}]}
    html = _doc(_sec_html("section-a", "A", "<p>x。y。</p>") + _sec_html("section-b", "B", "<p>z。</p>"))
    r = mod.check_report(html, structure=struct)
    msgs = " ".join(f["message"] for f in r["findings"] if f["check"] == "structuring")
    assert "羅列" in msgs or "body[]" in msgs


def test_110_double_fill_warns():
    """body[] と paragraphs[] の二重充填は warn。"""
    struct = {"meta": {"title": "t", "reportType": "tech-doc", "audience": "a", "keyMessage": "k", "schemaVersion": "1.1.0"},
              "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "narrative": {"essence": "e"},
                            "paragraphs": ["p"], "body": [{"type": "paragraph", "text": "b"}]}]}
    html = _doc(_sec_html("section-a", "A", "<p>b</p>"))
    r = mod.check_report(html, structure=struct)
    assert any("二重充填" in f["message"] for f in r["findings"])


def test_110_body_without_narrative_warns():
    struct = {"meta": {"title": "t", "reportType": "tech-doc", "audience": "a", "keyMessage": "k", "schemaVersion": "1.1.0"},
              "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "body": [{"type": "paragraph", "text": "b"}]}]}
    html = _doc(_sec_html("section-a", "A", "<p>b</p>"))
    r = mod.check_report(html, structure=struct)
    assert any("narrative" in f["message"] for f in r["findings"])


def test_110_keypoint_overuse_warns():
    struct = {"meta": {"title": "t", "reportType": "tech-doc", "audience": "a", "keyMessage": "k", "schemaVersion": "1.1.0"},
              "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "narrative": {"essence": "e"},
                            "body": [{"type": "key-point", "text": "1"}, {"type": "key-point", "text": "2"}, {"type": "key-point", "text": "3"}]}]}
    html = _doc(_sec_html("section-a", "A", "<p>x</p>"))
    r = mod.check_report(html, structure=struct)
    assert any(f["check"] == "emphasis-overuse" and "key-point" in f["message"] for f in r["findings"])


def test_110_highlight_overuse_warns():
    """1 section に ==highlight== が閾値(6)超で emphasis-overuse warn (html 駆動)。"""
    marks = "".join(f'<p><mark class="report-hl">h{i}</mark> ふつうの文。</p>' for i in range(8))
    html = _doc(_sec_html("section-a", "A", marks))
    r = mod.check_report(html)  # structure なし → html 駆動
    assert any(f["check"] == "emphasis-overuse" and "ハイライト" in f["message"] for f in r["findings"])


def test_110_structured_passes_clean():
    """適度に構造化された 1.1.0 (body + narrative + key-point 1個) は structuring/emphasis warn ゼロ。"""
    struct = {"meta": {"title": "t", "reportType": "tech-doc", "audience": "a", "keyMessage": "k", "schemaVersion": "1.1.0"},
              "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "narrative": {"essence": "本質", "approach": "解決"},
                            "body": [{"type": "paragraph", "text": "説明"},
                                     {"type": "table", "headers": ["h"], "rows": [["v"]], "caption": "t"},
                                     {"type": "key-point", "text": "要点"}]}]}
    html = _doc(_sec_html("section-a", "A", '<p>説明</p><figure class="report-table-wrap"><table class="report-table"><thead><tr><th>h</th></tr></thead><tbody><tr><td>v</td></tr></tbody></table></figure><div class="report-keypoint report-keypoint--accent"><div class="report-keypoint__body">要点</div></div>'))
    r = mod.check_report(html, structure=struct)
    assert not any(f["check"] in ("structuring", "emphasis-overuse") for f in r["findings"]), r["findings"]


# ===== C7: 1.2.0 構造化ゲート (through-line / 色覚非依存 / reportType横断 / render忠実度 / バグ修正) =====

def _meta_120(**kw):
    m = {"title": "t", "reportType": "internal-analysis", "audience": "a", "keyMessage": "k", "schemaVersion": "1.2.0"}
    m.update(kw)
    return m


def test_120_body_only_section_not_flagged_empty():
    """バグ修正: task-list / definition-list のみ (段落なし) の節を『空セクション』と誤検出しない。"""
    inner = (
        '<ul class="report-tasklist"><li class="is-done"><span class="report-tasklist__box">[x]</span>'
        '<span class="report-tasklist__text">完了</span></li></ul>'
        '<dl class="report-deflist"><dt>用語</dt><dd>定義</dd></dl>'
    )
    html = _doc(_sec_html("section-next", "次アクション", inner))
    r = mod.check_report(html)
    assert not any("空セクション" in f["message"] for f in r["findings"]), r["findings"]


def test_120_reference_role_without_narrative_no_warn():
    """role=reference は narrative 不要 (弧の強制は category error) → narrative warn を出さない。"""
    struct = {"meta": _meta_120(reportType="tech-doc"), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-ref", "heading": "参照", "role": "reference", "body": [{"type": "paragraph", "text": "列挙。"}]}]}
    html = _doc(_sec_html("section-ref", "参照", "<p>列挙。</p>"))
    r = mod.check_report(html, structure=struct)
    # narrative 欠如 warn (check=structuring, "narrative(本質…") が出ないこと (cross-cutting 等の別 warn は許容)。
    assert not any(f["check"] == "structuring" and "narrative(本質" in f["message"] for f in r["findings"]), r["findings"]


def test_120_analysis_role_without_narrative_warns():
    """role=analysis は narrative を強く期待 → 欠如で warn。"""
    struct = {"meta": _meta_120(), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-an", "heading": "分析", "role": "analysis", "body": [{"type": "paragraph", "text": "本文。"}]}]}
    html = _doc(_sec_html("section-an", "分析", "<p>本文。</p>"))
    r = mod.check_report(html, structure=struct)
    assert any("narrative" in f["message"] for f in r["findings"])


def test_130_essence_visual_missing_on_logical_section_warns():
    """1.3.0: 論理節(analysis/finding 等)が非 none visual を持たない → essence-visual warn (strict で fail)。"""
    struct = {"meta": _meta_120(), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-an", "heading": "分析", "role": "analysis",
                            "narrative": {"essence": "e", "approach": "a"},
                            "body": [{"type": "table", "headers": ["x"], "rows": [["y"]]}]}]}
    html = _doc(_sec_html("section-an", "分析", "<table><tr><td>y</td></tr></table>"))
    r = mod.check_report(html, structure=struct)
    assert any(f["check"] == "essence-visual" for f in r["findings"]), r["findings"]
    # strict では fail 昇格
    assert mod.check_report(html, structure=struct, strict=True)["passed"] is False


def test_130_essence_visual_present_passes():
    """1.3.0: 論理節が非 none visual を持てば essence-visual は出ない。"""
    struct = {"meta": _meta_120(), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-an", "heading": "分析", "role": "analysis",
                            "narrative": {"essence": "e", "approach": "a"},
                            "visual": {"kind": "svg", "spec": {"variant": "comparison",
                                       "nodes": [{"label": "A", "group": "l"}, {"label": "B", "group": "r"}]}},
                            "body": [{"type": "paragraph", "text": "本文"}]}]}
    html = _doc(_sec_html("section-an", "分析",
                          '<figure class="report-visual report-visual--svg"><svg viewBox="0 0 10 10"></svg></figure><p>本文</p>'))
    r = mod.check_report(html, structure=struct)
    assert not any(f["check"] == "essence-visual" for f in r["findings"]), r["findings"]


def test_130_essence_visual_exempts_summary_and_next_action():
    """1.3.0: 要約/次アクション等 (text-first 許容 role) は visual 無しでも essence-visual を出さない。"""
    struct = {"meta": _meta_120(), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [
                  {"id": "section-sum", "heading": "要約", "role": "summary",
                   "body": [{"type": "key-point", "text": "結論"}]},
                  {"id": "section-next", "heading": "次アクション", "role": "next-action",
                   "body": [{"type": "task-list", "tasks": [{"text": "T", "done": False}]}]},
              ]}
    html = _doc(_sec_html("section-sum", "要約", '<div class="report-keypoint"><div class="report-keypoint__body">結論</div></div>')
                + _sec_html("section-next", "次アクション", '<ul class="report-tasklist"><li>T</li></ul>'))
    r = mod.check_report(html, structure=struct)
    assert not any(f["check"] == "essence-visual" for f in r["findings"]), r["findings"]


def test_120_throughline_missing_warns():
    struct = {"meta": _meta_120(), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": f"section-{i}", "heading": f"H{i}", "role": "summary", "body": [{"type": "paragraph", "text": "p"}]} for i in range(4)]}
    html = _doc("\n".join(_sec_html(f"section-{i}", f"H{i}", "<p>p</p>") for i in range(4)))
    r = mod.check_report(html, structure=struct)
    assert any(f["check"] == "through-line" and "throughLine" in f["message"] for f in r["findings"])


def test_120_transition_absent_warns():
    struct = {"meta": _meta_120(throughLine="通し筋"), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": f"section-{i}", "heading": f"H{i}", "role": "summary", "body": [{"type": "paragraph", "text": "p"}]} for i in range(3)]}
    html = _doc("\n".join(_sec_html(f"section-{i}", f"H{i}", "<p>p</p>") for i in range(3)))
    r = mod.check_report(html, structure=struct)
    assert any(f["check"] == "through-line" and "transition" in f["message"] for f in r["findings"])


def test_120_reporttype_cross_cutting_missing_warns():
    struct = {"meta": _meta_120(throughLine="t"), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "role": "background", "transition": "x", "body": [{"type": "paragraph", "text": "p"}]}]}
    html = _doc(_sec_html("section-a", "A", "<p>p</p>"))
    r = mod.check_report(html, structure=struct)
    assert any(f["check"] == "cross-cutting" and "summary" in f["message"] for f in r["findings"])


def test_120_render_fidelity_deflist_missing_is_fail():
    """structure が definition-list を宣言したのに html に .report-deflist が無い → fail。"""
    struct = {"meta": _meta_120(throughLine="t"), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "role": "reference",
                            "body": [{"type": "definition-list", "terms": [{"term": "x", "definition": "y"}]}]}]}
    html = _doc(_sec_html("section-a", "A", "<p>def なし</p>"))  # deflist class を出していない
    r = mod.check_report(html, structure=struct)
    assert r["passed"] is False
    assert any(f["check"] == "render-fidelity" and "report-deflist" in f["message"] for f in r["findings"])


def test_120_render_fidelity_throughline_missing_is_fail():
    struct = {"meta": _meta_120(throughLine="通し筋"), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "role": "summary", "body": [{"type": "paragraph", "text": "p"}]}]}
    html = _doc(_sec_html("section-a", "A", "<p>p</p>"))  # report-throughline を出していない
    r = mod.check_report(html, structure=struct)
    assert r["passed"] is False
    assert any(f["check"] == "render-fidelity" and "throughLine" in f["message"] for f in r["findings"])


def test_120_readingorder_declared_but_not_rendered_is_fail():
    """structure が readingOrder を宣言したのに html に data-reading-order が無い → render-fidelity fail (placement 5field 対称被覆)。"""
    struct = {"meta": _meta_120(throughLine="t"), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "role": "summary", "readingOrder": "z-shape",
                            "body": [{"type": "paragraph", "text": "p"}]}]}
    html = _doc(_sec_html("section-a", "A", "<p>p</p>"))  # data-reading-order を出していない
    r = mod.check_report(html, structure=struct)
    assert r["passed"] is False
    assert any(f["check"] == "render-fidelity" and "reading-order" in f["message"] for f in r["findings"])


def test_role_classification_sets_are_disjoint():
    """narrative 要否2集合が排他 (import 時 assert と対) — 二重登録の desync を防ぐ。"""
    assert mod._NARRATIVE_REQUIRED_ROLES.isdisjoint(mod._NARRATIVE_OPTIONAL_ROLES)


def test_120_footnote_dangling_ref_warns():
    """本文の [^id] 参照に対応する footnote(id) が無い → footnote-ref warn (dangling / typo)。"""
    struct = {"meta": _meta_120(throughLine="t"), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "role": "reference",
                            "body": [{"type": "paragraph", "text": "根拠[^typo]を示す。"},
                                     {"type": "footnote", "footnotes": [{"id": "real", "text": "実在脚注"}]}]}]}
    html = _doc(_sec_html("section-a", "A", '<p>根拠を示す。</p><aside class="report-footnotes"><ol><li id="fn-real">[1] 実在脚注</li></ol></aside>'))
    r = mod.check_report(html, structure=struct)
    assert any(f["check"] == "footnote-ref" and "typo" in f["message"] for f in r["findings"])


def test_120_footnote_resolved_ref_no_warn():
    """[^id] 参照に対応する footnote(id) が在れば footnote-ref warn を出さない。"""
    struct = {"meta": _meta_120(throughLine="t"), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "role": "reference",
                            "body": [{"type": "paragraph", "text": "根拠[^src]を示す。"},
                                     {"type": "footnote", "footnotes": [{"id": "src", "text": "一次資料"}]}]}]}
    html = _doc(_sec_html("section-a", "A", '<p>根拠<sup class="report-fnref"><a href="#fn-src">[1]</a></sup>を示す。</p><aside class="report-footnotes"><ol><li id="fn-src">[1] 一次資料</li></ol></aside>'))
    r = mod.check_report(html, structure=struct)
    assert not any(f["check"] == "footnote-ref" for f in r["findings"])


def test_120_placement_emphasis_not_rendered_is_fail():
    struct = {"meta": _meta_120(throughLine="t"), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "role": "summary",
                            "body": [{"type": "paragraph", "text": "p"}],
                            "visual": {"kind": "svg", "layout": {"emphasisZone": "highlight"}, "spec": {"variant": "flow", "nodes": [{"id": "n-a", "label": "A"}]}}}]}
    html = _doc(_sec_html("section-a", "A", "<p>p</p>"))  # data-emphasis を出していない
    r = mod.check_report(html, structure=struct)
    assert r["passed"] is False
    assert any(f["check"] == "render-fidelity" and "data-emphasis" in f["message"] for f in r["findings"])


def test_120_colorblind_highlight_single_channel_warns():
    """mark.report-hl を使うのに CSS が非色第2チャネル (weight/underline) を欠く → colorblind-safe warn。"""
    style = "<style>\nmark.report-hl { background: yellow; color: black; }\n</style>"
    html = _doc(_sec_html("section-a", "A", '<p><mark class="report-hl">要点</mark></p>'), style=style)
    r = mod.check_report(html)
    assert any(f["check"] == "colorblind-safe" for f in r["findings"])


def test_120_colorblind_highlight_two_channel_ok():
    style = "<style>\nmark.report-hl { background: yellow; font-weight: 700; text-decoration: underline; }\n</style>"
    html = _doc(_sec_html("section-a", "A", '<p><mark class="report-hl">要点</mark></p>'), style=style)
    r = mod.check_report(html)
    assert not any(f["check"] == "colorblind-safe" for f in r["findings"])


def test_120_doc_highlight_budget_warns():
    marks = "".join(f'<p><mark class="report-hl">h{i}</mark></p>' for i in range(26))
    # 5 節に分散させ per-section cap を避けつつ doc 総量で超過させる。
    secs = "\n".join(_sec_html(f"section-{i}", f"H{i}", "".join(f'<p><mark class="report-hl">h</mark></p>' for _ in range(6))) for i in range(5))
    r = mod.check_report(_doc(secs))
    assert any(f["check"] == "emphasis-overuse" and "文書全体" in f["message"] for f in r["findings"])


def test_120_monotone_paragraph_floor_warns():
    struct = {"meta": _meta_120(throughLine="t"), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "role": "summary",
                            "body": [{"type": "paragraph", "text": f"p{i}"} for i in range(6)]}]}
    html = _doc(_sec_html("section-a", "A", "".join(f"<p>p{i}</p>" for i in range(6))))
    r = mod.check_report(html, structure=struct)
    assert any(f["check"] == "structuring" and "羅列" in f["message"] for f in r["findings"])


def test_120_gate_does_not_fire_on_110_doc():
    """1.1.0 doc には through-line/cross-cutting の C7 warn を出さない (旧 doc 誤発火防止)。"""
    struct = {"meta": {"title": "t", "reportType": "internal-analysis", "audience": "a", "keyMessage": "k", "schemaVersion": "1.1.0"},
              "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": f"section-{i}", "heading": f"H{i}", "body": [{"type": "paragraph", "text": "p"}], "narrative": {"essence": "e"}} for i in range(5)]}
    html = _doc("\n".join(_sec_html(f"section-{i}", f"H{i}", "<p>p</p>") for i in range(5)))
    r = mod.check_report(html, structure=struct)
    assert not any(f["check"] in ("through-line", "cross-cutting") for f in r["findings"]), r["findings"]


def test_120_role_classification_covers_all_schema_roles():
    """validator の narrative 要否2集合が schema の section.role enum を過不足なく覆う (fall-through 曖昧さ排除)。"""
    import json as _json
    schema = _json.loads((Path(__file__).resolve().parent.parent / "schemas" / "report-structure.schema.json").read_text(encoding="utf-8"))
    enum = set(schema["$defs"]["section"]["properties"]["role"]["enum"])
    classified = mod._NARRATIVE_REQUIRED_ROLES | mod._NARRATIVE_OPTIONAL_ROLES
    assert enum - classified == set(), f"未分類 role: {sorted(enum - classified)}"
    assert mod._NARRATIVE_REQUIRED_ROLES & mod._NARRATIVE_OPTIONAL_ROLES == set(), "REQUIRED と OPTIONAL が重複"


def test_120_focalpoint_declared_but_not_rendered_is_fail():
    """structure が placement.focalPoint を宣言したのに html に data-focal が無い → render-fidelity fail。"""
    struct = {"meta": _meta_120(throughLine="t"), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "role": "summary",
                            "body": [{"type": "paragraph", "text": "p"}],
                            "visual": {"kind": "svg", "layout": {"focalPoint": {"x": 30, "y": 70}}, "spec": {"variant": "flow", "nodes": [{"id": "n-a", "label": "A"}]}}}]}
    html = _doc(_sec_html("section-a", "A", "<p>p</p>"))  # data-focal を出していない
    r = mod.check_report(html, structure=struct)
    assert r["passed"] is False
    assert any(f["check"] == "render-fidelity" and "focalPoint" in f["message"] for f in r["findings"])


def test_120_large_deep_doc_without_parts_warns():
    """length=deep かつ多節(>=12)で throughLineParts 未宣言 → through-line warn (部構成で道標を促す)。"""
    struct = {"meta": _meta_120(length="deep", throughLine="x"), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": f"section-{i}", "heading": f"H{i}", "role": "summary", "transition": "t",
                            "body": [{"type": "paragraph", "text": "p"}]} for i in range(12)]}
    html = _doc("\n".join(_sec_html(f"section-{i}", f"H{i}", "<p>p</p>") for i in range(12)))
    r = mod.check_report(html, structure=struct)
    assert any(f["check"] == "through-line" and "throughLineParts" in f["message"] for f in r["findings"])


def test_120_large_deep_doc_with_parts_no_warn():
    """throughLineParts を宣言すれば part 未宣言 warn を出さない。"""
    struct = {"meta": _meta_120(length="deep", throughLine="x", throughLineParts=[{"arc": "第1部"}, {"arc": "第2部"}]),
              "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": f"section-{i}", "heading": f"H{i}", "role": "summary", "transition": "t",
                            "body": [{"type": "paragraph", "text": "p"}]} for i in range(12)]}
    html = _doc("\n".join(_sec_html(f"section-{i}", f"H{i}", "<p>p</p>") for i in range(12)))
    r = mod.check_report(html, structure=struct)
    assert not any(f["check"] == "through-line" and "throughLineParts" in f["message"] for f in r["findings"])


def test_120_clean_report_passes_strict():
    """完全な 1.2.0 report (throughLine + transition + role別narrative + 横断role + 新block render) は strict PASS。"""
    struct = {
        "meta": _meta_120(throughLine="本質→解決→活用", length="deep"),
        "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
        "sections": [
            {"id": "section-sum", "heading": "要約", "role": "summary", "transition": "次へ",
             "body": [{"type": "key-point", "text": "結論"}]},
            {"id": "section-an", "heading": "分析", "role": "analysis", "transition": "次へ",
             "narrative": {"essence": "本質", "approach": "解決"},
             "visual": {"kind": "svg", "spec": {"variant": "cycle", "nodes": [{"label": "A"}, {"label": "B"}]},
                        "caption": "本質構造"},
             "body": [{"type": "paragraph", "text": "本文"}]},
            {"id": "section-next", "heading": "次アクション", "role": "next-action",
             "body": [{"type": "task-list", "tasks": [{"text": "T", "done": False}]}]},
        ],
    }
    inner_sum = '<div class="report-keypoint report-keypoint--accent"><div class="report-keypoint__body">結論</div></div>'
    inner_an = ('<div class="report-narrative"><span class="report-narrative__label">本質課題</span></div>'
                '<figure class="report-visual report-visual--svg"><svg viewBox="0 0 100 100"></svg></figure><p>本文</p>')
    inner_next = '<ul class="report-tasklist"><li><span class="report-tasklist__box">[ ]</span><span class="report-tasklist__text">T</span></li></ul>'
    body = (
        _sec_html("section-sum", "要約", inner_sum).replace("</section>", '<p class="report-transition">次へ</p></section>')
        + _sec_html("section-an", "分析", inner_an).replace("</section>", '<p class="report-transition">次へ</p></section>')
        + _sec_html("section-next", "次アクション", inner_next)
    )
    # throughLine 帯 + data-emphasis 不要 (emphasis 未宣言)
    html = _doc('  <div class="report-throughline">本質→解決→活用</div>\n' + body)
    r = mod.check_report(html, structure=struct, strict=True)
    assert r["passed"] is True, r["findings"]


# ===== Phase3 (elegant review) で検出した回帰 =====

def test_120_paragraphs_only_deep_still_caught_raretsu():
    """opt-in ゲート抜け穴の封鎖: sv=1.2.0 or length=deep で全節 paragraphs[]-only は羅列 warn (body 不使用で escape させない)。"""
    struct = {"meta": _meta_120(length="deep", throughLine="x"), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": f"section-{i}", "heading": f"H{i}", "role": "analysis", "paragraphs": ["羅列文。"]} for i in range(5)]}
    html = _doc("\n".join(_sec_html(f"section-{i}", f"H{i}", "<p>羅列</p>") for i in range(5)))
    r = mod.check_report(html, structure=struct, strict=True)
    assert any(f["check"] == "structuring" and "羅列" in f["message"] for f in r["findings"])
    assert r["passed"] is False  # strict で fail (羅列退化を緑通過させない)


def test_120_brief_throughline_optout_no_warn():
    """length=brief は §6.3 マトリクスで throughLine を opt-out 許容 → 未宣言でも warn しない。"""
    struct = {"meta": _meta_120(length="brief"), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "role": "summary", "body": [{"type": "key-point", "text": "結論"}]}]}
    html = _doc(_sec_html("section-a", "A", '<div class="report-keypoint"><div class="report-keypoint__body">結論</div></div>'))
    r = mod.check_report(html, structure=struct)
    assert not any(f["check"] == "through-line" and "throughLine" in f["message"] for f in r["findings"])


def test_120_code_only_section_not_flagged_empty():
    """コードブロックのみの節 (tech-doc で頻出) を『空セクション』と誤検出しない (content marker に report-code)。"""
    inner = '<figure class="report-code-wrap"><pre class="report-code"><code>echo hi</code></pre></figure>'
    html = _doc(_sec_html("section-code", "実装例", inner))
    r = mod.check_report(html)
    assert not any("空セクション" in f["message"] for f in r["findings"]), r["findings"]


def test_120_narrative_dual_form_warns():
    """narrative に essence系と logic[] を併載すると render が logic[] を黙 drop → structuring warn で顕在化。"""
    struct = {"meta": _meta_120(throughLine="t"), "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
              "sections": [{"id": "section-a", "heading": "A", "role": "analysis",
                            "narrative": {"essence": "本質", "logic": [{"role": "claim", "text": "主張"}]},
                            "body": [{"type": "paragraph", "text": "p"}]}]}
    html = _doc('  <div class="report-throughline">t</div>\n' + _sec_html("section-a", "A", '<div class="report-narrative"></div><p>p</p>'))
    r = mod.check_report(html, structure=struct)
    assert any(f["check"] == "structuring" and "併載" in f["message"] for f in r["findings"])


# --- C9: 第3次 UI/UX shape (screen接合トークン/print非退行/狭画面degrade/aria-current/タイポ) 回帰保護 ---

_FULL_UIUX_STYLE = (
    "<style>\n"
    ":root{--report-width:190mm;--report-measure:78ch;--report-page-max:1360px;"
    "--fs-body:1.0625rem;--fs-title:2.05rem;}\n"
    ".report-layout{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));}\n"
    ".report-toc--sidebar{position:sticky;} a.is-active{font-weight:700;}\n"
    "@media print{.report{max-width:190mm;}}\n"
    "@media (max-width:900px){.report-layout{display:block;}}\n"
    "</style>"
)
_FULL_UIUX_HEAD = (
    "<script>x.setAttribute('aria-current','location');"
    "window.addEventListener('beforeprint',a);window.addEventListener('afterprint',b);</script>"
)


def test_uiux_shape_full_render_no_warn():
    """接合トークン + aria-current + before/afterprint が揃った full render は uiux-shape warn ゼロ。"""
    html = _doc(_section("section-a", "A", ["本文。"]), style=_FULL_UIUX_STYLE, head_extra=_FULL_UIUX_HEAD)
    r = mod.check_report(html)
    assert not any(f["check"] == "uiux-shape" for f in r["findings"]), r["findings"]


def test_uiux_shape_missing_tokens_warn():
    """--report-width を持つ full render で接合トークン (layout/measure/page-max 等) が欠けると uiux-shape warn。"""
    html = _doc(_section("section-a", "A", ["本文。"]), style="<style>:root{--report-width:190mm;}</style>")
    r = mod.check_report(html)
    assert any(f["check"] == "uiux-shape" for f in r["findings"]), r["findings"]


def test_uiux_shape_css_toc_selector_without_nav_does_not_require_scrollspy():
    """CSS の TOC selector だけは TOC 実体ではなく、scrollspy 欠落に誤爆しない。"""
    html = _doc(_section("section-a", "A", ["本文。"]), style=_FULL_UIUX_STYLE)
    r = mod.check_report(html)
    toc_messages = [
        f["message"] for f in r["findings"]
        if f["check"] == "uiux-shape"
        and any(token in f["message"] for token in ("scrollspy", "aria-current", "afterprint"))
    ]
    assert toc_messages == [], r["findings"]


def test_uiux_shape_actual_toc_nav_requires_scrollspy_contract():
    """実 DOM に sidebar TOC nav がある場合だけ active CSS/aria-current 同期を要求する。"""
    style = _FULL_UIUX_STYLE.replace("a.is-active{font-weight:700;}", "")
    toc = '<nav class="report-toc report-toc--sidebar" aria-label="目次"><a href="#section-a">A</a></nav>'
    html = _doc(toc + _section("section-a", "A", ["本文。"]), style=style)
    r = mod.check_report(html)
    messages = [f["message"] for f in r["findings"] if f["check"] == "uiux-shape"]
    assert any("scrollspy" in message for message in messages), r["findings"]
    assert any("aria-current" in message for message in messages), r["findings"]


def test_uiux_shape_skipped_for_partial_fixture():
    """--report-width を持たない部分 fixture では uiux-shape を発火させない (誤爆防止・full-render marker gate)。"""
    html = _doc(_section("section-a", "A", ["本文。"]))  # default_style は --report-width を含まない
    r = mod.check_report(html)
    assert not any(f["check"] == "uiux-shape" for f in r["findings"]), r["findings"]


def test_cli_require_structure_without_structure_exit_2(tmp_path):
    """--require-structure 指定 + --structure 欠落 → fail-open を封鎖し exit2。"""
    html = _write(tmp_path, "report.html", _valid_html())
    proc = _run_cli(str(html), "--require-structure")
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_canonical_generate_consumers_enable_required_structure_mode():
    """C01 の実行導線は structure 正本と required mode を常にペアで渡す。"""
    required_args = "--structure <report-structure.json> --require-structure --json"
    skill = (_PLUGIN_ROOT / "skills" / "run-slide-report-generate" / "SKILL.md").read_text(encoding="utf-8")
    orchestrator = (
        _PLUGIN_ROOT / "skills" / "run-slide-report-generate" / "prompts" / "R1-orchestrate.md"
    ).read_text(encoding="utf-8")
    assert required_args in skill
    assert required_args in orchestrator

    hook = _load_postgen_hook()
    context = hook.build_context("report", "/tmp/report-output")
    assert '--structure "/tmp/report-output/report-structure.json"' in context
    assert "--require-structure --json" in context
