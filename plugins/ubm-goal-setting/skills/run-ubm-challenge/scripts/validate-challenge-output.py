#!/usr/bin/env python3
# /// script
# name: validate-challenge-output
# version: 0.1.0
# purpose: 挑戦宣言と企画の Markdown が正本フォーマット (フロントマター・冒頭タイトル・●見出し6欄の順序・
#          挑戦の日付と規模と注記2行・リスク回避5理由・お金の理由・行うこと5項目と締め文・
#          定期報告の頻度かタイミング) を満たすかを保存前後に検査する決定論ゲート。
#          未置換プレースホルダ (◯ / 例） / <…>) と精神論の語を不合格 (FAIL) にする。
# inputs:
#   - fs: plugin references/action-language-policy.json（欠落・不正は終了コード2）
#   - argv: --file <path>
# outputs:
#   - stdout: PASS/FAIL (合格/不合格) と違反一覧
#   - exit: 0=合格 (PASS) / 1=不合格 (FAIL) / 2=引数不正・ファイル読み込み不能 (読めなければ合格にしない)
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""挑戦宣言と企画の保存前後バリデーション。

検査するのは「提出先が読んで追えるか」の機械判定できる部分だけに絞る。目的の文が本人の言葉か、
数字が目的とつながるか、といった中身の質は対話 (question-map.md) が受け持ち、ここでは評価しない。

見出し・注記・締め文の文字列の正本は references/challenge-format.md の骨格で、
このファイルの定数はそれに一字一句合わせる (tests が突き合わせる)。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

TITLE = "【挑戦宣言と企画】"
SECTION_PURPOSE = "●目的ーあなたの事業や会社の目的は何か？"
SECTION_GOAL = "●目標ーその目的に近づくための数値的な目標"
SECTION_CHALLENGE = "●その目標を実現するための挑戦"
SECTION_RISK = "●リスク回避方法"
SECTION_ACTIONS = "●挑戦を必ず達成するために行うこと"
SECTION_REPORT = "●目標を追うために定期の報告はどのタイミングで行いますか？"
SECTION_HEADINGS = (
    SECTION_PURPOSE, SECTION_GOAL, SECTION_CHALLENGE, SECTION_RISK, SECTION_ACTIONS, SECTION_REPORT,
)
CHALLENGE_NOTES = (
    "※ポイントー使える箱は定員数で意識の基準を落とさない",
    "※ズームなら基本100人以上",
)
RISK_REASONS = (
    "・健康が崩れない理由",
    "・信頼が崩れない理由",
    "・家族が崩れない理由",
    "・社内拠点が崩れない理由",
    "・開催前にお金が全て回収できているor1円も費用がかからない理由",
)
MONEY_REASON = RISK_REASONS[-1]
CLOSING_LINE = "上記行うことで必ず達成します。"
ACTION_COUNT = 5

FILENAME_RE = re.compile(r"^UBM - 挑戦宣言 - (\d{4}-\d{2}-\d{2})\.md$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# 挑戦の日付。「12月12日」「2026年12月12日」「2026-12-12」を受理する。
MONTH_DAY_RE = re.compile(r"(?:(\d{4})\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*日")
ISO_IN_TEXT_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
HEADCOUNT_RE = re.compile(r"\d+\s*(?:人|名)")
# 目標の数値 (G01)。str の \d は全角数字も数える (C01/C02 と同じ)。
DIGIT_RE = re.compile(r"\d")
ACTION_ITEM_RE = re.compile(r"^(\d+)\s*[.．、)）]\s*(.*)$")


# 行動の精神論の語の唯一正本。プロフィールで既存の判定範囲を保つ。
ACTION_POLICY_PATH = Path(__file__).resolve().parents[3] / "references/action-language-policy.json"
try:
    _action_policy = json.loads(ACTION_POLICY_PATH.read_text(encoding="utf-8"))
    _action_terms = _action_policy["challenge_stems"]
    if not isinstance(_action_terms, list) or not _action_terms or any(not isinstance(term, str) or not term for term in _action_terms):
        raise ValueError("challenge_stems は空でない文字列の配列である必要があります")
except (OSError, ValueError, KeyError, TypeError) as exc:
    sys.stderr.write(f"行動の語彙契約を読めません: {exc}\n")
    raise SystemExit(2)

SPIRIT_STEMS = tuple(_action_terms)


# 定期報告 (P01)。見出しは「どのタイミング」だけを聞くので、頻度かタイミング (曜日・時刻) のどちらかで合格。
# 報告先と報告する数字は対話で聞くだけで、ここでは検査しない。回数は数字 (全角を含む) と漢数字 (一〜十) で読む。
_KANSUJI = "一二三四五六七八九十"
_COUNT = rf"(?:\d+|[{_KANSUJI}]+)"
REPORT_FREQUENCY_RE = re.compile(
    r"毎日|毎朝|毎晩|毎週|毎月|隔週|隔月|週次|月次"
    # question-map の切り口① (すでに続いている定期の場) を頻度として受理する。面談は場の言い方
    # (「面談で」「面談ごと」) に限り、「12月15日に面談の結果を報告」を頻度と読まない。
    r"|週報|月報|定例|面談(?:で|の場|の際|のたび|ごと)"
    # 「週1で」「週に一度」「月2回」。「12月15日」の「月15」を頻度と読まないよう週・月の直前に数を許さず、
    # 回・度の付かない数のあとに「日」が続くもの (「来月1日」) も1回きりの日付として読まない。
    rf"|(?<![\d{_KANSUJI}])[週月]\s*に?\s*{_COUNT}(?![\d{_KANSUJI}])(?:\s*[回度]|(?!\s*日))"
    # 「1日に1回」「日に2回」「2週間に1回」「3ヶ月に1度」「3日ごと」。直前が月か数のもの
    # (「12月15日に1回」「12月 15日に1回」) は日付の一部として読まない。
    rf"|(?<![月\d{_KANSUJI}])(?<!月\s)(?:{_COUNT})?日\s*に?\s*{_COUNT}\s*回"
    rf"|(?<![月\d{_KANSUJI}])(?<!月\s){_COUNT}\s*(?:日|週間|[ヶヵかカケ箇]?月)\s*(?:に\s*{_COUNT}\s*[回度]|ごと|おき)"
)
REPORT_TIMING_RE = re.compile(r"[月火水木金土日]曜|\d{1,2}\s*時|\d{1,2}:\d{2}|月初|月末|週初|週末|朝|夜")

# 未置換プレースホルダ (X01)。例文・テンプレの記号が残ったまま提出される事故を止める。
PLACEHOLDER_RES = (
    ("◯", re.compile(r"[◯○]")),
    ("例）", re.compile(r"例[）)]")),
    ("<…>", re.compile(r"[<＜][^>＞\n]{1,40}[>＞]")),
)

# ---- お金の理由 (M01) の補助 ----------------------------------------------------------------

_YEN_UNITS = {"億": 100_000_000, "万": 10_000, "千": 1_000}
MONEY_TOKEN = r"\d[\d,]*(?:\.\d+)?\s*(?:億|万|千)?\s*円?"
# 金額と読める数 (単位か「円」が付いたもの)。人数・回数の数字を金額と取り違えないために分ける。
AMOUNT_RE = re.compile(r"\d[\d,]*(?:\.\d+)?\s*(?:(?:億|万|千)\s*円?|円)")
# 「3万×30人で90万」「5万円×10人＝50万円」を拾う。件数側の「万」は誤記 (例文の「5万×10万」) を
# 計算違いとして検出するために受理する。
PRODUCT_RE = re.compile(
    rf"(?P<unit>{MONEY_TOKEN})\s*[×xX✕*＊]\s*(?P<count>\d[\d,]*)\s*(?P<cunit>人|名|社|口|件|枚|万)?"
    rf"\s*(?:で|＝|=|→|は)\s*(?P<total>{MONEY_TOKEN})"
)
# 費用ゼロを示す言い方。
# 「100円」「3,000円」の末尾の 0円 を拾わないよう、0 の直前が数字・桁区切りでないことを要求する。
# 「無料ではない」「無料でない」「かからないわけではなく」「かからない、ということはない」のような否定は
# 費用ゼロと読まない。「かからないということです」のような肯定は否定と取り違えない。
ZERO_COST_RE = re.compile(
    r"(?:費用ゼロ|ゼロ円|(?<![\d,.])0\s*円|無料|かかって(?:い)?(?:ない|ません)|かからない|かかりません|負担なし)"
    r"(?!\s*[、,]?\s*(?:では|じゃ|でな|とは|(?:という|って)?(?:わけ|こと)(?:では|じゃ|は)(?:な|あり)))"
)
# 自分で払う費用。費用ゼロ・回収済みと同じ欄にあっても M01 にする (「会場費は無料だが講師料は自分で払う」)。
# 否定は直後に付く形 (「払わず」「負担しない」「自己負担はゼロ」「自分で払うものは一切ない」) だけを外し、
# 同じ文の離れた「ない」(「払うしかない」「払い、交通費はない」) と義務 (「払わないといけない」
# 「払わなくてはならない」) では外さない。
# 立替えは後で回収する前提の支払いなので、同じ文の後ろで回収済みと書いていれば数えない (self_pay_sentences)。
SELF_PAY_RE = re.compile(
    r"(?:(?:自分|私|僕|自社|当社)(?:で|が|の)(?:支?払|負担)|自己負担|自腹|持ち出し|自分持ち|(?P<advance>立て?替え))"
    r"(?!(?:わ|し)(?:ない(?!と(?:いけ|だめ|ダメ|な))|なく(?!て(?:は|も)?(?:いけ|なら|だめ|ダメ)|ちゃ)|なかっ)"
    r"|(?:い|し)ません|せず|わず|ず"
    r"|(?:う|った|る|た|する|した)?(?:もの|費用|分|お金|額|必要|こと|の)?(?:は|が|も)?\s*(?:一切|何も)?\s*"
    r"(?:ゼロ|なし|無し|ない|ありません|0\s*円))"
)
# 開催前に回収・確定していることを示す言い方。
# 回収は否定形 (「回収できていない」「回収できず」「回収していない」) と条件形 (「回収できれば」) を外す。
# 確定は後ろに付く語が多い (「確定予定」「確定前」「確定待ち」「確定次第」…) ので、完了形
# (「確定済み」「確定した」「確定している」「確定です」「確定額」、文や括弧の終わりの「確定」) だけを拾う。
COLLECTED_RE = re.compile(
    r"回収(?:済|して(?!い?な|いませ|おらず)|でき(?!な|ず|ませ|てい?な|ていませ|ておらず|れば|たら))"
    r"|(?<!未)確定(?:済|額|です|した(?!ら|場合)|しました|して(?:いる|います|おり)|(?=[。．、）)」\n]|$))"
    r"|入金済|決済済|支払(?:い)?済|受領済"
)
# 確定していない言い方。回収「予定」を回収「済み」と書く事故を拾うための材料。
# 「予定」はお金の動きに付くものだけを拾い、「開催予定」「目標300万円」は見込みと読まない。
# 否定形 (「未確定」「回収できていない」「入金されていない」) と条件形 (「回収できれば」「確定次第」) も拾い、
# 回収済みと同じ欄に混ざった未確定の額を数えない。
PROSPECT_RE = re.compile(
    r"見込み|想定|見通し|つもり|(?:入金|回収|振込|支払い?|決済|受領|売上)予定"
    r"|未(?:確定|回収|入金|決済)|確定せず|確定(?:予定|前|待ち)"
    r"|(?:回収|入金|確定)(?:でき|して|され)(?:てい|い)?(?:な|ず|ませ)|(?:回収|入金|確定)(?:でき|し|され)ておらず"
    r"|(?:回収|入金|確定)(?:でき(?:れば|たら)|し?次第|しだい|すれば|したら|され(?:れば|たら))"
)


def parse_yen(token: str) -> int | None:
    """「100万円」「3万」「50,000円」「2.5万」を円の整数にする。読めなければ None。"""
    m = re.fullmatch(r"\s*(\d[\d,]*(?:\.\d+)?)\s*(億|万|千)?\s*円?\s*", token)
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    return int(round(value * _YEN_UNITS.get(m.group(2) or "", 1)))


@dataclass(frozen=True)
class Product:
    """本文中の「単価 × 件数 = 合計」1件。"""

    raw: str
    unit_yen: int
    count: int
    total_yen: int

    @property
    def consistent(self) -> bool:
        return self.unit_yen * self.count == self.total_yen


def find_products(text: str) -> list[Product]:
    """お金の理由の本文から「単価 × 件数 = 合計」の式をすべて拾う。"""
    products = []
    for m in PRODUCT_RE.finditer(text):
        unit = parse_yen(m.group("unit"))
        total = parse_yen(m.group("total"))
        if unit is None or total is None:
            continue
        count = int(m.group("count").replace(",", ""))
        if m.group("cunit") == "万":
            count *= 10_000
        products.append(Product(m.group(0), unit, count, total))
    return products


SUM_RE = re.compile(
    rf"(?P<terms>{MONEY_TOKEN}(?:\s*[＋+]\s*{MONEY_TOKEN})+)\s*(?:で|＝|=|→|は)\s*(?P<total>{MONEY_TOKEN})"
)


@dataclass(frozen=True)
class Sum:
    """本文中の「A + B + C = 合計」1件。"""

    raw: str
    terms_yen: tuple[int, ...]
    total_yen: int

    @property
    def consistent(self) -> bool:
        return sum(self.terms_yen) == self.total_yen


def find_sums(text: str) -> list[Sum]:
    """お金の理由の本文から「A + B = 合計」の式をすべて拾う。"""
    sums = []
    for m in SUM_RE.finditer(text):
        terms = [parse_yen(t) for t in re.split(r"[＋+]", m.group("terms"))]
        total = parse_yen(m.group("total"))
        if total is None or any(t is None for t in terms):
            continue
        sums.append(Sum(m.group(0), tuple(terms), total))
    return sums


def self_pay_sentences(text: str) -> list[str]:
    """自分で払う費用を書いた文を返す。立替えは、同じ文の後ろで回収済みと書いていれば数えない。"""
    found = []
    for sentence in re.split(r"[。\n]", text):
        for m in SELF_PAY_RE.finditer(sentence):
            if m.group("advance") and COLLECTED_RE.search(sentence, m.end()):
                continue
            found.append(sentence.strip())
            break
    return found


def check_money_reason(text: str) -> list[str]:
    """お金の理由の本文を受け取り、M01 の違反メッセージを返す (空リストなら合格)。

    合格は「費用ゼロ」か「回収済み + 確定した金額」のどちらか。どちらでも、見込み・予定・未確定の額を書いた行、
    自分で払う費用を書いた行、単価×件数・合計の計算違いを違反にする。
    """
    problems: list[str] = []
    if not ZERO_COST_RE.search(text):
        if not COLLECTED_RE.search(text):
            problems.append("開催前に回収済み (回収・入金・決済済み) か、費用がかからない (0円・無料) かが書かれていません")
        elif not AMOUNT_RE.search(text):
            problems.append("回収済みと書かれていますが、確定した金額がありません")
    problems += [
        f"見込み・予定・未確定の金額は回収済みに数えられません: {line.strip()}"
        for line in text.splitlines()
        if PROSPECT_RE.search(line) and AMOUNT_RE.search(line)
    ]
    problems += [
        f"自分で払う費用は、開催前の回収済みにも費用ゼロにも数えられません: {sentence}"
        for sentence in self_pay_sentences(text)
    ]
    problems += [f"計算が合いません: {calc.raw}" for calc in (*find_products(text), *find_sums(text)) if not calc.consistent]
    return problems


# ---- 構造の読み取り --------------------------------------------------------------------------


@dataclass
class Violation:
    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


def split_frontmatter(text: str) -> tuple[dict[str, str] | None, list[str]]:
    """先頭の --- 区切りのフロントマターを key: value の dict にし、本文の行を返す。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, lines
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm: dict[str, str] = {}
            for raw in lines[1:i]:
                if ":" in raw and not raw.startswith((" ", "\t", "-")):
                    key, _, value = raw.partition(":")
                    fm[key.strip()] = value.strip().strip("'\"")
            return fm, lines[i + 1:]
    return None, lines


def split_sections(body: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    """●見出しごとに直下の行を切り出す。見出しの欠落・順序違いは違反文として返す。"""
    positions: dict[str, int] = {}
    for idx, line in enumerate(body):
        stripped = line.strip()
        if stripped in SECTION_HEADINGS and stripped not in positions:
            positions[stripped] = idx
    problems = [f"見出しがありません: {h}" for h in SECTION_HEADINGS if h not in positions]
    found = [h for h in SECTION_HEADINGS if h in positions]
    if [positions[h] for h in found] != sorted(positions[h] for h in found):
        problems.append("●見出しの順序がフォーマットと違います")
    ordered = sorted(found, key=lambda h: positions[h])
    sections: dict[str, list[str]] = {}
    for n, heading in enumerate(ordered):
        end = positions[ordered[n + 1]] if n + 1 < len(ordered) else len(body)
        sections[heading] = [line.rstrip() for line in body[positions[heading] + 1:end]]
    return sections, problems


def content_lines(lines: list[str], exclude: tuple[str, ...] = ()) -> list[str]:
    return [line for line in lines if line.strip() and line.strip() not in exclude]


def split_by_labels(lines: list[str], labels: tuple[str, ...]) -> tuple[dict[str, list[str]], list[str]]:
    """リスク回避の「・〜理由」ラベルごとに本文を切り出す。"""
    positions = {}
    for idx, line in enumerate(lines):
        if line.strip() in labels and line.strip() not in positions:
            positions[line.strip()] = idx
    problems = [f"理由の見出しがありません: {label}" for label in labels if label not in positions]
    found = [label for label in labels if label in positions]
    if [positions[label] for label in found] != sorted(positions[label] for label in found):
        problems.append("リスク回避5理由の順序がフォーマットと違います")
    ordered = sorted(found, key=lambda label: positions[label])
    parts = {}
    for n, label in enumerate(ordered):
        end = positions[ordered[n + 1]] if n + 1 < len(ordered) else len(lines)
        parts[label] = content_lines(lines[positions[label] + 1:end])
    return parts, problems


def parse_actions(lines: list[str]) -> list[tuple[int, str]]:
    """「1.〜」形式の行を (番号, 本文) にする。番号の無い続きの行は直前の項目へ足す。"""
    items: list[tuple[int, str]] = []
    for line in content_lines(lines, exclude=(CLOSING_LINE,)):
        m = ACTION_ITEM_RE.match(line.strip())
        if m:
            items.append((int(m.group(1)), m.group(2).strip()))
        elif items:
            number, text = items[-1]
            items[-1] = (number, f"{text} {line.strip()}".strip())
    return items


def challenge_dates(text: str, default_year: int | None) -> list[tuple[int | None, int, int]]:
    dates: list[tuple[int | None, int, int]] = []
    for m in MONTH_DAY_RE.finditer(text):
        year = int(m.group(1)) if m.group(1) else default_year
        dates.append((year, int(m.group(2)), int(m.group(3))))
    for m in ISO_IN_TEXT_RE.finditer(text):
        dates.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return dates


# ---- 検査本体 --------------------------------------------------------------------------------


def validate(text: str, filename: str | None = None) -> list[Violation]:
    v: list[Violation] = []
    fm, body = split_frontmatter(text)

    declared_on = challenge_on = None
    if fm is None:
        v.append(Violation("F04", "フロントマター (--- で囲んだ declared_on / challenge_date) がありません"))
    else:
        for key in ("declared_on", "challenge_date"):
            value = fm.get(key, "")
            if not ISO_DATE_RE.match(value):
                v.append(Violation("F04", f"フロントマターの {key} が YYYY-MM-DD ではありません: {value!r}"))
                continue
            try:
                parsed = date.fromisoformat(value)
            except ValueError:
                v.append(Violation("F04", f"フロントマターの {key} が実在しない日付です: {value}"))
                continue
            if key == "declared_on":
                declared_on = parsed
            else:
                challenge_on = parsed
        if declared_on and challenge_on and challenge_on < declared_on:
            v.append(Violation("D01", f"challenge_date ({challenge_on}) が declared_on ({declared_on}) より前です"))

    if filename:
        m = FILENAME_RE.match(filename)
        if m and declared_on and m.group(1) != declared_on.isoformat():
            v.append(Violation("N01", f"ファイル名の日付 {m.group(1)} と declared_on {declared_on} が一致しません"))

    first = next((line.strip() for line in body if line.strip()), "")
    if first != TITLE:
        v.append(Violation("F01", f"冒頭が {TITLE} ではありません: {first!r}"))

    sections, problems = split_sections(body)
    v.extend(Violation("F02", p) for p in problems)

    exclude_by_section = {
        SECTION_CHALLENGE: CHALLENGE_NOTES,
        SECTION_RISK: RISK_REASONS,
        SECTION_ACTIONS: (CLOSING_LINE,),
    }
    for heading, lines in sections.items():
        if not content_lines(lines, exclude_by_section.get(heading, ())):
            v.append(Violation("F03", f"{heading} の直下が空です"))

    if SECTION_GOAL in sections:
        goal_text = "\n".join(content_lines(sections[SECTION_GOAL]))
        if goal_text and not DIGIT_RE.search(goal_text):
            v.append(Violation("G01", "目標に数値がありません (件数・金額・人数のいずれかを数字で)"))

    if SECTION_CHALLENGE in sections:
        lines = sections[SECTION_CHALLENGE]
        stripped = {line.strip() for line in lines}
        for note in CHALLENGE_NOTES:
            if note not in stripped:
                v.append(Violation("C03", f"挑戦の注記がありません: {note}"))
        challenge_text = "\n".join(content_lines(lines, CHALLENGE_NOTES))
        if challenge_text:
            default_year = challenge_on.year if challenge_on else None
            found_dates = challenge_dates(challenge_text, default_year)
            if not found_dates:
                v.append(Violation("C01", "挑戦に実施日 (M月D日 か YYYY-MM-DD) がありません"))
            elif challenge_on and not any(
                (y in (None, challenge_on.year)) and mo == challenge_on.month and d == challenge_on.day
                for y, mo, d in found_dates
            ):
                v.append(Violation("D01", f"挑戦本文の日付が challenge_date ({challenge_on}) と一致しません"))
            if not HEADCOUNT_RE.search(challenge_text):
                v.append(Violation("C02", "挑戦に規模 (N人 / N名) がありません"))

    if SECTION_RISK in sections:
        parts, risk_problems = split_by_labels(sections[SECTION_RISK], RISK_REASONS)
        v.extend(Violation("R01", p) for p in risk_problems)
        for label, lines in parts.items():
            if not lines:
                v.append(Violation("R02", f"{label} の本文が空です"))
        money_lines = parts.get(MONEY_REASON)
        if money_lines:
            v.extend(Violation("M01", msg) for msg in check_money_reason("\n".join(money_lines)))

    if SECTION_ACTIONS in sections:
        lines = sections[SECTION_ACTIONS]
        items = parse_actions(lines)
        numbers = [n for n, _ in items]
        if numbers != list(range(1, ACTION_COUNT + 1)):
            v.append(Violation("A01", f"行うことは番号 1〜{ACTION_COUNT} の{ACTION_COUNT}項目にしてください (現在: {numbers})"))
        for n, item in items:
            if not item:
                v.append(Violation("A01", f"行うこと {n} の本文が空です"))
            hits = [stem for stem in SPIRIT_STEMS if stem in item]
            if hits:
                v.append(Violation("S01", f"行うこと {n} に精神論の語があります: {', '.join(hits)}"))
        if CLOSING_LINE not in {line.strip() for line in lines}:
            v.append(Violation("A02", f"締め文がありません: {CLOSING_LINE}"))

    if SECTION_REPORT in sections:
        report_text = "\n".join(content_lines(sections[SECTION_REPORT]))
        if report_text and not (REPORT_FREQUENCY_RE.search(report_text) or REPORT_TIMING_RE.search(report_text)):
            v.append(Violation("P01", "定期報告に頻度もタイミング (曜日・時刻) もありません"))

    body_text = "\n".join(body)
    for label, rx in PLACEHOLDER_RES:
        m = rx.search(body_text)
        if m:
            v.append(Violation("X01", f"未置換のプレースホルダ {label} が残っています: {m.group(0)!r}"))
    return v


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="挑戦宣言と企画の保存前後バリデーション")
    parser.add_argument("--file", required=True, type=Path)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2
    try:
        text = args.file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        sys.stderr.write(f"validate-challenge-output: ファイルを読めません: {exc}\n")
        return 2
    violations = validate(text, args.file.name)
    if violations:
        print(f"FAIL: {args.file} ({len(violations)} 件)")
        for item in violations:
            print(f"- {item}")
        return 1
    print(f"PASS: {args.file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
