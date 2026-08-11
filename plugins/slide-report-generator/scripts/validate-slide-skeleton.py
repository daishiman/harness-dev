#!/usr/bin/env python3
# /// script
# name: validate-slide-skeleton
# purpose: ページひな形の契約を機械検査する。写像表が全 slideType を覆うか、各ひな形が宣言した media 種別を実際に受け入れるか、幾何が frame-contract.json の内部整合を満たすか、生成物が契約から再生成した結果と一致するかを fail-closed で確認する。
# inputs:
#   - assets/slide-templates/{frame-contract.json,registry.json,slide-skeleton.css,slide-skeleton.js,*.html}
#   - vendor/scripts/style-builder.cjs (SPEC.colors = 配色の正本・read-only)
#   - schemas/structure.schema.json ($defs.slideTypeEnum.enum)
#   - CLI: [--root <plugin-root>] [--self-test] [--json] [--deck <html> ...]
# outputs:
#   - stdout: 検査結果 (--json で機械可読)
#   - exit: 0=PASS / 1=違反あり / 2=入力が読めない
# contexts: [gate]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""ページひな形が「毎回同じ精度で嵌まる」ことを機械で保証する。

## 何を守っているのか

ひな形を置いただけでは、次のいずれかで静かに壊れる。

- 新しい slideType を schema へ足したが写像表に載せ忘れる → その型だけ骨格
  なしで組まれ、粒度が揺れる (S1 が落とす)。
- ひな形が受け入れると宣言していない種別を写像表が指す → 差し込み物が
  スロットに合わず、面から食み出す (S3 が落とす)。
- 幾何を 1 か所だけ直して整合が崩れる。例えば chrome.side を変えて
  stage.width を直し忘れると、本文が面の端をはみ出す (S5 が落とす)。
- 生成物 (CSS / HTML) を手で編集して契約から乖離する (S4 が落とす)。
- 印刷倍率と mm 表記が食い違い、PDF だけズレる (S7 が落とす)。

いずれも「動くけれど間違っている」種類の壊れ方で、目視レビューを通過する。
だからここは fail-closed にする — 読めない入力は PASS にしない。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_CONTRACT = "assets/slide-templates/frame-contract.json"
_REGISTRY = "assets/slide-templates/registry.json"
_CSS = "assets/slide-templates/slide-skeleton.css"
_JS = "assets/slide-templates/slide-skeleton.js"
_SCHEMA = "schemas/structure.schema.json"
# ひな形の全数。`layout-*` へ絞ると、体系外の面 (旧世代の残骸など) が検査の外側に
# 居続ける — 検査が届かないものは「無いもの」ではなく「見ていないもの」であり、
# ディレクトリを開く読み手にはそれも候補として見える。*.html で全部を候補にする。
_TPL_GLOB = "assets/slide-templates/*.html"

# CSS px の物理サイズ。1px = 1/96 inch。zoom_factor の検算に使う。
_MM_PER_CSS_PX = 25.4 / 96


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_header_comment(html: str) -> str:
    """先頭の解説コメントを落とす。数値規律は本体だけに課す。"""
    return re.sub(r"^\s*<!--.*?-->\s*", "", html, count=1, flags=re.S)


def run_checks(root: Path) -> list[dict]:
    findings: list[dict] = []

    def add(check: str, where: str, message: str):
        findings.append({"check": check, "where": where, "message": message})

    contract_p, registry_p, schema_p = root / _CONTRACT, root / _REGISTRY, root / _SCHEMA
    for p in (contract_p, registry_p, schema_p):
        if not p.is_file():
            add("input-missing", str(p.relative_to(root)), "必須入力が無い")
    if findings:
        return findings

    c = _load_json(contract_p)
    reg = _load_json(registry_p)
    schema = _load_json(schema_p)

    base = c["grid"]["base"]
    cv, ch, st, pr, ty, fp = c["canvas"], c["chrome"], c["stage"], c["print"], c["typography"], c["fill_policy"]
    kinds = set(c["media"]["kinds"])

    # --- ひな形本体を読む -----------------------------------------------------
    tpls: dict[str, str] = {}
    for path in sorted(root.glob(_TPL_GLOB)):
        tpls[path.stem] = path.read_text(encoding="utf-8")
    if not tpls:
        add("input-missing", _TPL_GLOB, "ひな形が 1 枚も無い")
        return findings

    # --- S1: 写像表が slideType 全体を過不足なく覆う ---------------------------
    enum = schema["$defs"]["slideTypeEnum"]["enum"]
    mapped = reg["map"]
    for t in enum:
        if t not in mapped:
            add("S1-map-missing", _REGISTRY, f"slideType `{t}` が写像表に無い")
    for t in mapped:
        if t not in enum:
            add("S1-map-extra", _REGISTRY, f"写像表の `{t}` は schema の enum に無い")

    # --- S2: 参照先ひな形が実在する -------------------------------------------
    def _vals(block: str) -> set:
        return {v for k, v in reg.get(block, {}).items() if not k.startswith("$")}

    structural = {k: v for k, v in reg["structural_pages"].items() if not k.startswith("$")}
    # 役割ページ (目次・自己紹介・連絡先など) は slideType を持たないので map には現れない。
    # 引き先を role_pages が持つことで、「実体はあるが誰も引かないひな形」を作らない。
    referenced = ({e["skeleton"] for e in mapped.values()} | set(structural.values())
                  | _vals("role_pages") | set(reg["media_override"]["targets"]))
    for sk in sorted(referenced):
        if sk not in tpls:
            add("S2-skeleton-missing", _REGISTRY, f"ひな形 `{sk}` の実体が無い")
    for sk in sorted(set(tpls) - referenced):
        add("S2-skeleton-orphan", _REGISTRY,
            f"ひな形 `{sk}` を map / structural_pages / role_pages / media_override の誰も引かない")
    for sk in sorted(set(reg["skeletons"]) ^ set(tpls)):
        add("S2-skeleton-index-drift", _REGISTRY,
            f"`{sk}` が registry.skeletons と実体のどちらか一方にしか無い")

    # --- S3: 写像が指す media 種別を、そのひな形が受け入れると宣言している ------
    for t, e in sorted(mapped.items()):
        sk, media = e["skeleton"], e["media"]
        if media not in kinds:
            add("S3-media-unknown", _REGISTRY, f"`{t}` の media `{media}` は契約の種別に無い")
            continue
        html = tpls.get(sk)
        if html is None:
            continue
        m = re.search(r'data-media-kinds="([^"]*)"', html)
        declared = set((m.group(1) if m else "").split())
        if media not in declared:
            add("S3-media-mismatch", _REGISTRY,
                f"`{t}` は {sk} へ `{media}` を差し込むが、{sk} の宣言は {sorted(declared)}")

    # --- S4: 生成物が契約から再生成した結果と一致する --------------------------
    #   検査器が自前で内容を持たず、生成器を輸入して突合する (二重定義を作らない)。
    sys.path.insert(0, str(root / "scripts"))
    try:
        import importlib.util

        def _imp(name, rel):
            spec = importlib.util.spec_from_file_location(name, root / rel)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod

        css_mod = _imp("_srg_css", "scripts/build-slide-skeleton-css.py")
        tpl_mod = _imp("_srg_tpl", "scripts/build-slide-skeletons.py")
        js_mod = _imp("_srg_js", "scripts/build-slide-skeleton-js.py")
        palette = css_mod.read_palette(root)
    except Exception as e:  # 生成器が読めないなら PASS にしない
        add("S4-generator-unreadable", "scripts/", f"生成器を読み込めない: {e}")
    else:
        css_now = (root / _CSS).read_text(encoding="utf-8") if (root / _CSS).is_file() else ""
        if css_now != css_mod.build_css(c, palette):
            add("S4-css-drift", _CSS, "契約とパレットから再生成した CSS と一致しない (手編集の疑い)")
        js_now = (root / _JS).read_text(encoding="utf-8") if (root / _JS).is_file() else ""
        if js_now != js_mod.build_js(c):
            add("S4-js-drift", _JS, "契約から再生成した JS と一致しない (手編集の疑い、または未生成)")
        for spec in tpl_mod._SKELETONS:
            want = tpl_mod.render(spec, c)
            if tpls.get(spec["id"]) != want:
                add("S4-html-drift", f"{_TPL_GLOB} ({spec['id']})",
                    "契約から再生成したひな形と一致しない (手編集の疑い)")

    # --- S5: 幾何の内部整合 ----------------------------------------------------
    if st["x"] != ch["side"]:
        add("S5-geometry", _CONTRACT, f"stage.x({st['x']}) != chrome.side({ch['side']})")
    if st["y"] != ch["top"]:
        add("S5-geometry", _CONTRACT, f"stage.y({st['y']}) != chrome.top({ch['top']})")
    if st["width"] != cv["width"] - ch["side"] * 2:
        add("S5-geometry", _CONTRACT,
            f"stage.width({st['width']}) != canvas.width - side*2({cv['width'] - ch['side'] * 2})")
    if st["height"] != cv["height"] - ch["top"] - ch["bottom"]:
        add("S5-geometry", _CONTRACT,
            f"stage.height({st['height']}) != canvas.height - top - bottom"
            f"({cv['height'] - ch['top'] - ch['bottom']})")
    aspect = cv["aspect_ratio"].replace(" ", "")
    if "/" in aspect:
        a, b = (int(x) for x in aspect.split("/"))
        if cv["width"] * b != cv["height"] * a:
            add("S5-geometry", _CONTRACT, f"canvas が aspect_ratio {cv['aspect_ratio']} と一致しない")

    # --- S6: 4 の倍数グリッド --------------------------------------------------
    for label, val in (
        [(f"canvas.{k}", cv[k]) for k in ("width", "height")]
        + [(f"chrome.{k}", ch[k]) for k in ("top", "bottom", "side")]
        + [(f"stage.{k}", st[k]) for k in ("x", "y", "width", "height")]
        + [(f"spacing.{k}", v) for k, v in c["spacing"].items()]
    ):
        if isinstance(val, int) and val % base != 0:
            add("S6-grid", _CONTRACT, f"{label}={val} が {base} の倍数でない")
    for sk, html in sorted(tpls.items()):
        for n in re.findall(r"(?<![\w.-])(\d+)px", _strip_header_comment(html)):
            if int(n) % base != 0:
                add("S6-grid", f"{sk}.html", f"本文の {n}px が {base} の倍数でない")

    # --- S7: 印刷倍率と mm 表記の整合 -------------------------------------------
    def close(a: float, b: float, tol: float) -> bool:
        return abs(a - b) <= tol

    if not close(pr["stage_width_mm"], cv["width"] * pr["mm_per_px"], 0.5):
        add("S7-print", _CONTRACT,
            f"stage_width_mm({pr['stage_width_mm']}) != canvas.width * mm_per_px"
            f"({cv['width'] * pr['mm_per_px']:.2f})")
    if not close(pr["stage_height_mm"], cv["height"] * pr["mm_per_px"], 0.5):
        add("S7-print", _CONTRACT,
            f"stage_height_mm({pr['stage_height_mm']}) != canvas.height * mm_per_px"
            f"({cv['height'] * pr['mm_per_px']:.2f})")
    if not close(pr["letterbox_band_mm"], (pr["page_height_mm"] - pr["stage_height_mm"]) / 2, 0.05):
        add("S7-print", _CONTRACT,
            f"letterbox_band_mm({pr['letterbox_band_mm']}) != (page_height - stage_height)/2"
            f"({(pr['page_height_mm'] - pr['stage_height_mm']) / 2:.2f})")
    if not close(pr["zoom_factor"], pr["mm_per_px"] / _MM_PER_CSS_PX, 0.001):
        add("S7-print", _CONTRACT,
            f"zoom_factor({pr['zoom_factor']}) != mm_per_px / {_MM_PER_CSS_PX:.6f}"
            f"({pr['mm_per_px'] / _MM_PER_CSS_PX:.4f})")
    if pr["stage_width_mm"] > pr["page_width_mm"] or pr["stage_height_mm"] > pr["page_height_mm"]:
        add("S7-print", _CONTRACT, "面が A4 の紙面より大きい (端が切れる)")
    # @page は 1 か所だけが持つ。CSS に 2 つ以上あると読み込み順で結果が変わる。
    css_text = (root / _CSS).read_text(encoding="utf-8") if (root / _CSS).is_file() else ""
    n_page = len(re.findall(r"@page\s*\{", css_text))
    if n_page != 1:
        add("S7-print", _CSS, f"@page 宣言が {n_page} 個 (1 個であるべき)")

    # --- S8: ひな形の骨格 ------------------------------------------------------
    for sk, html in sorted(tpls.items()):
        body = _strip_header_comment(html)
        m = re.search(r'data-slide-skeleton="([^"]+)"', body)
        if not m:
            add("S8-structure", f"{sk}.html", "data-slide-skeleton が無い")
        elif m.group(1) != sk:
            add("S8-structure", f"{sk}.html", f"data-slide-skeleton={m.group(1)} がファイル名と違う")
        if body.count("srg-slide__stage") != 1:
            add("S8-structure", f"{sk}.html", "srg-slide__stage は面ごとに 1 個であるべき")
        if "srg-slide__main" not in body:
            add("S8-structure", f"{sk}.html", "srg-slide__main が無い (残り高さを埋める要素が不在)")
        if not re.search(r'class="srg-slide ', body):
            add("S8-structure", f"{sk}.html", "ルートが .srg-slide でない")
        # 全面画像以外で絶対配置を使うと、chrome と重なって位置がズレる。
        if "position: absolute" in body and sk != "layout-image-full":
            add("S8-structure", f"{sk}.html", "本文で position:absolute を使っている")
        # 端が切れる差し込みを禁止する。
        if "object-fit: cover" in body or "object-fit:cover" in body:
            add("S8-structure", f"{sk}.html", "object-fit:cover は端が切れるので禁止")
        # media を宣言するひな形は差し込み口を持つ。
        kinds_here = set(re.search(r'data-media-kinds="([^"]*)"', body).group(1).split()) \
            if re.search(r'data-media-kinds="([^"]*)"', body) else set()
        if kinds_here - {"none"} and "data-media-slot" not in body:
            add("S8-structure", f"{sk}.html", "media 種別を宣言しているのに差し込み口が無い")
        unknown = kinds_here - kinds
        if unknown:
            add("S8-structure", f"{sk}.html", f"未知の media 種別を宣言: {sorted(unknown)}")

    # --- S9: 前後ナビは両方書く (戻る先が消える事故の封じ手) --------------------
    for sk, html in sorted(tpls.items()):
        body = _strip_header_comment(html)
        if 'data-chrome="nav"' in body:
            for nav in ("prev", "next"):
                if f'data-nav="{nav}"' not in body:
                    add("S9-nav", f"{sk}.html", f"nav 帯に data-nav=\"{nav}\" が無い")

    # --- S10: 文字寸法と充填率の妥当性 -----------------------------------------
    for k in ("title", "heading", "subheading", "body", "note", "caption"):
        if ty[k] < ty["min"]:
            add("S10-typography", _CONTRACT, f"typography.{k}={ty[k]} が min({ty['min']}) 未満")
    order = ["title", "heading", "subheading", "body", "note", "caption"]
    for a, b in zip(order, order[1:]):
        if ty[a] < ty[b]:
            add("S10-typography", _CONTRACT, f"typography.{a} < typography.{b} (階層が逆転)")
    if not 0 < fp["min_stage_fill_ratio"] < fp["max_stage_fill_ratio"] <= 1:
        add("S10-fill", _CONTRACT, "fill_policy が 0 < min < max <= 1 を満たさない")

    # --- S11: 色の直書き禁止 ---------------------------------------------------
    #   ひな形に生の 16 進を書くと、パレット (vendor SPEC.colors) を変えてもその面
    #   だけ取り残される。しかも var(--x, #hex) の形で書くと --x が未定義のとき
    #   fallback が既定値ではなく「上書き不能な定数」になり、間違った配色が正解と
    #   して回り始める。色は CSS のトークン定義ブロック 1 か所だけが持つ。
    for sk, html in sorted(tpls.items()):
        hexes = re.findall(r"#[0-9A-Fa-f]{6}\b", _strip_header_comment(html))
        if hexes:
            add("S11-color-literal", f"{sk}.html",
                f"色を直書きしている: {sorted(set(hexes))} (var(--srg-*) を使う)")
    body_css = re.sub(r"/\* ---- 色トークン ----.*?\n\}", "", css_text, count=1, flags=re.S)
    stray = sorted(set(re.findall(r"#[0-9A-Fa-f]{6}\b", body_css)))
    if stray:
        add("S11-color-literal", _CSS,
            f"トークン定義ブロックの外に色を直書きしている: {stray}")

    # --- SK12: 2 体系の同居禁止 (ひな形側) --------------------------------------
    for sk, html in sorted(tpls.items()):
        for w, m in _mixture_findings(_strip_header_comment(html), f"{sk}.html"):
            add("SK12-mixed-system", w, m)

    return findings


# --- SK12: 体系混在の述語 (ひな形にも成果物 deck にも同じ規則を当てる) -----------
#   `slider-*` (engine 経路) と `.srg-*` (ひな形経路) は寸法の合わせ方も `@page` の
#   帯幅も違う別体系。`@page` は成果物に 1 つしか効かないため、混ぜた deck はどちら
#   へ寄せても片側が 43mm ずれる。vendor の validate-print.js は `slider-*` の存在を
#   測る述語しか持たず「同居」を見ない (混ぜると P03 がむしろ緑へ転じる) ので、
#   混在の検出はこちら側で持つ。SR-7-12 の実効手段はこの SK12。

_SLIDER_MARK = re.compile(r"\bslider__item\b")
_SRG_MARK = re.compile(r"\bsrg-slide\b|data-slide-skeleton")

_MIX_MSG = ("`slider__item` (engine 経路) と `srg-slide`/`data-slide-skeleton` "
            "(ひな形経路) が同一 HTML に同居している。@page は成果物に 1 つしか効かず "
            "必要な帯幅が体系ごとに違う (0mm と 21.47mm) ため、面をどちらか一方の体系へ "
            "寄せる (SR-7-12)")


def _mixture_findings(html: str, where: str) -> list[tuple[str, str]]:
    if _SLIDER_MARK.search(html) and _SRG_MARK.search(html):
        return [(where, _MIX_MSG)]
    return []


def check_decks(paths: list[Path]) -> list[dict]:
    """成果物 deck HTML を体系混在について検査する (SK12をdeckへ適用する口)。"""
    findings: list[dict] = []
    for p in paths:
        try:
            html = _strip_header_comment(p.read_text(encoding="utf-8"))
        except OSError as e:
            findings.append({"check": "SK12-mixed-system", "where": str(p),
                             "message": f"読めない: {e}"})
            continue
        for w, m in _mixture_findings(html, str(p)):
            findings.append({"check": "SK12-mixed-system", "where": w, "message": m})
    return findings


# --- self-test ---------------------------------------------------------------

def _self_test(root: Path) -> tuple[bool, list[str]]:
    """検出能を合成入力で確かめる。

    検査器は「赤くならないこと」で正しさを主張しがちなので、意図的に壊した
    入力で赤くなることを別途固定する。壊した入力が緑のままなら、その検査は
    存在していないのと同じ。
    """
    import shutil
    import tempfile

    log: list[str] = []
    ok = True

    def check(name: str, cond: bool):
        nonlocal ok
        log.append(("PASS " if cond else "FAIL ") + name)
        ok = ok and cond

    check("T1 実体は違反ゼロ", run_checks(root) == [])

    with tempfile.TemporaryDirectory() as td:
        sandbox = Path(td) / "plg"
        for rel in ("assets/slide-templates", "schemas", "scripts"):
            shutil.copytree(root / rel, sandbox / rel)
        # 配色の正本も要る (CSS 生成器がこれを読んで色トークンを定義するため)。
        # vendor 全体は重いので、参照する 1 ファイルだけを同じ相対位置へ置く。
        pal_rel = Path("vendor/scripts/style-builder.cjs")
        (sandbox / pal_rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / pal_rel, sandbox / pal_rel)
        base_findings = run_checks(sandbox)
        check("T2 複製も違反ゼロ (陰性対照)", base_findings == [])

        def mutate(fn, name, want_check):
            # 変異は 1 件ずつ独立に効かせたいので、毎回スナップショットへ戻す
            # (前の変異が残ると、どの検査が反応したのか分からなくなる)。
            snap = {p: p.read_bytes() for p in sandbox.rglob("*") if p.is_file()}
            try:
                fn()
                got = run_checks(sandbox)
                check(name, any(f["check"].startswith(want_check) for f in got))
            finally:
                for p, b in snap.items():
                    p.write_bytes(b)
                # 変異がファイルを増やした場合は消す。スナップショットの書き戻し
                # だけだと新規ファイルが残り、次の変異の結果に混ざる。
                for p in list(sandbox.rglob("*")):
                    if p.is_file() and p not in snap:
                        p.unlink()

        def _drop_map_entry():
            p = sandbox / _REGISTRY
            d = _load_json(p)
            d["map"].pop(sorted(d["map"])[0])
            p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

        def _bad_media():
            p = sandbox / _REGISTRY
            d = _load_json(p)
            k = next(k for k, v in d["map"].items() if v["skeleton"] == "layout-message")
            d["map"][k]["media"] = "codex-image"
            p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

        def _break_geometry():
            p = sandbox / _CONTRACT
            d = _load_json(p)
            d["stage"]["width"] += 4
            p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

        def _break_zoom():
            p = sandbox / _CONTRACT
            d = _load_json(p)
            d["print"]["zoom_factor"] = 1.0
            p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

        def _hand_edit_css():
            p = sandbox / _CSS
            p.write_text(p.read_text(encoding="utf-8") + "\n.srg-slide { color: red; }\n", encoding="utf-8")

        def _hand_edit_html():
            p = sandbox / "assets/slide-templates/layout-message.html"
            p.write_text(p.read_text(encoding="utf-8").replace("</section>", "<div></div></section>"),
                         encoding="utf-8")

        def _off_grid_px():
            p = sandbox / "assets/slide-templates/layout-quote.html"
            p.write_text(p.read_text(encoding="utf-8").replace("4px solid", "3px solid"), encoding="utf-8")

        def _drop_prev_nav():
            p = sandbox / "assets/slide-templates/layout-message.html"
            p.write_text(re.sub(r'<a class="srg-nav__prev".*?</a>\n\s*', "",
                                p.read_text(encoding="utf-8"), flags=re.S), encoding="utf-8")

        def _second_at_page():
            p = sandbox / _CSS
            p.write_text(p.read_text(encoding="utf-8") + "\n@page { size: A4 portrait; }\n", encoding="utf-8")

        def _tiny_font():
            p = sandbox / _CONTRACT
            d = _load_json(p)
            d["typography"]["caption"] = 12
            p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

        mutate(_drop_map_entry, "T3 写像表から 1 型消すと S1", "S1")
        mutate(_bad_media, "T4 受け入れない media を指すと S3", "S3")
        mutate(_break_geometry, "T5 stage 幅の不整合で S5", "S5")
        mutate(_break_zoom, "T6 印刷倍率の不整合で S7", "S7")
        mutate(_hand_edit_css, "T7 CSS 手編集で S4", "S4")
        mutate(_hand_edit_html, "T8 ひな形手編集で S4", "S4")
        mutate(_off_grid_px, "T9 4 の倍数でない px で S6", "S6")
        mutate(_drop_prev_nav, "T10 前ナビ欠落で S9", "S9")
        mutate(_second_at_page, "T11 @page 二重定義で S7", "S7")
        mutate(_tiny_font, "T12 下限未満の文字寸法で S10", "S10")

        def _hand_edit_js():
            p = sandbox / _JS
            p.write_text(p.read_text(encoding="utf-8") + "\n/* 手編集 */\n", encoding="utf-8")

        def _color_literal_in_html():
            p = sandbox / "assets/slide-templates/layout-quote.html"
            p.write_text(p.read_text(encoding="utf-8").replace(
                "var(--srg-focal)", "#F8F7F0", 1), encoding="utf-8")

        def _orphan_skeleton():
            p = sandbox / _REGISTRY
            d = _load_json(p)
            # 誰も引かなくなったひな形は、実体があっても使われない = 存在しないのと同じ
            del d["role_pages"]["anticipated_questions"]
            p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

        mutate(_hand_edit_js, "T13 JS 手編集で S4", "S4")
        mutate(_color_literal_in_html, "T14 ひな形への色直書きで S11", "S11")
        mutate(_orphan_skeleton, "T15 引き手を失ったひな形で S2", "S2")

        def _mix_systems():
            p = sandbox / "assets/slide-templates/layout-message.html"
            p.write_text(p.read_text(encoding="utf-8").replace(
                "</section>", '<div class="slider__item" data-total="2"></div></section>', 1),
                encoding="utf-8")

        mutate(_mix_systems, "T16 ひな形へ slider__item を混ぜると SK12", "SK12")

        def _stray_non_layout_html():
            # glob を `layout-*` から `*.html` へ広げた効き目そのものを固定する。
            # 体系外の名前で置いたファイルが検査の外側に居続けると、ディレクトリを
            # 開いた読み手には候補に見えるのに誰も見ていない状態になる。
            (sandbox / "assets/slide-templates/p99-legacy.html").write_text(
                '<section class="srg-slide"><p style="color:#7E9CD8">x</p></section>',
                encoding="utf-8")

        mutate(_stray_non_layout_html, "T17 layout- 以外の名前のひな形も検査対象 (S11)", "S11")

        # deck 経路 (--deck) は run_checks を通らないので、mutate では踏めない。
        # 混在で赤く・純粋で緑になる両方を固定する (片側だけだと常時赤の検査でも
        # 通ってしまう)。
        srg = '<div class="srg-slide" data-slide-skeleton="layout-message"></div>'
        mixed = sandbox / "deck-mixed.html"
        mixed.write_text(f"<html><body>{srg}"
                         '<div class="slider__item"></div></body></html>', encoding="utf-8")
        pure = sandbox / "deck-pure.html"
        pure.write_text(f"<html><body>{srg}</body></html>", encoding="utf-8")
        check("T18 混在 deck を --deck で赤くできる",
              any(f["check"] == "SK12-mixed-system" for f in check_decks([mixed])))
        check("T19 単一体系 deck は緑のまま (陰性対照)", check_decks([pure]) == [])

    return ok, log


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="validate-slide-skeleton")
    ap.add_argument("--root", default=None)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--deck", action="append", default=[],
                    help="成果物 deck HTML を SK12 (体系混在) で検査する。複数指定可")
    args = ap.parse_args(argv)

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent

    if args.self_test:
        ok, log = _self_test(root)
        sys.stdout.write("\n".join(log) + f"\nself-test: {'PASS' if ok else 'FAIL'} ({len(log)} checks)\n")
        return 0 if ok else 1

    decks = [Path(d) for d in args.deck]
    findings = run_checks(root) + check_decks(decks)
    if args.json:
        sys.stdout.write(json.dumps({"findings": findings,
                                     "decks_checked": [str(d) for d in decks],
                                     "status": "pass" if not findings else "fail"},
                                    ensure_ascii=False, indent=2) + "\n")
    else:
        for f in findings:
            sys.stdout.write(f"[{f['check']}] {f['where']}: {f['message']}\n")
        # deck を渡さない実行は「混在が無い」ではなく「混在を見ていない」。
        # 緑の意味を取り違えないよう、被覆をそのまま出す。
        cover = (f"decks={len(decks)}" if decks
                 else "decks=0 (成果物の体系混在は未検査 — --deck <html> で見る)")
        sys.stdout.write(f"slide-skeleton: findings={len(findings)} {cover} -> "
                         f"{'PASS' if not findings else 'FAIL'}\n")
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
