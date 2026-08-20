#!/usr/bin/env python3
"""図解の情報契約 (references/diagram-information-contract.md) を検査する。

既存の validate-svg-diagram.py (D0-D28) が見ているのは幾何と素材と**上限**である。
座標・寸法・色・書体・要素数の上限・複雑度の上限。そこに無いのが下限で、
「主キーの無い ER 図」「依存線の無いガント図」「目盛の無い価値軸」は
D0-D28 を全部緑で通過する。上限しか検査していないので誰も止めない。

本検査はその下限だけを見る。上限側は validate-svg-diagram.py のままで、
本検査はそれを置き換えない。両者は同じ図へ別々に掛ける。

判定は語彙の存在による近似で、意味の正しさは見ない。
図解の意味を機械が読むことはできないので、代わりに
「その情報を書いたなら必ず現れる語」の有無を見る。
そのぶん**取りこぼす側へ倒してある** — 誤検知で正しい図を止めるより、
欠落を 1 件見逃す方が害が小さい。検査が通ることは下限を満たしたことを
意味し、図がよいことは意味しない。

例外が 2 つある。参照の取りこぼし (I-ER-REF) と関係の不在 (I-REL-ISO) は
構造から確定的に判定できるので、語彙近似ではなく厳密に見る。

使い方:
    python3 validate-diagram-information.py [--strict] [--self-test] <path>...
    <path> は figure を含む .html、または作図入力の .json。
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# 重大度
#
# validate-svg-diagram.py と同じ流儀。未登録コードは _sev() が error へ倒し
# (fail-closed)、意図的な未登録は ERROR_BY_DESIGN へ明示して書き忘れと分ける。
# --self-test が SEVERITY ∪ ERROR_BY_DESIGN == ALL_CODES を検証する。
# ---------------------------------------------------------------------------
SEVERITY: dict[str, str] = {
    # I1-I5 は共通必須。既存資産にどれだけ欠落が眠っているか読めないうちは
    # warning で運用を始める (D10 を warning で始めたのと同じ理由)。
    # 仕上げ前の最終ゲートは --strict で warning ごと失格にできる。
    "I1": "warning",
    # I2 だけは他の共通必須より強い。「caption が量を主張しているのに図に量が無い」は
    # 欠落ではなく**矛盾**で、読者は主張を検証できないまま信じることになる。
    # ただし主張語の検出は語彙近似なので error には上げず、warning の中で
    # 最初に報告されるよう検査順を先頭へ置いてある。
    "I2": "warning",
    "I3": "warning",
    "I4": "warning",
    "I5": "warning",
    # 型別スロット。型が判別できた図にだけ掛かる。
    "I-ER": "warning",
    "I-STATE": "warning",
    "I-SEQ": "warning",
    "I-FLOW": "warning",
    "I-ARCH": "warning",
    "I-TIME": "warning",
    "I-CYCLE": "warning",
    "I-CHART": "warning",
    "I-CMP": "warning",
    "I-CLAIM": "warning",
    "I-STRUCT": "warning",
}

# SEVERITY へ意図的に登録しない = error 固定のコード。
#
# この 2 件は語彙近似ではなく構造から確定的に判定できる。
# 誤検知の余地が無く、かつ読者を確実に誤読させるので error 以外を選ぶ余地がない。
#   I-ER-REF  外部キー列を持つのに関係線が無い実体
#             → 読者は参照が存在しないと読む。正規化の妥当性判断が反転する。
#   I-REL-ISO どの関係も持たない節点
#             → 「載せる必要がある箱」と「線を引き忘れた箱」の区別が付かない。
#
# _sev() はこの集合を参照しない。ここは宣言であって分岐ではない。
# 分岐にすると fail-closed の既定値が弱まり、新しい検査の書き忘れが
# 再び静かに見逃されるようになる。
ERROR_BY_DESIGN: frozenset[str] = frozenset({"I-ER-REF", "I-REL-ISO"})

ALL_CODES: frozenset[str] = frozenset(SEVERITY) | ERROR_BY_DESIGN


def _sev(code: str) -> str:
    return SEVERITY.get(code, "error")


@dataclass
class Finding:
    code: str
    where: str
    message: str

    @property
    def severity(self) -> str:
        return _sev(self.code)

    def __str__(self) -> str:
        return f"[{self.severity}] {self.code} {self.where}: {self.message}"


# ---------------------------------------------------------------------------
# 型の判別
#
# 生成物には型を名乗る属性が無いことがある。判別できなければ共通必須 I1-I5 だけを
# 掛ける (型別は掛からない)。共通必須まで落とすと、生成物に対して検査が
# 何もしなくなり「宣言はあるが到達手段がない」型の欠陥に戻る。
# ---------------------------------------------------------------------------

# 型ファミリ → 判別に使う語。ファイル名・data 属性・HTML コメントを見る。
# 長い名前を先に置く (er が sequence へ誤当たりしないよう、境界も見る)。
FAMILY_KEYS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ER", ("er", "entity-relationship", "実体関連")),
    ("STATE", ("state", "it-state", "状態遷移")),
    ("SEQ", ("sequence", "シーケンス")),
    ("FLOW", ("flow", "swimlane", "data-flow", "スイムレーン", "フロー")),
    ("ARCH", ("architecture", "system-context", "high-level", "medallion",
              "dp-integration", "アーキテクチャ")),
    ("TIME", ("roadmap", "gantt", "vertical-timeline", "timeline", "chevron",
              "wave-steps", "kanban", "journey-map", "ロードマップ", "ガント")),
    ("CYCLE", ("cycle", "pdca", "flywheel", "triangle-cycle", "サイクル")),
    ("CHART", ("chart", "funnel", "heatmap", "waterfall", "scatter", "gauge",
               "radar", "ascent", "グラフ")),
    ("CMP", ("comparison", "matrix", "quadrant", "venn", "permission-matrix",
             "table-advanced", "比較", "マトリクス")),
    ("CLAIM", ("problem-solution", "prep", "fabe", "value-proposition",
               "persona", "star")),
    ("STRUCT", ("pyramid", "nested", "concentric", "org-chart", "person-network",
                "mindmap", "icon-grid", "point-cards", "value-stack",
                "ピラミッド", "組織図")),
)


def detect_family(path: str, text: str) -> str | None:
    """型ファミリを 1 つ返す。判別できなければ None。

    手掛かりの強い順に見る: ファイル名 → data 属性 → 冒頭コメント。
    複数当たったら最初に当たったものを採る (FAMILY_KEYS の並びが優先順位)。
    """
    base = os.path.basename(path).lower()
    stem = re.sub(r"-(golden|input|spec)\.(html|json)$", "", base)
    attrs = " ".join(re.findall(r'data-diagram-[a-z-]+="([^"]*)"', text)).lower()
    head = text[:1200].lower()
    haystacks = (stem, attrs, head)

    # 完全一致を先に全ファミリ分見る。境界一致より必ず先でなければならない:
    # "org-chart" は STRUCT の完全一致でありながら CHART の "-chart" 境界にも
    # 当たり、FAMILY_KEYS の並び順で CHART が先にあるため誤判定していた。
    # 一般に、より長く一致した方が正しい。
    for family, keys in FAMILY_KEYS:
        if stem in keys:
            return family
    for family, keys in FAMILY_KEYS:
        for key in keys:
            # 境界一致でだけ拾う。"er" が "sequence" の一部へ当たると
            # 全型が ER 判定になるので、部分一致は使えない。
            if stem.startswith(key + "-") or stem.endswith("-" + key):
                return family
    for family, keys in FAMILY_KEYS:
        for key in keys:
            pattern = r"(?<![a-z0-9-])" + re.escape(key) + r"(?![a-z0-9-])"
            for hay in haystacks[1:]:
                if re.search(pattern, hay):
                    return family
    return None


# ---------------------------------------------------------------------------
# 図の内側 / 外側
#
# 図は切り出されて流通する。印刷の抜粋・スライドの投影・画像としての引用の
# いずれでも figcaption は付いてこない。だから figcaption にしか無い情報は
# 「無い」として扱う。この分離が本検査の要で、ここを曖昧にすると
# 「caption に書いたから満たしている」で全部素通りする。
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_CAPTION_RE = re.compile(r"<figcaption\b.*?</figcaption>", re.S | re.I)
_SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S | re.I)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def _strip(html: str) -> str:
    return _TAG_RE.sub(" ", html)


def split_regions(text: str) -> tuple[str, str]:
    """(図の内側のテキスト, caption 等の外側のテキスト) を返す。

    内側 = <svg> の中の文字と、CSS 図解なら figure から caption を除いた本体。
    HTML コメントは作図者向けのメモなので、どちらにも数えない
    (コメントに書いた注記は読者へ届かない)。
    """
    body = _COMMENT_RE.sub(" ", text)
    outside = " ".join(_strip(m) for m in _CAPTION_RE.findall(body))
    without_caption = _CAPTION_RE.sub(" ", body)
    svgs = _SVG_RE.findall(without_caption)
    inside = " ".join(_strip(s) for s in svgs) if svgs else _strip(without_caption)
    return inside, outside


# ---------------------------------------------------------------------------
# 語彙
# ---------------------------------------------------------------------------

# 数値らしさ。年・件数・金額・割合・時間。単なる連番 (01/02) は数えない。
_NUMERIC_RE = re.compile(
    r"\d[\d,]*\s*(?:%|件|人|社|円|万|億|日|時間|分|週|か月|ヶ月|月|年|回|台|名|人日|pt|ポイント)"
    r"|\d[\d,]*\.\d+"
)
# 出所・時点・母数。1 つでもあれば I1 は満たすとみなす (3 つ全部は求めない)。
_PROVENANCE_RE = re.compile(
    r"出典|出所|実測|集計|調査|n\s*=|N\s*=|母数|回答|時点|基準日|現在|"
    r"20\d\d\s*[年/-]|20\d\d年度|第\s*[1-4Ⅰ-Ⅳ]\s*四半期"
)
# 母数の宣言。割合を載せる図では省略できない (契約 §I1)。
# 「68% が 100 人中 68 人か 8 人中 5 人か」は時点や出典では埋まらない別の穴で、
# 出所の論理和に混ぜると `2026年度` の 4 文字で母数の欠落まで免罪されてしまう。
_DENOMINATOR_RE = re.compile(r"[nN]\s*=\s*\d|母数|件中|人中|社中|回中|全\s*\d")
# 割合の表記。これが図内にあるなら母数を要求する。
_RATIO_RE = re.compile(r"\d[\d,]*(?:\.\d+)?\s*[%％]|\d\s*割(?!合)|パーセント")
# caption 側の量的主張。これがあるのに図内へ数値が無ければ I2。
_CLAIM_RE = re.compile(
    r"速くなる|遅くなる|縮む|伸び|増え|減り|減る|多い|少ない|高い|低い|"
    r"律速|ボトルネック|山になる|集中して|大半|ほとんど|過半|割を占め|"
    r"倍|以上|以下|最も|いちばん|一番|急に|急激"
)
# 凡例。線種・色を使い分けたときの対応表。
_LEGEND_RE = re.compile(r"凡例|実線|破線|点線|太線|── |―― |色は|線は|印は|▲|■ |□ ")
# 軸の宣言。または「軸は無い」という宣言。
_AXIS_RE = re.compile(
    r"軸|順不同|順序は|並びは|外側ほど|内側ほど|上ほど|下ほど|左から|右へ|"
    r"高いほど|大きいほど|縦は|横は|幅は|半径は|大きさは"
)
# 完了条件。
_DONE_RE = re.compile(
    r"完了|終了|合格|判定|基準|条件|Exit|exit|DoD|済み|満たしたら|できたら|"
    r"以内|まで|上限|しきい値|閾値"
)


def _has(pattern: re.Pattern[str], text: str) -> bool:
    return bool(pattern.search(text))


# I3 の語彙カウントから除く要素。詳細は check_symbols 内の注記。
_LEGEND_EL_RE = re.compile(r'<[a-z]+[^>]*\bdata-legend="1"[^>]*/?>')
_MARKER_RE = re.compile(r"<marker\b[\s\S]*?</marker>")
_TEXT_RE = re.compile(r"<text\b[\s\S]*?</text>")
# 紙・透明はどの図にも出るので語彙に数えない。CSS 変数で書かれた背景も同じ。
_BG_FILL_RE = re.compile(r"var\(--(bg|paper|surface)\b")


def _is_background_fill(value: str) -> bool:
    v = value.strip()
    if v.lower() in {"none", "#fff", "#ffffff", "transparent", "white"}:
        return True
    return bool(_BG_FILL_RE.search(v))


# ---------------------------------------------------------------------------
# 共通必須 I1-I5
# ---------------------------------------------------------------------------

# 全体を 100% として分け合う型。ここでだけ母数を独立に要求する。
# 進捗率・稼働率・達成率のような「既知の量に対する比」は母数が自明なので
# 対象にしない (全図へ掛けると roadmap の「60% 完了」まで鳴り、警告が死ぬ)。
_SHARE_TYPE_RE = re.compile(
    # 境界に `-` を含めない。ファイル名は kebab-case なので `pie-chart.json` の
    # `pie` は語の切れ目であって語の途中ではない。含めると実在の命名が全て漏れる。
    r"(?<![a-z0-9])(pie|donut|funnel|radar|stacked(?:-bar)?|hbar|"
    r"horizontal-bar|share|composition)(?![a-z0-9])|"
    r"円グラフ|積み上げ|ファネル|レーダー|横棒|構成比|内訳"
)


def _is_share_type(path: str, text: str) -> bool:
    base = os.path.basename(path).lower()
    attrs = " ".join(re.findall(r'data-diagram-[a-z-]+="([^"]*)"', text)).lower()
    return bool(_SHARE_TYPE_RE.search(base) or _SHARE_TYPE_RE.search(attrs))


def check_common(where: str, inside: str, outside: str,
                 share_type: bool = False) -> list[Finding]:
    out: list[Finding] = []
    numeric_inside = _has(_NUMERIC_RE, inside)

    # I2 を先頭に置く。欠落ではなく矛盾なので、報告の並びで先に目に入れたい。
    if _has(_CLAIM_RE, outside) and not numeric_inside:
        out.append(Finding(
            "I2", where,
            "caption が量を主張しているのに図の中に数値が無い。"
            "図へ量を入れるか、主張を図が支える範囲へ下げる",
        ))

    if numeric_inside and not _has(_PROVENANCE_RE, inside):
        out.append(Finding(
            "I1", where,
            "図の中に数値があるのに出所・時点・母数のどれも図内に無い。"
            "下端 1 行でよい (例: 2026年度・重複除外後 n=312)",
        ))
    # 契約 §I1 は「割合を出すなら母数は必須」と書いているのに、検査は
    # 出所・時点・母数の**論理和**しか見ていなかった。`2026年度` の 4 文字が
    # 母数の欠落まで免罪してしまう。割合が載っている図にだけ、母数を独立に
    # 要求する (契約の連言をここで 1 段だけ実装する)。
    elif share_type and _has(_RATIO_RE, inside) and not _has(_DENOMINATOR_RE, inside):
        out.append(Finding(
            "I1", where,
            "図の中に割合があるのに母数が図内に無い。"
            "68% が 100 人中 68 人か 8 人中 5 人かで結論は変わる (例: n=312)",
        ))

    return out


def check_symbols(where: str, raw: str, inside: str) -> list[Finding]:
    """I3 記号の凡例。

    「凡例が無い」を全図へ出すと、凡例の要らない図まで巻き込んで警告が
    無意味になる (最初の実装がそうで、69 件中 69 件が発火した)。
    凡例が要るのは**語彙を 2 つ以上使い分けたとき**だけなので、
    そこを SVG の属性から確定的に数える。語彙近似ではない。
    """
    body = _COMMENT_RE.sub(" ", raw)
    svg = " ".join(_SVG_RE.findall(body))
    if not svg:
        return []

    has_legend_mark = 'data-legend="1"' in svg
    # 語彙を数える前に「意味の使い分けではない塗り」を落とす。
    #   凡例の見本  : 凡例そのものの色。数えると凡例を描くほど凡例を要求される
    #   本文の文字色: 見出し・注記の墨色であって節点の分類ではない
    #   矢じり      : marker の塗りは線の一部で、独立した意味を持たない
    counted = _LEGEND_EL_RE.sub(" ", svg)
    counted = _MARKER_RE.sub(" ", counted)
    counted = _TEXT_RE.sub(" ", counted)

    vocabularies = 0
    # 線種: 破線を使っているなら実線との 2 語彙。
    if re.search(r'stroke-dasharray="[^"]+"', counted):
        vocabularies += 1
    # 線幅: 2 種類以上の stroke-width を線に与えているなら太さが語彙になる。
    widths = set(re.findall(r'stroke-width="([\d.]+)"', counted))
    if len(widths) >= 3:
        vocabularies += 1
    # 塗り分け: 背景以外の塗りが 3 色以上あれば色が語彙になっている。
    fills = {f for f in re.findall(r'fill="([^"]+)"', counted)
             if not _is_background_fill(f)}
    if len(fills) >= 3:
        vocabularies += 1

    if vocabularies >= 2 and not has_legend_mark and not _has(_LEGEND_RE, inside):
        return [Finding(
            "I3", where,
            "線種・太さ・色のうち 2 つ以上を使い分けているのに凡例が図内に無い。"
            "読者は使い分けの意味を推測するしかない",
        )]
    return []


def check_axis(where: str, inside: str, family: str | None) -> list[Finding]:
    """I4 軸の宣言。

    位置や大小が量に見える型にだけ掛ける。読者は形から量を反射的に読むので、
    軸名を書くか「並びは順不同」と書くかの二択で、書かない選択肢は無い。
    どちらでも満たせるよう _AXIS_RE は否定の宣言も拾う。
    """
    if family not in {"CHART", "STRUCT", "CMP", "TIME"}:
        return []
    if _has(_AXIS_RE, inside):
        return []
    return [Finding(
        "I4", where,
        "位置や大小が量に見える図なのに、軸の宣言も「順不同」の断りも図内に無い",
    )]


def check_common_done(where: str, inside: str, family: str | None) -> list[Finding]:
    """I5 完了条件。工程・段階を持つ型にだけ掛ける。"""
    if family not in {"FLOW", "TIME", "CYCLE", "STATE"}:
        return []
    if _has(_DONE_RE, inside):
        return []
    return [Finding(
        "I5", where,
        "工程や段階を持つ図なのに、完了条件が図内に無い。"
        "測定可能な形で書く (「即時参照できる」ではなく「5 分以内に参照」)",
    )]


# ---------------------------------------------------------------------------
# 型別スロット
#
# 各ファミリの必須スロットを (コード, 説明, 判定パターン) で宣言する。
# 表そのものが契約書 §2 の写しなので、契約書を変えたらここも変える。
# ---------------------------------------------------------------------------

FAMILY_SLOTS: dict[str, tuple[tuple[str, str, re.Pattern[str]], ...]] = {
    "ER": (
        ("主キー", "各実体の識別子に印が無い", re.compile(r"\bPK\b|主キー|識別子")),
        ("外部キーと参照先", "FK の参照先が書かれていない (FK だけでは足りない)",
         re.compile(r"FK\s*[→:\-]\s*\S|外部キー\s*[→:]")),
        ("カーディナリティ", "1:N などの多重度が無い",
         re.compile(r"1\s*[:対]\s*[N多1]|N\s*[:対]\s*[N多1]|多\s*対\s*[1多]")),
    ),
    "STATE": (
        ("初期状態", "どこから読み始めるかが無い", re.compile(r"初期|開始|起点|受付|入口")),
        ("終了状態", "どこで終わるかが無い", re.compile(r"終了|終端|完了|終状態|出口")),
        ("遷移の契機とガード", "契機と条件が区別されていない",
         re.compile(r"\[.+\]|条件|とき|場合|超過|以内")),
    ),
    "SEQ": (
        ("同期・非同期の別", "呼び出しの種別が無い", re.compile(r"同期|非同期|返す|戻り|応答")),
        ("失敗時の行き先", "エラー系路が無い",
         re.compile(r"失敗|否認|エラー|タイムアウト|拒否|不足|できな")),
    ),
    "FLOW": (
        ("担当", "各工程を誰がやるかが無い", re.compile(r"担当|部|課|係|チーム|者\b|名\b")),
        ("受け渡す成果物", "帯をまたぐとき何を渡すかが無い",
         re.compile(r"→|渡|提出|送付|申請書|伝票|一覧|報告|データ")),
        ("分岐の条件", "判断の閾値が無い", re.compile(r"以内|以上|以下|超|未満|かどうか|か\s*$|はい|いいえ")),
    ),
    "ARCH": (
        ("通信の向きと方式", "同期/非同期やプロトコルが無い",
         re.compile(r"同期|非同期|REST|API|バッチ|日次|毎|イベント|参照|連携")),
        ("責務", "各層・各ゾーンが何を保証するかが無い",
         re.compile(r"保証|責務|担う|管理|処理|保持|提供")),
    ),
    "TIME": (
        ("絶対時点", "年が無い。相対の週・月だけでは他資料と突合できない",
         re.compile(r"20\d\d")),
        ("依存", "先行・後続が無い。時間順に並べただけでは依存を示したことにならない",
         re.compile(r"前提|依存|後|完了後|待ち|を受けて|先行")),
    ),
    "CYCLE": (
        ("一周の周期", "1 周が月次か四半期かが無い",
         re.compile(r"周|月次|週次|日次|四半期|年次|か月|ヶ月|サイクル")),
        ("回る向き", "時計回りかどうかが無い", re.compile(r"時計回り|反時計|向き|→|順に|次へ")),
    ),
    "CHART": (
        ("単位", "軸の単位が無い",
         re.compile(r"%|件|人|社|円|万|億|日|時間|指数|点|回|台|名|人日")),
        ("尺度の定義", "起点・最大値・向きのいずれも無い",
         re.compile(r"0\b|起点|最大|上限|外側ほど|高いほど|基準|＝100|=100")),
    ),
    "CMP": (
        ("分類の関数", "読者が自分のケースを図の上に置ける基準が無い",
         re.compile(r"以内|以上|以下|超|未満|基準|境界|区切|判定|とは")),
        ("評価の根拠", "何をもって ○ / × かが無い",
         re.compile(r"可|不可|条件付|○|×|△|できる|できな|許可|禁止")),
    ),
    "CLAIM": (
        ("実行主体", "誰がやるかが無い", re.compile(r"担当|部|課|社|チーム|者\b|名\b|ベンダー")),
        ("期限", "いつまでかが無い", re.compile(r"まで|末|月内|以内|20\d\d|Q[1-4]|四半期")),
        ("証拠の裏付け", "出典・時期・件数のいずれも無い",
         re.compile(r"実測|出典|調査|社|件|20\d\d|平均|最小|最大")),
    ),
    "STRUCT": (
        ("序列の軸", "何の順で並ぶかが無い。意味が無いなら「順不同」と書く",
         re.compile(r"軸|順不同|順|上ほど|下ほど|外側|内側|大きいほど|広い|狭い")),
        ("関係の種類", "線が何を表すかが無い",
         re.compile(r"実線|破線|点線|所属|報告|連絡|包含|含む|拘束|依存|ではない")),
    ),
}


def check_family(where: str, inside: str, family: str | None) -> list[Finding]:
    slots = FAMILY_SLOTS.get(family or "", ())
    code = f"I-{family}"
    out: list[Finding] = []
    for name, why, pattern in slots:
        if not pattern.search(inside):
            out.append(Finding(code, where, f"{name}: {why}"))
    return out


# ---------------------------------------------------------------------------
# 厳密検査 — 構造から確定的に判定できる 2 件
# ---------------------------------------------------------------------------

def check_referential(where: str, spec: dict) -> list[Finding]:
    """I-ER-REF / I-REL-ISO。作図入力の JSON にだけ掛かる。

    SVG からノードと線の接続を復元するのは座標の突き合わせになり近似が入る。
    入力 JSON なら関係が名前で書かれているので、突き合わせが厳密にできる。
    だからこの 2 件は JSON 経路でだけ error として出す。
    """
    out: list[Finding] = []
    # 入れ子を掘る責務は _referential_roots() に一本化してある。ここで再度
    # 掘ると「どの階層を検査したか」の判断が 2 箇所に分かれ、片方だけ新しい
    # 語彙へ追随して静かに食い違う。渡された dict をそのまま本体として読む。
    body = spec
    if not isinstance(body, dict):
        return out

    entities = body.get("entities")
    relations = body.get("relations") or body.get("links") or body.get("edges") or []
    if not isinstance(relations, list):
        return out

    connected: set[str] = set()
    for r in relations:
        if isinstance(r, dict):
            for key in ("from", "to", "source", "target"):
                v = r.get(key)
                if isinstance(v, str):
                    connected.add(v)

    if isinstance(entities, list) and entities:
        names = [e.get("name") for e in entities if isinstance(e, dict)]
        # I-ER-REF: 他実体の名前を含む列を持つのに、その実体との関係線が無い。
        # 「受注番号」を持つ「請求」に 受注→請求 の線が無い、という取りこぼしを拾う。
        for e in entities:
            if not isinstance(e, dict):
                continue
            me = e.get("name")
            fields = " ".join(str(f) for f in (e.get("fields") or []))
            for other in names:
                if not other or other == me:
                    continue
                if other in fields:
                    linked = any(
                        isinstance(r, dict)
                        and {r.get("from"), r.get("to")} == {me, other}
                        for r in relations
                    )
                    if not linked:
                        out.append(Finding(
                            "I-ER-REF", where,
                            f"「{me}」が「{other}」を参照する列を持つのに関係線が無い。"
                            f"読者はこの参照が存在しないと読む",
                        ))
        # I-REL-ISO: どの関係も持たない実体。
        for name in names:
            if name and name not in connected and len(names) > 1:
                out.append(Finding(
                    "I-REL-ISO", where,
                    f"「{name}」はどの関係も持たない。線を引くか図から削る",
                ))

    # ER 以外の節点集合にも孤立検査を掛ける。
    #
    # 節点の同一性は 1 つの鍵では決まらない。作図入力は nodes 側を
    # id + label で書き、relations 側を id で参照することもあれば
    # label で参照することもある。最初の実装は name→label→id の順で
    # 「1 つだけ」選んでいたため、label を持つ節点は id で結ばれていても
    # 未接続と判定され、ほぼ全ての入力 JSON へ error を出していた。
    # error 重大度の誤検知は、検査そのものを信用できなくする。
    # 節点が名乗る識別子を全部集め、どれか 1 つでも関係側に現れれば接続とみなす。
    # 線を持たなくてよい節点。輪の中心・凡例・注記は工程ではないので、
    # 関係を持たないことが正しい。役割を名乗った節点だけを免除する
    # (「線が無い」を理由に免除すると検査が空になる)。
    #
    # 免除の根拠に **id を使わない**。理由は 2 つある。
    #   1. id は識別子であって宣言ではない。`id: "note"` はたまたまその綴りに
    #      なっただけかもしれず、作図者が「これは注記だ」と述べたことにならない。
    #   2. 本番語彙 (svgSpec) の id は `^n-[a-z0-9-]+$` に縛られている。
    #      `n-note` は HUB_ROLES と一致しないので、id 照合では**本番の図が
    #      構造的に一切免除されない**。免除機構が片方の語彙でだけ働くのは、
    #      免除機構が無いのと同じである。
    # 宣言は `role` に一本化する (`kind`/`type` は描画スタイルの語彙であって
    # 役割ではない。focal / store / external はどれも線を持つべき節点である)。
    HUB_ROLES = {"core", "center", "hub", "legend", "note", "title", "caption"}

    nodes = body.get("nodes")
    if isinstance(nodes, list) and relations:
        for n in nodes:
            if isinstance(n, dict):
                if str(n.get("role", "")).lower() in HUB_ROLES:
                    continue
                ids = {n.get(k) for k in ("id", "name", "label")}
                ids = {v for v in ids if isinstance(v, str) and v}
                shown = n.get("label") or n.get("name") or n.get("id")
            elif isinstance(n, str) and n:
                ids, shown = {n}, n
            else:
                continue
            if ids and not (ids & connected):
                out.append(Finding(
                    "I-REL-ISO", where,
                    f"「{shown}」はどの関係も持たない。線を引くか図から削る",
                ))
    return out


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

_DECL_RE = re.compile(r'\bdata-srg-declaration="([^"]*)"')


def html_declaration(chunk: str) -> dict | None:
    """図が運んできた宣言 (実体・節点・関係) を取り出す。無ければ None。

    描画済み SVG から復元するのではなく、レンダラが `data-srg-declaration`
    へ載せた申告をそのまま読む。復元は座標の近似になり、近似で error 重大度の
    失格を出すと誤検知が検査そのものの信用を壊す。宣言なら突き合わせが厳密で、
    JSON 経路と**同一の** check_referential へそのまま渡せる。

    壊れた宣言は None にする (握り潰して合格にしない — 呼出し側が
    「参照検査をしていない」として数える)。
    """
    m = _DECL_RE.search(chunk)
    if not m:
        return None
    try:
        doc = json.loads(html.unescape(m.group(1)))
    except json.JSONDecodeError:
        return None
    return doc if isinstance(doc, dict) else None


def check_html(path: str) -> tuple[list[Finding], bool, int]:
    """(findings, 検査できたか, 参照検査を掛けた図の数) を返す。

    第 2 要素が要るのは、findings が空のとき「合格した」と「見るものが
    無かった」の区別が付かないためである。両者を同じ空リストで返すと、
    パス解決の失敗も入力の破損も静かに緑になる。呼出し側はこの真偽で
    inspected を数え、テストが実ファイル数と突き合わせる。

    第 3 要素は同じ理由を参照検査 (I-ER-REF / I-REL-ISO) にも掛けたもの。
    宣言を持たない図は参照検査が**掛かっていない**のであって、参照が
    正しいのではない。inspected と別に数え、集計へ出す。
    """
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if "<figure" not in text and "<svg" not in text:
        return [], False, 0
    base = os.path.basename(path)
    out: list[Finding] = []
    referential = 0
    for label, chunk in _html_figures(text):
        where = base + label
        inside, outside = split_regions(chunk)
        family = detect_family(path, chunk)
        out += check_common(where, inside, outside, _is_share_type(path, chunk))
        out += check_symbols(where, chunk, inside)
        out += check_axis(where, inside, family)
        out += check_common_done(where, inside, family)
        out += check_family(where, inside, family)
        decl = html_declaration(chunk)
        if decl is not None:
            out += check_referential(where, decl)
            referential += 1
    return out, True, referential


_FIGURE_RE = re.compile(r"<figure\b[\s\S]*?</figure>", re.I)


def _html_figures(text: str) -> list[tuple[str, str]]:
    """HTML を図の単位へ割る。(図の名札, その図の HTML) の並びを返す。

    生成物 (report / slide) は 1 ファイルに図を何枚も持つ。丸ごと 1 枚として
    検査すると 2 つの壊れ方をする。

      1. **型が混ざる**: ER 図とガント図が同居した文書から型ファミリを 1 つ
         決めることはできない。どちらの必須スロットも掛からなくなる。
      2. **指摘が薄まる**: 数値の有無も凡例の有無も文書全体の論理和になり、
         1 枚でも満たしていれば全部満たしたことになる。

    ゴールデンのような 1 図 1 ファイルでは分割しない (名札を付けると
    where が冗長になるだけで、区別する相手がいない)。
    """
    figs = _FIGURE_RE.findall(text)
    if len(figs) <= 1:
        return [("", text)]
    out: list[tuple[str, str]] = []
    for i, fig in enumerate(figs):
        m = re.search(r'data-diagram-id="([^"]*)"', fig)
        out.append((f"#{m.group(1) if m else i}", fig))
    return out


def _referential_roots(doc: dict) -> list[tuple[str, dict]]:
    """参照検査へ渡す階層を (図の名札, 本体) の並びで返す。空なら検査対象なし。

    入力の語彙が 3 系統ある。
      A 手書き    : トップレベルに nodes[] / relations[]         (*-input.json)
      B builder   : {builder, surface, title, spec:{...}}        (*-spec.json)
      C production: structure.json の svgSpec (variant + nodes[] + edges[])
    C は 1 ファイルに複数の図を含むので、戻り値を並びにして全部検査する。
    1 つ目だけを見る作りにすると、2 つ目以降の図が黙って素通りする。

    **既知のキーだけを 1 段掘り、再帰はしない。** 再帰で `entities`/`nodes`
    を探すと、凡例や注記が持つ同名キーまで拾って error を誤爆させる。この
    検査器は失格を出す側 (ERROR_BY_DESIGN) なので、誤検知の害が取りこぼしの
    害より大きい。取りこぼしても静かに緑にはならない — 掘れなかった文書は
    inspected に数えず skipped として件数が出る (空振りガード)。新しい入れ子
    語彙が増えたときは skipped の増加として現れるので、そこで追随すればよい。
    """
    out: list[tuple[str, dict]] = []
    seen: list[int] = []

    def take(label: str, d: object) -> None:
        # 参照検査が読む語彙を 1 つも持たない dict は「掛からない」ので採らない。
        if not isinstance(d, dict):
            return
        if not (d.get("entities") or d.get("nodes")):
            return
        if id(d) in seen:  # A と B が同一 dict を指す入力での二重計上を防ぐ
            return
        seen.append(id(d))
        out.append((label, d))

    take("", doc)                # A 手書き
    take("", doc.get("spec"))    # B builder
    take("", doc.get("svgSpec"))  # C production (単図)

    # C production: 1 文書に複数の図。名札を付けて「どの図か」を追えるようにする。
    for key in ("slides", "sections", "blocks", "diagrams"):
        arr = doc.get(key)
        if not isinstance(arr, list):
            continue
        for i, item in enumerate(arr):
            if not isinstance(item, dict):
                continue
            name = item.get("diagramId") or item.get("id") or f"{key}[{i}]"
            take(f"#{name}", item.get("svgSpec"))
            take(f"#{name}", item.get("spec"))
    return out


def check_json(path: str) -> tuple[list[Finding], bool, int]:
    """(findings, 検査できたか, 参照検査を掛けた図の数) を返す。check_html と同じ理由。

    JSON が壊れている・dict でない・参照検査の語彙を持たないときは
    「見るものが無かった」であって合格ではない。
    """
    with open(path, encoding="utf-8") as fh:
        try:
            doc = json.load(fh)
        except json.JSONDecodeError:
            return [], False, 0
    if not isinstance(doc, dict):
        return [], False, 0
    roots = _referential_roots(doc)
    if not roots:
        return [], False, 0
    base = os.path.basename(path)
    out: list[Finding] = []
    for label, body in roots:
        out += check_referential(base + label, body)
    return out, True, len(roots)


def self_test() -> int:
    """検査器そのものの健全性を見る。

    新しい検査コードを足したとき SEVERITY か ERROR_BY_DESIGN のどちらかへの
    登録を強制する。片方へ入れ忘れると _sev() が黙って error へ倒し、
    「意図した error」と「書き忘れ」が見分けられなくなる。
    """
    problems: list[str] = []

    declared = frozenset(SEVERITY) | ERROR_BY_DESIGN
    if declared != ALL_CODES:
        problems.append(f"SEVERITY ∪ ERROR_BY_DESIGN != ALL_CODES: {declared ^ ALL_CODES}")

    overlap = frozenset(SEVERITY) & ERROR_BY_DESIGN
    if overlap:
        problems.append(f"両方へ登録されたコード: {sorted(overlap)}")

    # 型別コードが FAMILY_SLOTS と対応しているか。
    for family in FAMILY_SLOTS:
        if f"I-{family}" not in ALL_CODES:
            problems.append(f"FAMILY_SLOTS の {family} に対応するコードが未登録")

    # 型判別: 全ファミリの代表名が正しく引けること。とくに "er" が
    # "sequence" や "person-network" へ誤当たりしないこと。
    cases = [
        ("er-golden.html", "ER"),
        ("sequence-golden.html", "SEQ"),
        ("person-network-golden.html", "STRUCT"),
        ("gantt-golden.html", "TIME"),
        ("pdca-input.json", "CYCLE"),
        ("bar-chart-golden.html", "CHART"),
        # 完全一致が境界一致に勝つこと。"org-chart" は STRUCT の完全一致だが
        # CHART の "-chart" にも当たる。並び順で決めると誤る。
        ("org-chart-golden.html", "STRUCT"),
    ]
    for name, expect in cases:
        got = detect_family(name, "")
        if got != expect:
            problems.append(f"型判別 {name}: {expect} を期待したが {got}")

    # 内側 / 外側の分離。caption にだけ書いた語を内側と数えないこと。
    inside, outside = split_regions(
        "<figure><svg><text>本体</text></svg>"
        "<figcaption>出典: 実測 2026年</figcaption></figure>"
    )
    if "出典" in inside:
        problems.append("figcaption の語が図の内側と数えられている")
    if "出典" not in outside:
        problems.append("figcaption の語が外側として取れていない")

    # 母数の独立要求は「全体を分け合う型」だけに掛かること。ここを全図へ
    # 広げると roadmap の「60% 完了」まで鳴り、警告そのものが死ぬ。
    share = "構成比 42% と 58%。出典: 社内集計 2026年"
    if not check_common("t", share, "", share_type=True):
        problems.append("割合のみで母数の無い円グラフに I1 が鳴っていない")
    if check_common("t", share, "", share_type=False):
        problems.append("割合を扱わない型で母数の I1 が鳴っている")
    if check_common("t", share + " n=312", "", share_type=True):
        problems.append("母数がある図に I1 が鳴っている")
    if not _is_share_type("pie-share.json", "") or _is_share_type("roadmap.json", ""):
        problems.append("_is_share_type の型判定が誤っている")

    # I3 は語彙が 1 つの図で鳴らないこと。ここが緩むと全図で発火して
    # 警告そのものが読まれなくなる (最初の実装がそうだった)。
    plain = '<svg><rect fill="#FFFFFF" stroke-width="1.5"/><text>あ</text></svg>'
    if check_symbols("t", plain, "あ"):
        problems.append("語彙 1 つの図で I3 が鳴っている")
    mixed = ('<svg><path stroke-dasharray="4 3" stroke-width="1"/>'
             '<rect fill="#A00" stroke-width="2"/><rect fill="#0A0" stroke-width="3"/>'
             '<rect fill="#00A"/><text>本文</text></svg>')
    if not check_symbols("t", mixed, "本文"):
        problems.append("語彙 3 つの図で I3 が鳴っていない")
    if check_symbols("t", mixed, "凡例 破線は未確定"):
        problems.append("凡例のある図で I3 が鳴っている")

    # 凡例を描いたこと自体が語彙を増やして凡例を要求する自己敗北ループが
    # 起きないこと。見本の塗りは数えず、印そのものが免責になる。
    with_legend = ('<svg><path stroke-dasharray="4 3" stroke-width="1"/>'
                   '<rect fill="#A00" stroke-width="2"/><rect fill="#0A0" stroke-width="3"/>'
                   '<rect data-legend="1" fill="#00A"/>'
                   '<rect data-legend="1" fill="#0AA"/><text>本文</text></svg>')
    if check_symbols("t", with_legend, "本文"):
        problems.append("凡例の印がある図で I3 が鳴っている")
    # 本文の文字色・矢じりの塗りは分類ではないので語彙に数えない。
    inky = ('<svg><defs><marker><path fill="#111"/></marker></defs>'
            '<path stroke-dasharray="4 3"/>'
            '<text fill="#222">見出し</text><text fill="#333">注記</text>'
            '<rect fill="var(--bg, #FFFFFF)"/></svg>')
    if check_symbols("t", inky, "見出し 注記"):
        problems.append("文字色・矢じりを色の語彙に数えている")

    # 厳密検査が実際に発火すること。掘る責務は _referential_roots() にあるので
    # check_referential を直接呼ばず本番と同じ経路を通す。直呼びにすると「掘れて
    # いないのに検査は動く」自己テストになり、空振りガードが守る境界を跨げない。
    roots = _referential_roots({"spec": {
        "entities": [
            {"name": "受注", "fields": ["受注番号 : PK"]},
            {"name": "請求", "fields": ["請求番号 : PK", "受注番号 : FK"]},
        ],
        "relations": [],
    }})
    if not roots:
        problems.append("spec 直下の本体を掘れていない")
    got = [f for _label, body in roots for f in check_referential("t", body)]
    codes = {f.code for f in got}
    if "I-ER-REF" not in codes:
        problems.append("参照の取りこぼしを検出できていない")
    if "I-REL-ISO" not in codes:
        problems.append("孤立節点を検出できていない")
    for f in got:
        if f.severity != "error":
            problems.append(f"{f.code} が error になっていない")

    # 節点を id で結び label で表示する入力で誤検知しないこと。
    # ここが緩むと error 重大度の誤検知が全入力へ出て、検査が信用を失う。
    linked = check_referential("t", {
        "nodes": [{"id": "a", "label": "受付"}, {"id": "b", "label": "審査"}],
        "relations": [{"from": "a", "to": "b"}],
    })
    if linked:
        problems.append(f"id で結ばれた節点を孤立と誤判定している: {linked[0].message}")

    # 生成物 HTML の図単位分割。型の違う図が混ざった文書を 1 枚と見ないこと。
    two = ('<html><figure data-diagram-id="f1"><svg></svg></figure>'
           '<figure data-diagram-id="f2"><svg></svg></figure></html>')
    split = _html_figures(two)
    if [lb for lb, _ in split] != ["#f1", "#f2"]:
        problems.append(f"複数図の HTML を図単位へ割れていない: {[lb for lb, _ in split]}")
    one = '<html><figure data-diagram-id="f1"><svg></svg></figure></html>'
    if [lb for lb, _ in _html_figures(one)] != [""]:
        problems.append("1 図の HTML に不要な名札が付いている")

    # 1 文書に複数の図がある C 系。2 つ目以降が黙って素通りしないこと。
    multi = _referential_roots({"slides": [
        {"diagramId": "d1", "svgSpec": {"nodes": [{"id": "n-a", "label": "A"}]}},
        {"diagramId": "d2", "svgSpec": {"nodes": [{"id": "n-b", "label": "B"}]}},
    ]})
    if len(multi) != 2:
        problems.append(f"複数図の文書で {len(multi)} 件しか掘れていない")
    if [lb for lb, _ in multi] != ["#d1", "#d2"]:
        problems.append(f"どの図かの名札が付いていない: {[lb for lb, _ in multi]}")

    # 生成物 HTML が運ぶ宣言。復元ではなく申告を読むので、JSON 経路と同じ
    # 指摘が同じ重大度で出ること。ここが黙ると .html は参照を素通りする。
    decl = {"entities": [{"name": "受注", "fields": ["受注番号"]},
                         {"name": "請求", "fields": ["請求番号", "受注番号"]}],
            "relations": []}
    carried = ('<figure class="report-visual" data-srg-declaration="'
               + html.escape(json.dumps(decl, ensure_ascii=False), quote=True)
               + '"><svg></svg></figure>')
    got_html = html_declaration(carried)
    if got_html is None:
        problems.append("figure が運ぶ宣言を読めていない")
    elif not any(f.code == "I-ER-REF" for f in check_referential("t", got_html)):
        problems.append("生成物 HTML の宣言に参照検査が掛かっていない")
    # 宣言の無い図を「参照検査済み」に数えないこと。ここが緩むと、宣言を
    # 運ばない図が全部「参照は正しい」ことにされる (空振りガード)。
    if html_declaration('<figure><svg></svg></figure>') is not None:
        problems.append("宣言の無い図に宣言があることにされている")
    if html_declaration('<figure data-srg-declaration="{壊れ"></figure>') is not None:
        problems.append("壊れた宣言が検査対象として通っている")

    for p in problems:
        print(f"[self-test] {p}", file=sys.stderr)
    if problems:
        return 1
    print("self-test ok")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--strict", action="store_true", help="warning も失格にする")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.paths:
        ap.error("検査対象を 1 つ以上指定する")

    findings: list[Finding] = []
    inspected = 0
    referential = 0
    skipped: list[str] = []
    for path in args.paths:
        if path.endswith(".html"):
            got, ok, ref = check_html(path)
        elif path.endswith(".json"):
            got, ok, ref = check_json(path)
        else:
            got, ok, ref = [], False, 0
        findings += got
        referential += ref
        if ok:
            inspected += 1
        else:
            skipped.append(os.path.basename(path))

    for f in findings:
        print(str(f))

    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity != "error"]
    failed = bool(errors) or (args.strict and bool(findings))
    # 空振りの明示。件数を出さないと「合格」と「見るものが無かった」が
    # 呼出し側から区別できず、パス解決の失敗が緑で通る。
    if skipped:
        print("skipped (検査対象なし): " + " ".join(sorted(skipped)))
    # referential は inspected の内数ではなく別軸。図の体裁 (数値・凡例・軸) を
    # 見たことと、参照の取りこぼしを見たことは別で、後者は宣言を運んできた図に
    # しか掛からない。合算すると「全部見た」ように読めるので必ず分けて出す。
    print(
        f"diagram information contract: targets={len(args.paths)} "
        f"inspected={inspected} skipped={len(skipped)} "
        f"referential={referential} "
        f"errors={len(errors)} warnings={len(warnings)} "
        f"-> {'FAIL' if failed else 'PASS'}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
