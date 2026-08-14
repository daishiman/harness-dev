"""diagram-goldens 63 組 + production 2 組 = 65 組を CI で実行する。

goldens は references 各所で「契約を全部満たした実例」「回帰基準線」と宣言されて
いるが、その宣言を実行する経路がどの workflow にも無く、手で叩いたときしか
作動していなかった。本 test は `plugins/**/test_*.py` を walk する CI 機構に
乗ることで、workflow を変更せずにその宣言を実行可能にする。

(1) 63 組が対で揃っていること (手書き 53 = *-input.json + *-golden.html、
    builders 10 = *-spec.json + *-golden.html) と、production 2 組の射影が揃うこと。
    片側だけ増えたら赤。
(2) 全 golden が --check-grid --strict で指摘ゼロ。
(3) 検査が空振りしていないこと (inspected が golden 件数と一致する)。
    これが無いと「対象 0 件でも PASS」を回帰ガードとして受理してしまう。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_VALIDATOR = _PLUGIN_ROOT / "scripts" / "validate-svg-diagram.py"
_GOLDEN_DIR = (
    _PLUGIN_ROOT
    / "skills"
    / "run-slide-report-generate"
    / "examples"
    / "diagram-goldens"
)
_BUILDER_DIR = _GOLDEN_DIR / "builders"
# 本番語彙 (svgSpec) のゴールデン。builders/ との違いは「射影が 1 層挟まる」こと。
# 射影が入力を落とす欠陥は builders/ のゴールデンでは原理的に捕まらない。
_PRODUCTION_DIR = _GOLDEN_DIR / "production"


def _hand_goldens() -> list[Path]:
    return sorted(_GOLDEN_DIR.glob("*-golden.html"))


def _builder_goldens() -> list[Path]:
    return sorted(_BUILDER_DIR.glob("*-golden.html"))


def _production_goldens() -> list[Path]:
    return sorted(_PRODUCTION_DIR.glob("*-production-golden.html"))


# --- (1) 入力とゴールデンが対で揃っている ---------------------------------------

def test_hand_written_goldens_are_paired_with_input_json():
    missing = [
        g.name
        for g in _hand_goldens()
        if not g.with_name(g.name.replace("-golden.html", "-input.json")).exists()
    ]
    assert missing == [], f"入力 JSON が無いゴールデン: {missing}"


def test_builder_goldens_are_paired_with_spec_json():
    missing = [
        g.name
        for g in _builder_goldens()
        if not g.with_name(g.name.replace("-golden.html", "-spec.json")).exists()
    ]
    assert missing == [], f"spec JSON が無いゴールデン: {missing}"


def test_orphan_inputs_have_a_golden():
    orphans = [
        p.name
        for p in sorted(_GOLDEN_DIR.glob("*-input.json"))
        if not p.with_name(p.name.replace("-input.json", "-golden.html")).exists()
    ] + [
        p.name
        for p in sorted(_BUILDER_DIR.glob("*-spec.json"))
        if not p.with_name(p.name.replace("-spec.json", "-golden.html")).exists()
    ]
    assert orphans == [], f"ゴールデンが無い入力: {orphans}"


# --- (2)(3) 契約検査が実際に走り、指摘ゼロで通る --------------------------------

def test_production_goldens_are_paired_with_svgspec_json():
    """本番語彙のゴールデンと入力が対で揃っている。

    ここが空でも他のテストは全部緑になる。本番経路に基準線が 1 本も無い
    状態こそが元の欠陥だったので、最低 1 件あることも併せて要求する。
    """
    goldens = _production_goldens()
    assert goldens, "本番語彙 (svgSpec) のゴールデンが 1 件も無い"
    missing = [
        g.name for g in goldens
        if not g.with_name(g.name.replace("-production-golden.html", "-svgspec.json")).exists()
    ]
    assert missing == [], f"入力 JSON が無い本番ゴールデン: {missing}"


def test_production_goldens_are_regenerable():
    """本番ゴールデンが CLI の出力そのものである (手作業で化粧されていない)。"""
    renderer = _PLUGIN_ROOT / "scripts" / "render-production-golden.cjs"
    for golden in _production_goldens():
        src = golden.with_name(golden.name.replace("-production-golden.html", "-svgspec.json"))
        proc = subprocess.run(
            ["node", str(renderer), str(src)], capture_output=True, text=True,
        )
        assert proc.returncode == 0, f"{src.name} の再生成が失敗:\n{proc.stderr.strip()}"
        assert proc.stdout == golden.read_text(encoding="utf-8"), (
            f"{golden.name} が再生成結果と一致しない (手で編集された可能性がある)"
        )


def test_production_high_level_keeps_declared_edges():
    """射影が edges[] を落としていないこと。

    段間の依存が全部落ちると buildHighLevel は段レベルのトランク 1 本へ倒れ、
    図としては成立してしまう。**成立するのに情報が消える**ため、幾何検査でも
    情報検査でも捕まらない。宣言した辺の本数が線として現れることを直接見る。
    """
    import json
    src = _PRODUCTION_DIR / "high-level-svgspec.json"
    spec = json.loads(src.read_text(encoding="utf-8"))["svgSpec"]
    by_id = {n["id"]: n for n in spec["nodes"]}
    group_order = [g["id"] for g in spec["groups"]]

    def tier(node_id: str) -> int:
        return group_order.index(by_id[node_id]["group"])

    # 隣の段へ向かう辺だけが線になる (段飛ばし・逆向きは対象外)。
    expected = sum(
        1 for e in spec["edges"] if tier(e["to"]) == tier(e["from"]) + 1
    )
    html = (_PRODUCTION_DIR / "high-level-production-golden.html").read_text(encoding="utf-8")
    drawn = html.count("<path ")
    assert drawn == expected, (
        f"宣言した段間の辺 {expected} 本に対し線が {drawn} 本。"
        "射影が edges[] を落とすと 1 本のトランクへ倒れる"
    )


def test_production_swimlane_draws_only_declared_handoffs():
    """レーン図が順序を捏造していないこと。

    以前は order 未指定の升目へ位置の連番 (レーン番号 × 工程数 + 列) を
    既定の順序として与えていたので、edges[] を持つ svgSpec を射影しても
    「レーン 1 の全工程 → レーン 2 の全工程」という受け渡しが描かれた。
    入力に無い主張なので、宣言した辺の本数と線の本数を直接突き合わせる。
    """
    import json
    src = _PRODUCTION_DIR / "swimlane-svgspec.json"
    expected = len(json.loads(src.read_text(encoding="utf-8"))["svgSpec"]["edges"])
    html = (_PRODUCTION_DIR / "swimlane-production-golden.html").read_text(encoding="utf-8")
    drawn = html.count("<path ")
    assert drawn == expected, (
        f"宣言した受け渡し {expected} 本に対し線が {drawn} 本。"
        "多ければ位置から順序を作っており、少なければ edges[] を捨てている"
    )


def test_production_goldens_carry_their_declaration():
    """生成物が参照検査の材料を運んでいること。

    描画済み SVG から実体と関係を復元するのは座標の近似になるので、
    レンダラは `data-srg-declaration` へ申告をそのまま載せる。運ばれて
    いなければ .html は I-ER-REF / I-REL-ISO を素通りする — しかも
    「指摘なし」として緑で通るので、欠落は検査結果からは見えない。
    宣言した節点の id と、運ばれた宣言の id を直接突き合わせる。
    """
    import html as htmllib
    import json
    goldens = _production_goldens()
    assert goldens, "production ゴールデンが 0 件 (パス解決の失敗を PASS にしない)"
    for golden in goldens:
        src = golden.with_name(golden.name.replace("-production-golden.html", "-svgspec.json"))
        declared = {
            n["id"] for n in json.loads(src.read_text(encoding="utf-8"))["svgSpec"]["nodes"]
        }
        m = re.search(r'data-srg-declaration="([^"]*)"', golden.read_text(encoding="utf-8"))
        assert m, f"{golden.name} が宣言を運んでいない (.html の参照検査が空振りする)"
        carried = {n.get("id") for n in json.loads(htmllib.unescape(m.group(1)))["nodes"]}
        assert carried == declared, (
            f"{golden.name}: 宣言した節点 {sorted(declared)} に対し "
            f"運ばれたのは {sorted(carried)}"
        )


def test_all_goldens_pass_strict_diagram_contract():
    goldens = _hand_goldens() + _builder_goldens() + _production_goldens()
    assert goldens, "ゴールデンが 1 件も見つからない (パス解決の失敗を PASS にしない)"

    proc = subprocess.run(
        [sys.executable, str(_VALIDATOR), "--check-grid", "--strict",
         *[str(p) for p in goldens]],
        capture_output=True,
        text=True,
    )
    summary = (proc.stdout + proc.stderr).strip()
    assert proc.returncode == 0, f"契約検査が失格を返した:\n{summary}"

    # 空振り PASS を回帰ガードとして受理しないための下限確認。
    m = re.search(r"inspected=(\d+)", summary)
    assert m, f"サマリに inspected トークンが無い:\n{summary}"
    assert int(m.group(1)) == len(goldens), (
        f"検査対象が実ファイル数と一致しない "
        f"(inspected={m.group(1)} / goldens={len(goldens)}):\n{summary}"
    )


# --- (4) 情報の下限 -------------------------------------------------------------
#
# 上の検査は幾何・配色・複雑度の**上限**しか見ない。上限しか無かった間、
# 主キーの無い ER 図も依存線の無いガント図も母数の無いグラフも全部緑で通った。
# 下限 (references/diagram-information-contract.md) は別の検査器が持つ。

_INFO_VALIDATOR = _PLUGIN_ROOT / "scripts" / "validate-diagram-information.py"

# 参照検査 (entities/nodes を辿る 2 つの error) の語彙を持たない図。
# グラフ系は系列と数値であって節点と辺ではなく、階層系は items の入れ子で
# 節点 id を持たない。ここに載っていない名が skipped に出たら、掘り方が
# 入力の語彙に追随できていない合図なのでテストを落とす。
_INFO_SKIP_ALLOWLIST = {
    # グラフ (系列・数値のみ)
    "bar-chart-input.json", "clock-chart-input.json", "gauge-chart-input.json",
    "hbar-chart-input.json", "heatmap-input.json", "line-chart-input.json",
    "pie-chart-input.json", "radar-chart-input.json", "scatter-plot-input.json",
    "stacked-bar-input.json", "waterfall-input.json",
    # 階層・帯・時系列 (節点 id を持たない構造)
    "architecture-layers-input.json", "architecture-spec.json",
    "data-flow-spec.json", "dp-integration-spec.json", "high-level-spec.json",
    "it-state-spec.json", "journey-map-input.json", "medallion-spec.json",
    "sequence-spec.json", "state-spec.json", "swimlane-process-input.json",
    "swimlane-spec.json",
}


def test_information_validator_self_test():
    """検査器そのものの健全性。

    新しい検査コードの重大度登録漏れ、型判別の誤り、
    error 重大度の誤検知をここで止める。誤検知する検査は
    使われなくなり、使われない検査は無いのと同じになる。
    """
    proc = subprocess.run(
        [sys.executable, str(_INFO_VALIDATOR), "--self-test"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def test_all_goldens_carry_required_information():
    """ゴールデンが情報契約の下限を満たす。

    error だけを失格にする (warning は語彙近似で誤検知しうるため)。
    error は参照の取りこぼしと孤立節点の 2 件だけで、どちらも構造から
    確定的に判定でき、読者を確実に誤読させる。
    """
    targets = (
        _hand_goldens()
        + _builder_goldens()
        + _production_goldens()
        + sorted(_GOLDEN_DIR.glob("*-input.json"))
        + sorted(_BUILDER_DIR.glob("*-spec.json"))
        + sorted(_PRODUCTION_DIR.glob("*-svgspec.json"))
    )
    assert targets, "検査対象が 1 件も無い (パス解決の失敗を PASS にしない)"

    proc = subprocess.run(
        [sys.executable, str(_INFO_VALIDATOR), *[str(p) for p in targets]],
        capture_output=True, text=True,
    )
    out = proc.stdout + proc.stderr
    errors = [ln for ln in out.splitlines() if ln.startswith("[error]")]
    assert proc.returncode == 0 and not errors, (
        "情報契約が失格を返した:\n" + "\n".join(errors or [proc.stderr.strip()])
    )

    # 空振りガード。findings が空でも「合格した」とは限らず、パス解決の失敗も
    # 入力の破損も同じ空リストになる。検査できた件数を数えて突き合わせる。
    m = re.search(r"targets=(\d+) inspected=(\d+) skipped=(\d+)", out)
    assert m, "検査サマリが出ていない:\n" + out.strip()
    got_targets, inspected, skipped = (int(g) for g in m.groups())
    assert got_targets == len(targets), f"渡した件数と食い違う: {got_targets}"
    assert inspected + skipped == got_targets
    assert inspected > 0, "1 件も検査できていない"

    # 検査対象外は「参照検査の語彙 (entities/nodes) を持たない図」に限られる。
    # 許可名簿を上限として持ち、名簿外が skipped に落ちたら落とす。名簿から
    # 減る方向 (検査できる図が増える) は素通しでよいので部分集合で判定する。
    reported = set()
    for ln in out.splitlines():
        if ln.startswith("skipped (検査対象なし): "):
            reported = set(ln.split(": ", 1)[1].split())
    unexpected = sorted(reported - _INFO_SKIP_ALLOWLIST)
    assert not unexpected, (
        "参照検査の語彙を持つはずの図が黙って素通りしている: " + " ".join(unexpected)
    )


# --- (5) 文書全体の id 衝突 (D22 / D23・SR-15-20) --------------------------------
#
# 上の検査は全て「1 つの図」を単位に見る。1 面 1 図の golden では、面を
# またいで同じ id が並ぶ状態そのものが作れない。実際 2026/8 に、全面の SVG が
# 同じ `arrow-blue` を定義していたため 1 面目以外の矢じりが消えた欠陥が
# D0-D21 を 1 件も鳴らさずに出荷された。文書を単位に見る検査をここで踏む。

_RENDERER = _PLUGIN_ROOT / "vendor" / "scripts" / "render-slide.cjs"


def _svg(*body: str, ids: str = "") -> str:
    return (
        '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
        + ids + "".join(body) + "</svg>"
    )


def _run_validator(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_VALIDATOR), str(path)],
        capture_output=True, text=True,
    )


def test_svg_diagram_validator_self_test():
    """検査器そのものの健全性 (重大度の登録漏れ・D22/D23 の作動確認を含む)。"""
    proc = subprocess.run(
        [sys.executable, str(_VALIDATOR), "--self-test"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def test_duplicate_ids_across_svgs_in_one_file_is_error(tmp_path: Path):
    """2 つの SVG が同じ id を定義したら error。

    個々の SVG はどちらも正しい (D3 も通る) が、ブラウザは url(#...) を文書内で
    最初に現れる定義へ解決するので、2 面目の参照は隠れている 1 面目を指す。
    """
    marker = '<defs><marker id="arrow-blue"><path d="M0 0"/></marker></defs>'
    line = ('<line x1="40" y1="100" x2="200" y2="100" stroke="#43436c"'
            ' marker-end="url(#arrow-blue)"/>')
    deck = tmp_path / "dup.html"
    deck.write_text(
        "<html><body>" + _svg(line, ids=marker) * 2 + "</body></html>",
        encoding="utf-8",
    )
    proc = _run_validator(deck)
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, f"重複 id が素通りした:\n{out}"
    assert "[D22]" in out and "arrow-blue" in out, out


def test_duplicate_ids_are_checked_beyond_arrow_prefix(tmp_path: Path):
    """罠は marker 固有ではない。clipPath でも同じ error が出る。

    `arrow-` 接頭辞へ絞った検査だと、次に別の defs が増えた日にまた素通りする。
    """
    clip = ('<defs><clipPath id="clip-a">'
            '<rect x="0" y="0" width="10" height="10"/></clipPath></defs>')
    rect = ('<rect x="40" y="60" width="200" height="60" fill="#FFFFFF"'
            ' stroke="#43436c" clip-path="url(#clip-a)"/>')
    deck = tmp_path / "dup-clip.html"
    deck.write_text(
        "<html><body>" + _svg(rect, ids=clip) * 2 + "</body></html>",
        encoding="utf-8",
    )
    out = _run_validator(deck)
    assert "[D22]" in (out.stdout + out.stderr), (out.stdout + out.stderr)


def test_reference_into_another_slide_svg_is_error(tmp_path: Path):
    """参照先が別の面の SVG にしか無ければ error (D23)。"""
    grad = ('<defs><linearGradient id="grad-a">'
            '<stop offset="0" stop-color="#43436c"/></linearGradient></defs>')
    rect = ('<rect x="40" y="60" width="200" height="60" fill="url(#grad-a)"'
            ' stroke="#43436c"/>')
    deck = tmp_path / "cross-ref.html"
    deck.write_text(
        "<html><body>" + _svg(rect, ids=grad) + _svg(rect) + "</body></html>",
        encoding="utf-8",
    )
    proc = _run_validator(deck)
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0 and "[D23]" in out, out


def test_shared_defs_svg_is_not_flagged(tmp_path: Path):
    """描画物を持たない共有 defs 置き場への参照は正当 (誤検出させない)。

    `<svg width="0" height="0">` に全面ぶんの gradient / filter を集める書き方は
    既存デッキで実際に使われている。この SVG は何も描かないので面の切替
    (visibility:hidden) の影響を受けず、どの面から参照しても定義は生きている。
    """
    shared = (
        '<svg width="0" height="0" style="position:absolute"'
        ' xmlns="http://www.w3.org/2000/svg"><defs>'
        '<filter id="card-shadow"><feDropShadow dx="0" dy="4"/></filter>'
        '<linearGradient id="card-fill-blue">'
        '<stop offset="0" stop-color="#43436c"/></linearGradient></defs></svg>'
    )
    rect = ('<rect x="40" y="60" width="200" height="60" fill="url(#card-fill-blue)"'
            ' stroke="#43436c" filter="url(#card-shadow)"/>')
    deck = tmp_path / "shared-defs.html"
    deck.write_text(
        "<html><body>" + shared + _svg(rect) + _svg(rect) + "</body></html>",
        encoding="utf-8",
    )
    proc = _run_validator(deck)
    out = proc.stdout + proc.stderr
    # D1 (viewBox 無し) はこの置き場の形そのものへの別の指摘なので、ここでは
    # 見ない。この test の主張は「参照の検査が正当な共有を咎めない」ことだけ。
    assert "[D22]" not in out and "[D23]" not in out, f"正当な共有 defs を咎めた:\n{out}"


def test_rendered_deck_scopes_marker_ids_per_slide(tmp_path: Path):
    """決定論経路の出力が文書全体で id を一意に保つ (2026/8 の欠陥の回帰固定)。

    svg-kit の `markerDefs` は面をまたいで同じ `arrow-blue` を出すので、
    面番号による分離が外れると同名 id が並ぶ。上の合成 HTML と違い、
    ここは実レンダラの出力そのものを検査に掛ける。
    """
    import json
    step = lambda label, icon: {"label": label, "desc": "説明", "icon": icon}  # noqa: E731
    source = tmp_path / "structure.json"
    source.write_text(json.dumps({
        "meta": {"title": "id scope regression"},
        "slides": [
            {"id": f"s{i}", "slideType": "slide-flow", "content": {
                "title": f"流れ {i}",
                "steps": [step("入力", "fa-solid fa-pen"),
                          step("対話", "fa-solid fa-comments"),
                          step("出力", "fa-solid fa-file-lines")],
            }}
            for i in (1, 2)
        ],
    }, ensure_ascii=False), encoding="utf-8")
    out_dir = tmp_path / "deck"
    proc = subprocess.run(
        ["node", str(_RENDERER), str(source), "--out", str(out_dir), "--no-validate"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (proc.stdout + proc.stderr).strip()
    html = (out_dir / "index.html").read_text(encoding="utf-8")

    ids = re.findall(r'id="(arrow-[^"]+)"', html)
    assert ids, "矢印 marker が 1 つも出ていない (検査が空振りしている)"
    assert len(ids) == len(set(ids)), f"同名の marker id が並んでいる: {sorted(ids)}"
    # 参照が定義の無い id を指していないこと (面番号の付け方が片側だけ変わる事故)
    refs = set(re.findall(r"url\(#(arrow-[^)]+)\)", html))
    assert refs <= set(ids), f"定義の無い marker を参照している: {sorted(refs - set(ids))}"

    result = _run_validator(out_dir / "index.html")
    assert result.returncode == 0, (result.stdout + result.stderr).strip()


# --- (6) id をそのまま書く参照 (aria-labelledby・SR-15-20) ----------------------
#
# 2026/8、ブログ記事の 4 つの図が `aria-labelledby="title desc"` を共有していた。
# 絵は 1px も変わらないため目視でもスクショ比較でも気付けないが、
# 読み上げは全て先頭の図の <title>/<desc> になる。url(#...) だけを見る検査は
# この形の参照を素通りするので、参照の種類ごとに踏んでおく。

def _labelled_svg(uid: str, ref: str, label: str) -> str:
    return (
        '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg"'
        f' role="img" aria-labelledby="{ref}">'
        f'<title id="{uid}">{label}</title>'
        '<rect x="40" y="60" width="200" height="60" fill="#FFFFFF" stroke="#43436c"/>'
        "</svg>"
    )


def test_duplicate_title_id_across_figures_is_flagged(tmp_path: Path):
    """同名の <title id> を持つ 2 図は D22 で止まる (読み上げが先頭へ吸われる)。"""
    page = tmp_path / "aria-dup.html"
    page.write_text(
        "<html><body>"
        + _labelled_svg("title", "title", "1 枚目")
        + _labelled_svg("title", "title", "2 枚目")
        + "</body></html>",
        encoding="utf-8",
    )
    proc = _run_validator(page)
    out = proc.stdout + proc.stderr
    assert "[D22]" in out, f"同名 title id を見逃した:\n{out}"
    assert proc.returncode != 0


def test_aria_labelledby_pointing_at_another_figure_is_flagged(tmp_path: Path):
    """aria-labelledby が別の図の title を指していたら D23 で止まる。

    id は一意なので D22 は鳴らない。url(#...) しか見ない検査だとここが穴になる。
    """
    page = tmp_path / "aria-cross.html"
    page.write_text(
        "<html><body>"
        + _labelled_svg("title-s1", "title-s1", "1 枚目")
        + _labelled_svg("title-s2", "title-s1", "2 枚目")
        + "</body></html>",
        encoding="utf-8",
    )
    proc = _run_validator(page)
    out = proc.stdout + proc.stderr
    assert "[D22]" not in out, f"id は一意なのに D22 が鳴った:\n{out}"
    assert "[D23]" in out, f"別の図を指す aria 参照を見逃した:\n{out}"


def test_aria_labelledby_pointing_outside_svg_is_not_flagged(tmp_path: Path):
    """SVG の外の見出しを指す aria 参照は咎めない (検査は SVG しか見ていない)。"""
    page = tmp_path / "aria-outside.html"
    page.write_text(
        '<html><body><h2 id="sec-faq">FAQ</h2>'
        + _labelled_svg("title-s1", "sec-faq", "1 枚目")
        + "</body></html>",
        encoding="utf-8",
    )
    proc = _run_validator(page)
    out = proc.stdout + proc.stderr
    assert "[D23]" not in out, f"SVG 外への正当な参照を咎めた:\n{out}"


def test_scoped_title_ids_pass(tmp_path: Path):
    """図ごとに接尾辞を付けた形 (実ファイルへ施した修正と同じ形) は通る。"""
    page = tmp_path / "aria-scoped.html"
    page.write_text(
        "<html><body>"
        + _labelled_svg("title-s1", "title-s1", "1 枚目")
        + _labelled_svg("title-s2", "title-s2", "2 枚目")
        + "</body></html>",
        encoding="utf-8",
    )
    proc = _run_validator(page)
    out = proc.stdout + proc.stderr
    assert "[D22]" not in out and "[D23]" not in out, f"正しい形を咎めた:\n{out}"
