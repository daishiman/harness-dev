"""lint-count-parity.py のテスト。

(1) 現在の plugin 実体に対し count-drift ゼロ (回帰ガード: 散文の数詞が実装から
    ずれたら赤。数字を実測値へ直しただけでは再発するので、ここが再発の封鎖点)。
(2) 実測器が「正本」を数えていること (散文由来の値を読んでいないことの固定)。
(3) 検出能 (数字ずらし / 未アノテーション / 未登録 key / orphan)。
(4) false-positive 非発火 (コードブロック内・count-exempt 行・図ごとの要素数)。
"""
from __future__ import annotations

import importlib.util
import inspect
import re
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _PLUGIN_ROOT / "scripts" / "lint-count-parity.py"


def _load():
    spec = importlib.util.spec_from_file_location("lint_count_parity_mod", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


# --- (1) 回帰ガード -----------------------------------------------------------

def test_current_plugin_has_no_count_drift():
    findings = mod.run_checks(_PLUGIN_ROOT)
    assert findings == [], "count-drift: " + "; ".join(
        f"{f['check']} @ {f['where']}: {f['message']}" for f in findings
    )


def test_self_test_passes():
    ok, log = mod._self_test(_PLUGIN_ROOT)
    assert ok, "\n".join(l for l in log if l.startswith("FAIL"))


# --- (2) 実測器が正本を数えている ---------------------------------------------

def test_every_key_measurable():
    """1 key でも実測不能なら、その key の parity 検査は静かに無効になる。"""
    for key, fn in mod.MEASURERS.items():
        val = fn(_PLUGIN_ROOT)
        assert isinstance(val, int) and val > 0, f"{key} が実測できない (実測={val})"


def test_measurers_are_internally_consistent():
    live = {k: fn(_PLUGIN_ROOT) for k, fn in mod.MEASURERS.items()}
    assert live["slideType"] == live["slideTypeNonD3"] + live["d3Component"]
    assert live["diagramGolden"] == (
        live["diagramGoldenHand"] + live["diagramGoldenBuilder"]
        + live["diagramGoldenProduction"]
    )
    assert live["diagramCheckMax"] == live["diagramCheck"] - 1
    assert live["svgBuilder"] == (
        live["svgBuilderCore"] + live["svgBuilderStruct"] + live["svgBuilderOwn"]
    )


def test_measurers_do_not_read_prose():
    """実測器が「別の散文」を読んでいないことを源から固定する。

    散文の数字を別の散文で検証すると自己参照になり SSOT が消える。markdown を
    正本にしてよいのは「その markdown 自身が数えられる対象そのもの」である
    3 key に限る (見出し群 / DT-ID 群 / SR 行群)。それ以外の実測器の本体に
    `.md` が現れたら、散文を真値として読み始めた合図なので落とす。
    """
    md_backed = {"cssDiagramType", "slideTypeDecision", "specRegistryRule"}
    for key, fn in mod.MEASURERS.items():
        if key in md_backed:
            continue
        body = inspect.getsource(fn)
        # 実測器が参照する定数名を展開してから判定する (定数経由の迂回を塞ぐ)。
        for const in re.findall(r"\b(_[A-Z][A-Z0-9_]*)\b", body):
            body += " " + str(getattr(mod, const, ""))
        assert ".md" not in body, f"{key} の実測器が markdown を読んでいる (SSOT が散文へ退化)"



def _series_root(tmp_path, items: list[str], extra: str = "") -> Path:
    """svg-kit.cjs だけを持つ合成 root。SERIES 実測器の入力を 1 箇所ずつ壊すため。"""
    kit = tmp_path / "vendor" / "scripts" / "svg-kit.cjs"
    kit.parent.mkdir(parents=True, exist_ok=True)
    body = ",\n".join(f"  '{s}'" for s in items)
    kit.write_text(f"{extra}const SERIES = [\n{body},\n];\n", encoding="utf-8")
    return tmp_path


def test_series_measurers_separate_frames_from_distinct_colors(tmp_path):
    """枠数と区別できる色数は別物。同色 2 枠 (D29 が鳴った形) を数字で分離できるか。"""
    distinct = _series_root(tmp_path / "ok", [
        "var(--a, #111111)", "var(--b, #222222)", "var(--c, #333333)",
    ])
    assert mod._m_series(distinct) == 3
    assert mod._m_series_distinct(distinct) == 3

    dup = _series_root(tmp_path / "ng", [
        "var(--a, #111111)", "var(--b, #111111)", "var(--c, #333333)",
    ])
    assert mod._m_series(dup) == 3, "枠は減っていない (減るなら枠を数えていない)"
    assert mod._m_series_distinct(dup) == 2, "同色 2 枠が 1 つに畳まれない"


def test_series_block_is_read_without_stripping_urls(tmp_path):
    """全文へコメント除去を当てると `://` を含む行で文字列が壊れる。その再発を止める。

    実ファイルには `xmlns="http://...` の行がある。`SERIES` 側は逆に、ブロック内の
    `//` コメントで無効化した要素を数えてはいけない (不在を書いた行が存在として数
    えられる形)。両方をこの 1 本で固定する。
    """
    root = _series_root(
        tmp_path,
        ["var(--a, #111111)", "var(--b, #222222)"],
        extra='const S = `<svg xmlns="http://www.w3.org/2000/svg">`;\n',
    )
    kit = root / "vendor" / "scripts" / "svg-kit.cjs"
    kit.write_text(
        kit.read_text(encoding="utf-8").replace(
            "];", "  // 'var(--c, #333333)' は b と同色だったため置いていない\n];"),
        encoding="utf-8",
    )
    assert mod._m_series(root) == 2
    assert mod._m_series_distinct(root) == 2


# --- (3) 検出能 ---------------------------------------------------------------

def _probe(tmp_path, text: str, name: str = "probe.md"):
    """正本は実 root、走査だけ tmp_path。検出ロジックは run_checks 本体を通す。"""
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return mod.run_checks(_PLUGIN_ROOT, scan_root=tmp_path)


def test_detects_off_by_one(tmp_path):
    live = mod.MEASURERS["slideType"](_PLUGIN_ROOT)
    out = _probe(tmp_path, f"<!-- count: slideType -->{live + 1} slideType\n")
    assert any(f["check"] == "count-parity" for f in out)


def test_detects_unannotated(tmp_path):
    live = mod.MEASURERS["slideType"](_PLUGIN_ROOT)
    out = _probe(tmp_path, f"{live} slideType を使う\n")
    assert any(f["check"] == "count-unannotated" for f in out)


def test_detects_unknown_key(tmp_path):
    out = _probe(tmp_path, "<!-- count: noSuchKey -->5 個\n")
    assert any(f["check"] == "count-unknown-key" for f in out)


def test_detects_orphan_annotation(tmp_path):
    out = _probe(tmp_path, "<!-- count: slideType --> 整数の無い行\n")
    assert any(f["check"] == "count-annotation-orphan" for f in out)


# --- (4) false-positive 非発火 -------------------------------------------------

def test_correct_annotation_is_silent(tmp_path):
    live = mod.MEASURERS["slideType"](_PLUGIN_ROOT)
    assert _probe(tmp_path, f"<!-- count: slideType -->{live} slideType\n") == []


def test_code_fence_is_not_scanned(tmp_path):
    live = mod.MEASURERS["slideType"](_PLUGIN_ROOT)
    assert _probe(tmp_path, f"```\n{live + 9} slideType\n```\n") == []


def test_exempt_marker_is_respected(tmp_path):
    assert _probe(tmp_path, "<!-- count-exempt: 自己記述 -->24 slideType\n") == []


def test_per_figure_counts_are_not_flagged(tmp_path):
    """chart-types.md 系の『ゴールデンは 5 件』は図ごとの要素数で、集合の大きさではない。"""
    text = (
        "- カテゴリ数: ゴールデンは 5 件。上限 8（`CAPACITY.buildBarChart`）\n"
        "- 系列数: ゴールデンは 2 系列\n"
        "- 階層 2-4 層、ノード 4-8（ゴールデンは 3 層 6 ノード）\n"
    )
    assert _probe(tmp_path, text) == []


def test_json_counts_are_checked_without_annotation(tmp_path):
    """JSON は HTML コメントを置けないので、注釈を要求せず直接突合する。

    `.claude-plugin/plugin.json` の description にあった `97 slideType` は、
    走査 glob が `.md` 3 系統だけだったため本 lint をすり抜けて生き残った。
    """
    live = mod.MEASURERS["slideType"](_PLUGIN_ROOT)
    rel = ".claude-plugin/plugin.json"

    ok = _probe(tmp_path, '{"description": "slide=%d slideType"}\n' % live, rel)
    assert ok == [], f"正しい JSON の数詞に指摘が出た: {ok}"

    ng = _probe(tmp_path, '{"description": "slide=%d slideType"}\n' % (live + 1), rel)
    assert any(f["check"] == "count-parity" for f in ng), ng
    assert not any(f["check"] == "count-unannotated" for f in ng), (
        "JSON へアノテーションを要求すると恒久免除と同じになる"
    )
