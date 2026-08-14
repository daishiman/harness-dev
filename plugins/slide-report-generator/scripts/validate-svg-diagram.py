#!/usr/bin/env python3
# /// script
# name: validate-svg-diagram
# purpose: 生成済み SVG 図解が図解レイアウト契約を満たすか決定論的に検査する。
# inputs:
#   - argv: 検査対象の .svg / .html パス (複数可)
# outputs:
#   - stdout: 検査サマリ
#   - stderr: 違反の一覧
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""validate-svg-diagram.py — 図解レイアウト契約の決定論ゲート。

契約の説明は references/diagram-layout-contract.md、値の正本は
references/spec-registry.md §15 / §15-a。

決定論経路 (vendor/scripts/svg-*.cjs) でも LLM 経路 (agents/*) でも、出来上がるのは
同じ SVG なので、検査は成果物側に一本化する。レンダリング (Playwright) を必要と
しない静的検査だけを扱い、実描画でしか分からない項目 (フォント実測の字形差など)
は ui-quality-reviewer 側の責務として残す。

検査コードは D (Diagram) 接頭辞。同じ scripts/ にある validate-report-visual.py も
C1.. を使うため、番号だけで参照すると取り違える。

検査項目 (根拠 SR-ID は references/spec-registry.md §15。件数は ALL_CODES が正本):
  D0  パース可能     SVG として構文解析できる
  D1  viewBox 収容   図形・文字が viewBox の外へ出ていない
  D2  数値健全性     NaN / undefined / Infinity が座標に混入していない
  D3  marker 解決    marker-end/-start の参照先が同じ SVG 内で定義されている
  D4  最小フォント   font-size が 12px 未満でない (SR-3-05)
  D5  斜めコネクタ   <line>/<polyline> は水平か垂直 (放射状・チャート型は例外申告)
  D6  4px グリッド   矩形の座標・寸法が 4px グリッド上にある (SR-5 系)
  D7  accent 抑制    強調色の面塗りが 1 図あたり 2 件以下 (視線の着地点をひとつに)
  D8  FA unicode     <text> 内に Font Awesome の PUA コードがない (SR-3-06)
  D9  線の太さ       stroke-width が 1.25 未満でない (縮小表示で灰色に溶ける)
  D10 パレット逸脱   色が svg-kit の TOKENS/SERIES 由来か var(--*) 参照 (SR-2-02/2-08)
  D11 複雑度上限     1 図のノード相当+コネクタ数が上限以内 (svg-builder の CAPACITY 由来)
  D12 外部依存       SVG 内に <script> / 外部 http(s) 参照 / 外部フォントが無い (SR-3-06)
  D13 font-family    書体が svg-kit の既定スタック内 (SR-3-01。字幅モデルの前提)
  D14 CSS グリッド   CSS/HTML 図解の間隔が --space-* 由来・px 寸法が GRID の倍数 (§D-1)
  D15 複雑度予算     注釈・凡例・ノード/コネクタ・フォント階層が §D-2 の 21 項目以内
  D16 CSS accent     CSS/HTML 図解の accent 色を持つ要素が §D-2 #3 以内 (D7 の CSS 版)
  D17 斜め path      コネクタ <path> に斜めの直線セグメントが無い (§D-3 原則 1)
  D18 文字収容       文字が viewBox とラベル箱に収まる (§D-8・error/warning の 2 段)
  D19 辺への溶け     コネクタが箱の辺と共線で 12px 以上走っていない (SR-15-19)
  D20 線の重なり     別々のコネクタが同一直線上で 12px 以上重なっていない (SR-15-19)
  D21 箱の貫通       コネクタが無関係な箱の内側を 12px 以上貫いていない (SR-15-19)
  D22 id 一意性      1 ファイル内で SVG の id が重複していない (SR-15-20)
  D23 参照の閉じ     文書内参照 (url(#id) / aria-labelledby / href="#id") の
                     参照先が自分の SVG か共有 defs にある (SR-15-20)

D0-D9 が幾何と可読性を見るのに対し、D10-D13 は「素材」を見る。素材の検査が
必要なのは、ビルダー関数の入口 (CAPACITY やトークン表) は決定論経路にしか
効かず、agent が SVG を直接書く LLM 経路を素通りするため。契約は
「どちらの経路でも同じ契約で採点する」(diagram-layout-contract.md §冒頭) と
宣言しているので、上限も語彙も成果物側で見直す。

D10/D13 の許可集合と D11 の上限は、この検査器へ二重定義せず
vendor/scripts/svg-kit.cjs / svg-builder.cjs から実行時に正規表現抽出する
(lint-contract-drift.py の _load_thresholds と同じ手口)。値の正本を 1 つに
保たないと、パレットを差し替えたときに検査器だけが古い色を許し続ける。

D6 だけは既定で走らせない (--check-grid で有効化)。列分割の余りで幅が 253px に
なるような箱は実際には誰も気付かない一方、件数だけは全検査の 9 割を占めて
D5/D7 のような本当に読ませたい指摘を埋めてしまうため。

exit 0 = error 0 件、exit 1 = error あり。warning は exit code に影響しない。

サマリ末尾の inspected= / coverage= は「どれだけ検査したか」で、合否とは別物。
coverage=none (inspected=0) の PASS は「検査対象が 1 つも無かった」であって
「検査して合格した」ではない。exit code はこの区別に影響されないので、
判定を表示する側 (hooks/hook-postgen-eval.py) が必ず両方を読むこと。
"""
from __future__ import annotations

import os
import re
import sys
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"

# 検査コード -> 既定の重大度。error は exit 1、warning は報告のみ。
# 未登録のコードは "error" 扱い (fail-closed)。新しい検査を足したとき、
# ここへ書き忘れても静かに見逃されるのではなく必ず失格側へ倒すため。
# error は「直さないと図解として読めない」もの、warning は「人が見て判断する
# 余地があるか、誤検知しうる」ものに割り当てる。
SEVERITY: dict[str, str] = {
    # D0 パース不能 / D2 NaN 混入 / D3 marker 未定義 は誤検知の余地がなく、
    # いずれも「矢印や図形が消える」形で読者に届く。未登録=error のまま。
    # D1 viewBox はみ出しは曲線の膨らみを拾わず通過点だけで測るため検出漏れ側へ
    # 倒れており、拾えた時点で本物。D4/D8 は SR-3-05 / SR-3-06 の明文規則。同じく error。
    #
    # D5 は放射状スポークが正当な語彙である型 (RADIAL_TYPES) を列挙で除外している。
    # 列挙漏れの新タイプで誤検知しうるので warning に留め、除外漏れが判明した
    # 時点で RADIAL_TYPES へ足す運用にする。
    "D5": "warning",
    # D6 は既定オフ。--check-grid で明示的に見るときも、4px からのずれ自体は
    # 誰も気付かない見た目なので報告だけに留める。
    "D6": "warning",
    # D7 は「強調色は 2 件まで」という美的な指針で、3 件目が本当に害かは図による。
    # 生成を止めるほどの確度はない。
    "D7": "warning",
    # D9 は視認性の下限。細い線は「見えない」のであって「読めない」ではなく、
    # 意図的に薄いグリッドを敷く意匠もありうるので warning に留める。
    "D9": "warning",
    # D10 は既存資産にどれだけ palette 外の色が残っているか読めないため warning。
    # テーマ切替で図だけ色が追随しない実害はあるが、生成を止める確度はまだない。
    # 仕上げ前の最終ゲートで落としたいときは --strict で warning ごと失格にできる。
    "D10": "warning",
    # D11 は「読める密度か」の目安であって、上限を 1 超えた図が読めない訳ではない。
    # ノード相当の数え方 (text と重なる rect/circle) も近似なので warning。
    "D11": "warning",
    # D12 は未登録のまま = error。根拠は D8 (SR-3-06) と同一で、外部参照は
    # 「CDN が落ちた瞬間にその図が消える」形で読者に届く。D8 が error なら
    # 同じ根拠の D12 も同格でなければ筋が通らない。
    #
    # D13 は書体差が字幅に直結し、svg-kit の charWidth 近似 (= fitText/wrapText の
    # 収まり計算) の前提を崩す。ただし実害は「1 行の収まりが少しずれる」であり、
    # 図が読めなくなる訳ではないので warning。
    "D13": "warning",
    # --- 第 4 次 update (D-6 検査 owner 表の「D14 系 新設」) --------------------
    # D14-D17 は D0-D13 が素通りしてきた CSS/HTML 構成の図解と、<path> の斜め
    # セグメントを見る。いずれも既存資産にどれだけ違反が眠っているか読めないので
    # warning から運用を始める (D10 を warning で始めたのと同じ理由)。
    # D14 グリッドは D6 と同格。ずれ自体は誰も気付かない見た目である。
    "D14": "warning",
    # D15 は複雑度予算。上限を 1 超えた図が読めなくなる訳ではない (D11 と同格)。
    "D15": "warning",
    # D16 は accent 個数。D7 の CSS 図解版なので severity も D7 に揃える。
    "D16": "warning",
    # D17 は <path> の斜めセグメント。D5 (<line> の斜め) の path 版なので D5 に揃える。
    # 直線セグメントだけを見て曲線・円弧は見ないため検出漏れ側へ倒れている。
    "D17": "warning",
    # --- 第 5 次 update (§D-8 文字量と図解サイズの依存関係) ---------------------
    # D18 は 2 段構えで、ここに載るのは弱い方 (箱への収容) だけである。
    # 「文字を含む最小の <rect> がラベル箱」という近似なので、箱でない矩形を
    # 掴む余地がある。強い方 (viewBox の外へ出た文字 = 確実に切れて読めない) は
    # この表を通さず error 固定で出す。
    "D18": "warning",
    # --- 第 6 次 update (描画の破綻) -------------------------------------------
    # D19/D20 は「線がそこに在るのに読めない」型。値は正しく線も引かれており、
    # 壊れているのは重なりという幾何関係だけである。矩形の辺に沿う線・並走する
    # 線には正当な意匠 (帯の区切り、束ねた表現) もありうるので warning。
    # ゴールデンは --strict で走るため、作例側では実質 error として効く。
    "D19": "warning",
    "D20": "warning",
    # D21 も同型。箱を貫く線は「その箱を経由する」と誤読させるが、内側へ
    # 意図的に線を差し込む語彙 (ハブの中心、注記の引き出し) もありうる。
    "D21": "warning",
    # --- 第 7 次 update (文書スコープの id 衝突) ---------------------------------
    # D22/D23 は SEVERITY へ登録しない = fail-closed の error。理由は
    # ERROR_BY_DESIGN の側に書いてある (D3 と同根拠で「矢じりが消える」)。
}


# SEVERITY へ「意図的に」登録しない検査コード。
#
# _sev() は未登録コードを "error" へ倒す (fail-closed)。この機構が本当に働いて
# いることは、未登録のまま error として運用されている検査が実在して初めて
# 検証される。一方で「未登録」は書き忘れとも区別が付かないため、意図的な
# 未登録をここへ明示して両者を機械的に分ける。
#
# ここに載るコードはいずれも「誤検知の余地がなく、直さないと図が読めない/
# 消える」もので、error 以外の重大度を選ぶ余地がない:
#   D0  SVG として解析できない        (図が 1px も描かれない)
#   D1  viewBox はみ出し              (通過点だけで測るので検出漏れ側。拾えたら本物)
#   D2  NaN/undefined/Infinity 混入   (その属性を持つ図形が消える)
#   D3  marker 参照先が未定義          (矢じりが消える)
#   D4  最小フォント違反              (SR-3-05 の明文規則)
#   D8  Font Awesome PUA              (SR-3-06。CDN 未ロードで文字が全部消える)
#   D12 外部依存                      (D8 と同根拠。CDN が落ちた瞬間に図が消える)
#   D22 id が文書内で重複             (2 枚目以降の参照が 1 枚目へ吸われ矢じりが消える)
#   D23 url(#...) の参照先が他の SVG   (同上。参照が自分の図の外を向いている)
#
# D22/D23 は D3 と同じ「参照が解決しない」型だが、D3 が 1 つの SVG の中しか
# 見ないのに対し、D22 は 1 ファイル (= 1 HTML) の中の SVG どうしを見る。
# スライド HTML は全面の SVG を 1 文書へ同居させるので、同名 id は必ず起きうる。
# ブラウザは url(#x) を「文書内で最初に現れる #x」へ解決し、面の切替が
# visibility:hidden である以上、2 枚目以降の参照先は不可視の marker になる。
# 結果は「線は引かれているのに矢じりだけ消える」で、読んで判断する余地がない。
#
# _sev() の挙動はこの集合を参照しない (SEVERITY.get(code, "error") のまま)。
# ここは宣言であって分岐ではない。分岐にすると fail-closed の既定値が
# 「この表に載っているものだけ error」へ弱まり、新しい検査の書き忘れが
# 再び静かに見逃されるようになる。
ERROR_BY_DESIGN: frozenset[str] = frozenset({
    "D0", "D1", "D2", "D3", "D4", "D8", "D12", "D22", "D23",
})

# D0-D23 の全コード。SEVERITY ∪ ERROR_BY_DESIGN がこれと一致することを
# --self-test が検証する (新しい検査を足したとき、どちらかへの登録を強制する)。
ALL_CODES: frozenset[str] = frozenset(f"D{i}" for i in range(24))


def _sev(code: str) -> str:
    return SEVERITY.get(code, "error")

# `fill="url(#grad-1)"` `clip-path="url(#clip-2)"` `filter="url(#f)"` のような
# 文書内参照。クォートの種類と前後の空白を許して id 部分だけを取る。
_URL_REF_RE = re.compile(r"url\(\s*['\"]?#([^)'\"\s]+)['\"]?\s*\)")
# marker-* の参照は D3 が見る。D23 で重ねて見ると同じ違反が 2 件出る。
_MARKER_ATTRS = frozenset({"marker-end", "marker-start", "marker-mid", "marker"})
# url(#...) 以外の文書内参照。値は id をそのまま (空白区切りで複数) 書く。
# aria-labelledby="title desc" は <title>/<desc> を読み上げ名に使う指定で、
# これも「文書内で最初に現れる #title」へ解決する。絵は変わらないので目視では
# 気付けないが、後ろの図の読み上げが全て先頭の図の説明になる。
_ARIA_IDREF_ATTRS = frozenset({"aria-labelledby", "aria-describedby"})

# SR-3-05: 11px 以下は禁止。12px は小バッジ・軸ラベルのみ許容なので下限は 12。
MIN_FONT_PX = 12
# 線の太さの下限。SVG は必ず縮小されて表示される (viewBox 1080 の図が記事本文幅
# 804px に入れば 0.75 倍) ため、1 未満の線は非 Retina で 1 デバイスピクセルを
# 割ってアンチエイリアスされ、灰色に溶けて見えなくなる。svg-kit.cjs の
# STROKE.hairline と同値にしてあり、片方を変えるならもう片方も変える。
MIN_STROKE_WIDTH = 1.25
# 4px グリッド (SR-5 系)。0.5px 未満のずれは丸め誤差として許す。
GRID = 4
GRID_TOLERANCE = 0.5
# viewBox からのはみ出し許容量。stroke 半幅とマーカーの食い込みぶん。
BLEED_TOLERANCE = 2.0
# 強調色の面塗り上限。焦点が複数あると視線の着地点が散る。
MAX_ACCENT_FILLS = 2
# 放射状スポークや同半径円弧を正当な語彙として持つ図解タイプ。
# class 名か data-slide-type にこれらが現れる SVG では D5 を warning へ落とす。
# 部分一致で見る。"cycle" は slide-diagram-cycle / cycle-svg の双方に当たる。
RADIAL_TYPES = (
    "integration", "dp-integration", "hub-spoke",
    "cycle", "mindmap", "star", "radar", "venn", "concentric",
    "pie", "gauge", "medallion", "scatter", "d3-",
)
# 斜めのコネクタが語彙として正当な型。放射状 (中心からの直線) に加えて、
# データ系列そのものが斜線であるチャート型もここに入る。
CHART_TYPES = (
    "chart", "line-", "area-", "trend", "sparkline", "slope", "waterfall",
)
# D18 の許容。
#   canvas: 文字が viewBox 端をこれだけ超えたら error (境界ぴったりの意匠を殺さない)
#   box   : 箱の左右 pad。fitText の既定 padX=12 より緩く取り、決定論経路が
#           「収まる」と判断した図を検査器が溢れると言わない側へ倒す
#   bg    : viewBox 面積のこの比率以上を占める <rect> は背景板なのでラベル箱でない
TEXT_BLEED_TOLERANCE = 4.0
TEXT_BOX_PAD = 8.0
BACKGROUND_RECT_RATIO = 0.8
# D19/D20 の許容。
#   collinear: これ以下の差は同一直線とみなす (4px グリッドの丸め誤差ぶん)
#   overlap  : 重なりがこの長さ未満なら、端点が辺に着地しただけの正常な接続とみなす。
#              コネクタは必ず箱の辺で終わるので、閾値 0 では全コネクタが引っ掛かる。
COLLINEAR_TOLERANCE = 0.5
MIN_OVERLAP_PX = 12.0
# 強調色として扱うトークン名。既存パレットの語彙だけを見る (新しい色は増やさない)。
ACCENT_TOKENS = ("--sakura-pink", "--surimi-orange", "--peach-red", "accent")
# Font Awesome の Private Use Area。
PUA_RE = re.compile(r"[-]")

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")

# ---------------------------------------------------------------------------
# 素材レイヤ (D10-D13) の正本読み出し
#
# 許可色・許可書体・複雑度上限は vendor/scripts/*.cjs が正本で、ここへ写経すると
# 二重定義になる (パレットを差し替えた日に検査器だけが古い色を許す)。
# lint-contract-drift.py の _load_thresholds と同じく、実装ファイルから
# 正規表現で抽出する。ファイル I/O だけでネットワークには触れない。
# ---------------------------------------------------------------------------
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KIT_REL = os.path.join("vendor", "scripts", "svg-kit.cjs")
_BUILDER_REL = os.path.join("vendor", "scripts", "svg-builder.cjs")

# 抽出に失敗した検査は「見なかったこと」にせず 1 度だけ warning で告げる。
# 検査器が黙って素通りするより、vendor が壊れている事実を出した方がよい。
_SOURCE_WARNED: set[str] = set()

_HEX_RE = re.compile(r"#([0-9A-Fa-f]{3,8})\b")
_RGB_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", re.I)
# 色を載せる属性。style 属性の中の同名宣言も同じ規則で見る。
_COLOR_ATTRS = ("fill", "stroke", "stop-color", "flood-color")
_STYLE_COLOR_RE = re.compile(r"\b(fill|stroke|stop-color|flood-color)\s*:\s*([^;]+)", re.I)
# 色として評価しない値。url(#...) はグラデーション/パターン参照で、
# 参照先の stop-color 側が別途 D10 に掛かるのでここでは素通しする。
_SAFE_COLOR_WORDS = {"", "none", "currentcolor", "transparent", "inherit", "initial", "unset"}
# 総称ファミリ。実体の書体名ではなく「最後の逃げ場」なので常に許可する。
_GENERIC_FAMILIES = {
    "sans-serif", "serif", "monospace", "cursive", "fantasy",
    "system-ui", "ui-sans-serif", "ui-serif", "ui-monospace", "inherit",
}


def _read_source(rel: str) -> str:
    try:
        with open(os.path.join(_PLUGIN_ROOT, rel), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _norm_hex(raw: str) -> str | None:
    """#RGB / #RGBA / #RRGGBB / #RRGGBBAA を小文字 6 桁へ。α は色の同一性に無関係。"""
    h = raw.lower()
    if len(h) in (3, 4):
        return "".join(c * 2 for c in h[:3])
    if len(h) in (6, 8):
        return h[:6]
    return None


_palette_cache: frozenset[str] | None = None


def _allowed_palette() -> frozenset[str]:
    """svg-kit.cjs の TOKENS / SERIES に現れる hex を許可色集合として抽出する。

    TOKENS は `ink: 'var(--fg, #43436c)'` (CSS 変数+フォールバック) と
    `paper: '#FFFFFF'` (リテラル) が混在するので、両ブロック内の hex を
    形にこだわらず全部拾う。NODE_STYLES の rgba(...) は本表の hex を
    そのまま α 付きにしたものなので、rgb 三つ組を hex へ畳めば同じ集合で通る。
    """
    global _palette_cache
    if _palette_cache is not None:
        return _palette_cache
    src = _read_source(_KIT_REL)
    out: set[str] = set()
    for block, close in (("TOKENS", r"\}"), ("SERIES", r"\]")):
        m = re.search(rf"const\s+{block}\s*=\s*[\{{\[](.*?)\n{close};", src, re.S)
        if not m:
            continue
        for raw in _HEX_RE.findall(m.group(1)):
            norm = _norm_hex(raw)
            if norm:
                out.add(norm)
    _palette_cache = frozenset(out)
    return _palette_cache


_families_cache: frozenset[str] | None = None


def _allowed_families() -> frozenset[str]:
    """svg-kit.cjs textBlock の既定フォントスタックを許可書体集合として抽出する。

    書体名を検査器へ書くと、kit 側でスタックを差し替えた瞬間に嘘になる。
    正本は textBlock の `o.family || "..."` の 1 行だけ。
    """
    global _families_cache
    if _families_cache is not None:
        return _families_cache
    src = _read_source(_KIT_REL)
    m = re.search(r"const\s+family\s*=\s*o\.family\s*\|\|\s*\"([^\"]+)\"", src)
    out: set[str] = set()
    if m:
        for part in m.group(1).split(","):
            name = part.strip().strip("'\"").strip().lower()
            if name:
                out.add(name)
    _families_cache = frozenset(out)
    return _families_cache


_charwidth_cache: "tuple[re.Pattern[str], re.Pattern[str], dict[str, float]] | None | bool" = False


def _char_width_model() -> "tuple[re.Pattern[str], re.Pattern[str], dict[str, float]] | None":
    """svg-kit.cjs の charWidth() を字幅モデルとして抽出する (D18 の土台)。

    D18 は「この文字列はこの箱に収まるか」を測る検査だが、その物差しを検査器へ
    書き写すと、決定論ビルダーが収まると判断した図を検査器が溢れると言い出す
    (あるいはその逆) という食い違いが起きる。fitText/wrapText が使うのと同じ
    charWidth を正本にすれば、両者は定義上ずれない。

    抽出できない場合は None を返し、呼出し側は D18 を「検査できない」として
    1 度だけ告げる (黙って素通りしない)。
    """
    global _charwidth_cache
    if _charwidth_cache is not False:
        return _charwidth_cache  # type: ignore[return-value]
    src = _read_source(_KIT_REL)
    body = re.search(r"function charWidth\(ch\)\s*\{(.*?)\n\}", src, re.S)
    full = re.search(r"const\s+RE_FULLWIDTH\s*=\s*\n?\s*/\[(.+?)\]/", src, re.S)
    kana = re.search(r"const\s+RE_HALFWIDTH_KANA\s*=\s*/\[(.+?)\]/", src)
    if not (body and full and kana):
        _charwidth_cache = None
        return None
    b = body.group(1)
    pats = {
        "full": r"RE_FULLWIDTH\.test\(ch\)\)\s*return\s*([\d.]+)",
        "kana": r"RE_HALFWIDTH_KANA\.test\(ch\)\)\s*return\s*([\d.]+)",
        "space": r"ch === ' '\)\s*return\s*([\d.]+)",
        "digit": r"code >= 48 && code <= 57\)\s*return\s*([\d.]+)",
        "upper": r"code >= 65 && code <= 90\)\s*return\s*([\d.]+)",
        "lower": r"code >= 97 && code <= 122\)\s*return\s*([\d.]+)",
        "ascii": r"code < 128\)\s*return\s*([\d.]+)",
    }
    w: dict[str, float] = {}
    for key, pat in pats.items():
        m = re.search(pat, b)
        if not m:
            _charwidth_cache = None
            return None
    for key, pat in pats.items():
        w[key] = float(re.search(pat, b).group(1))  # type: ignore[union-attr]
    tail = re.findall(r"return\s*([\d.]+);", b)
    if not tail:
        _charwidth_cache = None
        return None
    w["other"] = float(tail[-1])
    try:
        _charwidth_cache = (re.compile(f"[{full.group(1)}]"), re.compile(f"[{kana.group(1)}]"), w)
    except re.error:
        _charwidth_cache = None
    return _charwidth_cache  # type: ignore[return-value]


_paper_cache: "str | None | bool" = False


def _paper_token() -> str | None:
    """svg-kit.cjs TOKENS.paper (カード地 = 不透明マスクの色) を抽出する。"""
    global _paper_cache
    if _paper_cache is not False:
        return _paper_cache  # type: ignore[return-value]
    m = re.search(r"const TOKENS\s*=\s*\{.*?\n\s*paper:\s*'([^']+)'", _read_source(_KIT_REL), re.S)
    _paper_cache = m.group(1) if m else None
    return _paper_cache  # type: ignore[return-value]


def _is_label_mask(el: ET.Element, paper: str | None) -> bool:
    """その <rect> が「文字の下に敷く不透明マスク」か (= ラベル箱ではない)。

    arrowLabel のマスクは文字幅 + 12px で作る密着した白地であり、余白を持つ
    ラベル箱ではない。これをラベル箱と取り違えると、正しく描けている図が
    軒並み「箱に収まらない」と言われる (D18 較正で実際に 25 件出た)。
    見分けは「カード地の色で塗られ、輪郭を持たない」こと。
    """
    stroke = (el.get("stroke") or "none").strip().lower()
    if stroke not in ("none", ""):
        return False
    fill = (el.get("fill") or "").strip()
    # paper を読めなかったときは輪郭の有無だけで判断する (マスク側へ倒す)
    return True if paper is None else fill == paper


def _measure_text(s: str, font_size: float, letter_spacing: float = 0.0) -> float | None:
    """文字列の描画幅 (px) を charWidth モデルで推定する。

    letter_spacing は字間の追加分 (px)。SVG の実装差を踏まえ、最後の 1 文字の
    後ろには足さない (過大評価による誤検知を作らないため、控えめな側へ倒す)。
    """
    model = _char_width_model()
    if model is None:
        return None
    re_full, re_kana, w = model
    total = 0.0
    for ch in s:
        if re_full.match(ch):
            total += w["full"]
        elif re_kana.match(ch):
            total += w["kana"]
        elif ch == " ":
            total += w["space"]
        else:
            code = ord(ch)
            if 48 <= code <= 57:
                total += w["digit"]
            elif 65 <= code <= 90:
                total += w["upper"]
            elif 97 <= code <= 122:
                total += w["lower"]
            elif code < 128:
                total += w["ascii"]
            else:
                total += w["other"]
    return total * font_size + max(0, len(s) - 1) * letter_spacing


_capacity_cache: int | None = None


def _capacity_max() -> int:
    """svg-builder.cjs の CAPACITY 表の最大値 (= 決定論経路が 1 枚に載せる最大件数)。"""
    global _capacity_cache
    if _capacity_cache is not None:
        return _capacity_cache
    src = _read_source(_BUILDER_REL)
    m = re.search(r"const\s+CAPACITY\s*=\s*\{(.*?)\n\};", src, re.S)
    vals = [int(v) for _, v in re.findall(r"(build[A-Za-z]+)\s*:\s*(\d+)", m.group(1))] if m else []
    _capacity_cache = max(vals) if vals else 0
    return _capacity_cache


# D11 の上限係数。CAPACITY の最大値 (現状 8 = buildCycle/buildSnake 等) を N として
#   ノード本体      N   … 1 件 = 1 図形
#   ノード付属図形  N   … 番号バッジ・アイコン台座など (buildCycle 実測で 1 ノード 2 図形)
#   コネクタ        N   … 環状フローは 1 ノードにつき 1 本
#   付随ラベル/凡例 N   … タイトル・凡例・注記の箱
# の 4 群に分かれるので上限は 4N。決定論経路の実測最大は buildVs(8+8) の 29 件で、
# 4N=32 はそれを 3 件上回る。つまり「ビルダーで描ける最も密な図」は必ず通り、
# それを超える密度の図 (= LLM が直接書いた過密な図) だけが引っ掛かる。
COMPLEXITY_FACTOR = 4
# 密度が語彙そのものである型 (ガント・年表・マトリクス・散布図・D3 等) の緩和倍率。
# D5 の RADIAL_TYPES と同じ「型申告で例外にする」作法。class / data-slide-type を見る。
COMPLEXITY_RELAX = 1.5
DENSE_TYPES = (
    "gantt", "timeline", "roadmap", "matrix", "swimlane", "table",
    "scatter", "radar", "network", "mindmap", "d3-", "chart-", "calendar",
)


class Finding:
    __slots__ = ("severity", "code", "where", "message")

    def __init__(self, severity: str, code: str, where: str, message: str):
        self.severity = severity
        self.code = code
        self.where = where
        self.message = message

    def __str__(self) -> str:
        return f"{self.severity.upper()} [{self.code}] {self.where}: {self.message}"


def _num(value: object, default: float | None = None) -> float | None:
    """属性値を数値へ。'12px' や '1.5e2' も受ける。NaN/Inf は None にせず返す。"""
    if value is None:
        return default
    match = _NUM_RE.search(str(value))
    if not match:
        return default
    try:
        return float(match.group(0))
    except ValueError:
        return default


def extract_svgs(path: str) -> list[tuple[str, str]]:
    """ファイルから SVG 断片を取り出す。html の場合は複数返る。"""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if path.endswith(".svg"):
        return [(f"{os.path.basename(path)}", text)]
    # <script> / <style> の中身は走査対象から外す。記事 HTML には Mermaid の
    # バンドル JS が丸ごと埋め込まれており、その中の文字列リテラル
    # ("<svg ...>" + e + "</svg>" のような連結片) を図解として拾ってしまう。
    # 中身を同じ長さの空白へ潰し、タグの位置 (= 親 class の探索) を保つ。
    text = re.sub(
        r"(<(script|style)\b[^>]*>)(.*?)(</\2>)",
        lambda m: m.group(1) + (" " * len(m.group(3))) + m.group(4),
        text, flags=re.S | re.I,
    )
    out = []
    base = os.path.basename(path)
    for i, m in enumerate(re.finditer(r"<svg\b.*?</svg>", text, re.S)):
        # 図解タイプは <svg> 自身でなく、それを包む .slider__item / セクションの
        # class に載っている (render-slide.cjs は svg へ class を付けない)。
        # D5 の RADIAL_TYPES 判定は「この図が放射状語彙の型か」を知る必要があるので、
        # 直前の class をラベルとして拾い、名前に含めて判定材料にする。
        # 直前の class は .slider__content のような器のこともある。型を載せているのは
        # slide-<type> / diagram-<type> なので、そちらを優先して最も近いものを取る。
        owner = ""
        for cm in re.finditer(r'class="([^"]*)"', text[: m.start()]):
            for token in cm.group(1).split():
                if token.startswith(("slide-", "diagram-", "chart-")):
                    owner = token
        label = f"{base}#svg{i + 1}"
        if owner:
            label += f"[{owner}]"
        out.append((label, m.group(0)))
    return out


def _viewbox(root: ET.Element) -> tuple[float, float, float, float] | None:
    raw = root.get("viewBox")
    if not raw:
        return None
    parts = [_num(p) for p in raw.replace(",", " ").split()]
    if len(parts) != 4 or any(p is None for p in parts):
        return None
    return tuple(parts)  # type: ignore[return-value]


def _localname(qname: str) -> str:
    """`{http://www.w3.org/2000/svg}rect` のような修飾名から局所名だけ取り出す。"""
    return qname.split("}")[-1]


def _iter(root: ET.Element):
    for el in root.iter():
        yield _localname(el.tag), el


_NUM_TOKEN_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
_CMD_TOKEN_RE = re.compile(r"[A-Za-z]|-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")

# 絶対コマンドごとの (引数個数, 終点 x が始まる添字)。制御点は拾わず終点だけ見る。
# A (円弧) は rx ry rot large sweep x y の 7 引数で、座標は末尾 2 個だけ。
# 素朴に 2 個ずつ刻むと 220 220 が (220,220)、rot/flag が (0,0) と読まれ、
# bbox が実際の弧より大きく出て偽の viewBox はみ出しになる。
_PATH_CMDS = {
    "M": (2, 0),
    "L": (2, 0),
    "T": (2, 0),
    "H": (1, None),
    "V": (1, None),
    "C": (6, 4),
    "S": (4, 2),
    "Q": (4, 2),
    "A": (7, 5),
    "Z": (0, None),
}

# 座標系がローカルな入れ物。marker の d="M0,0 L10,4 L0,8 z" は marker 自身の
# 座標系であって親 SVG の viewBox とは無関係なので、はみ出し判定から外す。
_LOCAL_COORD_TAGS = {"defs", "marker", "symbol", "clipPath", "pattern", "mask"}


def _local_coord_elems(root: ET.Element) -> set[int]:
    """ローカル座標系の入れ物とその子孫の id 集合 (D1 の対象外)。"""
    out: set[int] = set()

    def walk(el: ET.Element, inside: bool) -> None:
        tag = el.tag.split("}")[-1]
        here = inside or tag in _LOCAL_COORD_TAGS
        if here:
            out.add(id(el))
        for child in el:
            walk(child, here)

    walk(root, False)
    return out


def _marker_owner(root: ET.Element) -> dict[int, str]:
    """<marker> の中にある要素 → その marker の id。

    D7 が使う。svg-kit の arrowMarkers は使う色を選ばせず全種類を <defs> へ吐く
    ため、accent 色のマーカー多角形は「図が強調に使ったか」と無関係に必ず 2 件
    現れる。参照されていないマーカーは 1px も描かれないので、これを強調として
    数えると D7 は図の中身ではなく defs の定型文を測ることになる。
    """
    out: dict[int, str] = {}

    def walk(el: ET.Element, owner: str | None) -> None:
        tag = el.tag.split("}")[-1]
        here = el.get("id") if tag == "marker" else owner
        if here:
            out[id(el)] = here
        for child in el:
            walk(child, here)

    walk(root, None)
    return out


def _path_points(d: str) -> list[tuple[float, float]]:
    """絶対コマンドの path から「通過点」を拾う。読めない d は空を返す。"""
    tokens = _CMD_TOKEN_RE.findall(d)
    pts: list[tuple[float, float]] = []
    x = y = 0.0
    i = 0
    cmd = ""
    while i < len(tokens):
        tok = tokens[i]
        if tok.isalpha():
            if tok not in _PATH_CMDS:
                return []  # 相対コマンド等は絶対座標として読めない
            cmd = tok
            i += 1
            if cmd == "Z":
                continue
        if not cmd or cmd == "Z":
            return []
        argc, xi = _PATH_CMDS[cmd]
        args = tokens[i : i + argc]
        if len(args) < argc or any(a.isalpha() for a in args):
            return []
        vals = [float(a) for a in args]
        i += argc
        if cmd == "H":
            x = vals[0]
        elif cmd == "V":
            y = vals[0]
        else:
            x, y = vals[xi], vals[xi + 1]
        pts.append((x, y))
        if cmd == "M":
            cmd = "L"  # 暗黙の後続は L
    return pts


def _bbox(tag: str, el: ET.Element) -> tuple[float, float, float, float] | None:
    """描画要素の概算バウンディングボックス。求まらない要素は None。"""
    if tag == "rect":
        x, y = _num(el.get("x"), 0.0), _num(el.get("y"), 0.0)
        w, h = _num(el.get("width")), _num(el.get("height"))
        if None in (x, y, w, h):
            return None
        return (x, y, x + w, y + h)
    if tag in ("circle", "ellipse"):
        cx, cy = _num(el.get("cx"), 0.0), _num(el.get("cy"), 0.0)
        rx = _num(el.get("r")) if tag == "circle" else _num(el.get("rx"))
        ry = _num(el.get("r")) if tag == "circle" else _num(el.get("ry"))
        if None in (cx, cy, rx, ry):
            return None
        return (cx - rx, cy - ry, cx + rx, cy + ry)
    if tag == "line":
        x1, y1 = _num(el.get("x1")), _num(el.get("y1"))
        x2, y2 = _num(el.get("x2")), _num(el.get("y2"))
        if None in (x1, y1, x2, y2):
            return None
        return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
    if tag in ("polyline", "polygon"):
        nums = [float(t) for t in _NUM_TOKEN_RE.findall(el.get("points") or "")]
        if len(nums) < 4:
            return None
        xs, ys = nums[0::2], nums[1::2]
        return (min(xs), min(ys), max(xs), max(ys))
    if tag == "path":
        # 図の主役 (コネクタ) は path。曲線の膨らみは拾えないが、通過点だけでも
        # 「そもそも canvas の外に置かれている」は捕まる。読めない d は判定しない
        # (相対コマンド等。誤検知を出さない側へ倒す)。
        pts = _path_points(el.get("d") or "")
        if len(pts) < 2:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))
    if tag == "text":
        # 文字送りは実フォント依存だが、全角 1 字 = font-size、半角 = 半分の
        # 概算で十分「viewBox の外へ出た」は捕まる。字形差の精査は実描画側の責務。
        x, y = _num(el.get("x"), 0.0), _num(el.get("y"), 0.0)
        fs = _num(el.get("font-size"), 16.0)
        if None in (x, y) or not fs:
            return None
        body = "".join(el.itertext())
        width = sum(fs if ord(c) > 0x2E80 else fs * 0.5 for c in body)
        anchor = (el.get("text-anchor") or "start").strip()
        if anchor == "middle":
            left = x - width / 2
        elif anchor == "end":
            left = x - width
        else:
            left = x
        # y はベースライン。上に約 0.8em、下に約 0.2em の字面が乗る。
        return (left, y - fs * 0.8, left + width, y + fs * 0.2)
    return None


def _has_nonfinite(el: ET.Element) -> list[str]:
    bad = []
    for key, raw in el.attrib.items():
        low = str(raw).lower()
        if "nan" in low or "undefined" in low or "infinity" in low:
            bad.append(f"{key}={raw!r}")
    return bad


# ---------------------------------------------------------------------------
# D10-D13 の判定部品
#
# D1 が使う _local_coord_elems (defs/marker/symbol/clipPath/pattern/mask の中身)
# は「座標系が親と別物だから幾何を測れない」という理由の除外であって、素材の
# 除外理由ではない。marker の塗りも <pattern> の色もパレット内であるべきだし、
# defs の中に <script> や外部 image を隠されたら同じだけ危ない。よって
# D10-D13 はこの除外リストを使わず SVG 全体を走査する。
# ---------------------------------------------------------------------------


def _color_violation(value: str, palette: frozenset[str]) -> tuple[str, str] | None:
    """色値を判定する。許容なら None、違反なら (種別, 値) を返す。"""
    v = (value or "").strip()
    low = v.lower()
    if low in _SAFE_COLOR_WORDS or low.startswith("url("):
        return None

    hexes = _HEX_RE.findall(v)
    rgbs = [(int(r), int(g), int(b)) for r, g, b in _RGB_RE.findall(v)]

    # 純黒は許可集合に入っていても常に指摘する。OLED では黒が完全消灯して
    # 隣接する面との境界が消え、印刷ではインクが乗り過ぎて細部が潰れる。
    # Kanagawa Lotus の ink (#43436c) を使えば両方とも避けられる。
    for raw in hexes:
        if _norm_hex(raw) == "000000":
            return ("black", v)
    if (0, 0, 0) in rgbs:
        return ("black", v)

    literal = False
    for raw in hexes:
        literal = True
        norm = _norm_hex(raw)
        if norm is None or norm not in palette:
            return ("palette", v)
    for r, g, b in rgbs:
        literal = True
        if f"{r:02x}{g:02x}{b:02x}" not in palette:
            return ("palette", v)

    if literal:
        return None
    if "var(" in low:
        # リテラルを 1 つも含まない var(--x) 参照。解決先はテーマ側の責務。
        return None
    # ここへ来るのは red / rebeccapurple のような名前付き色や未知の記法。
    # 名前付き色は Kanagawa Lotus のどれとも一致しないので落とす。
    return ("palette", v)


def _iter_color_values(el: ET.Element):
    """要素から (属性名, 色値) を取り出す。style 属性内の宣言も同じ規則で見る。"""
    for attr in _COLOR_ATTRS:
        raw = el.get(attr)
        if raw is not None:
            yield attr, raw
    style = el.get("style")
    if style:
        for prop, raw in _STYLE_COLOR_RE.findall(style):
            yield f"style/{prop.lower()}", raw


def _font_family_names(el: ET.Element) -> list[tuple[str, str]]:
    """要素が指定する font-family を (出どころ, 書体名) の一覧へ展開する。"""
    out: list[tuple[str, str]] = []
    raw = el.get("font-family")
    sources = [("font-family", raw)] if raw else []
    style = el.get("style")
    if style:
        m = re.search(r"\bfont-family\s*:\s*([^;]+)", style, re.I)
        if m:
            sources.append(("style/font-family", m.group(1)))
    for where, stack in sources:
        for part in (stack or "").split(","):
            name = part.strip().strip("'\"").strip()
            if name:
                out.append((where, name))
    return out


def _count_diagram_elements(root: ET.Element) -> tuple[int, int]:
    """(ラベル付きノード相当の数, コネクタの数) を数える。

    ノード相当は「文字を伴う図形」= 読者が 1 つの意味の塊として読む単位。
      - <text> を直接の子に持つ <g> (kit の nodeRect 等が作る形)
      - 上で数えた <g> の外にあり、文字の中心を 1-2 個含む rect / circle
    地のカードや背景パネルも文字と重なるが、それらは中に文字を 3 つ以上抱える
    ので 1-2 個という上限で落ちる。ノードは自分のラベル (+補足 1 行) しか
    抱えないという経験則を使っている。
    """
    centers: list[tuple[float, float]] = []
    for tag, el in _iter(root):
        if tag == "text":
            box = _bbox("text", el)
            if box:
                centers.append(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2))

    consumed: set[int] = set()
    nodes = 0
    for tag, el in _iter(root):
        if tag != "g":
            continue
        if any(child.tag.split("}")[-1] == "text" for child in el):
            nodes += 1
            for desc in el.iter():
                consumed.add(id(desc))

    for tag, el in _iter(root):
        if tag not in ("rect", "circle") or id(el) in consumed:
            continue
        box = _bbox(tag, el)
        if not box:
            continue
        inside = sum(1 for cx, cy in centers
                     if box[0] <= cx <= box[2] and box[1] <= cy <= box[3])
        if 1 <= inside <= 2:
            nodes += 1

    connectors = 0
    for tag, el in _iter(root):
        if tag in ("path", "line") and (el.get("marker-end") or el.get("marker-start")):
            connectors += 1
    return nodes, connectors


# D12: SVG 断片の中だけを見る。HTML 全体の外部依存 (CDN の <script> 等) は
# validate-report-visual.py / build-*.js 側の責務で、ここで見ると二重報告になる。
_D12_SCRIPT_RE = re.compile(r"<\s*script\b", re.I)
_D12_LINK_RE = re.compile(r"<\s*link\b[^>]*>", re.I)
_D12_IMPORT_RE = re.compile(r"@import\s+[^;]*", re.I)
_D12_URL_RE = re.compile(r"url\(\s*['\"]?\s*(?:https?:)?//[^)'\"]*", re.I)
# href / src が外部を指しているか。プロトコル相対 (//cdn...) も外部。
_D12_EXTERNAL_VALUE_RE = re.compile(r"^\s*(?:https?:)?//", re.I)
# 外部を「読み込む」属性だけを見る。<a href="https://..."> は資源の取得では
# なく単なるリンクで、CDN が落ちても図は消えないため対象外。
# <script> / <link> は上のタグ検出で必ず 1 件出るので、ここへ入れると二重報告になる。
_D12_LOADER_TAGS = {"image", "use", "feImage", "textPath", "filter", "pattern", "mask"}


def _check_external_refs(name: str, svg_text: str, root: ET.Element) -> list[Finding]:
    """D12: SVG 断片内の外部依存を検出する。

    Google Fonts 等の例外は設けない。SR-3-06 が FontAwesome の PUA を禁じる
    理由 (CDN 未ロードでアイコンが全部消える) は外部フォントにもそのまま
    当てはまり、図の文字が意図と違う書体で描かれれば収まり計算ごと崩れる。

    注意: HTML 入力では extract_svgs が <style> の中身を空白へ潰しているので、
    SVG 内 <style> の @import は .svg 直接入力のときだけ拾える。潰さないと
    Mermaid のバンドル JS を図解として拾ってしまうため、この取りこぼしは受け入れる。
    """
    out: list[Finding] = []
    if _D12_SCRIPT_RE.search(svg_text):
        out.append(Finding(
            _sev("D12"), "D12", name,
            "SVG 内に <script> がある。図解は静的な描画だけで完結させる "
            "(スクリプトは埋め込み先の CSP や sanitizer で落ちて図が壊れる)"))
    for m in _D12_LINK_RE.finditer(svg_text):
        out.append(Finding(
            _sev("D12"), "D12", name,
            f"SVG 内に外部リソースの読み込み {m.group(0)[:80]} がある。"
            "外部フォント・外部スタイルは読み込まれなかった瞬間に図が別物になる (SR-3-06 と同根拠)"))
    for m in _D12_IMPORT_RE.finditer(svg_text):
        if _D12_URL_RE.search(m.group(0)):
            out.append(Finding(
                _sev("D12"), "D12", name,
                f"SVG 内に外部 @import がある: {m.group(0)[:80]}"))
    for tag, el in _iter(root):
        if tag not in _D12_LOADER_TAGS:
            continue
        for key, raw in el.attrib.items():
            if key.split("}")[-1] not in ("href", "src"):
                continue
            if _D12_EXTERNAL_VALUE_RE.match(str(raw)):
                out.append(Finding(
                    _sev("D12"), "D12", name,
                    f"<{tag}> が外部を参照している ({key.split('}')[-1]}={raw!r})。"
                    "画像・アイコンは SVG 内へ埋め込むか、生成側で取り込む"))
    # style 属性・presentation 属性に紛れた url(http...) (filter や mask の外部参照)。
    for m in _D12_URL_RE.finditer(svg_text):
        if _D12_IMPORT_RE.search(svg_text[max(0, m.start() - 40):m.start()]):
            continue  # @import として上で報告済み
        out.append(Finding(
            _sev("D12"), "D12", name,
            f"SVG 内に外部 URL 参照がある: {m.group(0)[:80]}"))
    return out


# ---------------------------------------------------------------------------
# 第 4 次 update: 作図文法の数値契約 (D14-D17)
#
# D0-D13 は <svg> だけを抽出して検査するので、CSS/HTML で組んだ図解
# (.slider__item[data-v8-diagram] 配下の div/span による箱と矢印) は 1 件も
# 検査に掛からないまま素通りしていた。決定論経路は render-slide.cjs の
# テンプレートに守られるが、agent が HTML を直接書く経路には何の防具も無い。
#
# 閾値は全て実装 / 契約文書から実行時に読む (SR-15-11 と同じ作法):
#   - グリッド刻み        vendor/scripts/svg-kit.cjs の GRID
#   - CSS の間隔スケール  vendor/scripts/style-builder.cjs の SPEC.spacing
#   - 複雑度予算 21 項目  references/diagram-layout-contract.md §D-2 の表
#   - accent の色         vendor/scripts/svg-kit.cjs の TOKENS.accent / accentTint
# 抽出に失敗した検査は黙って素通りさせず、1 度だけ warning で「検査できない」と告げる。
# ---------------------------------------------------------------------------
_CONTRACT_REL = os.path.join("references", "diagram-layout-contract.md")
_STYLE_REL = os.path.join("vendor", "scripts", "style-builder.cjs")

_grid_cache: float | None = None


def _grid_step() -> float:
    """svg-kit.cjs の GRID (4px グリッドの刻み幅・SR-5 系の正本)。"""
    global _grid_cache
    if _grid_cache is not None:
        return _grid_cache
    m = re.search(r"^const\s+GRID\s*=\s*([0-9.]+)", _read_source(_KIT_REL), re.M)
    _grid_cache = float(m.group(1)) if m else 0.0
    return _grid_cache


_space_cache: tuple[str, ...] | None = None


def _space_scale() -> tuple[str, ...]:
    """style-builder.cjs の SPEC.spacing 9 段 (--space-1 … --space-9 の実値)。"""
    global _space_cache
    if _space_cache is not None:
        return _space_cache
    m = re.search(r"spacing\s*:\s*\[([^\]]*)\]", _read_source(_STYLE_REL))
    vals = tuple(v.strip().strip("'\"") for v in m.group(1).split(",") if v.strip()) if m else ()
    _space_cache = vals
    return _space_cache


_budget_cache: dict[int, int] | None = None


def _complexity_budget() -> dict[int, int]:
    """diagram-layout-contract.md §D-2 の複雑度予算表を {項番: 上限} で読む。

    表は `| # | 対象 | 上限 | 超えたときの正しい対処 |` の 4 列。第 4 次 update 章が
    この値の正本 (既存実装のどこにも定義が無い新規の値) なので、検査器へ写経せず
    毎回ここから読む。表の形が変わったら空 dict になり、D15 は検査できないと告げる。
    """
    global _budget_cache
    if _budget_cache is not None:
        return _budget_cache
    text = _read_source(_CONTRACT_REL)
    m = re.search(r"\n##\s*D-2\..*?(?=\n##\s|\Z)", text, re.S)
    out: dict[int, int] = {}
    if m:
        for row in re.finditer(r"^\|\s*(\d+)\s*\|[^|]+\|\s*(\d+)\s*\|", m.group(0), re.M):
            out[int(row.group(1))] = int(row.group(2))
    _budget_cache = out
    return _budget_cache


# §D-2 の項番。番号で参照すると読めないので名前を付ける (値は持たない)。
_BUDGET_NODES = 1
_BUDGET_CONNECTORS = 2
_BUDGET_ACCENT = 3
_BUDGET_ANNOTATION = 4
_BUDGET_LEGEND = 20
_BUDGET_FONT_STEPS = 21

_accent_cache: tuple[str, ...] | None = None


def _accent_signatures() -> tuple[str, ...]:
    """TOKENS.accent / accentTint が名乗る文字列 (CSS 変数名・hex・rgb 三つ組)。

    CSS 図解の accent は `style="border-color: var(--sakura-pink, #D27E99)"` のように
    書かれるので、色の同一性ではなく「その色を名指す綴り」の集合で数える。
    """
    global _accent_cache
    if _accent_cache is not None:
        return _accent_cache
    src = _read_source(_KIT_REL)
    sigs: set[str] = set()
    for key in ("accent", "accentTint"):
        m = re.search(rf"^\s*{key}\s*:\s*'([^']+)'", src, re.M)
        if not m:
            continue
        raw = m.group(1)
        for var in re.findall(r"(--[a-z0-9-]+)", raw):
            sigs.add(var)
        for hx in _HEX_RE.findall(raw):
            norm = _norm_hex(hx)
            if norm:
                sigs.add(f"#{norm}")
        for r, g, b in _RGB_RE.findall(raw):
            sigs.add(f"{r},{g},{b}")
    _accent_cache = tuple(sorted(sigs))
    return _accent_cache


# --- CSS/HTML 図解ブロックの検出規約 (diagram-layout-contract.md §D-7) --------
# 決定論経路 render-slide.cjs は図解スライドの .slider__item へ
# data-v8-diagram="<variant>" を付ける。これが最も確実な標識。
# LLM 手書き経路はこの属性を付けないことがあるので、図解語彙の class 接頭辞も見る。
_BLOCK_MARK_ATTR = "data-v8-diagram"
_BLOCK_CLASS_PREFIXES = ("diagram-", "slide-diagram-", "chart-", "d3-")
_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
_OPEN_TAG_RE = re.compile(r"<([a-zA-Z][a-zA-Z0-9-]*)((?:\"[^\"]*\"|'[^']*'|[^>])*?)(/?)>", re.S)
_CLOSE_TAG_RE = re.compile(r"</([a-zA-Z][a-zA-Z0-9-]*)\s*>", re.S)
_ANY_TAG_RE = re.compile(
    r"</?([a-zA-Z][a-zA-Z0-9-]*)((?:\"[^\"]*\"|'[^']*'|[^>])*?)(/?)>", re.S)


def _attr(attrs: str, name: str) -> str | None:
    m = re.search(rf'\b{name}\s*=\s*"([^"]*)"', attrs, re.I)
    if m:
        return m.group(1)
    m = re.search(rf"\b{name}\s*=\s*'([^']*)'", attrs, re.I)
    return m.group(1) if m else None


def _is_block_root(tag: str, attrs: str) -> bool:
    if re.search(rf"\b{_BLOCK_MARK_ATTR}\b", attrs, re.I):
        return True
    for token in (_attr(attrs, "class") or "").split():
        if token.startswith(_BLOCK_CLASS_PREFIXES):
            return True
    return False


def _block_end(text: str, tag: str, start: int) -> int:
    """開始タグ直後の位置 start から、対応する閉じタグの終端を返す (深さ勘定)。"""
    depth = 1
    pos = start
    while depth > 0:
        m = _ANY_TAG_RE.search(text, pos)
        if not m:
            return len(text)
        pos = m.end()
        if m.group(1).lower() != tag:
            continue
        if m.group(0).startswith("</"):
            depth -= 1
        elif not m.group(3) and m.group(1).lower() not in _VOID_TAGS:
            depth += 1
    return pos


def extract_diagram_blocks(path: str) -> list[tuple[str, str]]:
    """HTML から CSS/HTML 構成の図解ブロックを取り出す ((ラベル, 断片) の一覧)。

    <svg> しか持たないブロックは D0-D13 が既に見ているので返さない。
    入れ子 (図解ブロックの中の .diagram-legend 等) は外側 1 件だけを図解として数える。
    """
    if not path.endswith((".html", ".htm")):
        return []
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    # extract_svgs と同じ理由で <script>/<style> の中身を潰す (長さは保つ)。
    text = re.sub(
        r"(<(script|style)\b[^>]*>)(.*?)(</\2>)",
        lambda m: m.group(1) + (" " * len(m.group(3))) + m.group(4),
        text, flags=re.S | re.I,
    )
    base = os.path.basename(path)
    out: list[tuple[str, str]] = []
    pos = 0
    n = 0
    while True:
        m = _OPEN_TAG_RE.search(text, pos)
        if not m:
            break
        tag, attrs, selfclose = m.group(1).lower(), m.group(2), m.group(3)
        if tag in ("script", "style") or selfclose or tag in _VOID_TAGS:
            pos = m.end()
            continue
        if not _is_block_root(tag, attrs):
            pos = m.end()
            continue
        end = _block_end(text, tag, m.end())
        body = text[m.start():end]
        # SVG だけで組まれた図解は D0-D13 の担当。CSS/HTML の器が無いものは返さない。
        # 判定は器の中身に対して行う (根の開始タグ自身を数えると全ブロックが該当する)。
        stripped = re.sub(r"<svg\b.*?</svg>", "", text[m.end():end], flags=re.S | re.I)
        if re.search(r"<(div|span|p|ul|ol|li|table|figure|section)\b", stripped, re.I):
            n += 1
            variant = _attr(attrs, _BLOCK_MARK_ATTR) or (_attr(attrs, "class") or "").split()
            label = f"{base}#block{n}"
            if isinstance(variant, str) and variant:
                label += f"[{variant}]"
            out.append((label, body))
        pos = end  # 入れ子の図解語彙は外側 1 件に畳む
    return out


# D14: グリッドを課す幾何プロパティと、--space-* から取るべき間隔プロパティ。
# 線幅・不透明度・フォントは §D-1「グリッドの適用外」により対象外。
_GEOM_PROPS = (
    "width", "height", "min-width", "min-height", "max-width", "max-height",
    "top", "right", "bottom", "left", "border-radius",
)
_SPACING_PROPS = (
    "gap", "row-gap", "column-gap", "margin", "margin-top", "margin-right",
    "margin-bottom", "margin-left", "padding", "padding-top", "padding-right",
    "padding-bottom", "padding-left",
)
_DECL_RE = re.compile(r"([a-z-]+)\s*:\s*([^;\"']+)")
_LEN_RE = re.compile(r"(-?[0-9.]+)(px|rem|em|vw|vh|%)")
# 角丸の許可 3 段は §D-1 の表が正本だが、D14 は「grid の倍数か」までを見る
# (3 段のうちどれか、までは踏み込まない。6 は GRID の倍数でないため)。


def _iter_style_decls(block: str):
    """図解ブロック内の style 属性から (要素の抜粋, プロパティ, 値) を列挙する。"""
    for m in re.finditer(r"<[a-zA-Z][^>]*>", block, re.S):
        style = _attr(m.group(0), "style")
        if not style:
            continue
        for prop, val in _DECL_RE.findall(style):
            yield m.group(0)[:60], prop.lower(), val.strip()


def _check_css_grid(name: str, block: str) -> list[Finding]:
    """D14: CSS 図解の間隔・寸法が刻みの上にあるか (§D-1)。

    §D-1 の「CSS 側」節に従い、間隔は px グリッドではなく `--space-*` 9 段で読み替える
    (slide の html は font-size:1vw なので rem は画面幅に比例し、px グリッドという
    概念自体が成立しない)。寸法に px を直書きした場合だけ GRID の倍数を課す。
    """
    out: list[Finding] = []
    grid = _grid_step()
    steps = len(_space_scale())
    seen: set[str] = set()
    for where, prop, val in _iter_style_decls(block):
        key = f"{prop}:{val}"
        if key in seen:
            continue
        if prop in _SPACING_PROPS:
            if "var(--space-" in val:
                for idx in re.findall(r"var\(\s*--space-(\d+)", val):
                    if steps and not (1 <= int(idx) <= steps):
                        seen.add(key)
                        out.append(Finding(
                            _sev("D14"), "D14", name,
                            f"{prop}: var(--space-{idx}) が spacing スケール 1-{steps} 段の外 "
                            f"(style-builder.cjs SPEC.spacing が正本)"))
                continue
            if _LEN_RE.search(val) and not val.strip().startswith("0"):
                seen.add(key)
                out.append(Finding(
                    _sev("D14"), "D14", name,
                    f"{prop}: {val!r} が間隔値の直書き ({where}…)。"
                    f"CSS 図解の間隔は --space-1 … --space-{steps or 9} から選ぶ "
                    "(§D-1: 新しい間隔段を作らないことがグリッドの読み替え)"))
            continue
        if prop in _GEOM_PROPS and grid:
            for num, unit in _LEN_RE.findall(val):
                if unit != "px":
                    continue
                v = abs(float(num))
                if v and abs(v - round(v / grid) * grid) > GRID_TOLERANCE:
                    seen.add(key)
                    out.append(Finding(
                        _sev("D14"), "D14", name,
                        f"{prop}: {val!r} が {grid:g}px グリッド上にない ({where}…)"))
    return out


def _count_class(block: str, token: str) -> int:
    """class 属性に token を丸ごと 1 語として持つ要素の数。"""
    n = 0
    for m in re.finditer(r"<[a-zA-Z][^>]*>", block, re.S):
        if token in (_attr(m.group(0), "class") or "").split():
            n += 1
    return n


def _count_class_prefix(block: str, *needles: str) -> int:
    n = 0
    for m in re.finditer(r"<[a-zA-Z][^>]*>", block, re.S):
        tokens = (_attr(m.group(0), "class") or "").split()
        if any(nd in t for t in tokens for nd in needles):
            n += 1
    return n


def _check_budget(name: str, block: str) -> list[Finding]:
    """D15: 複雑度予算 (§D-2) のうち機械で数えられる項目。

    §D-2 の owner 表が D14 系へ割り当てたのは #4 (annotation)・#20 (凡例)・
    #21 (フォント階層) と型別上限で、#1/#2 は D11 が SVG 側で見ている。
    CSS 図解には D11 が効かないので #1/#2 も class 語彙から近似して数える。
    """
    out: list[Finding] = []
    budget = _complexity_budget()
    if not budget:
        return out

    def over(item: int, count: int, label: str, advice: str) -> None:
        cap = budget.get(item)
        if cap is not None and count > cap:
            out.append(Finding(
                _sev("D15"), "D15", name,
                f"{label}が {count} 件で §D-2 #{item} の上限 {cap} 件を超えている。{advice}"))

    over(_BUDGET_ANNOTATION, _count_class(block, "diagram-annotation"),
         "注釈 (.diagram-annotation)", "3 つ目の注釈が要るなら、それは本文へ書く内容 (§D-5)")
    over(_BUDGET_LEGEND, _count_class(block, "diagram-legend__item"),
         "凡例項目", "種別が多すぎる。NODE_STYLES の使用種別を減らす")
    over(_BUDGET_NODES, _count_class_prefix(block, "node", "card", "step", "box"),
         "ノード相当", "9 ノードを超えたら、それはたいてい 2 枚の図である")
    over(_BUDGET_CONNECTORS, _count_class_prefix(block, "arrow", "connector", "link"),
         "コネクタ相当", "配置で分かる関係に線は要らない")

    sizes = {val for _, prop, val in _iter_style_decls(block) if prop == "font-size"}
    sizes |= set(re.findall(r'font-size="([^"]+)"', block))
    over(_BUDGET_FONT_STEPS, len(sizes),
         "フォントサイズの階層", "見出し / ラベル / 副ラベル / 注記の 4 段で足りる")
    return out


def _check_css_accent(name: str, block: str) -> list[Finding]:
    """D16: CSS 図解の accent 出現要素数 (§D-2 #3・D7 の CSS 版)。"""
    sigs = _accent_signatures()
    budget = _complexity_budget().get(_BUDGET_ACCENT)
    if not sigs or budget is None:
        return []
    hits = 0
    for m in re.finditer(r"<[a-zA-Z][^>]*>", block, re.S):
        tag = m.group(0)
        # hex は綴りの大小を問わない (#D27E99 と #d27e99 は同じ色)。
        blob = " ".join(filter(None, (
            _attr(tag, "style"), _attr(tag, "fill"), _attr(tag, "stroke"), _attr(tag, "class")))).lower()
        if any(sig in blob for sig in sigs):
            hits += 1
    if hits > budget:
        return [Finding(
            _sev("D16"), "D16", name,
            f"accent ロールの色を持つ要素が {hits} 件で上限 {budget} 件を超えている "
            f"(accent の綴り: {', '.join(sigs)})。"
            "主張が複数ある状態で、視線の着地点が定まらない (§D-2 #3 / style-tokens §3)")]
    return []


# D17: <path> の直線セグメントだけを見る。C/S/Q/T は曲線、A は円弧で、いずれも
# §D-3 原則 1 が語彙として認めている (bridge 弧・昇格弧・放射状)。斜めの直線だけが
# 「配置が間違っている」の兆候なので、そこへ絞る (検出漏れ側へ倒す)。
_LINEAR_CMDS = {"M", "L", "H", "V"}


def _path_line_segments(d: str) -> list[tuple[float, float, float, float]]:
    """絶対コマンド path から直線セグメント (x1,y1,x2,y2) を取り出す。"""
    tokens = _CMD_TOKEN_RE.findall(d)
    segs: list[tuple[float, float, float, float]] = []
    x = y = 0.0
    started = False
    i = 0
    cmd = ""
    while i < len(tokens):
        tok = tokens[i]
        if tok.isalpha():
            if tok not in _PATH_CMDS:
                return []  # 相対コマンド等は絶対座標として読めない
            cmd = tok
            i += 1
            if cmd == "Z":
                continue
        if not cmd or cmd == "Z":
            return []
        argc, xi = _PATH_CMDS[cmd]
        args = tokens[i:i + argc]
        if len(args) < argc or any(a.isalpha() for a in args):
            return []
        vals = [float(a) for a in args]
        i += argc
        px, py = x, y
        if cmd == "H":
            x = vals[0]
        elif cmd == "V":
            y = vals[0]
        else:
            x, y = vals[xi], vals[xi + 1]
        if cmd in _LINEAR_CMDS and started and cmd != "M":
            segs.append((px, py, x, y))
        if cmd == "M":
            started = True
            cmd = "L"  # 暗黙の後続は L
    return segs


def _connector_segments(tag: str, el: ET.Element) -> list[tuple[float, float, float, float]]:
    """D5 が見る「コネクタの直線セグメント」を (x1,y1,x2,y2) の列で返す。

    <polyline>/<polygon> は**矢じりを持つものだけ**を対象にする。塞ぎたい
    抜け道は「ノード間を結ぶコネクタを <line> の連なりでなく polyline で書けば
    D5 を通り抜けられる」であり、コネクタは本プラグインの語彙では必ず
    marker-* を持つ (kit.connector は arrowUrl を必ず付ける)。

    一方、矢じりのない polyline/polygon は折れ線チャートの系列・レーダーの
    輪郭・ジャーニーマップの感情推移・三角形や矢羽根といった**データ線と図形**
    である。これらの斜めは §D-3 原則 1 が禁じている対象ではない (原則 1 が
    禁じるのはノード間のコネクタの斜めであって、量や気分の推移を形にした線や、
    図形そのものの輪郭ではない)。型申告ではなく要素の形で見分けるので、
    型名を列挙し漏らしても誤検知しない。

    polygon の閉じ辺 (末尾→先頭) は見ない。コネクタとして polygon を使う
    書き方に閉じ辺の意味は無く、見れば矢羽根や三角形の輪郭を誤って拾うだけ。
    """
    if tag == "line":
        return [(
            _num(el.get("x1"), 0.0) or 0.0, _num(el.get("y1"), 0.0) or 0.0,
            _num(el.get("x2"), 0.0) or 0.0, _num(el.get("y2"), 0.0) or 0.0,
        )]
    if not any(el.get(a) for a in ("marker-end", "marker-start", "marker-mid")):
        return []
    nums = [float(v) for v in _NUM_RE.findall(el.get("points") or "")]
    pts = list(zip(nums[0::2], nums[1::2]))
    return [(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]) for i in range(len(pts) - 1)]


def _transformed_elems(root: ET.Element) -> set[int]:
    """transform を持つ要素とその子孫の id 集合 (D18 の対象外)。

    回転・拡大が掛かった座標系では属性値から実際の描画位置を測れない。
    測れないものを測ったふりをすると誤検知になるので、素直に見送る。
    """
    out: set[int] = set()

    def walk(el: ET.Element, inside: bool) -> None:
        here = inside or bool(el.get("transform"))
        if here:
            out.add(id(el))
        for child in el:
            walk(child, here)

    walk(root, False)
    return out


def _text_runs(el: ET.Element) -> list[tuple[float, float, str]]:
    """<text> を「行」の列 (x, baseline y, 文字列) へ分解する。

    svg-kit の textBlock は 1 行 = 1 <tspan x dy> で書き出すので、行ごとに
    独立した水平範囲を持つ。<text> 直下の地の文も 1 行として扱う。
    """
    base_x = _num(el.get("x"), 0.0) or 0.0
    base_y = _num(el.get("y"), 0.0) or 0.0
    runs: list[tuple[float, float, str]] = []
    head = (el.text or "").strip()
    if head:
        runs.append((base_x, base_y, head))
    cur_y = base_y
    for child in el:
        if child.tag.split("}")[-1] != "tspan":
            continue
        cx = _num(child.get("x"), base_x) or 0.0
        cy = _num(child.get("y"))
        cur_y = cy if cy is not None else cur_y + (_num(child.get("dy"), 0.0) or 0.0)
        content = (child.text or "").strip()
        if content:
            runs.append((cx, cur_y, content))
        tail = (child.tail or "").strip()
        if tail:
            runs.append((base_x, cur_y, tail))
    return runs


def _letter_spacing_px(value: str | None, font_size: float) -> float:
    """letter-spacing 属性を px へ。em 指定は font-size 基準で換算する。"""
    v = (value or "").strip()
    if not v:
        return 0.0
    m = re.match(r"^(-?[\d.]+)(em|px|)$", v)
    if not m:
        return 0.0
    n = float(m.group(1))
    return n * font_size if m.group(2) == "em" else n


def _check_text_fit(
    name: str, root: ET.Element, vb: tuple[float, float, float, float] | None,
    local_coord: set[int],
) -> list[Finding]:
    """D18: 文字が canvas と箱に収まるか (§D-8 文字量と図解サイズの依存関係)。

    2 段構え。
      canvas 収容 (error)   viewBox の外へ出た文字は確実に切れて読めない。
      箱への収容 (warning)  文字を含む最小の <rect> をラベル箱と見なす近似なので、
                            箱でない矩形を掴む余地がある分だけ確度を落とす。

    物差しは _char_width_model (= svg-kit の charWidth)。決定論経路の fitText は
    padX=12 で内寸を取るので、ここを TEXT_BOX_PAD=8 に緩めておけば
    「ビルダーが収まると判断した図」は構造的に通る。
    """
    out: list[Finding] = []
    if _char_width_model() is None:
        if "charwidth" not in _SOURCE_WARNED:
            _SOURCE_WARNED.add("charwidth")
            out.append(Finding(
                _sev("D18"), "D18", name,
                f"{_KIT_REL} の charWidth を抽出できないため D18 を検査できない"))
        return out

    transformed = _transformed_elems(root)
    # ラベル箱の候補。背景板 (viewBox の大半を覆う矩形) は箱ではない
    vb_area = (vb[2] * vb[3]) if vb else 0.0
    paper = _paper_token()
    boxes: list[tuple[float, float, float, float]] = []
    for tag, el in _iter(root):
        if tag != "rect" or id(el) in local_coord or id(el) in transformed:
            continue
        if _is_label_mask(el, paper):
            continue
        x, y = _num(el.get("x"), 0.0), _num(el.get("y"), 0.0)
        w, h = _num(el.get("width")), _num(el.get("height"))
        if w is None or h is None or w <= 0 or h <= 0:
            continue
        if vb_area and w * h >= BACKGROUND_RECT_RATIO * vb_area:
            continue
        boxes.append((x or 0.0, y or 0.0, w, h))

    for tag, el in _iter(root):
        if tag != "text" or id(el) in local_coord or id(el) in transformed:
            continue
        fs = _num(el.get("font-size"))
        if fs is None or fs <= 0:
            continue
        anchor = (el.get("text-anchor") or "start").strip()
        ls = _letter_spacing_px(el.get("letter-spacing"), fs)
        for x, y, content in _text_runs(el):
            w = _measure_text(content, fs, ls)
            if w is None or w <= 0:
                continue
            if anchor == "middle":
                x0, x1 = x - w / 2, x + w / 2
            elif anchor == "end":
                x0, x1 = x - w, x
            else:
                x0, x1 = x, x + w
            # baseline から上へアセンダ、下へディセンダ
            y0, y1 = y - fs * 0.85, y + fs * 0.25

            if vb:
                vx, vy, vw, vh = vb
                over = []
                if x0 < vx - TEXT_BLEED_TOLERANCE:
                    over.append(f"左へ {vx - x0:.0f}px")
                if x1 > vx + vw + TEXT_BLEED_TOLERANCE:
                    over.append(f"右へ {x1 - (vx + vw):.0f}px")
                if y0 < vy - TEXT_BLEED_TOLERANCE:
                    over.append(f"上へ {vy - y0:.0f}px")
                if y1 > vy + vh + TEXT_BLEED_TOLERANCE:
                    over.append(f"下へ {y1 - (vy + vh):.0f}px")
                if over:
                    out.append(Finding(
                        "error", "D18", name,
                        f"「{_ellipsis(content)}」({fs:g}px) が viewBox の外へ出る"
                        f" ({' / '.join(over)})。文字を削るか canvas を 1 段大きくする"))
                    continue

            # アンカー点 (baseline の起点) を含む最小の矩形をラベル箱と見なす
            owner = None
            for bx, by, bw, bh in boxes:
                if not (bx <= x <= bx + bw and by - fs <= y <= by + bh + fs):
                    continue
                if owner is None or bw * bh < owner[2] * owner[3]:
                    owner = (bx, by, bw, bh)
            if owner is None:
                continue
            inner = owner[2] - TEXT_BOX_PAD * 2
            if w > inner:
                need = int(max(1, inner // fs))
                out.append(Finding(
                    _sev("D18"), "D18", name,
                    f"「{_ellipsis(content)}」({fs:g}px・推定 {w:.0f}px) が"
                    f" 幅 {owner[2]:g}px の箱に収まらない (内寸 {inner:g}px)。"
                    f"この箱に置ける全角は約 {need} 文字。"
                    "ラベルを短くするか箱を広げる (font-size を 12px 未満にはしない)"))
    return out


def _ellipsis(s: str, limit: int = 18) -> str:
    return s if len(s) <= limit else s[:limit] + "…"


def _check_diagonal_paths(name: str, root: ET.Element, diagonal_ok: bool) -> list[Finding]:
    """D17: コネクタ <path> に斜めの直線セグメントが無いか (§D-3 原則 1)。"""
    out: list[Finding] = []
    # 放射状スポークとチャートのデータ線は §D-3 例外 (a) が明示的に認めた語彙。
    # 契約が正しいと言っているものを毎回 warning で読ませると、本当の逸脱が
    # その中に埋もれる。黙る。
    if diagonal_ok:
        return out
    for tag, el in _iter(root):
        if tag != "path":
            continue
        # コネクタ (矢じり付き、または塗り無しの線) だけを見る。面塗りの path は図形。
        is_connector = bool(el.get("marker-end") or el.get("marker-start")) or (
            (el.get("fill") or "none").strip().lower() == "none" and el.get("stroke"))
        if not is_connector:
            continue
        for x1, y1, x2, y2 in _path_line_segments(el.get("d") or ""):
            if abs(x1 - x2) > 1.0 and abs(y1 - y2) > 1.0:
                out.append(Finding(
                    _sev("D17"), "D17", name,
                    f"斜めの <path> セグメント ({x1:.0f},{y1:.0f})→({x2:.0f},{y2:.0f})。"
                    "経路は軸平行のセグメントと角丸だけで作る。斜め線が要ると感じたら、"
                    "直すのは線の形ではなくノードの配置 (§D-3 原則 1)"))
                break  # 1 本の path につき 1 件で足りる
    return out


# ---------------------------------------------------------------------------
# D19/D20 描画の破綻
#
# D0-D18 は「必要な情報が載っているか」「座標が規約通りか」を見る。どちらも
# 通るのに描かれた結果だけが壊れる欠陥が実在した (2026/8, high-level 図):
#   (a) 分岐の横走りが宛先 <rect> の上辺と同一直線上を走り、線が枠へ溶けた
#   (b) 同じ段の間を走る複数本が全部同じ高さで折れ、重なった区間で 2 本が 1 本に見えた
# どちらも値は正しく、線も引かれている。壊れているのは**要素間の重なり**という
# 関係だけで、要素を 1 つずつ見る検査では原理的に捕まらない。
# ---------------------------------------------------------------------------


def _connector_axis_segments(
    root: ET.Element, skip: set[int]
) -> list[tuple[str, float, float, float, int, str]]:
    """コネクタの軸平行セグメントを (軸, 定数座標, 区間始, 区間終, 所有要素 id, 説明) で返す。

    斜めセグメントは D5/D17 の担当なので見ない。<line>/<polyline> は矢じりを
    持つものだけを対象にする (根拠は _connector_segments と同じ。矢じりの無い
    直線は区切り罫やデータ線であって、辺に沿わせる意匠が正当にありうる)。
    """
    out: list[tuple[str, float, float, float, int, str]] = []
    for tag, el in _iter(root):
        if id(el) in skip:
            continue
        if tag == "path":
            is_connector = bool(el.get("marker-end") or el.get("marker-start")) or (
                (el.get("fill") or "none").strip().lower() == "none" and el.get("stroke"))
            if not is_connector:
                continue
            segs = _path_line_segments(el.get("d") or "")
        elif tag in ("line", "polyline"):
            if not any(el.get(a) for a in ("marker-end", "marker-start", "marker-mid")):
                continue
            segs = _connector_segments(tag, el)
        else:
            continue
        for x1, y1, x2, y2 in segs:
            dx, dy = abs(x1 - x2), abs(y1 - y2)
            if dy <= COLLINEAR_TOLERANCE and dx > COLLINEAR_TOLERANCE:
                out.append(("h", (y1 + y2) / 2, min(x1, x2), max(x1, x2), id(el),
                            f"({x1:.0f},{y1:.0f})→({x2:.0f},{y2:.0f})"))
            elif dx <= COLLINEAR_TOLERANCE and dy > COLLINEAR_TOLERANCE:
                out.append(("v", (x1 + x2) / 2, min(y1, y2), max(y1, y2), id(el),
                            f"({x1:.0f},{y1:.0f})→({x2:.0f},{y2:.0f})"))
    return out


def _stroked_rects(
    root: ET.Element, vb: tuple[float, float, float, float] | None, skip: set[int]
) -> list[tuple[float, float, float, float]]:
    """枠線を持つ <rect> を (x, y, w, h) で返す。

    枠線の無い矩形は溶ける辺を持たないので対象外。背景板 (viewBox 面積の
    BACKGROUND_RECT_RATIO 以上) も外す。帯の縁に沿って線を走らせるのは
    レーン図などで正当な語彙であり、そこを咎めると誤検知しか生まない。
    """
    area = (vb[2] * vb[3]) if vb else 0.0
    out: list[tuple[float, float, float, float]] = []
    for tag, el in _iter(root):
        if tag != "rect" or id(el) in skip:
            continue
        if (el.get("stroke") or "none").strip().lower() in ("", "none"):
            continue
        x = _num(el.get("x"), 0.0) or 0.0
        y = _num(el.get("y"), 0.0) or 0.0
        w = _num(el.get("width"))
        h = _num(el.get("height"))
        if not w or not h or w <= 0 or h <= 0:
            continue
        if area and w * h >= area * BACKGROUND_RECT_RATIO:
            continue
        out.append((x, y, w, h))
    return out


def _all_rects(
    root: ET.Element, vb: tuple[float, float, float, float] | None, skip: set[int]
) -> list[tuple[float, float, float, float]]:
    """枠線の有無を問わない全 <rect>。包含関係の判定材料としてだけ使う。"""
    area = (vb[2] * vb[3]) if vb else 0.0
    out: list[tuple[float, float, float, float]] = []
    for tag, el in _iter(root):
        if tag != "rect" or id(el) in skip:
            continue
        x = _num(el.get("x"), 0.0) or 0.0
        y = _num(el.get("y"), 0.0) or 0.0
        w = _num(el.get("width"))
        h = _num(el.get("height"))
        if not w or not h or w <= 0 or h <= 0:
            continue
        if area and w * h >= area * BACKGROUND_RECT_RATIO:
            continue
        out.append((x, y, w, h))
    return out


def _overlap(a1: float, a2: float, b1: float, b2: float) -> float:
    return min(a2, b2) - max(a1, b1)


def _leaf_rects(
    rects: list[tuple[float, float, float, float]],
    inner: list[tuple[float, float, float, float]] | None = None,
) -> list[tuple[float, float, float, float]]:
    """他の矩形を内包しない矩形だけを返す。

    レーン帯・グループ枠・章の囲みは「容れ物」であって節点ではない。容れ物を
    線が横切るのは正当な語彙 (レーンをまたぐ受け渡し、層の境界を越える依存) で、
    そこを咎めると検出のほとんどが誤検知になる。面積比の閾値では帯と節点を
    分けられない (細長い帯は面積が小さい) ため、包含関係で見る。
    """
    # 内包の判定材料は枠線の有無を問わない全矩形にする。帯の中身が塗りだけで
    # 描かれている図 (ガントのバー等) では、枠線付きだけを見ると帯が葉に見える。
    pool = rects if inner is None else inner
    out = []
    for a in rects:
        ax, ay, aw, ah = a
        contains = any(
            b[2] * b[3] < aw * ah - 0.5  # 同一矩形・同寸の重ね描きは内包でない
            and ax - 0.5 <= b[0] and ay - 0.5 <= b[1]
            and b[0] + b[2] <= ax + aw + 0.5 and b[1] + b[3] <= ay + ah + 0.5
            for b in pool
        )
        if not contains:
            out.append(a)
    return out


def _check_connector_on_box_edge(
    name: str, root: ET.Element, vb: tuple[float, float, float, float] | None,
    skip: set[int],
) -> list[Finding]:
    """D19: コネクタの直線区間が箱の辺と同一直線上を走っていないか。

    辺と重なった線は枠に溶けて消える。矢じりだけが箱の横に残るので、読者には
    「どこから来た矢印か分からない矢じり」として届く。端点が辺へ着地する
    正常な接続と区別するため、重なりの長さが MIN_OVERLAP_PX 以上のときだけ言う。
    """
    out: list[Finding] = []
    rects = _stroked_rects(root, vb, skip)
    if not rects:
        return out
    for axis, c, lo, hi, _owner, where in _connector_axis_segments(root, skip):
        for rx, ry, rw, rh in rects:
            if axis == "h":
                edges, span = (ry, ry + rh), (rx, rx + rw)
            else:
                edges, span = (rx, rx + rw), (ry, ry + rh)
            for edge in edges:
                if abs(c - edge) > COLLINEAR_TOLERANCE:
                    continue
                ov = _overlap(lo, hi, span[0], span[1])
                if ov < MIN_OVERLAP_PX:
                    continue
                out.append(Finding(
                    _sev("D19"), "D19", name,
                    f"コネクタの直線区間 {where} が <rect> "
                    f"({rx:.0f},{ry:.0f},{rw:.0f}x{rh:.0f}) の辺と同一直線上を "
                    f"{ov:.0f}px 重なって走っている。線が枠に溶けて消え、矢じりだけが残る。"
                    "経路を箱の外側へ逃がすか、折れ点を辺から離す"))
                return out  # 1 図につき 1 件で足りる (直せば連鎖して消える)
    return out


def _check_overlapping_connectors(
    name: str, root: ET.Element, skip: set[int]
) -> list[Finding]:
    """D20: 別々のコネクタの直線区間が同一直線上で重なっていないか。

    重なった区間は 1 本にしか見えない。線が消える訳ではないので図は「描けて」
    いるが、読者は本数を数え違える (依存が 3 本あるのに 2 本に見える)。
    同じ要素内の区間どうしは対象外 (1 本の経路が自分自身と重なるのは
    折り返しの意匠で、別の話)。
    """
    segs = _connector_axis_segments(root, skip)
    for i in range(len(segs)):
        axis_i, c_i, lo_i, hi_i, own_i, where_i = segs[i]
        for j in range(i + 1, len(segs)):
            axis_j, c_j, lo_j, hi_j, own_j, where_j = segs[j]
            if axis_i != axis_j or own_i == own_j:
                continue
            if abs(c_i - c_j) > COLLINEAR_TOLERANCE:
                continue
            ov = _overlap(lo_i, hi_i, lo_j, hi_j)
            if ov < MIN_OVERLAP_PX:
                continue
            return [Finding(
                _sev("D20"), "D20", name,
                f"別々のコネクタの直線区間 {where_i} と {where_j} が同一直線上で "
                f"{ov:.0f}px 重なっている。重なった区間は 1 本にしか見えないため、"
                "読者は線の本数を数え違える。折れ点の位置を線ごとにずらして"
                "レーンを分ける")]
    return []


def _check_connector_through_box(
    name: str, root: ET.Element, vb: tuple[float, float, float, float] | None,
    skip: set[int],
) -> list[Finding]:
    """D21: コネクタの直線区間が箱の内側を貫いていないか。

    貫かれた箱は「その線がここを経由する」と読まれる。実際には無関係な線が
    たまたま重なっているだけなので、読者は無い経路を 1 本読み取る。
    辺と同一直線上の重なりは D19 の担当なので、内側へ 1px 入った範囲だけを見る。
    """
    out: list[Finding] = []
    rects = _leaf_rects(_stroked_rects(root, vb, skip), _all_rects(root, vb, skip))
    if not rects:
        return out
    inset = 1.0
    for axis, c, lo, hi, _owner, where in _connector_axis_segments(root, skip):
        for rx, ry, rw, rh in rects:
            if axis == "h":
                near, far, span = ry, ry + rh, (rx, rx + rw)
            else:
                near, far, span = rx, rx + rw, (ry, ry + rh)
            if not (near + inset < c < far - inset):
                continue
            ov = _overlap(lo, hi, span[0], span[1])
            if ov < MIN_OVERLAP_PX:
                continue
            out.append(Finding(
                _sev("D21"), "D21", name,
                f"コネクタの直線区間 {where} が <rect> "
                f"({rx:.0f},{ry:.0f},{rw:.0f}x{rh:.0f}) の内側を {ov:.0f}px 貫いている。"
                "無関係な箱を経由しているように読まれる。"
                "間に箱がある区間は迂回させるか、ノードの並び順を変える"))
            return out  # 1 図につき 1 件で足りる
    return out


def check_diagram_block(name: str, block: str) -> list[Finding]:
    """CSS/HTML 構成の図解ブロックへ D14-D16 を当てる。"""
    findings: list[Finding] = []
    if not _grid_step() and "grid" not in _SOURCE_WARNED:
        _SOURCE_WARNED.add("grid")
        findings.append(Finding(
            _sev("D14"), "D14", name,
            f"{_KIT_REL} の GRID を抽出できないため D14 の寸法検査ができない"))
    if not _space_scale() and "spacing" not in _SOURCE_WARNED:
        _SOURCE_WARNED.add("spacing")
        findings.append(Finding(
            _sev("D14"), "D14", name,
            f"{_STYLE_REL} の SPEC.spacing を抽出できないため D14 の間隔検査ができない"))
    if not _complexity_budget() and "budget" not in _SOURCE_WARNED:
        _SOURCE_WARNED.add("budget")
        findings.append(Finding(
            _sev("D15"), "D15", name,
            f"{_CONTRACT_REL} §D-2 の複雑度予算表を抽出できないため D15/D16 を検査できない"))
    findings.extend(_check_css_grid(name, block))
    findings.extend(_check_budget(name, block))
    findings.extend(_check_css_accent(name, block))
    return findings


def check_svg(name: str, svg_text: str, check_grid: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        return [Finding(_sev("D0"), "D0", name, f"SVG としてパースできない ({exc})")]

    vb = _viewbox(root)
    if vb is None:
        findings.append(Finding(_sev("D1"), "D1", name, "viewBox が無いか不正 (SR-1-02)"))
    # 型名は SVG 本文にあるとは限らない (HTML 埋め込みでは親の class 側にある)。
    # extract_svgs が name へ載せた owner class も一緒に見る。
    haystack = f"{name} {svg_text}"
    # 斜めが語彙として正当な型 (放射状スポーク / チャートのデータ線) をまとめて判定
    diagonal_ok = any(t in haystack for t in RADIAL_TYPES + CHART_TYPES)

    local_coord = _local_coord_elems(root)
    marker_owner = _marker_owner(root)
    defined_markers: set[str] = set()
    referenced_markers: set[str] = set()
    accent_fills = 0
    # marker 内の accent は「そのマーカーが参照されたか」が走査を終えるまで確定
    # しないので、marker id 別に貯めておいて最後に合流させる
    marker_accents: dict[str, int] = {}

    palette = _allowed_palette()
    families = _allowed_families()
    # 同じ色・同じ書体が 100 箇所に出ても、直す作業は 1 回。値ごとに 1 件へ畳む。
    seen_colors: set[str] = set()
    seen_families: set[str] = set()
    if not palette and "palette" not in _SOURCE_WARNED:
        _SOURCE_WARNED.add("palette")
        findings.append(Finding(
            _sev("D10"), "D10", name,
            f"{_KIT_REL} の TOKENS/SERIES から許可色を抽出できないため D10 を検査できない"))
    if not families and "families" not in _SOURCE_WARNED:
        _SOURCE_WARNED.add("families")
        findings.append(Finding(
            _sev("D13"), "D13", name,
            f"{_KIT_REL} の textBlock から既定フォントスタックを抽出できないため D13 を検査できない"))

    for tag, el in _iter(root):
        if tag == "marker":
            mid = el.get("id")
            if mid:
                defined_markers.add(mid)
        for attr in ("marker-end", "marker-start", "marker-mid"):
            ref = el.get(attr)
            if ref:
                m = re.search(r"url\(#([^)]+)\)", ref)
                if m:
                    referenced_markers.add(m.group(1))

        # D2 数値健全性
        bad = _has_nonfinite(el)
        if bad:
            findings.append(Finding(_sev("D2"), "D2", name, f"<{tag}> に不正な数値: {', '.join(bad)}"))

        # D1 viewBox 収容 (ローカル座標系の入れ物の中は対象外)
        box = None if id(el) in local_coord else _bbox(tag, el)
        if vb and box:
            vx, vy, vw, vh = vb
            x1, y1, x2, y2 = box
            if (x1 < vx - BLEED_TOLERANCE or y1 < vy - BLEED_TOLERANCE
                    or x2 > vx + vw + BLEED_TOLERANCE or y2 > vy + vh + BLEED_TOLERANCE):
                findings.append(Finding(
                    _sev("D1"), "D1", name,
                    f"<{tag}> が viewBox の外にはみ出している "
                    f"(要素 {x1:.1f},{y1:.1f}〜{x2:.1f},{y2:.1f} / viewBox {vx},{vy},{vw},{vh})"))

        # D4 最小フォント
        fs = _num(el.get("font-size"))
        if fs is not None and fs < MIN_FONT_PX:
            findings.append(Finding(
                _sev("D4"), "D4", name,
                f"<{tag}> の font-size={fs:g}px が下限 {MIN_FONT_PX}px 未満 (SR-3-05)"))

        # D9 線の太さ
        sw = _num(el.get("stroke-width"))
        # stroke-width=0 は「線を引かない」の表明 (filledStyle など) なので対象外。
        # 塗りだけの図形に太さの下限を課しても意味がない。
        if sw is not None and 0 < sw < MIN_STROKE_WIDTH:
            findings.append(Finding(
                _sev("D9"), "D9", name,
                f"<{tag}> の stroke-width={sw:g} が下限 {MIN_STROKE_WIDTH} 未満。"
                "縮小表示・印刷で灰色に溶けて見えなくなる (svg-kit の STROKE トークンを使う)"))

        # D5 斜めコネクタ。放射状スポークとチャートのデータ線は §D-3 例外 (a) の
        # 対象なので黙る。<polyline>/<polygon> も見るのは、同じ折れ線を <line> の
        # 連なりで書けば指摘され polyline で書けば通る、という抜け道を塞ぐため。
        if tag in ("line", "polyline", "polygon") and not diagonal_ok:
            for x1, y1, x2, y2 in _connector_segments(tag, el):
                if abs(x1 - x2) > 1.0 and abs(y1 - y2) > 1.0:
                    findings.append(Finding(
                        _sev("D5"), "D5", name,
                        f"斜めの <{tag}> ({x1:.0f},{y1:.0f})→({x2:.0f},{y2:.0f})。"
                        "コネクタは直交エルボか同半径円弧にする"))
                    break  # 1 要素につき 1 件で足りる

        # D6 4px グリッド (既定オフ: 件数が多く他の指摘を埋めるため)
        if check_grid and tag == "rect":
            for key in ("x", "y", "width", "height"):
                v = _num(el.get(key))
                if v is None:
                    continue
                off = abs(v - round(v / GRID) * GRID)
                if off > GRID_TOLERANCE:
                    findings.append(Finding(
                        _sev("D6"), "D6", name,
                        f"<rect {key}={v:g}> が {GRID}px グリッド上にない (ずれ {off:.2f}px)"))

        # D7 accent 抑制
        fill = el.get("fill") or ""
        if tag in ("rect", "circle", "ellipse", "path", "polygon") and fill not in ("none", ""):
            if any(tok in fill for tok in ACCENT_TOKENS):
                owner = marker_owner.get(id(el))
                if owner is None:
                    accent_fills += 1
                else:
                    marker_accents[owner] = marker_accents.get(owner, 0) + 1

        # D10 パレット逸脱 (defs/marker の中も見る。マーカーの色もパレット内であるべき)
        if palette:
            for attr, raw in _iter_color_values(el):
                hit = _color_violation(raw, palette)
                if not hit:
                    continue
                kind, value = hit
                key = f"{kind}:{value.lower()}"
                if key in seen_colors:
                    continue
                seen_colors.add(key)
                if kind == "black":
                    findings.append(Finding(
                        _sev("D10"), "D10", name,
                        f"{attr}={value!r} が純黒。OLED では面が完全に消灯して境界が失われ、"
                        "印刷ではインクが乗り過ぎて潰れる。ink (var(--fg, ...)) を使う"))
                else:
                    findings.append(Finding(
                        _sev("D10"), "D10", name,
                        f"{attr}={value!r} が palette 外 (SR-2-02/2-08)。"
                        "色は svg-kit の TOKENS/SERIES から取り、var(--x, #fallback) 形式で書く。"
                        "直書きの色はテーマ切替でその図だけ追随しない"))

        # D13 font-family ホワイトリスト (D4 と同じ走査ループへ相乗り)
        if families:
            for where, fam in _font_family_names(el):
                low = fam.lower()
                if low in families or low in _GENERIC_FAMILIES:
                    continue
                if low in seen_families:
                    continue
                seen_families.add(low)
                findings.append(Finding(
                    _sev("D13"), "D13", name,
                    f"{where} の {fam!r} が許可外 (SR-3-01)。"
                    f"許可は {', '.join(sorted(families))} と総称ファミリのみ。"
                    "書体が変わると字幅が変わり、svg-kit の charWidth 近似を前提にした "
                    "fitText/wrapText の収まり計算がそのまま外れる"))

        # D8 FA unicode
        if tag == "text" or tag == "tspan":
            if el.text and PUA_RE.search(el.text):
                findings.append(Finding(
                    _sev("D8"), "D8", name,
                    "<text> 内に Font Awesome の PUA コードがある (SR-3-06)。"
                    "アイコンは foreignObject 側へ置く"))

    # D3 marker 解決
    for ref in sorted(referenced_markers - defined_markers):
        findings.append(Finding(
            _sev("D3"), "D3", name,
            f"marker '#{ref}' が参照されているが同じ SVG 内で定義されていない"))

    # D7 判定 (図単位)。実際に marker-start/mid/end から参照された marker の中身
    # だけを数に入れる (定義されただけのマーカーは描画されないので強調ではない)
    accent_fills += sum(n for mid, n in marker_accents.items() if mid in referenced_markers)
    if accent_fills > MAX_ACCENT_FILLS:
        findings.append(Finding(
            _sev("D7"), "D7", name,
            f"強調色の面塗りが {accent_fills} 件。{MAX_ACCENT_FILLS} 件以下に抑えると"
            "視線の着地点がひとつに定まる"))

    # D11 成果物側の複雑度上限 (図単位)。
    # CAPACITY はビルダー関数の入口に効く上限で、agent が SVG を直接書く経路には
    # 一切効かない。同じ上限を成果物側でも見ることで両経路の採点を揃える。
    cap = _capacity_max()
    if cap:
        limit = cap * COMPLEXITY_FACTOR
        dense_ok = any(t in haystack for t in DENSE_TYPES)
        if dense_ok:
            limit = int(limit * COMPLEXITY_RELAX)
        nodes, connectors = _count_diagram_elements(root)
        total = nodes + connectors
        if total > limit:
            findings.append(Finding(
                _sev("D11"), "D11", name,
                f"要素が {total} 件 (ノード相当 {nodes} + コネクタ {connectors}) で上限 {limit} 件を超えている。"
                f"決定論経路の 1 枚あたり上限は CAPACITY 最大 {cap} 件で、その 4 倍 "
                f"(本体/付属図形/コネクタ/凡例) を成果物側の上限に置いている。"
                "figure を分けるか、まとめられる階層を 1 段落とす"
                + ("（密度が語彙である型のため上限を緩めた上での超過）" if dense_ok else "")))
    elif "capacity" not in _SOURCE_WARNED:
        _SOURCE_WARNED.add("capacity")
        findings.append(Finding(
            _sev("D11"), "D11", name,
            f"{_BUILDER_REL} の CAPACITY を抽出できないため D11 を検査できない"))

    # D12 外部依存 (走査範囲は extract_svgs が返した SVG 断片の中だけ)
    findings.extend(_check_external_refs(name, svg_text, root))

    # D17 <path> の斜めセグメント (§D-3 原則 1。D5 が見る <line> の path 版)
    findings.extend(_check_diagonal_paths(name, root, diagonal_ok))

    # D18 文字収容 (§D-8)
    findings.extend(_check_text_fit(name, root, vb, local_coord))

    # D19/D20 描画の破綻。座標をそのまま読めない要素 (transform 下・入れ子座標系)
    # は測れないので見送る。測れないものを測ったふりをすると誤検知になる。
    unmeasurable = local_coord | _transformed_elems(root)
    findings.extend(_check_connector_on_box_edge(name, root, vb, unmeasurable))
    findings.extend(_check_overlapping_connectors(name, root, unmeasurable))
    findings.extend(_check_connector_through_box(name, root, vb, unmeasurable))

    # D15 のうち SVG で数えられる 2 項目。
    # #4 annotation は §D-5 が「注釈は font-base のイタリック」と定めているので、
    # font-style="italic" の <text> 数がそのまま注釈数になる。
    # #21 フォント階層は font-size の種類数。
    budget = _complexity_budget()
    if budget:
        italics = 0
        sizes: set[str] = set()
        for tag, el in _iter(root):
            style = el.get("style") or ""
            if tag in ("text", "tspan"):
                if (el.get("font-style") or "").strip() == "italic" or "italic" in style:
                    italics += 1
            fs = el.get("font-size")
            if fs:
                sizes.add(str(fs).strip())
        for item, count, label, advice in (
            (_BUDGET_ANNOTATION, italics, "注釈 (font-style=italic の <text>)",
             "3 つ目の注釈が要るなら、それは本文へ書く内容 (§D-5)"),
            (_BUDGET_FONT_STEPS, len(sizes), "フォントサイズの階層",
             "見出し / ラベル / 副ラベル / 注記の 4 段で足りる"),
        ):
            cap = budget.get(item)
            if cap is not None and count > cap:
                findings.append(Finding(
                    _sev("D15"), "D15", name,
                    f"{label}が {count} 件で §D-2 #{item} の上限 {cap} 件を超えている。{advice}"))

    return findings


def _is_shared_defs_svg(root: ET.Element) -> bool:
    """描画物を持たない「共有 defs 置き場」の SVG か。

    <svg width="0" height="0" style="position:absolute"><defs>…</defs></svg> の
    形で全面ぶんの gradient / filter を 1 箇所へ置く書き方は、既存デッキで
    実際に使われている正当な設計。この SVG は自分では何も描かないので面の
    切替 (visibility:hidden) の影響を受けず、どの面から参照しても定義は
    生きている。ここへの参照を D23 で咎めると誤検出になる。

    判定は「defs / style / title / desc / metadata 以外の子要素を持たない」。
    描画要素が 1 つでもあれば、それは面の一部なので共有置き場とは呼ばない。
    """
    ignorable = {"defs", "style", "title", "desc", "metadata"}
    for child in root:
        if _localname(child.tag) not in ignorable:
            return False
    return True


def check_document(label: str, svgs: list[tuple[str, str]]) -> list[Finding]:
    """D22 / D23: 1 ファイルに同居する SVG 全体で見ないと分からない違反 (SR-15-20)。

    check_svg は 1 つの SVG しか見ないので、この 2 つは原理的に捕まらない。
    スライド HTML は全面の SVG を 1 文書へ同居させ、各面のビルダーは自分の
    defs を「その図の中では一意」な名前 (arrow-blue 等) で書く。個々の SVG
    としては正しく、D3 も通る。それでもブラウザは url(#arrow-blue) を
    「文書内で最初に現れる #arrow-blue」へ解決するため、2 枚目以降の面の参照は
    1 枚目の marker を指す。面の切替が visibility:hidden である以上、その
    marker は隠れており、線は引かれているのに矢じりだけが描かれない。

    重複が起きるのは marker に限らない。clipPath / linearGradient / filter /
    pattern / mask など url(#...) で参照される定義は全て同じ罠を踏むので、
    検査対象は id 全般にする。arrow- 接頭辞へ絞ると、次に別の defs が
    増えた日にまた素通りする。

    D22 は「同名 id が 2 箇所以上で定義されている」。同じ id が 1 つの SVG の
    中で 2 度出る場合も同じ表で拾う (そもそも不正)。
    D23 は「参照先が自分の SVG にも共有 defs にも無い」。参照先が
    別の面の SVG にしか無い場合と、どこにも無い場合の 2 通りを区別して出す。
    marker-* の参照は D3 の担当なので、同じ違反を 2 度出さないよう除く。

    参照は url(#...) だけではない。aria-labelledby / aria-describedby /
    href="#..." は id をそのまま書く形の参照で、これも文書内で最初に現れる
    id へ解決する。絵が変わらないぶん目視で気付けないので検査に含める。
    ただしこの形の参照は SVG の外の要素 (見出し等) を指すことが正当にあり、
    この関数は SVG しか受け取らないためその定義を見られない。よって
    「別の SVG にしかない」時だけ出し、「どこにも無い」時は黙る。
    """
    findings: list[Finding] = []
    # id -> その id を定義している SVG 名の一覧 (同じ SVG 内の重複も件数で残す)
    owners: dict[str, list[str]] = {}
    # SVG 名 -> (自分が定義した id 集合, 参照した id -> 参照箇所の説明)
    local_defs: dict[str, set[str]] = {}
    local_refs: dict[str, dict[str, str]] = {}
    # id をそのまま書く参照 (aria-labelledby / href="#id")。url(#...) と違い
    # 「SVG の外の h2 や figcaption を指す」正当な使い方があり、check_document
    # は SVG しか受け取らないのでその定義を見られない。よって「どこにも無い」
    # では鳴らさず、「別の SVG にしかない」時だけ鳴らす (下の emission を参照)。
    idref_refs: dict[str, dict[str, str]] = {}
    shared_ids: set[str] = set()
    for name, svg_text in svgs:
        try:
            root = ET.fromstring(svg_text)
        except ET.ParseError:
            continue  # パース不能は D0 の担当。ここでは黙って飛ばす
        defined: set[str] = set()
        refs: dict[str, str] = {}
        idrefs: dict[str, str] = {}
        for tag, el in _iter(root):
            eid = el.get("id")
            if eid:
                owners.setdefault(eid, []).append(name)
                defined.add(eid)
            for attr, value in el.attrib.items():
                lname = _localname(attr)
                if lname in _MARKER_ATTRS:
                    continue  # D3 の担当
                if lname in _ARIA_IDREF_ATTRS:
                    for token in str(value).split():
                        idrefs.setdefault(token, f"<{tag}> の {lname}")
                    continue
                if lname == "href" and str(value).startswith("#"):
                    idrefs.setdefault(str(value)[1:], f"<{tag}> の {lname}")
                    continue
                for m in _URL_REF_RE.finditer(str(value)):
                    refs.setdefault(m.group(1), f"<{tag}> の {lname}")
            if tag == "style" and el.text:
                for m in _URL_REF_RE.finditer(el.text):
                    refs.setdefault(m.group(1), "<style> の中")
        local_defs[name] = defined
        local_refs[name] = refs
        idref_refs[name] = idrefs
        if _is_shared_defs_svg(root):
            shared_ids |= defined
    for eid in sorted(owners):
        places = owners[eid]
        if len(places) < 2:
            continue
        where = ", ".join(sorted(set(places)))
        findings.append(Finding(
            _sev("D22"), "D22", label,
            f"id '#{eid}' が {len(places)} 回定義されている ({where})。"
            "1 つの文書に同名 id があると url(#...) は最初の定義へ解決され、"
            "後の面の参照が別の面 (= 隠れている面) を指す。"
            "面ごとに接尾辞を付けて一意にする (SR-15-20)"))
    for name, refs in local_refs.items():
        for ref in sorted(set(refs) - local_defs.get(name, set()) - shared_ids):
            elsewhere = sorted(set(owners.get(ref, [])))
            if elsewhere:
                detail = (f"参照先は {', '.join(elsewhere)} にしかない。"
                          "その面が隠れている間は参照した側も描かれない")
            else:
                detail = "参照先がこのファイルのどこにも無い"
            findings.append(Finding(
                _sev("D23"), "D23", name,
                f"'#{ref}' が {refs[ref]} から参照されているが同じ SVG 内で定義されていない。"
                f"{detail} (SR-15-20)"))
    for name, idrefs in idref_refs.items():
        for ref in sorted(set(idrefs) - local_defs.get(name, set()) - shared_ids):
            elsewhere = sorted(set(owners.get(ref, [])))
            if not elsewhere:
                continue  # SVG の外の要素を指している可能性がある。ここでは判断しない
            findings.append(Finding(
                _sev("D23"), "D23", name,
                f"'#{ref}' が {idrefs[ref]} から参照されているが同じ SVG 内で定義されていない。"
                f"参照先は {', '.join(elsewhere)} にしかなく、別の図の要素を指す (SR-15-20)"))
    return findings


# ---------------------------------------------------------------------------
# 自己テスト (--self-test)
#
# D18 は「既存ゴールデンで誤検知 0」だけを基準に較正すると、何も検出しない
# 検査でも満点が取れてしまう (緩めすぎの罠)。意図的に溢れさせた図を必ず
# 捕まえることを、較正と同じ場所で固定する。
# ---------------------------------------------------------------------------
_SELF_TEST_CASES: tuple[tuple[str, str, tuple[tuple[str, str], ...], tuple[str, ...]], ...] = (
    (
        "箱に収まる短いラベル",
        '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="40" y="60" width="200" height="60" fill="#FFFFFF" stroke="#43436c"/>'
        '<text x="140" y="95" text-anchor="middle" font-size="16">受注登録</text></svg>',
        (),
        ("D18",),
    ),
    (
        "箱幅 100px に全角 20 文字 (canvas には収まる位置)",
        '<svg viewBox="0 0 600 200" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="250" y="60" width="100" height="60" fill="#FFFFFF" stroke="#43436c"/>'
        '<text x="300" y="95" text-anchor="middle" font-size="16">'
        '受注から請求までを一気通貫で処理する仕組み</text></svg>',
        (("warning", "D18"),),
        (),
    ),
    (
        "viewBox の右外へ出る文字",
        '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
        '<text x="360" y="100" text-anchor="start" font-size="16">'
        '右端からはみ出す長いラベル</text></svg>',
        (("error", "D18"),),
        (),
    ),
    (
        "矢じり付き polyline の斜め (コネクタの抜け道)",
        '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
        '<defs><marker id="a"><path d="M0 0"/></marker></defs>'
        '<polyline points="40,40 200,160" fill="none" stroke="#43436c"'
        ' marker-end="url(#a)"/></svg>',
        (("warning", "D5"),),
        (),
    ),
    (
        "矢じり付き polygon の斜め (コネクタの抜け道)",
        '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
        '<defs><marker id="a"><path d="M0 0"/></marker></defs>'
        '<polygon points="40,40 200,160" fill="none" stroke="#43436c"'
        ' marker-end="url(#a)"/></svg>',
        (("warning", "D5"),),
        (),
    ),
    (
        "矢じり無し polygon の斜辺 (レーダー輪郭・三角形なので対象外)",
        '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
        '<polygon points="200,40 340,160 60,160" fill="none" stroke="#43436c"/></svg>',
        (),
        ("D5",),
    ),
    (
        "矢じり無し polyline の斜め (データ線なので対象外)",
        '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
        '<polyline points="40,40 200,160" fill="none" stroke="#43436c"/></svg>',
        (),
        ("D5",),
    ),
    (
        "チャート型申告下の斜め line",
        '<svg class="chart-line" viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
        '<line x1="40" y1="40" x2="200" y2="160" stroke="#43436c"/></svg>',
        (),
        ("D5",),
    ),
    (
        "分岐の横走りが宛先の上辺と同一直線 (線が枠へ溶ける)",
        '<svg viewBox="0 0 400 300" xmlns="http://www.w3.org/2000/svg">'
        '<defs><marker id="a"><path d="M0 0"/></marker></defs>'
        '<rect x="60" y="200" width="160" height="60" fill="#FFFFFF" stroke="#43436c"/>'
        '<path d="M300,80 V200 H140 V200" fill="none" stroke="#43436c"'
        ' marker-end="url(#a)"/></svg>',
        (("warning", "D19"),),
        (),
    ),
    (
        "横走りを段間に逃がした正しい経路",
        '<svg viewBox="0 0 400 300" xmlns="http://www.w3.org/2000/svg">'
        '<defs><marker id="a"><path d="M0 0"/></marker></defs>'
        '<rect x="60" y="200" width="160" height="60" fill="#FFFFFF" stroke="#43436c"/>'
        '<path d="M300,80 V160 H140 V200" fill="none" stroke="#43436c"'
        ' marker-end="url(#a)"/></svg>',
        (),
        ("D19", "D20"),
    ),
    (
        "2 本のコネクタが同じ高さで横走りして重なる (本数が読めない)",
        '<svg viewBox="0 0 400 300" xmlns="http://www.w3.org/2000/svg">'
        '<defs><marker id="a"><path d="M0 0"/></marker></defs>'
        '<path d="M100,80 V160 H300 V220" fill="none" stroke="#43436c"'
        ' marker-end="url(#a)"/>'
        '<path d="M160,80 V160 H340 V220" fill="none" stroke="#43436c"'
        ' marker-end="url(#a)"/></svg>',
        (("warning", "D20"),),
        (),
    ),
    (
        "2 本の横走りをレーン分けした正しい経路",
        '<svg viewBox="0 0 400 300" xmlns="http://www.w3.org/2000/svg">'
        '<defs><marker id="a"><path d="M0 0"/></marker></defs>'
        '<path d="M100,80 V140 H300 V220" fill="none" stroke="#43436c"'
        ' marker-end="url(#a)"/>'
        '<path d="M160,80 V180 H340 V220" fill="none" stroke="#43436c"'
        ' marker-end="url(#a)"/></svg>',
        (),
        ("D19", "D20"),
    ),
    (
        "箱の辺へ端点が着地するだけの正常な接続 (重なり長 0)",
        '<svg viewBox="0 0 400 300" xmlns="http://www.w3.org/2000/svg">'
        '<defs><marker id="a"><path d="M0 0"/></marker></defs>'
        '<rect x="60" y="200" width="160" height="60" fill="#FFFFFF" stroke="#43436c"/>'
        '<path d="M140,80 V200" fill="none" stroke="#43436c" marker-end="url(#a)"/></svg>',
        (),
        ("D19", "D21"),
    ),
    (
        "間の箱を貫く水平コネクタ (無い経路を読ませる)",
        '<svg viewBox="0 0 600 300" xmlns="http://www.w3.org/2000/svg">'
        '<defs><marker id="a"><path d="M0 0"/></marker></defs>'
        '<rect x="240" y="100" width="120" height="80" fill="#FFFFFF" stroke="#43436c"/>'
        '<path d="M80,140 H520" fill="none" stroke="#43436c" marker-end="url(#a)"/></svg>',
        (("warning", "D21"),),
        (),
    ),
    (
        "間の箱を迂回した水平コネクタ",
        '<svg viewBox="0 0 600 300" xmlns="http://www.w3.org/2000/svg">'
        '<defs><marker id="a"><path d="M0 0"/></marker></defs>'
        '<rect x="240" y="100" width="120" height="80" fill="#FFFFFF" stroke="#43436c"/>'
        '<path d="M80,140 V240 H520 V180" fill="none" stroke="#43436c"'
        ' marker-end="url(#a)"/></svg>',
        (),
        ("D19", "D20", "D21"),
    ),
)

# D22/D23 は SVG どうしの関係を見るため、1 つの SVG を渡す _SELF_TEST_CASES では
# 表現できない。(ラベル, [SVG 断片...], 期待コード, 出てはいけないコード) で持つ。
# この表のケースは check_document と各 SVG の check_svg を合わせて採点する。
_SELF_TEST_DOC_CASES: tuple[tuple[str, tuple[str, ...], tuple[tuple[str, str], ...], tuple[str, ...]], ...] = (
    (
        "2 面が同じ marker id を持つ (2 面目の矢じりが消える)",
        (
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
            '<defs><marker id="arrow-blue"><path d="M0 0"/></marker></defs>'
            '<line x1="40" y1="100" x2="200" y2="100" stroke="#43436c"'
            ' marker-end="url(#arrow-blue)"/></svg>',
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
            '<defs><marker id="arrow-blue"><path d="M0 0"/></marker></defs>'
            '<line x1="40" y1="100" x2="200" y2="100" stroke="#43436c"'
            ' marker-end="url(#arrow-blue)"/></svg>',
        ),
        (("error", "D22"),),
        (),
    ),
    (
        "面ごとに接尾辞を付けて一意にした 2 面",
        (
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
            '<defs><marker id="arrow-blue-s1"><path d="M0 0"/></marker></defs>'
            '<line x1="40" y1="100" x2="200" y2="100" stroke="#43436c"'
            ' marker-end="url(#arrow-blue-s1)"/></svg>',
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
            '<defs><marker id="arrow-blue-s2"><path d="M0 0"/></marker></defs>'
            '<line x1="40" y1="100" x2="200" y2="100" stroke="#43436c"'
            ' marker-end="url(#arrow-blue-s2)"/></svg>',
        ),
        (),
        ("D22",),
    ),
    (
        "clipPath の id が 2 面で衝突 (marker 以外でも同じ罠)",
        (
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
            '<defs><clipPath id="clip-a"><rect x="0" y="0" width="10" height="10"/>'
            '</clipPath></defs>'
            '<rect x="40" y="60" width="200" height="60" fill="#FFFFFF"'
            ' stroke="#43436c" clip-path="url(#clip-a)"/></svg>',
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
            '<defs><clipPath id="clip-a"><rect x="0" y="0" width="10" height="10"/>'
            '</clipPath></defs>'
            '<rect x="40" y="60" width="200" height="60" fill="#FFFFFF"'
            ' stroke="#43436c" clip-path="url(#clip-a)"/></svg>',
        ),
        (("error", "D22"),),
        (),
    ),
    (
        "id を 1 つも持たない 2 面 (重複しようがない)",
        (
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
            '<rect x="40" y="60" width="200" height="60" fill="#FFFFFF" stroke="#43436c"/></svg>',
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
            '<rect x="40" y="60" width="200" height="60" fill="#FFFFFF" stroke="#43436c"/></svg>',
        ),
        (),
        ("D22",),
    ),
    (
        "参照先がどこにも無い gradient (参照が宙に浮く)",
        (
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
            '<rect x="40" y="60" width="200" height="60" fill="url(#grad-a)"'
            ' stroke="#43436c"/></svg>',
        ),
        (("error", "D23"),),
        (),
    ),
    (
        "gradient を自分の defs に持つ (参照が閉じている)",
        (
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
            '<defs><linearGradient id="grad-a"><stop offset="0" stop-color="#43436c"/>'
            '</linearGradient></defs>'
            '<rect x="40" y="60" width="200" height="60" fill="url(#grad-a)"'
            ' stroke="#43436c"/></svg>',
        ),
        (),
        ("D23",),
    ),
    (
        "別の面の SVG にしかない gradient を参照している (参照が隠れる面を向く)",
        (
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
            '<defs><linearGradient id="grad-a"><stop offset="0" stop-color="#43436c"/>'
            '</linearGradient></defs>'
            '<rect x="40" y="60" width="200" height="60" fill="url(#grad-a)"'
            ' stroke="#43436c"/></svg>',
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
            '<rect x="40" y="60" width="200" height="60" fill="url(#grad-a)"'
            ' stroke="#43436c"/></svg>',
        ),
        (("error", "D23"),),
        (),
    ),
    (
        "共有 defs 置き場からの参照は正当 (描画物が無いので面の切替に影響されない)",
        (
            '<svg width="0" height="0" style="position:absolute"'
            ' xmlns="http://www.w3.org/2000/svg">'
            '<defs><filter id="card-shadow"><feDropShadow dx="0" dy="4"/></filter>'
            '<linearGradient id="card-fill-blue"><stop offset="0" stop-color="#43436c"/>'
            '</linearGradient></defs></svg>',
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
            '<rect x="40" y="60" width="200" height="60" fill="url(#card-fill-blue)"'
            ' stroke="#43436c" filter="url(#card-shadow)"/></svg>',
        ),
        (),
        ("D22", "D23"),
    ),
    (
        "2 つの図が同じ title/desc id を持つ (絵は変わらないが読み上げが先頭の図になる)",
        (
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg"'
            ' role="img" aria-labelledby="title desc">'
            '<title id="title">1 枚目</title><desc id="desc">1 枚目の説明</desc>'
            '<rect x="40" y="60" width="200" height="60" fill="#FFFFFF" stroke="#43436c"/></svg>',
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg"'
            ' role="img" aria-labelledby="title desc">'
            '<title id="title">2 枚目</title><desc id="desc">2 枚目の説明</desc>'
            '<rect x="40" y="60" width="200" height="60" fill="#FFFFFF" stroke="#43436c"/></svg>',
        ),
        (("error", "D22"),),
        (),
    ),
    (
        "aria-labelledby が別の図の title を指している (読み上げが入れ替わる)",
        (
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg"'
            ' role="img" aria-labelledby="title-s1">'
            '<title id="title-s1">1 枚目</title>'
            '<rect x="40" y="60" width="200" height="60" fill="#FFFFFF" stroke="#43436c"/></svg>',
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg"'
            ' role="img" aria-labelledby="title-s1">'
            '<title id="title-s2">2 枚目</title>'
            '<rect x="40" y="60" width="200" height="60" fill="#FFFFFF" stroke="#43436c"/></svg>',
        ),
        (("error", "D23"),),
        (),
    ),
    (
        "aria-labelledby が SVG の外の見出しを指している (SVG しか見ない検査は黙る)",
        (
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg"'
            ' role="img" aria-labelledby="sec-faq">'
            '<rect x="40" y="60" width="200" height="60" fill="#FFFFFF" stroke="#43436c"/></svg>',
        ),
        (),
        ("D22", "D23"),
    ),
    (
        "図ごとに接尾辞を付けた title/desc (参照が自分の中で閉じている)",
        (
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg"'
            ' role="img" aria-labelledby="title-s1 desc-s1">'
            '<title id="title-s1">1 枚目</title><desc id="desc-s1">1 枚目の説明</desc>'
            '<rect x="40" y="60" width="200" height="60" fill="#FFFFFF" stroke="#43436c"/></svg>',
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg"'
            ' role="img" aria-labelledby="title-s2 desc-s2">'
            '<title id="title-s2">2 枚目</title><desc id="desc-s2">2 枚目の説明</desc>'
            '<rect x="40" y="60" width="200" height="60" fill="#FFFFFF" stroke="#43436c"/></svg>',
        ),
        (),
        ("D22", "D23"),
    ),
    (
        "marker 未定義は D3 の担当で D23 は重ねて出さない",
        (
            '<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">'
            '<line x1="40" y1="100" x2="200" y2="100" stroke="#43436c"'
            ' marker-end="url(#arrow-blue)"/></svg>',
        ),
        (("error", "D3"),),
        ("D23",),
    ),
)


def _check_severity_registry() -> list[str]:
    """重大度表そのものの自己検査。違反があれば説明文の一覧を返す。

    見るのは 2 点だけ:
      1. D0-D23 の全コードが SEVERITY か ERROR_BY_DESIGN のどちらかに属する
         (= 新しい検査を足したとき、重大度の選択を必ず一度は明示させる)
      2. 両者が交差しない
         (= 「明示的に warning」と「意図して未登録の error」の二枚舌を禁じる)
    _sev() の既定値 (未登録 = error) は変えない。これは fail-closed 機構の
    上に被せた宣言の検査であって、機構そのものの置き換えではない。
    """
    problems: list[str] = []
    registered = frozenset(SEVERITY)
    both = sorted(registered & ERROR_BY_DESIGN)
    if both:
        problems.append(
            f"SEVERITY と ERROR_BY_DESIGN の両方に載っているコードがある: {', '.join(both)}"
            " (意図的な未登録なら SEVERITY から消し、明示登録なら ERROR_BY_DESIGN から消す)")
    missing = sorted(ALL_CODES - registered - ERROR_BY_DESIGN,
                     key=lambda c: int(c[1:]))
    if missing:
        problems.append(
            f"どちらの表にも無いコードがある: {', '.join(missing)}"
            " (warning にするなら SEVERITY へ、error のままにするなら ERROR_BY_DESIGN へ書く)")
    unknown = sorted((registered | ERROR_BY_DESIGN) - ALL_CODES,
                     key=lambda c: (len(c), c))
    if unknown:
        problems.append(
            f"D0-D23 に無いコードが表に載っている: {', '.join(unknown)}"
            " (検査を増やしたなら ALL_CODES の範囲も更新する)")
    return problems


def _self_test() -> int:
    """検査器そのものの自己テスト。exit 0 = 全 PASS。"""
    failed = 0
    registry_problems = _check_severity_registry()
    if registry_problems:
        failed += 1
        for p in registry_problems:
            print(f"  NG   - 重大度表の登録 ({p})", file=sys.stderr)
    else:
        print(f"  ok   - 重大度表の登録 (SEVERITY {len(SEVERITY)} 件 + "
              f"ERROR_BY_DESIGN {len(ERROR_BY_DESIGN)} 件 = D0-D23 の {len(ALL_CODES)} 件・交差なし)")
    for label, svg, expect, forbid in _SELF_TEST_CASES:
        found = {(f.severity, f.code) for f in check_svg(f"self-test:{label}", svg, check_grid=True)}
        codes = {c for _, c in found}
        missing = [f"{sev} {code}" for sev, code in expect if (sev, code) not in found]
        extra = [c for c in forbid if c in codes]
        if missing or extra:
            failed += 1
            detail = []
            if missing:
                detail.append(f"この severity/code で出るべきだが出ない: {', '.join(missing)}")
            if extra:
                detail.append(f"出てはいけないのに出た: {', '.join(extra)}")
            print(f"  NG   - {label} ({' / '.join(detail)})", file=sys.stderr)
        else:
            print(f"  ok   - {label}")
    for label, fragments, expect, forbid in _SELF_TEST_DOC_CASES:
        svgs = [(f"self-test:{label}#svg{i + 1}", frag) for i, frag in enumerate(fragments)]
        results = list(check_document(f"self-test:{label}", svgs))
        for svg_name, frag in svgs:
            results.extend(check_svg(svg_name, frag))
        found = {(f.severity, f.code) for f in results}
        codes = {c for _, c in found}
        missing = [f"{sev} {code}" for sev, code in expect if (sev, code) not in found]
        extra = [c for c in forbid if c in codes]
        if missing or extra:
            failed += 1
            detail = []
            if missing:
                detail.append(f"この severity/code で出るべきだが出ない: {', '.join(missing)}")
            if extra:
                detail.append(f"出てはいけないのに出た: {', '.join(extra)}")
            print(f"  NG   - {label} ({' / '.join(detail)})", file=sys.stderr)
        else:
            print(f"  ok   - {label}")
    total = len(_SELF_TEST_CASES) + len(_SELF_TEST_DOC_CASES) + 1  # +1 = 重大度表の登録検査
    print(f"validate-svg-diagram self-test: {total - failed}/{total} "
          f"{'PASS' if not failed else 'FAIL'}")
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    paths = [a for a in argv[1:] if not a.startswith("-")]
    strict = "--strict" in argv[1:]
    check_grid = "--check-grid" in argv[1:]
    usage = ("usage: validate-svg-diagram.py <file.svg|file.html> [...] "
             "[--strict] [--check-grid] | --self-test")
    # --help は「使い方を知りたい」意図であって失敗ではない。CI がこの終了コードを
    # 見て落ちないよう、引数不足 (=2) と明示的なヘルプ要求 (=0) を分ける。
    if "--help" in argv[1:] or "-h" in argv[1:]:
        print(usage)
        return 0
    if "--self-test" in argv[1:]:
        return _self_test()
    if not paths:
        print(usage, file=sys.stderr)
        return 2

    total_svgs = 0
    total_blocks = 0
    errors = 0
    warnings = 0

    def report(f: Finding) -> None:
        nonlocal errors, warnings
        if f.severity == "error":
            errors += 1
        else:
            warnings += 1
        print(str(f), file=sys.stderr)

    for path in paths:
        if not os.path.isfile(path):
            print(f"ERROR [D0] {path}: ファイルが無い", file=sys.stderr)
            errors += 1
            continue
        svgs = extract_svgs(path)
        for name, svg_text in svgs:
            total_svgs += 1
            for f in check_svg(name, svg_text, check_grid=check_grid):
                report(f)
        # D22 は SVG どうしの関係を見るので、1 つずつ見る check_svg では捕まらない。
        # ファイル単位で 1 度だけ走らせる。
        for f in check_document(os.path.basename(path), svgs):
            report(f)
        # CSS/HTML 構成の図解 (D14-D16)。<svg> を 1 つも持たない図解はここでしか見られない。
        for name, block in extract_diagram_blocks(path):
            total_blocks += 1
            for f in check_diagram_block(name, block):
                report(f)

    # --strict では warning も失格にする (仕上げ前の最終ゲート用)
    failed = errors > 0 or (strict and warnings > 0)
    result = "FAIL" if failed else "PASS"
    # 検査対象が 1 件も無かったことを機械可読に出す。
    #
    # 合否 (error 件数で決まる) と検査量は別の情報である。D3 経路の生成物は
    # <svg> ではなく <script type="application/json" data-d3-mount> しか持たない
    # ため svgs=0 css-blocks=0 になり、それでも errors=0 なので PASS と出る。
    # 「検査して合格した」と「検査対象が 1 つも無かった」が同じ文字列になると、
    # 下流 (hooks/hook-postgen-eval.py) が空振りを保証として読む。
    #
    # 既存の `svgs=N css-blocks=N errors=N warnings=N -> PASS` の形と語順は
    # 後方互換のため一切変えず、末尾へトークンを足すだけにする。exit code も
    # 変えない (合否は今までどおり error 件数だけで決まる)。
    #   inspected: 実際に検査した対象の総数 (= svgs + css-blocks)
    #   coverage : none = 検査対象 0 件 (合否を語る資格が無い) / checked = 1 件以上
    inspected = total_svgs + total_blocks
    coverage = "none" if inspected == 0 else "checked"
    print(f"svg diagram contract: svgs={total_svgs} css-blocks={total_blocks} "
          f"errors={errors} warnings={warnings} -> {result} "
          f"inspected={inspected} coverage={coverage}")
    if inspected == 0:
        print("svg diagram contract: NO-TARGET — 検査対象 (<svg> / CSS-HTML 図解ブロック) が "
              "0 件だったため、この PASS は「検査して合格した」ことを意味しない "
              "(D3 マウント点のみの生成物など)", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
