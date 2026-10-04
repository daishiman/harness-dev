#!/usr/bin/env python3
# /// script
# name: validate-cross-level
# version: 0.1.0
# purpose: 期報・月報・週報の3ファイルを同時に読み、期アンカーの値が三層で一致しているかを照合する
# inputs:
#   - argv: --quarterly PATH --monthly PATH [--weekly PATH] [--month N]
# outputs:
#   - stdout: アンカーごとの三層並記 / 照合対象 N 件中 不一致 M 件（抽出不可 K 件）/ STATUS
#   - exit: 0=全一致 / 1=不一致または抽出不可あり / 2=引数・入力不正 / 3=抽出0件（何も判定していない）
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""UBM目標設定 三層（期報・月報・週報）アンカー横断照合。

`validate-goal-output.py --peer` との役割分担:

- `validate-goal-output.py --peer` は **2ファイルの総当たり・WARN のみ・3アンカー**。
  単一ファイルの保存前バリデーションに付随する補助検査で、不一致でも rc は上がらない。
- 本スクリプトは **3ファイル同時・rc を持つ・8アンカー**。期報を正本とした継承関係が
  崩れていないかを判定するための独立した検査器で、不一致があれば rc=1 を返す。

照合の考え方:

期報が正本で、月報・週報がそれを継承する。ただし継承の形は2種類ある。

1. **同値継承**: 期全体の値をそのまま下位層が書き写す（今期の売上目標 など）。
2. **内訳継承**: 期報が月別内訳として書いた値を、月報が自分の層の値として書く
   （無料相談の延べ回数120回のうち10月分56回 → 月報の56回）。

内訳継承のアンカーは「期報が当月について書いた数」と「月報が自分の数として書いた数」を
比べる。期合計と月の値を直接比べると必ず不一致になるため、そうはしない。
対象月は月報のファイル名の末尾の日付から決める（最終月曜起点のため、期間終了日の月が当月）。

**rc=1（照合して不一致あり）と rc=3（1件も抽出できず何も判定していない）は別物。**
抽出できなかったアンカーは「不一致」に混ぜず「抽出不可」として個別に列挙し、1件でも
あれば rc=1 にする（検査できていない状態を PASS にしない）。

抽出範囲から外す節: 【仮置き事項】【衝突】【来月以降に対応すること】【確定済み・解消済みの記録】
【この期報の値を直したときに追随させる箇所】【前期/前月/前週の振り返り】。これらには
「以前は500,000だった」のような経緯の記述が入っており、現在値として拾うと誤判定になる。
"""

from __future__ import annotations

import argparse
import datetime
import io
import re
import sys
from pathlib import Path

LEVELS = ("quarterly", "monthly", "weekly")
LEVEL_JA = {"quarterly": "期報", "monthly": "月報", "weekly": "週報"}

# 抽出範囲から外す節。## の見出しで判定し、配下の ### も自動的に外れる。
_EXCLUDE_SECTION = re.compile(
    r"仮置き事項"
    r"|衝突"
    r"|来(?:週|月|期)以降に対応すること"
    r"|確定済み|解消済み"
    r"|追随させる箇所"
    r"|前(?:週|月|期)の"
)

# 節本文に限って落とす前処理。validate-journal-output.py と同じ形を使う
# （新しい前処理を考えない）。ファイル全体ではなく節本文だけに当てる。
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_FENCED_CODE_RE = re.compile(r"^```.*?^```", re.DOTALL | re.MULTILINE)

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BULLET = re.compile(r"^(?:[*-]\s*(?:\[[ xX]\]\s*)?|・\s*(?:\[[ xX]\]\s*)?)")
_NOTE_PREFIXES = ("（", "(", "※", ">")
_ZENKAKU_DIGIT = re.compile(r"[０-９]")
# 全角を半角へ直すと規則に当たる行は「全角数字で書かれている」と判定する。
# 当たらない行は無関係なので触らない（人名の中の全角数字などを誤検出しない）。
_Z2H = str.maketrans("０１２３４５６７８９，．", "0123456789,.")
_DATE_IN_NAME = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


class Spec:
    """1レベル分の抽出規則。

    head        : ## 見出し本文に当てる正規表現
    pattern     : 値を取る正規表現（グループ1が値。`{M}` は対象月に置換される）
    line_filter : その行が満たすべき正規表現（None なら全行）
    allow_note  : （ ( ※ > で始まる注記行からも取るか
    why         : 取れなかったときに表示する理由
    """

    def __init__(self, head, pattern, line_filter=None, allow_note=False, why=""):
        self.head = re.compile(head)
        self.pattern = pattern
        self.line_filter = re.compile(line_filter) if line_filter else None
        self.allow_note = allow_note
        self.why = why

    def needs_month(self) -> bool:
        return "{M}" in self.pattern


class Anchor:
    def __init__(self, name, kind, specs):
        self.name = name
        self.kind = kind  # "number" | "date"
        self.specs = specs  # dict[level] -> list[Spec]


_NUM = r"([0-9][0-9,]*)"
_ISO = r"(\d{4}-\d{2}-\d{2})"


def _scalar(head: str, pattern: str = None) -> list:
    """見出し直下の単独行から値を取る規則（注記行は飛ばす）。"""
    return [Spec(head, pattern or (r"^" + _NUM + r"\s*$"),
                 why=f"{head} の直下に値だけの行が無い")]


ANCHORS = [
    # 1. 同値継承。三層とも同じ見出しに同じ数字が立つ。
    Anchor("今期の売上目標", "number", {
        "quarterly": _scalar(r"^【今期の売上目標】$"),
        "monthly": _scalar(r"^【今期の売上目標】$"),
        "weekly": _scalar(r"^【今期の売上目標】$"),
    }),
    # 2. 内訳継承。期報は月別内訳、月報は自分の月の値、週報は日割りの根拠行。
    Anchor("当月の売上目標", "number", {
        "quarterly": [Spec(r"^【事業計画書数値】$", r"{M}月" + _NUM,
                           line_filter=r"月別の売上目標", allow_note=True,
                           why="【事業計画書数値】に「月別の売上目標：…{M}月…」の行が無い")],
        "monthly": _scalar(r"^【今月の売上目標】$"),
        "weekly": [Spec(r"^【今週の売上目標】$", _NUM + r"\s*÷", allow_note=True,
                        why="【今週の売上目標】に日割りの根拠行（「月額 ÷ 日数」の形）が無い")],
    }),
    # 3-5. 内訳継承。期報の当月分 ↔ 月報の最重要数字。週報は週の内訳なので対象外。
    Anchor("無料相談の延べ回数", "number", {
        "quarterly": [Spec(r"^【今期の売上以外の成果目標】$", r"{M}月" + _NUM + r"回",
                           line_filter=r"無料相談の延べ回数", allow_note=True,
                           why="【今期の売上以外の成果目標】に「無料相談の延べ回数…{M}月…回」が無い")],
        "monthly": [Spec(r"^【今月の最重要数字】$", r"延べ回数\s*" + _NUM + r"回",
                         allow_note=True,
                         why="【今月の最重要数字】に「延べ回数…回」が無い")],
    }),
    Anchor("1回目の実人数", "number", {
        "quarterly": [Spec(r"^【今期の売上以外の成果目標】$", r"{M}月" + _NUM + r"名",
                           line_filter=r"1回目", allow_note=True,
                           why="【今期の売上以外の成果目標】に「1回目…{M}月…名」が無い")],
        "monthly": [Spec(r"^【今月の最重要数字】$", r"実人数[：:]\s*" + _NUM + r"名",
                         allow_note=True,
                         why="【今月の最重要数字】に「実人数：…名」が無い")],
    }),
    Anchor("月額継続コンサルの累積件数", "number", {
        "quarterly": [Spec(r"^【今期の売上以外の成果目標】$", r"{M}月" + _NUM + r"件",
                           line_filter=r"累積", allow_note=True,
                           why="【今期の売上以外の成果目標】に「累積は…{M}月…件」が無い")],
        "monthly": [Spec(r"^【今月の最重要数字】$", r"件数[：:]\s*" + _NUM + r"件",
                         allow_note=True,
                         why="【今月の最重要数字】に「件数：…件」が無い")],
    }),
    # 6-8. 同値継承（スナップショットだが三層で同じ時点を書く約束のもの）。
    Anchor("現在事業パートナー数", "number", {
        "quarterly": _scalar(r"^【現在事業パートナー数】$"),
        "monthly": _scalar(r"^【現在事業パートナー数】$"),
        "weekly": _scalar(r"^【現在事業パートナー数】$"),
    }),
    Anchor("現在のグリッドパートナー数", "number", {
        "quarterly": _scalar(r"^【現在のグリッドパートナー数】$"),
        "monthly": _scalar(r"^【現在のグリッドパートナー数】$"),
        "weekly": _scalar(r"^【現在のグリッドパートナー数】$"),
    }),
    Anchor("次回の壁打ち予定日", "date", {
        "quarterly": _scalar(r"^【次回の壁打ち予定日】$", r"^" + _ISO),
        "monthly": _scalar(r"^【次回の壁打ち予定日】$", r"^" + _ISO),
        "weekly": _scalar(r"^【次回の壁打ち予定日】$", r"^" + _ISO),
    }),
]


class Section:
    def __init__(self, heading: str, start: int):
        self.heading = heading
        self.start = start
        self.lines: list[tuple[int, str]] = []
        self.excluded = bool(_EXCLUDE_SECTION.search(heading))

    def body(self) -> list[tuple[int, str]]:
        """節本文からコメント・コードフェンスを落として返す。

        範囲を節本文（数百字程度）に限ってから落とす。素朴な正規表現をファイル全体へ
        広げると本文が消えるため、ここを広げてはいけない。
        """
        raw = "\n".join(t for _, t in self.lines)
        if "<!--" not in raw and "```" not in raw:
            return list(self.lines)
        # 行番号を保つため、落とした範囲の改行は残す（行数が変わると行番号がずれる）。
        def _blank(m: "re.Match[str]") -> str:
            return "\n" * m.group(0).count("\n")

        cleaned = _FENCED_CODE_RE.sub(_blank, _HTML_COMMENT_RE.sub(_blank, raw)).split("\n")
        return [(no, text) for (no, _), text in zip(self.lines, cleaned)]


def parse_sections(text: str) -> list[Section]:
    """## 単位で節に切る。### 以下は親の ## の本文に含める。

    除外は2段で効く。
    - ## の見出しが除外語に当たれば、その節全体を見ない。
    - ### 以下の小見出しが除外語に当たれば、そこから次の小見出しまでの行を本文に入れない。
      アンカーの節の中に「確定済み・解消済みの記録」「仮置き事項」が入っている形を落とす。
    """
    sections: list[Section] = []
    current: Section | None = None
    sub_excluded = False
    for i, line in enumerate(text.split("\n"), start=1):
        m = _HEADING.match(line)
        if m:
            depth = len(m.group(1))
            if depth <= 2:
                current = Section(m.group(2), i)
                sections.append(current)
                sub_excluded = False
            else:
                sub_excluded = bool(_EXCLUDE_SECTION.search(m.group(2)))
            continue
        if current is not None and not sub_excluded:
            current.lines.append((i, line))
    return sections


def read_doc(path: Path) -> str:
    # 日本語パスの NFC/NFD 不一致を避けるため io.open で開く。
    with io.open(str(path), "r", encoding="utf-8") as f:
        return f.read()


def target_month(monthly_path: Path, text: str) -> int | None:
    """対象月（当月）を決める。月報の期間終了日の月。

    UBM の月報は最終月曜起点のため、2026-09-28〜2026-10-25 の当月は 10 月。
    ファイル名の末尾の日付を見て、無ければ本文1行目の見出しを見る。
    """
    for source in (monthly_path.name, text.split("\n")[0] if text else ""):
        found = _DATE_IN_NAME.findall(source)
        if found:
            return int(found[-1][1])
    return None


def extract(sections: list[Section], specs: list[Spec], month: int | None):
    """(値, 行番号, 理由) を返す。取れなければ値は None。"""
    reasons = []
    zenkaku_at: int | None = None
    for spec in specs:
        if spec.needs_month():
            if month is None:
                reasons.append("対象月が決まらない（月報のファイル名に日付が無い）")
                continue
            pattern = re.compile(spec.pattern.replace("{M}", str(month)))
            why = spec.why.replace("{M}", str(month))
        else:
            pattern = re.compile(spec.pattern)
            why = spec.why
        reasons.append(why)
        for sec in sections:
            if sec.excluded or not spec.head.match(sec.heading):
                continue
            for no, raw in sec.body():
                line = _BULLET.sub("", raw).strip()
                if not line:
                    continue
                if not spec.allow_note and line.startswith(_NOTE_PREFIXES):
                    continue
                if spec.line_filter and not spec.line_filter.search(line):
                    continue
                m = pattern.search(line)
                if not m:
                    if zenkaku_at is None and _ZENKAKU_DIGIT.search(line):
                        half = line.translate(_Z2H)
                        if half != line and pattern.search(half):
                            zenkaku_at = no
                    continue
                if _ZENKAKU_DIGIT.search(line):
                    return None, no, "全角数字が含まれている（半角のみで書く）"
                return m.group(1), no, ""
    if zenkaku_at is not None:
        return None, zenkaku_at, "全角数字が含まれている（半角のみで書く）"
    return None, None, reasons[0] if reasons else "抽出規則が無い"


def normalize(value: str, kind: str) -> str:
    return value.replace(",", "") if kind == "number" else value


def verify(docs: dict, month: int | None) -> tuple[int, list[str]]:
    """docs: level -> (path, sections)。未指定レベルは含めない。"""
    lines: list[str] = []
    lines.append("UBM目標設定 三層（期報・月報・週報）アンカー横断照合")
    lines.append(f"対象月: {month}月" if month else "対象月: 不明")
    for level in LEVELS:
        if level in docs:
            lines.append(f"{LEVEL_JA[level]}: {docs[level][0]}")
        else:
            lines.append(f"{LEVEL_JA[level]}: （未指定）")
    lines.append("")

    compared = 0
    mismatched: list[str] = []
    unextractable: list[str] = []
    extracted_total = 0

    for anchor in ANCHORS:
        active = [lv for lv in LEVELS if lv in docs and lv in anchor.specs]
        if len(active) < 2:
            lines.append(f"[対象外] {anchor.name}（照合できる層が1つ以下）")
            continue
        compared += 1
        shown = []
        values = {}
        missing = []
        for level in active:
            raw, no, why = extract(docs[level][1], anchor.specs[level], month)
            if raw is None:
                missing.append(f"{LEVEL_JA[level]}: {why}")
                shown.append(f"{LEVEL_JA[level]}=（抽出不可）")
                continue
            extracted_total += 1
            values[level] = normalize(raw, anchor.kind)
            shown.append(f"{LEVEL_JA[level]}={values[level]}（{no}行目）")
        joined = "  ".join(shown)
        if missing:
            unextractable.append(anchor.name)
            lines.append(f"[抽出不可] {anchor.name}  {joined}")
            for m in missing:
                lines.append(f"    - {m}")
        elif len(set(values.values())) > 1:
            mismatched.append(anchor.name)
            lines.append(f"[NG] {anchor.name}  {joined}")
        else:
            lines.append(f"[OK] {anchor.name}  {joined}")

    lines.append("")
    lines.append(
        f"照合対象 {compared} 件中 不一致 {len(mismatched)} 件"
        f"（抽出不可 {len(unextractable)} 件）"
    )
    if mismatched:
        lines.append("不一致のアンカー: " + " / ".join(mismatched))
    if unextractable:
        lines.append("抽出不可のアンカー: " + " / ".join(unextractable))

    if extracted_total == 0:
        lines.append(
            "どのアンカーも1件も抽出できませんでした。"
            "これは「一致していた」ではなく「何も判定していない」です。"
        )
        return 3, lines
    if mismatched or unextractable:
        return 1, lines
    return 0, lines


def _print_trailer(measured_at: str, argv: list[str]) -> None:
    print(f"MEASURED_AT: {measured_at}")
    print(f"ARGS: {' '.join(argv)}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="UBM目標設定 期報・月報・週報の期アンカー横断照合", add_help=True
    )
    ap.add_argument("--quarterly", required=True, metavar="PATH", help="期報（正本）")
    ap.add_argument("--monthly", required=True, metavar="PATH", help="月報")
    ap.add_argument("--weekly", metavar="PATH", help="週報（任意）")
    ap.add_argument("--month", type=int, metavar="N", help="対象月の上書き（既定は月報の期間終了日の月）")

    measured_at = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        if e.code == 0:
            return 0
        _print_trailer(measured_at, argv)
        return 2

    docs = {}
    texts = {}
    for level, path_str in (
        ("quarterly", args.quarterly),
        ("monthly", args.monthly),
        ("weekly", args.weekly),
    ):
        if not path_str:
            continue
        path = Path(path_str)
        try:
            text = read_doc(path)
        except OSError as e:
            print(f"入力不正: {LEVEL_JA[level]} を読めません: {path} ({e})")
            _print_trailer(measured_at, argv)
            return 2
        texts[level] = text
        docs[level] = (str(path), parse_sections(text))

    month = args.month or target_month(Path(args.monthly), texts["monthly"])
    if args.month is not None and not (1 <= args.month <= 12):
        print(f"引数不正: --month は 1〜12 で指定してください（受領値: {args.month}）")
        _print_trailer(measured_at, argv)
        return 2

    rc, lines = verify(docs, month)
    for line in lines:
        print(line)
    _print_trailer(measured_at, argv)
    print({0: "STATUS: PASS", 1: "STATUS: FAIL", 3: "STATUS: NO_TARGET"}[rc])
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
