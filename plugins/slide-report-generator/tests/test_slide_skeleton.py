"""ページひな形 (assets/slide-templates/) の契約テスト。

(1) 回帰ガード: 実体は違反ゼロ。生成物が契約から再生成した結果と一致する。
(2) 検出能: validate-slide-skeleton.py の --self-test が全て緑。
(3) 被覆: schema の slideType 全種が写像表に載り、参照先が実在する。
(4) 症状に対する構造的封じ手が消えていないこと (空白・chrome・ナビ・印刷)。

なぜ (4) を別に持つか: 検査器を通すことと、症状が再発しないことは別。
`flex: 1 1 auto` や `@page` の単一性は「消しても検査が緑のまま」になり得る
書き換えが存在するので、症状に直結する不変条件をここで名指しで固定する。
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_TPL_DIR = _PLUGIN_ROOT / "assets" / "slide-templates"


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, _PLUGIN_ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


validator = _load("scripts/validate-slide-skeleton.py", "validate_slide_skeleton_mod")
css_builder = _load("scripts/build-slide-skeleton-css.py", "build_slide_skeleton_css_mod")
tpl_builder = _load("scripts/build-slide-skeletons.py", "build_slide_skeletons_mod")
js_builder = _load("scripts/build-slide-skeleton-js.py", "build_slide_skeleton_js_mod")

PALETTE = css_builder.read_palette(_PLUGIN_ROOT)

CONTRACT = json.loads((_TPL_DIR / "frame-contract.json").read_text(encoding="utf-8"))
REGISTRY = json.loads((_TPL_DIR / "registry.json").read_text(encoding="utf-8"))


def _body(stem: str) -> str:
    return validator._strip_header_comment((_TPL_DIR / f"{stem}.html").read_text(encoding="utf-8"))


def _all_bodies() -> dict[str, str]:
    return {p.stem: _body(p.stem) for p in sorted(_TPL_DIR.glob("*.html"))}


# --- (1) 回帰ガード -----------------------------------------------------------

def test_no_findings_on_real_plugin():
    findings = validator.run_checks(_PLUGIN_ROOT)
    assert findings == [], "; ".join(
        f"{f['check']} @ {f['where']}: {f['message']}" for f in findings
    )


def test_generated_css_matches_contract():
    cur = (_TPL_DIR / "slide-skeleton.css").read_text(encoding="utf-8")
    assert cur == css_builder.build_css(CONTRACT, PALETTE), (
        "slide-skeleton.css が手編集されている。変更は frame-contract.json か"
        " vendor の SPEC.colors へ入れて再生成する"
    )


def test_generated_skeletons_match_contract():
    for spec in tpl_builder._SKELETONS:
        cur = (_TPL_DIR / f"{spec['id']}.html").read_text(encoding="utf-8")
        assert cur == tpl_builder.render(spec, CONTRACT), f"{spec['id']} が手編集されている"


# --- (2) 検出能 ---------------------------------------------------------------

def test_validator_self_test_passes():
    ok, log = validator._self_test(_PLUGIN_ROOT)
    assert ok, "\n".join(l for l in log if l.startswith("FAIL"))


# --- (3) 被覆 -----------------------------------------------------------------

def test_every_slide_type_is_mapped():
    enum = json.loads((_PLUGIN_ROOT / "schemas" / "structure.schema.json").read_text(encoding="utf-8"))
    enum = enum["$defs"]["slideTypeEnum"]["enum"]
    assert set(enum) == set(REGISTRY["map"]), (
        "schema の slideType と写像表が一致しない: "
        f"未写像={sorted(set(enum) - set(REGISTRY['map']))} "
        f"余剰={sorted(set(REGISTRY['map']) - set(enum))}"
    )


def test_every_skeleton_is_referenced():
    """使われないひな形を残さない (選択肢が増えるだけで判断がぶれる)。"""
    referenced = {e["skeleton"] for e in REGISTRY["map"].values()}
    referenced |= {v for k, v in REGISTRY["structural_pages"].items() if not k.startswith("$")}
    referenced |= set(REGISTRY["media_override"]["targets"])
    # slideType を持たない役割ページ (目次・自己紹介・連絡先など) の引き先。
    referenced |= {v for k, v in REGISTRY["role_pages"].items() if not k.startswith("$")}
    on_disk = {p.stem for p in _TPL_DIR.glob("*.html")}
    assert on_disk - referenced == set(), f"どこからも参照されないひな形: {sorted(on_disk - referenced)}"
    assert referenced - on_disk == set(), f"実体の無いひな形を参照: {sorted(referenced - on_disk)}"


def test_image_and_diagram_and_chart_cases_all_have_a_skeleton():
    """図解・画像・チャート・文字だけ、どのパターンでも受け皿がある。"""
    declared = set()
    for body in _all_bodies().values():
        m = re.search(r'data-media-kinds="([^"]*)"', body)
        if m:
            declared |= set(m.group(1).split())
    for kind in ("svg-diagram", "d3-diagram", "chart", "codex-image", "block", "none"):
        assert kind in declared, f"{kind} を受け入れるひな形が 1 枚も無い"


# --- (4) 症状に対する封じ手が消えていない -------------------------------------

def test_main_slot_absorbs_remaining_height_on_every_page():
    """空白過多の封じ手。これが消えると要素の少ない面で下が真っ白になる。"""
    css = (_TPL_DIR / "slide-skeleton.css").read_text(encoding="utf-8")
    assert re.search(r"\.srg-slide__main\s*\{[^}]*flex:\s*1 1 auto", css)
    for stem, body in _all_bodies().items():
        assert "srg-slide__main" in body, f"{stem} に main スロットが無い"


def test_stage_geometry_is_derived_not_hardcoded():
    """面ごとの座標直書きを禁じる。直書きが入るとページ間で位置がズレる。"""
    for stem, body in _all_bodies().items():
        # border-left / margin-top のような複合語は除く (位置指定だけを禁じる)。
        assert not re.search(r"(?<![\w-])(top|left|right|bottom)\s*:\s*-?\d+px", body), \
            f"{stem} が座標を直書きしている"
        assert "position: absolute" not in body or stem == "layout-image-full", \
            f"{stem} が絶対配置を使っている"


def test_nav_keeps_both_directions():
    """『戻るページが反映されない』の封じ手。端でも要素は消さず disabled にする。"""
    for stem, body in _all_bodies().items():
        if 'data-chrome="nav"' not in body:
            continue
        assert 'data-nav="prev"' in body and 'data-nav="next"' in body, f"{stem} のナビが片方向"
        assert 'data-disabled=' in body, f"{stem} が端の面の表現手段を持たない"


def test_single_at_page_declaration():
    """@page が複数あると読み込み順で印刷結果が変わり、再現しなくなる。"""
    css = (_TPL_DIR / "slide-skeleton.css").read_text(encoding="utf-8")
    assert len(re.findall(r"@page\s*\{", css)) == 1


def test_print_geometry_fits_a4():
    pr = CONTRACT["print_skeleton"]
    assert pr["stage_width_mm"] <= pr["page_width_mm"]
    assert pr["stage_height_mm"] <= pr["page_height_mm"]
    # 帯は上下対称。非対称だと面が紙の中央から外れる。
    assert abs(pr["page_height_mm"] - pr["stage_height_mm"] - pr["letterbox_band_mm"] * 2) < 0.05
    # zoom は CSS px (1/96 inch) を mm へ落とす倍率と一致する。
    assert abs(pr["zoom_factor"] - pr["mm_per_px"] / (25.4 / 96)) < 0.001


def test_no_cover_fit_anywhere():
    """cover は端を切る。図中の文字や人物が欠けるので全面禁止。"""
    css = (_TPL_DIR / "slide-skeleton.css").read_text(encoding="utf-8")
    assert "object-fit: cover" not in css
    for stem, body in _all_bodies().items():
        assert not re.search(r"object-fit\s*:\s*cover", body), f"{stem} に cover が現れている"


def test_autofit_floor_is_declared():
    """文字を無限に縮めて『収まった』ことにしない下限が宣言されている。"""
    css = (_TPL_DIR / "slide-skeleton.css").read_text(encoding="utf-8")
    assert f"--srg-fs-min: {CONTRACT['typography']['min']}px" in css
    # 少なくとも本文を持つ面は autofit 対象を宣言している。
    for stem, body in _all_bodies().items():
        assert "data-autofit=" in body, f"{stem} に自動縮小対象が無い"


def test_generated_js_matches_contract():
    """宣言だけあって実装が無い状態へ戻らないようにする。

    `data-autofit` と `--srg-fit` は長いあいだ「ひな形と README が宣言し、
    実装するファイルはどこにも無い」契約だった。収まらない文字はただ切れて
    いたので、履行者の実在をここで固定する。
    """
    cur = (_TPL_DIR / "slide-skeleton.js").read_text(encoding="utf-8")
    assert cur == js_builder.build_js(CONTRACT), "slide-skeleton.js が手編集されている"
    for name in ("data-autofit", "--srg-fit", "data-overflow"):
        assert name in cur, f"{name} を扱う実装が JS に無い"
    assert f"FS_MIN = {CONTRACT['typography']['min']}" in cur, "下限が契約から来ていない"


def test_colors_are_defined_not_only_fallbacks():
    """色は 1 か所で「定義」する。fallback だけの色は上書きできない定数になる。

    `var(--srg-fg, #43436c)` を定義なしで使うと、パレットを差し替えても
    その色は永久に fallback のまま出る。既定値のつもりが正解として回り始める
    ので、トークンは :root で定義し、使用箇所に 16 進を残さない。
    """
    css = (_TPL_DIR / "slide-skeleton.css").read_text(encoding="utf-8")
    for token in ("--srg-surface", "--srg-fg", "--srg-fg-muted", "--srg-focal",
                  "--srg-link", "--srg-hairline"):
        assert re.search(rf"^\s*{token}:", css, re.M), f"{token} が定義されていない"
    # 定義はパレット (vendor の SPEC.colors) を参照する形であること。
    # 参照するトークン名は _PALETTE_VARS が正本で、ここに書き写さない。
    for key, var in css_builder._PALETTE_VARS.items():
        assert f"var({var}, {PALETTE[key]})" in css, f"{var} をパレット参照の形で使っていない"
    for stem, body in _all_bodies().items():
        assert not re.search(r"#[0-9A-Fa-f]{6}\b", body), f"{stem} が色を直書きしている"
