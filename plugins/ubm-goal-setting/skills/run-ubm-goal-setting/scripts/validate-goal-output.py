#!/usr/bin/env python3
# /// script
# name: validate-goal-output
# version: 0.4.0
# purpose: 目標設定・振り返り対話の出力 Markdown を保存前に検証する決定論ゲート。
#          未展開プレースホルダ/ファイル名日付パターン/全角数字/差分+-表記/種別別必須見出し/
#          見出し重複/NG表現/やらないこと3項目以上/プロジェクト別タスク種別方針/行末の期日トークン/
#          貢献0の括弧3形/前回ブロックの初回マーカーと挽回の対応行/行動の見直し記録/日付索引 等を検査。
#          軌道修正記録の分割規則（split_revision_record）は validate-cross-level.py と共用する。
#          旧 validate-goal-output.sh 474 行の契約移植 (逐語移植ではない)。
#          --peer 指定時のみ、他層ファイルとの期アンカー2値の層間整合を WARN で報告する。
# inputs:
#   - fs: plugin references/action-language-policy.json（欠落・不正は終了コード2。--help は読まずに出す）
#   - argv: --file PATH --type weekly|monthly|quarterly|yearly (bimonthly は後方互換の別名)
#           [--peer PATH ...] (任意・複数可。層間整合の比較相手)
# outputs:
#   - stdout: PASS 詳細 / 結果サマリ
#   - stderr: 引数の誤り・入力を読めないときの ERROR 行（検査の FAIL 理由は stdout の FAIL 行に出す）
#   - exit: 0=PASS / 1=FAIL / 2=引数の誤り・--file や --peer が無い/ファイルでない/UTF-8 で読めない・語彙契約を読めない
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""目標設定出力 Markdown の保存前バリデーション。

旧 validate-goal-output.sh の契約移植。種別 (週報/月報/期報/1年) 別の必須見出し・NG表現・
やらないこと3項目以上・売上系フォーマット等を保存前に検査し違反を FAIL させる。
種別はファイル名推論でなく明示引数 --type (weekly/monthly/quarterly/yearly) を正本とする。
`yearly` は 4層 (1年 → 3ヶ月 → 1ヶ月 → 1週間) の最上位層で、期間語は「今年/前年」。
挑戦宣言 (05_Project/UBM/挑戦宣言/) を正本に、到達点をここへ置いて下位層へ割っていく。
`bimonthly` は quarterly の後方互換の別名として受理し続ける (期報=3ヶ月へ改定済み)。
ただし --type と本文のタイトル見出しラベルの不一致は error とする (種別の取り違え検出)。

`--peer PATH` を渡したときだけ他層のファイルを開き、期アンカー (今期の売上目標 /
今期の累計売上実績) を突き合わせる。不一致は WARN で、rc は変えない。
最重要数字はどの組でも比較しない (各層の売上とその内訳で、層ごとに値が違うのが正しい)。
--peer 未指定時のコードパスは従来と同一。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# 行動の精神論の語の唯一正本。プロフィールで既存の判定範囲を保つ。
ACTION_POLICY_PATH = Path(__file__).resolve().parents[3] / "references/action-language-policy.json"


def _load_goal_spirit_re() -> re.Pattern:
    policy = json.loads(ACTION_POLICY_PATH.read_text(encoding="utf-8"))
    terms = policy["goal_exact_phrases"]
    # 空白だけの語を許すと、空白を含むすべての行が精神論として FAIL になる。
    if not isinstance(terms, list) or not terms or any(not isinstance(term, str) or not term.strip() for term in terms):
        raise ValueError("goal_exact_phrases は空白だけでない文字列の配列である必要があります")
    return re.compile("|".join(re.escape(term) for term in terms))


# import の時点では止めない。語彙契約が壊れていても --help は出せるようにし、
# 検査を始める前に main が終了コード2で止める。
try:
    GOAL_SPIRIT_RE = _load_goal_spirit_re()
    ACTION_POLICY_ERROR = None
except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
    GOAL_SPIRIT_RE = None
    ACTION_POLICY_ERROR = f"{type(exc).__name__}: {exc}"

# --type -> kind (分岐キー)。期報=quarterly=3-月報（３ヶ月）。
# "bimonthly" は期報が2ヶ月だった頃の旧キー。新規は quarterly を正とし、旧キーも受理し続ける。
TYPE_MAP = {
    "weekly": "week",
    "monthly": "month",
    "quarterly": "period",
    "yearly": "year",       # 1年目標（挑戦宣言を正本とする最上位層）
    "bimonthly": "period",  # 後方互換の別名（旧2ヶ月期報の呼び出し・過去スクリプト用）
}

# --type -> 本文のタイトル見出しラベル。
# quarterly と bimonthly は kind がどちらも period なので、kind だけを見ると
# 「3ヶ月期報を --type bimonthly で検証」しても通ってしまう。種別の取り違えを
# 検出するために、元の --type の値とラベルの対応をここで正本として持つ。
TYPE_TITLE_LABEL = {
    "weekly": "1週間の目標",
    "monthly": "1ヶ月の目標",
    "quarterly": "3ヶ月の目標",
    "yearly": "1年の目標",
    "bimonthly": "2ヶ月の目標",
}

# 旧種別。取り違え時に「引数が古い」のか「ファイルが古い」のかを言い分けるために使う。
LEGACY_TYPES = {"bimonthly"}


def judge_sales_coverage(total: int, target: int) -> tuple[str, str]:
    """成果目標の売上貢献合計 total と、今期間の売上目標 target を突き合わせる。

    「この成果を達成したら、売上がここまで動く」という線が引けているかの判定。
    戻り値は (verdict, message)。verdict は次のいずれか:
      "ok"   … 線がつながっている（PASS を出す）
      "warn" … 疑わしいが保存は通す（WARN を出す。rc は変わらない）
      "fail" … 保存を止める（FAIL を出す。rc=1）
      "info" … 判定しない（情報行のみ出す）

    採用しているポリシー:
      1. 完全一致は求めない。`total >= target` を満たせば線はつながっている
        （超過は「成果の出しすぎ」ではなく、取りこぼし前提の積み増しでありうる）
      2. 未達は target の 5% 以内なら warn（端数・単価の丸めで生じる程度のズレ）
      3. それを超える未達は fail。線が引けないまま保存させない
      4. target が 0（売上目標を置かない期間）は判定せず info

    message には必ず total と target の実数を含める。差分だけだと、
    どちらが動いたのかが読めなくなる。
    """
    if target <= 0:
        return ("info", f"突合: 貢献合計 {total} / 売上目標 {target}（売上目標が無いため判定しない）")

    shortfall = target - total
    if shortfall <= 0:
        return ("ok", f"突合: 貢献合計 {total} / 売上目標 {target}（線がつながっている）")

    if shortfall <= target * 0.05:
        return (
            "warn",
            f"突合: 貢献合計 {total} / 売上目標 {target}（不足 {shortfall}）。"
            "端数程度のズレ。成果の単価・件数を見直すか、売上目標を置き直してください",
        )

    return (
        "fail",
        f"突合: 貢献合計 {total} / 売上目標 {target}（不足 {shortfall}）。"
        "成果目標が足りていません。この成果が全部出ても売上目標に届きません。"
        "相手を足すか、売上目標を置き直してください（行動を足してごまかさない）",
    )

# --- 層間整合（--peer）用の期アンカー定義 ---
# references/data-contract.md が「期アンカー・全レベル同値」と定めている値。
# 週報/月報/期報のどの層でも同じ値でなければならないが、継承は inherited_context の
# 作成時 pull（一方向）しかなく、上位確定後に下位へ push する経路が無い。しかも実際の
# 作成順は下位が先になることがあるので、正しく運用しても最低1回はズレる。
# そのため不一致は FAIL でなく WARN とし、気づかせるだけにする。
#
# (アンカー名, 見出しの正規表現, 値の型) 値の型: "number" | "text"
PEER_ANCHORS = [
    ("今期の売上目標", r"^## 【今期の売上目標】", "number"),
    ("今期の累計売上実績", r"^## 【今期の累計売上実績】", "number"),
]

# 【今(週|月|期|年)の最重要数字】は、どの組でも一致検査の対象にしない。各層の最重要数字は、
# その層の売上（月報・期報は `今(月|期)の売上目標：` の1行）と、その売上につながる人数・件数の内訳で、
# 層ごとに値が違うのが正しい（例: 期「今期の売上目標：1000000」と「困りごとを解決した件数：6件」に対して
# 週「- [ ] 今週の売上：150000」と「- [ ] 提案の受諾・月額顧問の成約：2件」）。旧版は月報・期報の組だけを比べていたが、月報に当月の売上を
# 置いた（確定事項Q）ので、その組も正しい書き方が毎回 WARN になる。1年の到達点（#0a/#0b）の
# 継承は validate-cross-level.py が rc を持って照合する。比べていないことが分かるよう、peer ごとに
# この SKIP 行を印字し、分母には入れない。
KEY_NUMBER_SKIP_NOTE = (
    "  SKIP: 最重要数字（各層の売上とその内訳のため一致検査の対象外。"
    "1年の到達点は validate-cross-level.py で照合）"
)

# 値ではなく注釈である行。継承元の記載や補足は値として拾わない。
_NOTE_PREFIXES = ("（", "(", "※")


def _section_body(lines: list[str], head_rx: str) -> list[str] | None:
    """`head_rx` に一致する最初の見出しの本文（次の ^## まで）を返す。無ければ None。"""
    rx = re.compile(head_rx)
    n = len(lines)
    for i, line in enumerate(lines):
        if rx.search(line):
            j = i + 1
            body = []
            while j < n and not lines[j].startswith("## "):
                body.append(lines[j])
                j += 1
            return body
    return None


def _content_lines(body: list[str]) -> list[str]:
    """空行・区切り線・注釈行を除いた本文行。"""
    out = []
    for l in body:
        s = l.strip()
        if not s or re.match(r"^-{3,}$", s):
            continue
        if s.startswith(_NOTE_PREFIXES):
            continue
        out.append(s)
    return out


def _bullet_text(line: str) -> str | None:
    """箇条書き行なら記号を外した本文を、箇条書きでなければ None を返す。"""
    s = line.strip()
    m = re.match(r"^(?:[*-] |・)\s*(.*)$", s)
    return m[1].strip() if m else None


def _norm_name(name: str) -> str:
    """項目名の照合キー。空白と強調記号だけを落とす（同義の判定はしない）。"""
    return re.sub(r"[\s　]+", "", name).strip("*")


# 前回正本が無い初回に、前回ブロックの各欄へ置く1行（共通部品D）。
INITIAL_MARKER = "初回（前回正本なし）"

# 軌道修正記録（共通部品E）の種類ごとの欄。validate-cross-level.py もこの定義と
# split_revision_record を読み込んで使う。同じ記録を2つの検査器が別々の規則で割ると、
# 片方だけが通る行が生まれる。
REVISION_RECORD_FIELDS = {
    "上位配分の見直し": ("上位計画", "実行目標", "理由", "上位への影響"),
    "行動の見直し": ("変更前", "変更後", "理由", "上位への影響"),
}


def split_revision_record(body: str, record_kind: str) -> tuple[str, dict[str, str] | None] | None:
    """`{種類}：{対象}｜欄：値｜…` の1行（箇条書き記号は外したもの）を割る。

    Returns:
        種類の語で始まらない行は None。
        それ以外は (対象, 欄)。対象が読めなければ対象は空文字。欄は
        REVISION_RECORD_FIELDS の欄名がちょうど各1件・空欄なしのときだけ dict、
        そうでなければ None（呼び出し側が「欄の不備」として報告する）。
    """
    if not body.startswith(record_kind):
        return None
    parts = re.split(r"[｜|]", body)
    first = re.fullmatch(re.escape(record_kind) + r"[：:]\s*(.+)", parts[0].strip())
    if not first:
        return "", None
    target = first[1].strip()
    required = REVISION_RECORD_FIELDS[record_kind]
    fields: dict[str, str] = {}
    for part in parts[1:]:
        pair = re.fullmatch(r"([^：:]+)[：:]\s*(.*)", part.strip())
        if pair and pair[1].strip() not in fields:
            fields[pair[1].strip()] = pair[2].strip()
    if len(parts) != len(required) + 1 or set(fields) != set(required) or not all(fields.values()):
        return target, None
    return target, fields


def extract_peer_anchors(text: str) -> dict[str, str | None]:
    """期アンカー2値を正規化して取り出す。見つからない項目は None（＝比較対象外）。"""
    lines = text.split("\n")
    result: dict[str, str | None] = {}
    for name, head_rx, kind in PEER_ANCHORS:
        body = _section_body(lines, head_rx)
        result[name] = None if body is None else _normalize_anchor(_content_lines(body), kind)
    return result


def _normalize_anchor(content: list[str], kind: str) -> str | None:
    if not content:
        return None
    if kind == "number":
        for l in content:
            m = re.search(r"[0-9][0-9,]*", l)
            if m:
                return m.group(0).replace(",", "")
        return None
    # text: 先頭の箇条書き記号・チェックボックスを落として比較する
    first = re.sub(r"^(?:[*-]\s*(?:\[[ xX]\]\s*)?|・)", "", content[0]).strip()
    return first or None


class Validator:
    def __init__(self, text: str, basename: str, kind: str, type_name: str = "",
                 peers: list[tuple[str, str]] | None = None):
        self.lines = text.split("\n")
        self.text = text
        self.basename = basename
        self.kind = kind  # week | month | period
        # 本文中の記述では切り替えない。月報の frontmatter で明示した場合だけ適用。
        frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
        self.concise_monthly = kind == "month" and bool(
            frontmatter and re.search(
                r"^monthly_action_style:\s*concise\s*$", frontmatter[1], re.M
            )
        )
        # 元の --type の値。kind へ潰す前の値で、ラベル照合の正本。
        self.type_name = type_name or next(
            (t for t, k in TYPE_MAP.items() if k == kind), ""
        )
        # (表示名, 本文) の並び。空（既定）なら層間整合チェックは一切走らない。
        self.peers = peers or []
        self.errors = 0
        self.warnings = 0

    def fail(self, msg: str) -> None:
        print(f"FAIL: {msg}")
        self.errors += 1

    def warn(self, msg: str) -> None:
        print(f"WARN: {msg}")
        self.warnings += 1

    def ok(self, msg: str) -> None:
        print(f"PASS: {msg}")

    def check_key_number_sales_line(self) -> None:
        """月報・期報の最重要数字にある売上の1行が、その層の売上目標と同じ値かを照合する。

        最重要数字は、その層の売上と、その売上に至る人数・回数・件数を置く節で、
        売上の行（`今月の売上目標：{金額}` / `今期の売上目標：{金額}`）は
        【今(月|期)の売上目標】の値を写す。写し間違えると、毎日見る数字と目標の金額が
        食い違ったまま運用されるのに、どの検査も赤くならなかった。
        月報は節を置くのが既定（無ければ WARN）、期報は任意（無ければ何もしない）。
        週報・1年は最重要数字の書き方が違う（週は `- [ ]` 形式、1年は到達点）ので対象外。
        """
        if self.kind not in ("month", "period"):
            return
        word = self._period_word()
        body = _section_body(self.lines, r"^## 【" + word + r"の最重要数字】")
        if body is None:
            if self.kind == "month":
                self.warn(f"【{word}の最重要数字】が無い（`{word}の売上目標：{{金額}}` の1行と、"
                          "その売上に至る人数・回数・件数を置く）")
            return
        # 行頭の `- ` `- [ ] ` `・` は validate-cross-level.py の _BULLET と同じく読み飛ばす
        rx = re.compile(r"^\s*(?:[*-]\s*(?:\[[ xX]\]\s*)?|・\s*(?:\[[ xX]\]\s*)?)?"
                        + word + r"の売上目標[：:]\s*([0-9][0-9,]*)\s*円?\s*$")
        amounts = [int(m.group(1).replace(",", "")) for m in map(rx.match, body) if m]
        if not amounts:
            self.fail(f"【{word}の最重要数字】に `{word}の売上目標：{{金額}}` の1行が無い"
                      f"（金額は【{word}の売上目標】と同じ値を半角数字で）")
            return
        target = self._current_sales_target()
        if target is None:
            return  # 売上目標そのものの欠落は check_goal_section が FAIL にする
        wrong = [a for a in amounts if a != target]
        if wrong:
            self.fail(f"【{word}の最重要数字】の `{word}の売上目標：{wrong[0]}` が"
                      f"【{word}の売上目標】の {target} と違う（同じ値を写す）")
        else:
            self.ok(f"【{word}の最重要数字】の売上の行が【{word}の売上目標】と一致（{target}）")

    def check_report_alignment(self) -> None:
        """前期間の項目落ちと、月報の二重管理の数量・単位・期日ずれを検査する。

        前回ブロック（前回の目標→実績→差分）の項目一致は週報・月報・期報・1年で共通。
        自然言語の同義判定や人数の推定はしない。項目名・順序・数値トークンを
        比較し、自然言語で書かれた対象の意味は生成時のレビューに残す。
        """
        previous_word = {"week": "前週", "month": "前月", "period": "前期", "year": "前年"}.get(self.kind)
        if previous_word is None:
            return

        def section(label):
            # 行動の管理用見出しだけが（行動管理）等の補足を持つ。
            base = label.removesuffix("（提出）")
            suffix = "（提出）" if label.endswith("（提出）") else ""
            extra = r"(?:（行動管理[^）]*）)?" if "行動" in base else ""
            matches = self.sections_by_regex("【" + re.escape(base) + extra + re.escape(suffix) + "】")
            return matches[0][1] if matches else None

        def items(lines):
            return [re.sub(r"^([*-] |・)\s*(\[[ xX]\]\s*)?", "", line).strip()
                    for line in (lines or []) if self._is_bullet(line)]

        def key(item):
            return re.sub(r"\s+", "", re.split(r"[：:]", item, maxsplit=1)[0]).strip("*")

        def signature(item):
            # 人数と期日の月を入れ替えても同じ数字の袋になる、という誤一致を防ぐ。
            text = re.sub(r"(?<=\d),(?=\d)", "", item)
            dates = re.findall(r"(?<!\d)(?:\d{4}[-/])?\d{1,2}[-/]\d{1,2}(?!\d)", text)
            normalized_dates = tuple(tuple(int(n) for n in re.split(r"[-/]", date)) for date in dates)
            text = re.sub(r"(?<!\d)(?:\d{4}[-/])?\d{1,2}[-/]\d{1,2}(?!\d)", "", text)
            quantities = tuple(re.findall(
                r"([+-]?\d+(?:\.\d+)?)\s*(ヶ月|か月|時間|人|名|件|回|社|円|通|分|日|週|月|年)?\s*(以上|以下|未満|超)?", text
            ))
            # 数字を持たない期日（各回翌日・毎週金曜等）も省略・変更しない。
            deadline = re.search(r"期日\s*(.*)$", text)
            relative_deadline = re.sub(r"\s+", "", deadline[1]) if deadline else ""
            return normalized_dates, quantities, relative_deadline

        def named(entries):
            return all(re.search(r"[：:]", i) for i in entries)

        def is_initial(body):
            content = _content_lines(body or [])
            return len(content) == 1 and _bullet_text(content[0]) == INITIAL_MARKER

        marker_hint = f"初回は `- {INITIAL_MARKER}` の1行"

        # 売上の欄（数値1つ）も前回ブロックの一部。空欄は転記漏れで、初回はマーカーを置く。
        for suffix in ("", "（提出）"):
            for tail in ("目標", "実績", "目標と実績の差分"):
                label = f"{previous_word}の売上{tail}{suffix}"
                body = section(label)
                if body is not None and not _content_lines(body):
                    self.fail(f"前回ブロック: 【{label}】が空です（前回の値を転記する。{marker_hint}）")

        # 前期間の目標・実績・差分は、提出用（月報だけ）と管理用それぞれで全項目を保持する。
        for family in ("売上以外の成果", "行動"):
            for suffix in ("", "（提出）"):
                tails = ("目標", "実績", "目標と実績の差分")
                labels = [f"{previous_word}の{family}{tail}{suffix}" for tail in tails]
                target_body = section(labels[0])
                if target_body is None:
                    continue  # 見出しの有無は必須見出しの検査が担う（提出用は行動ブロックを持たない）。
                if is_initial(target_body):
                    for label in labels[1:]:
                        body = section(label)
                        if body is not None and not is_initial(body):
                            self.fail(f"前期間の項目一致: 【{labels[0]}】が初回なので【{label}】も `- {INITIAL_MARKER}` の1行にしてください")
                    self.ok(f"前期間の項目一致: 【{labels[0]}】は初回（前回正本なし）のため照合しない")
                    continue
                if not _content_lines(target_body):
                    self.fail(f"前期間の項目一致: 【{labels[0]}】が空です（前回の目標を転記する。{marker_hint}）")
                    continue
                # 目標に項目があるのに実績・差分の欄が無いと、項目ごとの対応が取れない。
                # 提出用は差分の欄を持たない既定テンプレートなので、差分だけは求めない。
                for tail, label in zip(tails[1:], labels[1:]):
                    if section(label) is None and not (suffix and tail == "目標と実績の差分"):
                        self.fail(f"前期間の項目一致: 【{labels[0]}】に項目があるのに【{label}】がありません")
                reference = items(target_body)
                if not reference or not named(reference):
                    self.warn(f"前期間の項目一致: 【{labels[0]}】は項目名のない旧形式のため未照合")
                    continue
                expected = [key(i) for i in reference]
                if len(set(expected)) != len(expected):
                    self.fail(f"前期間の項目一致: 【{labels[0]}】に重複した項目名があります")
                for label in labels[1:]:
                    body = section(label)
                    if body is None:
                        continue  # 欄の欠落は上で報告済み（提出用の差分は対象外）。
                    if not _content_lines(body):
                        self.fail(f"前期間の項目一致: 【{label}】が空です（確認中も項目ごとに残す）")
                        continue
                    actual_items = items(body)
                    if actual_items and not named(actual_items):
                        self.warn(f"前期間の項目一致: 【{label}】は項目名のない旧形式のため未照合")
                    elif [key(i) for i in actual_items] != expected:
                        self.fail(f"前期間の項目一致: 【{label}】の項目名・順序を【{labels[0]}】に揃えてください（確認中も項目ごとに残す）")

        if self.kind != "month":
            return  # 提出用・管理用の二重構造は月報だけ。

        # 説明の省略は許すが、同じ項目の数値・期日は省略・変更しない。
        for label in ("前月の売上目標", "前月の売上実績", "今月の売上目標",
                      "前月の売上以外の成果目標", "前月の売上以外の成果実績",
                      "前月の行動目標", "前月の行動実績",
                      "今月の売上以外の成果目標", "今月の行動目標"):
            managed, submitted = section(label), section(label + "（提出）")
            if managed is None or submitted is None:
                continue
            if is_initial(managed) and is_initial(submitted):
                continue  # 両方とも初回マーカー。照合する値が無い。
            left, right = items(managed), items(submitted)
            if label in ("前月の売上目標", "前月の売上実績", "今月の売上目標"):
                # 売上欄の正本は総額。表示側の内訳だけを省略しても不一致ではない。
                managed_total = self._first_sales_amount(managed)
                submitted_total = self._first_sales_amount(submitted)
                if managed_total is None or submitted_total is None:
                    self.warn(f"月報同期: 【{label}】の総額を読み取れないため未照合")
                elif managed_total != submitted_total:
                    self.fail(f"月報同期: 【{label}】の提出用と管理用の総額が異なります")
                if not left or not right:
                    continue  # 内訳は両方にある場合だけ、項目・数量を照合する。
            if not left and not right:
                if signature("\n".join(managed)) != signature("\n".join(submitted)):
                    self.fail(f"月報同期: 【{label}】の提出用と管理用の数値が異なります")
                continue
            # 管理用は成果ごとのグループ順。行動は順序ではなく項目名で照合する。
            if named(left + right):
                left_keys, right_keys = [key(i) for i in left], [key(i) for i in right]
                keys_match = (sorted(left_keys) == sorted(right_keys) if label == "今月の行動目標"
                              else left_keys == right_keys)
                if not keys_match or len(set(left_keys)) != len(left_keys):
                    self.fail(f"月報同期: 【{label}】の提出用と管理用の項目が異なります")
                    continue
                pairs = [(i, next(j for j in right if key(j) == key(i))) for i in left]
            else:
                self.warn(f"月報同期: 【{label}】は項目名のない旧形式のため未照合（項目名：内容 に揃えてください）")
                pairs = []
            for a, b in pairs:
                if signature(a) != signature(b):
                    self.fail(f"月報同期: 【{label}】「{key(a)}」の数量・単位・期日が提出用と管理用で異なります")

        # 明確に結果を数えるラベルだけを検出。一般の動詞の推測で誤判定しない。
        for label in ("今月の行動目標（提出）", "今月の行動目標（行動管理・優先順位付き）"):
            for item in items(section(label)):
                if re.match(r"(?:初回の無料相談の実人数|面談の実人数|再面談の実人数|紹介してくださった人数|新規成約件数)[：:]", item):
                    self.fail(f"月報の成果・行動分離: 結果を数える項目は成果目標へ移してください: {item}")

    # --- 期日トークン（共通部品A）---
    # 行末が `期日` ＋任意の空白＋トークン＋任意の `まで`／`までに` で終わること。
    # `今週` は週報だけのトークン（月報以上で書くと、どの週かが決まらない）。
    # `毎月`・`今月中` はトークンではない（月の中のいつかが決まらない）。
    DEADLINE_TOKEN = (r"[0-9]{1,2}/[0-9]{1,2}(?:（[月火水木金土日]）)?|[0-9]{4}-[0-9]{2}-[0-9]{2}"
                      r"|[月火水木金土日]曜(?:日)?|毎日|毎朝|毎週(?:[月火水木金土日]曜(?:日)?)?")

    def _deadline_rx(self) -> re.Pattern:
        token = self.DEADLINE_TOKEN + ("|今週" if self.kind == "week" else "")
        return re.compile(r"期日\s*(?:" + token + r")(?:までに|まで)?\s*$")

    def _deadline_hint(self) -> str:
        week = "・今週" if self.kind == "week" else ""
        return ("行末を `期日` ＋ M/D（後ろに（曜）可）・YYYY-MM-DD・{月〜日}曜・毎日・毎朝・"
                f"毎週（後ろに{{曜}}曜 可）{week} ＋任意の まで／までに で終える。毎月・今月中はトークンではない")

    # --- 前回ブロックの挽回（共通部品D）---
    # `- {前回の項目名}：{起点}→{到達点}（今回の行動目標「{今回の項目名}」で実行）`
    RECOVERY_LINE_RX = re.compile(
        r"^(?:[*-] |・)(?P<prev>[^：:]+?)[：:](?P<start>.+?)→(?P<goal>.+?)"
        r"（今回の行動目標「(?P<item>[^」]+)」で実行）\s*$"
    )
    RECOVERY_FORM = "`- {前回の項目名}：{起点}→{到達点}（今回の行動目標「{今回の項目名}」で実行）`"

    def check_recovery_lines(self) -> None:
        """「…未達を挽回するための行動」の対応行を検査する（4層・月報は提出用と管理用の両方）。

        対象は見出しの直下から最初の `###` まで。要因分析の `###` 小見出し以下は対象外。
        挽回の中身の妥当性（起点・到達点が足りるか）はレビューに残し、ここでは
        「今回のどの行動目標で実行するか」が実在する行動へつながっていることだけを見る。
        """
        names = self._current_action_names()
        deadline_in_text = re.compile(r"期日\s*(?:" + self.DEADLINE_TOKEN + r"|今週)")
        checked = 0
        for start, body in self.sections_by_regex("未達を挽回するための行動"):
            heading = self.lines[start].strip()
            head_lines: list[str] = []
            for line in body:
                if re.match(r"^#{3,6}\s", line):
                    break
                head_lines.append(line)
            content = _content_lines(head_lines)
            if not content:
                self.fail(f"挽回の対応行: {heading} が空です（未達が無ければ `- なし`、初回は `- {INITIAL_MARKER}`）")
                continue
            for line in content:
                checked += 1
                text = _bullet_text(line)
                if text in ("なし", INITIAL_MARKER):
                    if len(content) > 1:
                        self.fail(f"挽回の対応行: {heading} の `- {text}` はほかの行と並べられません")
                    continue
                m = self.RECOVERY_LINE_RX.match(line)
                if m is None:
                    self.fail(f"挽回の対応行: {heading} の行は {self.RECOVERY_FORM} か `- なし` か "
                              f"`- {INITIAL_MARKER}` で書いてください: {line}")
                    continue
                # 「判断期日の確認」のような語は期日ではない。`期日` ＋トークンの形だけを見る。
                if deadline_in_text.search(m["prev"] + m["start"] + m["goal"]):
                    self.fail(f"挽回の対応行: 期日は今回の行動目標の側にだけ書きます（挽回行には書かない）: {line}")
                if _norm_name(m["item"]) not in names:
                    self.fail(f"挽回の対応行: 「{m['item']}」が今回の行動目標の項目名にありません: {line}")
        if checked:
            print(f"INFO: 挽回の対応行 {checked} 行を照合しました（今回の行動目標の項目名 {len(names)} 件）")

    # --- 軌道修正記録（共通部品E）---
    def _check_action_revision(self, body: str, names: set[str], where: str) -> None:
        target, fields = split_revision_record(body, "行動の見直し")
        form = "`- 行動の見直し：{項目名}｜変更前：…｜変更後：…｜理由：…｜上位への影響：…`"
        if not target:
            self.fail(f"行動の見直し: {where} に項目名がありません（{form}）: {body}")
        elif fields is None:
            self.fail(f"行動の見直し: {where} の「{target}」は変更前・変更後・理由・上位への影響を各1件、空欄なく書いてください（{form}）")
        elif _norm_name(target) not in names:
            self.fail(f"行動の見直し: {where} の「{target}」が今回の行動目標の項目名にありません")
        elif _norm_name(fields["変更前"]) == _norm_name(fields["変更後"]):
            self.fail(f"行動の見直し: {where} の「{target}」は変更前と変更後が同じで、見直しを確認できません")
        else:
            self.ok(f"行動の見直し: {where} の「{target}」")

    def check_revision_records(self) -> None:
        """週報の【今週の見直し記録】と、月報の冒頭の【確認された情報】の行動の見直しを検査する。

        理由・上位への影響の妥当性はレビューに残す。ここで見るのは欄がそろっていること、
        項目名が今回の行動目標に実在すること、変更前と変更後が違うことだけ。
        上位配分の見直しの数値の対応は validate-cross-level.py が照合する。
        """
        names = self._current_action_names()
        if self.kind == "week":
            for _, body in self.sections_by_regex(r"【今週の見直し記録】"):
                content = _content_lines(body)
                where = "【今週の見直し記録】"
                if not content:
                    self.fail(f"{where} が空です（見直しが無い週は `- なし`）")
                    continue
                for line in content:
                    text = _bullet_text(line)
                    if text == "なし":
                        if len(content) > 1:
                            self.fail(f"{where} の `- なし` はほかの行と並べられません")
                        continue
                    if text is not None and text.startswith("行動の見直し"):
                        self._check_action_revision(text, names, where)
                        continue
                    if text is not None and text.startswith("上位配分の見直し"):
                        target, fields = split_revision_record(text, "上位配分の見直し")
                        if not target or fields is None:
                            self.fail(f"{where} の上位配分の見直しは対象・上位計画・実行目標・理由・上位への影響を各1件、空欄なく書いてください: {line}")
                        continue
                    self.fail(f"{where} の行は `- なし` か `- 行動の見直し：…` か `- 上位配分の見直し：…` で書いてください: {line}")
        elif self.kind == "month":
            for start, body in self.sections_by_regex(r"【確認された情報】"):
                where = self.lines[start].strip()
                for line in _content_lines(body):
                    text = _bullet_text(line)
                    text = line if text is None else text
                    if text.startswith("行動の見直し"):
                        self._check_action_revision(text, names, where)

    # --- 日付索引（共通部品A）---
    # `- {M/D（曜）}：{項目名}、{項目名}｜やらない：{内容}`（行動の無い日は `- {M/D（曜）}：なし｜やらない：{内容}`）
    DATE_INDEX_RX = re.compile(
        r"^(?:[*-] |・)(?P<date>[0-9]{1,2}/[0-9]{1,2}（[月火水木金土日]）)[：:]\s*(?P<items>.+?)"
        r"(?:\s*[｜|]\s*やらない[：:]\s*(?P<notdo>.*?))?\s*$"
    )
    DATE_INDEX_FORM = "`- {M/D（曜）}：{項目名}、{項目名}｜やらない：{内容}`"

    def _project_task_names(self) -> set[str]:
        lines = self.sed_range("【プロジェクト別タスク】", r"^## ")
        return {self._item_name(l) for l in lines
                if re.match(r"^(?:- |・)\[[ xX]\]", l) and self._item_name(l)}

    def check_date_index(self) -> None:
        """週報の【今週の大きな到達ライン】と月報の【今月の日別タスク】を日付索引として検査する。

        済／未済のチェックは行動目標の行だけに付ける（週の正本は行動目標）。索引は
        「どの日にどの行動目標を進めるか」を引くための目次なので、チェックボックスを
        持たず、項目名は同じ文書の行動目標（月報は【プロジェクト別タスク】も）に実在すること。
        """
        if self.kind == "week":
            label, allowed = "今週の大きな到達ライン", self._current_action_names()
        elif self.kind == "month":
            label = "今月の日別タスク"
            allowed = self._current_action_names() | self._project_task_names()
        else:
            return
        checked = 0
        for _, body in self.sections_by_regex("【" + re.escape(label) + "】"):
            for raw in body:
                if not re.match(r"^\s*(?:[*-] |・)", raw):
                    continue
                line = raw.strip()
                checked += 1
                if raw != raw.lstrip():
                    self.fail(f"日付索引: 【{label}】は入れ子にしません（1日1行の {self.DATE_INDEX_FORM}）: {line}")
                    continue
                if re.match(r"^(?:[*-] |・)\s*\[[ xX]\]", line):
                    self.fail(f"日付索引: 【{label}】にチェックボックスは付けません（済／未済は行動目標の行で付ける）: {line}")
                    continue
                m = self.DATE_INDEX_RX.match(line)
                if m is None:
                    self.fail(f"日付索引: 【{label}】の行は {self.DATE_INDEX_FORM} で書いてください: {line}")
                    continue
                if m["items"].strip() == "なし":
                    if not (m["notdo"] or "").strip():
                        self.fail(f"日付索引: 行動の無い日は `- {{M/D（曜）}}：なし｜やらない：{{内容}}` で書いてください: {line}")
                    continue
                if m["notdo"] is not None and not m["notdo"].strip():
                    self.fail(f"日付索引: `｜やらない：` の後が空です: {line}")
                for item in m["items"].split("、"):
                    if _norm_name(item) not in allowed:
                        self.fail(f"日付索引: 【{label}】の「{item.strip()}」が行動目標の項目名にありません: {line}")
        if checked:
            print(f"INFO: 日付索引 {checked} 行を照合しました（参照できる項目名 {len(allowed)} 件）")

    # --- セクション抽出ヘルパ ---
    def sections_by_regex(self, pattern: str):
        """`^## .*{pattern}.*` に一致する見出しの本文 (次の ^## まで) を列挙。"""
        rx = re.compile(r"^## .*" + pattern + r".*")
        out = []
        n = len(self.lines)
        for i, line in enumerate(self.lines):
            if rx.search(line):
                j = i + 1
                while j < n and not self.lines[j].startswith("## "):
                    j += 1
                out.append((i, self.lines[i + 1:j]))
        return out

    def capture_awk(self, pred) -> list[str]:
        """awk '/^## /{if(pred)f=1;next; else f=0} f' 相当。複数節を累積。"""
        f = False
        out: list[str] = []
        for line in self.lines:
            if line.startswith("## "):
                if pred(line):
                    f = True
                    continue
                f = False
            if f:
                out.append(line)
        return out

    def capture_from_start(self, start_rx: str) -> list[str]:
        """awk '/{start}/{f=1;next} /^## /{f=0} f' 相当 (任意の ^## で停止)。"""
        rx = re.compile(start_rx)
        f = False
        out: list[str] = []
        for line in self.lines:
            if rx.match(line):
                f = True
                continue
            if line.startswith("## "):
                f = False
            if f:
                out.append(line)
        return out

    def sed_range(self, start_sub: str, end_rx: str) -> list[str]:
        """sed -n '/start_sub/,/end_rx/p' 相当 (start は部分一致, end は正規表現, 両端含む)。"""
        rx_end = re.compile(end_rx)
        out: list[str] = []
        active = False
        for line in self.lines:
            if not active:
                if start_sub in line:
                    active = True
                    out.append(line)
                continue
            out.append(line)
            if rx_end.search(line):
                break
        return out

    # --- 各チェック ---
    def check_require_exact(self, label: str) -> None:
        rx = re.compile(r"^## 【" + re.escape(label) + r"】[ \t]*$")
        if any(rx.search(l) for l in self.lines):
            self.ok(f"必須見出し「## 【{label}】」")
        else:
            self.fail(f"必須見出し「## 【{label}】」がありません（完全一致）")

    # 旧 check_require_prefix は check_title_matches_type に統合した。
    # 旧 check_require_prefix の prefix_any 引数は「3ヶ月」「2ヶ月」の両方を無条件に受理するため、--type の取り違えを
    # 検出できなかった（同じ3ヶ月期報が quarterly でも bimonthly でも PASS していた）。

    def has_title(self, label: str) -> bool:
        return any(l.startswith(f"## 【{label}】") for l in self.lines)

    def check_title_matches_type(self) -> None:
        """--type と本文のタイトル見出しラベルが一致することを要求する。

        不一致は error。読みの後方互換（旧2ヶ月期報を --type bimonthly で再検証）は
        ラベル側も旧表記なので通る。
        """
        expected = TYPE_TITLE_LABEL.get(self.type_name)
        if expected is None:
            return
        if self.has_title(expected):
            self.ok(f"必須タイトル見出し「## 【{expected}】…」")
            return

        other = next(
            (t for t, lbl in TYPE_TITLE_LABEL.items()
             if t != self.type_name and self.has_title(lbl)),
            None,
        )
        if other is None:
            self.fail(f"必須タイトル見出し「## 【{expected}】」がありません")
            return

        if self.type_name in LEGACY_TYPES:
            hint = f"引数側が旧種別です。現行のファイルは --type {other} で検証してください"
        elif other in LEGACY_TYPES:
            hint = f"ファイル側が旧種別です。旧ファイルを再検証するなら --type {other} を指定してください"
        else:
            hint = f"--type {other} を指定してください"
        self.fail(
            f"--type {self.type_name}（【{expected}】）で検証していますが、"
            f"本文のタイトル見出しは「## 【{TYPE_TITLE_LABEL[other]}】…」です（{hint}）"
        )

    def check_section_optional(self, section: str) -> None:
        if section in self.text:
            self.ok(f"セクション「{section}」")
        else:
            self.warn(f"セクション「{section}」がありません（任意）")

    def check_goal_section(self, pattern: str, label: str, mode: str) -> None:
        for start, body in self.sections_by_regex(pattern):
            if mode == "numeric":
                table_hit = has_markdown_table(body)
                subhead_hit = [l for l in body if re.match(r"^### ", l)]
                if table_hit or subhead_hit:
                    self.fail(
                        f"売上系セクション「{label}」に表またはサブ見出しが含まれています（数値1つのみ許可）"
                    )
                # 区切り線 `---` は次セクションとの境界であって本文ではない。
                # 数えると「1,000,000 + ---」で常に2行になり、正しい形が警告になる。
                non_empty = [
                    l for l in body
                    if not re.match(r"^\s*$", l)
                    and not l.startswith("（")
                    and not re.match(r"^\{\{.*\}\}$", l)
                    and not re.match(r"^\s*-{3,}\s*$", l)
                ]
                if len(non_empty) > 1:
                    self.warn(f"売上系セクション「{label}」が複数行になっています（数値1つのみ推奨）")
            elif mode == "bullet":
                table_hit = has_markdown_table(body)
                if table_hit:
                    self.fail(f"「{label}」セクションに Markdown 表が含まれています（箇条書きのみ許可）")

    # --- 逆算チェーン（売上 → 成果 → 行動）ヘルパ ---

    # --- シンプルさの上限 ---
    # 週報は実行を絞るため件数も上限。長期3層は独立項目を保持し、件数は推奨とする。
    # 文章量は件数削減でなく、各項目の短さで抑える。
    MAX_OUTCOME_ITEMS = 5      # 成果目標の件数
    MAX_OUTCOME_CHARS = 50     # 成果目標1項目の本体（`→ 売上貢献` の前まで）
    MAX_ACTION_ITEMS = 8       # 行動目標の件数
    MAX_ACTION_CHARS = 60      # 行動目標1項目の本体（1行目・期日込み）

    # 成果目標セクションに置いてはいけない「実行完了型」の語尾。
    # 実行した時点で達成になってしまうものは成果ではなく行動なので、行動目標側へ移す。
    OUTCOME_NG_VERBS = (
        "実施する", "開催する", "参加する", "送付する", "作成する",
        "提出する", "共有する", "告知する", "打診する", "連絡する",
    )

    @staticmethod
    def _is_bullet(line: str) -> bool:
        return bool(re.match(r"^([*-] |・)", line))

    @staticmethod
    def _outcome_key(item: str) -> str:
        """成果目標の1項目から参照キー（`：` の前の対象名）を取り出す。"""
        body = re.sub(r"^([*-] |・)\s*", "", item)
        body = re.split(r"→", body)[0]
        body = re.split(r"[：:]", body)[0]
        return body.strip().strip("*").strip()

    @staticmethod
    def _ref_matches_key(ref: str, key: str) -> bool:
        """行動目標の参照 `ref` が、成果目標のキー `key` を指しているか判定する。

        C5（実在しない成果目標を参照していないか）と C6（どの行動からも支えられて
        いない成果目標が無いか）は、同じ「参照が成果を指す」関係を逆向きに見ている
        だけである。両者が別々の判定式を持つと、`ref="田所"` / `key="田所さん"` の
        ような入力で「C5 は実在すると言い、C6 は支えられていないと言う」相反した
        2行が同時に出る。そのため一致判定はこの1つの述語に集約する。

        Args:
            ref: 行動目標の `→ 支える成果目標：` に書かれた1つの参照名
                 （`・` 区切りは呼び出し側で分解済み。`（土台）` 等の免除も処理済み）
            key: 成果目標1項目から取り出した対象名（`_outcome_key` の戻り値）

        Returns:
            ref が key を指しているとみなせるなら True

        採用しているポリシー: 空白を落としたうえでの完全一致。
        部分一致を許すと `→ 支える成果目標：さん` があらゆるキーに一致してしまい、
        「実在する成果目標を指すこと」という契約が空洞化する。略記を許したくなったら、
        略記側ではなく成果目標のキーそのものを短くするのが正しい直し方。
        """
        def norm(s: str) -> str:
            return re.sub(r"[\s　]+", "", s).strip("*")

        return bool(norm(ref)) and norm(ref) == norm(key)

    @staticmethod
    def _outcome_head(item: str) -> str:
        """成果目標の1項目から本文（`→` より前）だけを取り出す。

        `→ 売上貢献：0（無料相談を支える）` のような理由欄は
        自由記述であり、実行完了型の判定対象にしてはいけない。C1 が理由を書けと
        要求しているのに C2 がその理由で FAIL させる、という自家撞着を避ける。
        """
        head = re.sub(r"^([*-] |・)\s*", "", item)
        return re.split(r"→", head)[0].strip()

    # kind -> 今期間を指す語。週報では【今期の売上目標】は期アンカー（3ヶ月分）であって
    # 今週の売上目標ではない。ここを `今(週|月|期)` で緩く拾うと、週報で期アンカーの側を
    # 掴んで突合が壊れるので、種別ごとに1語へ固定する。
    KIND_PERIOD_WORD = {"week": "今週", "month": "今月", "period": "今期", "year": "今年"}

    def _period_word(self) -> str:
        return self.KIND_PERIOD_WORD.get(self.kind, "今週")

    def _current_outcome_items(self) -> list[str]:
        """今期間の成果目標を「箇条書き行 + 続く注記行」を1項目へ束ねて返す。

        成果目標は1項目=2行で書く（1行目に成果、2行目に `→ 売上貢献：` の式）。
        1行に詰めると横に長くなって金額が読み飛ばされるため、正本のフォーマットで
        改行を必須にした。ここで束ねずに箇条書き行だけを見ると、貢献額の行が丸ごと
        視界から外れ、C1 が全項目を「貢献額なし」と誤判定する。

        空行が項目の区切り。セクション末尾の `合計 … ＝ 今週の売上目標 …` の行が
        最後の項目にぶら下がらないようにするためでもある。
        """
        groups: list[list[str]] = []
        pat = r"【" + self._period_word() + r"の売上以外の成果目標】"
        for _, body in self.sections_by_regex(pat):
            cur: list[str] | None = None
            for line in body:
                if self._is_bullet(line):
                    cur = [line]
                    groups.append(cur)
                elif not line.strip():
                    cur = None
                elif cur is not None:
                    cur.append(line)
        return ["\n".join(g) for g in groups]

    # `→ 売上貢献：` に続く記述（改行までの1行分）。式も理由も、まずここへ丸ごと取る。
    CONTRIB_RX = re.compile(r"→\s*売上貢献\s*[：:]\s*([^\n]*)")

    # `50000 × 3件 = 150000` の形。件数に付く単位語は捨てずに取っておく（C1e で見る）。
    CONTRIB_EXPR_RX = re.compile(
        r"([0-9][0-9,]*)\s*[×xX*]\s*([0-9][0-9,]*)\s*((?:[ヶヵカか]?月|年|件|名|回|本))?\s*"
        r"[=＝]\s*([0-9][0-9,]*)"
    )

    # 裸の数字に随伴する「括弧の根拠」。数字の直後に括弧書きが続く形だけを根拠と認める。
    # 文末に付いた括弧まで拾うと `→ 売上貢献：150000（Aさん）` のような、金額の
    # 出どころを説明していない注記でも通ってしまう。
    CONTRIB_BASIS_RX = re.compile(r"^[0-9][0-9,]*\s*[（(]\s*[^）)]")

    # 貢献0の括弧は次の3形だけ（共通部品B）。0より大きい貢献の括弧は自由記述のまま。
    #   形1 `0（{同じ文書の直接成果の項目名}を支える）`  当期の直接成果を支える中間成果
    #   形2 `0（{M}月の{直接成果の項目名}を支える）`     来期以降の直接成果を支える中間成果
    #   形3 `0（{M}月計上・{根拠}）`                     翌期に計上する直接成果
    # 「見込み」等の自由記述を許すと、将来の金額・時期の推測が根拠の欄に紛れ込む。
    ZERO_BOOKED_RX = re.compile(r"^0\s*[（(]\s*(?:1[0-2]|[1-9])月計上・\s*\S.*?\s*[）)]\s*$")
    ZERO_FUTURE_RX = re.compile(r"^0\s*[（(]\s*(?:1[0-2]|[1-9])月の\s*\S.*?を支える\s*[）)]\s*$")
    ZERO_SUPPORT_RX = re.compile(r"^0\s*[（(]\s*(?P<target>.+?)を支える\s*[）)]\s*$")
    ZERO_FORMS_HINT = ("`0（{同じ文書の直接成果の項目名}を支える）`／"
                       "`0（{M}月の{直接成果の項目名}を支える）`／`0（{M}月計上・{根拠}）`")

    # 件数に付いてはいけない期間単位。`50000 × 3ヶ月 = 150000` を今期間の売上として
    # 計上すると、今期間に入らない金銭で目標が埋まる（月額顧問なら初月の 50000 だけが
    # 今期間の売上に立つ）。`件`/`名`/`回`/`本` は今期間に確定する数え方なので許す。
    PERIOD_COUNT_UNIT_RX = re.compile(r"^(?:[ヶヵカか]?月|年)$")

    @classmethod
    def _parse_contribution(
        cls, item: str
    ) -> tuple[int | None, tuple[int, int, int] | None, str, str]:
        """成果目標1項目から売上貢献額を読み取る。

        貢献額には、式（`単価 × 件数 = 貢献額`）か括弧の根拠のどちらかが必ず随伴して
        いなければならない。裸の数字1つだけでは、その数字が正しいかを後から誰も
        検算できない。式で残っていれば単価が下がったとき・本数が変わったときに何が
        崩れるかがその場で分かる。ただし値引き後の一括見積のように単価×件数へ分解
        できない成果は実在するので、式そのものは必須にしない（要求するのは「検算
        可能な根拠が随伴すること」であって「式の形」ではない）。判定は C1（R-a）で行う。

        Returns:
            (貢献額, 式, 記述全体, 件数の単位) の4つ組。
            貢献額は式があれば `=` の右辺、無ければ先頭の数値。読めなければ None。
            式は `(単価, 件数, 右辺)`。式で書かれていないときは None。
            件数の単位は式の件数に付いていた単位語（無ければ空文字）。
        """
        m = cls.CONTRIB_RX.search(item)
        if not m:
            return None, None, "", ""
        raw = m.group(1).strip()

        expr = cls.CONTRIB_EXPR_RX.search(raw)
        if expr:
            unit, count, stated = (
                int(g.replace(",", "")) for g in (expr.group(1), expr.group(2), expr.group(4))
            )
            return stated, (unit, count, stated), raw, expr.group(3) or ""

        num = re.match(r"([0-9][0-9,]*)", raw)
        if num:
            return int(num.group(1).replace(",", "")), None, raw, ""
        return None, None, raw, ""

    @staticmethod
    def _first_sales_amount(lines: list[str]) -> int | None:
        for line in lines:
            match = re.match(r"^\s*([0-9][0-9,]*)\s*円?\s*$", line)
            if match:
                return int(match[1].replace(",", ""))
        return None

    def _current_sales_target(self) -> int | None:
        pat = r"【" + self._period_word() + r"の売上目標】"
        for _, body in self.sections_by_regex(pat):
            amount = self._first_sales_amount(body)
            if amount is not None:
                return amount
        return None

    # `### → 月額顧問の成約：Aさんの成約（150000円）` のグループ見出し（項目名に個人名を入れない）。
    ACTION_GROUP_RX = re.compile(r"^#{3,6}\s*→\s*(.+?)\s*$")

    # 見出しの括弧内に書かれた金額。`（0円・8月の仕込み）` のように補足が続く形も拾う（C4c で FAIL にするため）。
    GROUP_AMOUNT_RX = re.compile(r"[（(]\s*([0-9][0-9,]*)\s*円")

    @classmethod
    def _group_ref(cls, heading: str) -> str:
        """行動目標のグループ見出しから、支える成果目標の参照名を取り出す。"""
        m = cls.ACTION_GROUP_RX.match(heading)
        if not m:
            return ""
        return re.split(r"[：:]", m.group(1))[0].strip().strip("*")

    @classmethod
    def _group_amount(cls, heading: str) -> int | None:
        """グループ見出しの括弧内の金額を取り出す。金額が書かれていなければ None。

        None は「検査対象外」を意味する。`### → （土台）` のように成果に紐づかない
        免除グループには金額が無く、そこへ金額を書かせる意味も無い。
        """
        m = cls.GROUP_AMOUNT_RX.search(heading)
        return int(m.group(1).replace(",", "")) if m else None

    def _is_current_action_heading(self, line: str) -> bool:
        """今期間の行動目標の見出しか（管理用と、月報の提出用の両方）。"""
        return ("行動目標" in line and self._period_word() in line
                and not re.search(r"差分|実績", line))

    def _is_managed_action_heading(self, line: str) -> bool:
        """今期間の行動目標の管理用見出しか（月報の提出用 `（提出）` を除く）。"""
        return self._is_current_action_heading(line) and "（提出）" not in line

    @staticmethod
    def _item_name(line: str) -> str:
        """箇条書き1行（チェックボックス可）の項目名（「：」より前）。項目名が無ければ空文字。"""
        body = re.sub(r"^\s*([*-] |・)\s*(\[[ xX]\]\s*)?", "", line)
        if not re.search(r"[：:]", body):
            return ""
        return _norm_name(re.split(r"[：:]", body, maxsplit=1)[0])

    def _current_action_names(self) -> set[str]:
        """今回の行動目標の項目名（管理用・提出用）。挽回の対応行・見直し記録・日付索引の参照先。"""
        names = set()
        for line in self.capture_awk(self._is_current_action_heading):
            if self._is_bullet(line) and self._item_name(line):
                names.add(self._item_name(line))
        return names

    def _current_action_groups(self) -> list[tuple[str, int | None, list[list[str]]]]:
        """今期間の行動目標を、支える成果目標ごとのグループへ束ねる。

        行動目標は `### → {成果目標名}：{要約}（{金額}円）` の見出しで区切り、その
        配下に `- [ ]` を並べる。売上 → 成果 → 行動の一直線を、そのまま文書の目次に
        するための構造である。行ごとに `→ 支える成果目標：` を繰り返す旧記法だと、
        同じ成果名が何度も現れるだけで「どの成果に何件ぶら下がっているか」は読み手が
        頭の中で集計するしかなかった。

        Returns:
            `(参照名, 見出しの金額, ブロック群)` の並び。参照名はグループ見出しから
            取れなければ空文字（呼び出し側が行内の `→ 支える成果目標：` へ
            フォールバックする。旧記法で書かれた既存ファイルを読めるようにするため）。
            見出しの金額は書かれていなければ None（C4b の検査対象外）。
        """
        # 期間語は種別ごとに1語へ固定する（成果・売上側と同じ理由）。`今(週|月|期)` の
        # 緩いマッチだと、週報ファイル内の期アンカー見出しを行動目標として掴みうる。
        # 月報の提出用セクション（`## 【今月の行動目標（提出）】`）はグループ見出しを
        # 持たない1行1行動の規定なので、所属の検査（C4/C5）と件数（S3）から外す。
        # 成果・売上側の抽出が `】` 直前一致で `（提出）` を拾わないのと揃える。
        groups: list[tuple[str, int | None, list[list[str]]]] = [("", None, [])]
        cur: list[str] | None = None
        for line in self.capture_awk(self._is_managed_action_heading):
            if self.ACTION_GROUP_RX.match(line):
                groups.append((self._group_ref(line), self._group_amount(line), []))
                cur = None
            elif self._is_bullet(line):
                cur = [line]
                groups[-1][2].append(cur)
            elif cur is not None and line.strip():
                cur.append(line)
        return [g for g in groups if g[2]]

    def _current_action_blocks(self) -> list[list[str]]:
        """グループを畳んだ、今期間の全行動ブロック（件数・長さの検査用）。"""
        return [b for _, _, blocks in self._current_action_groups() for b in blocks]

    def check_goal_chain(self) -> None:
        """売上 → 成果 → 行動の逆算が最後までつながっているかを検査する。

        文章での指示だけでは「行動ありき」に戻ってしまうため、連鎖そのものを機械で止める。
        """
        print("")
        print("--- 逆算チェーン（売上 → 成果 → 行動）---")

        outcome_items = self._current_outcome_items()
        if not outcome_items:
            self.fail("今期間の成果目標セクションに箇条書き項目がありません")
            return

        # C1: 各成果目標に売上貢献額があるか（売上と成果を数値で結ぶ線）
        #
        # 合計は欠落の有無に関わらず、読み取れた分だけ積む（C3 の暫定突合で使う）。
        total = 0
        missing: list[str] = []
        amounts: list[int] = []
        key_amounts: dict[str, int] = {}
        # 直接成果（貢献額が0より大きい、または形3）の項目名と、形を後で照合する貢献0の項目。
        direct_keys: list[str] = []
        zero_items: list[tuple[str, str]] = []
        for i in outcome_items:
            amount, factors, raw, count_unit = self._parse_contribution(i)
            head = self._outcome_head(i)
            if amount is None:
                missing.append(i)
                continue
            total += amount
            amounts.append(amount)
            key_amounts[self._outcome_key(i)] = amount
            if amount > 0 or (factors is None and self.ZERO_BOOKED_RX.match(raw)):
                direct_keys.append(self._outcome_key(i))
            elif factors is None and self.CONTRIB_BASIS_RX.match(raw):
                zero_items.append((head, raw))

            # C1a（R-a）: 貢献額には式か括弧の根拠のどちらかが必ず随伴する。
            # 裸の数字を通すと、式で書いた人だけが C1c の検算 FAIL を負い、根拠を
            # 出さなかった人は免除される。情報量の多い正しい記法のほうが罰せられる
            # 非対称をここで塞ぐ。貢献 0 の理由要求も、この一般規則の特殊ケースとして
            # 吸収した（0 のときだけ厳しくする独立の検査は廃止）。
            if factors is None and not self.CONTRIB_BASIS_RX.match(raw):
                self.fail(
                    "売上貢献に式または括弧の根拠がありません"
                    "（例: `→ 売上貢献：50000 × 3 = 150000` / "
                    "`→ 売上貢献：150000（値引き後の一括見積）` / "
                    "`→ 売上貢献：0（無料相談を支える）` / "
                    "`→ 売上貢献：0（9月の顧問契約を支える）` / "
                    "`→ 売上貢献：0（8月計上・顧問契約の初月分）`）: " + head
                )

            # C1c: 式の検算。`50000 × 3 = 200000` のような計算違いを見逃すと、
            # 「式で書けば根拠が残る」という記法の意味そのものが失われる。
            if factors is not None:
                unit, count, stated = factors
                if unit * count != stated:
                    self.fail(
                        f"売上貢献の式が合っていません（{unit} × {count} = {unit * count}）: "
                        f"{head} → 売上貢献：{raw}"
                    )

            # C1e（R-b）: 期間をまたぐ計上の禁止。件数に期間単位が付いた式は、
            # 今期間に入らない金銭を今期間の売上目標へ充ててしまう。
            if count_unit and self.PERIOD_COUNT_UNIT_RX.match(count_unit):
                self.fail(
                    f"売上貢献の件数に期間単位「{count_unit}」が付いています"
                    f"（{self._period_word()}に実際に売上として立つ分だけを計上してください。"
                    "月額顧問なら初月分だけを計上し、残りは次の期間の成果目標にする）: "
                    f"{head} → 売上貢献：{raw}"
                )

        if missing:
            for i in missing:
                self.fail(
                    "成果目標に「→ 売上貢献：<単価> × <件数> = <貢献額>」がありません: "
                    + self._outcome_head(i)
                )
        else:
            self.ok(f"全 {len(outcome_items)} 件の成果目標に売上貢献額あり（合計 {total}）")

        # C1f: 貢献0の括弧の形。形1の支える先は同じ文書の直接成果に実在すること。
        # 直接成果を全項目読み終えてから照合する（支える先が後ろに書かれていてもよい）。
        for head, raw in zero_items:
            if self.ZERO_FUTURE_RX.match(raw):
                continue
            support = self.ZERO_SUPPORT_RX.match(raw)
            if support is None:
                self.fail(f"貢献0の括弧は3形だけです（{self.ZERO_FORMS_HINT}）: {head} → 売上貢献：{raw}")
            elif not any(self._ref_matches_key(support["target"], k) for k in direct_keys):
                self.fail(
                    f"貢献0の支える先「{support['target']}」が同じ文書の直接成果"
                    "（貢献額が0より大きい成果目標、または `0（{M}月計上・…）` の成果目標）の項目名にありません"
                    "（来期以降の直接成果なら `0（{M}月の{項目名}を支える）`）: "
                    f"{head} → 売上貢献：{raw}"
                )
        if zero_items:
            print(f"INFO: 貢献0の括弧 {len(zero_items)} 件の形を照合しました（直接成果 {len(direct_keys)} 件）")

        # C1d: 貢献 0 の偏りを見る。0 の項目は「今期間の売上には乗らないが、先に繋がる」
        # 仕込みであり、一定数はあってよい。ただし大半が 0 なら、その期間は売上から
        # 逆算した目標になっていない（＝今週やることが今週の数字に効かない）。
        # amounts には、貢献額が読み取れた項目だけが入っている。
        # 1件しかない期間は母数が小さすぎて偏りを論じられないので判定しない。
        zeros = [a for a in amounts if a == 0]
        if self.kind != "week" and zeros:
            print("INFO: 売上貢献0の中間成果は、受注への対応と二重計上がないことを確認してください")
        elif len(amounts) >= 2 and len(zeros) * 2 > len(amounts):
            self.warn(
                f"売上貢献 0 の成果目標が {len(zeros)}/{len(amounts)} 件です。"
                f"{self._period_word()}の売上に効く成果を1件足すか、"
                "仕込みの成果を次の期間へ送ってください"
            )

        # S1/S2: シンプルさ（成果目標の件数・長さ・1項目1成果）
        if len(outcome_items) > self.MAX_OUTCOME_ITEMS:
            if self.kind == "week":
                self.fail(f"成果目標が{len(outcome_items)}件です（上限{self.MAX_OUTCOME_ITEMS}件）。絞り込んでください")
            else:
                self.warn(f"成果目標が{len(outcome_items)}件です（推奨{self.MAX_OUTCOME_ITEMS}件以下）。独立項目は保持し、重複と説明量を確認してください")
        else:
            self.ok(f"成果目標 {len(outcome_items)} 件（上限{self.MAX_OUTCOME_ITEMS}件）")
        for i in outcome_items:
            head = re.sub(r"^([*-] |・)\s*", "", i)
            head = re.split(r"→", head)[0].strip()
            if len(head) > self.MAX_OUTCOME_CHARS:
                self.fail(
                    f"成果目標が長すぎます（{len(head)}字・上限{self.MAX_OUTCOME_CHARS}字）: {head}"
                )
            if "・" in head and self.kind == "week":
                self.fail(f"成果目標に複数の成果が入っています（1項目1成果に分ける）: {head}")

        # C2: 実行完了型を成果目標に置いていないか
        bad_verb = [i for i in outcome_items
                    if any(v in self._outcome_head(i) for v in self.OUTCOME_NG_VERBS)]
        if bad_verb:
            for i in bad_verb:
                self.fail(
                    "成果目標が実行完了型です（実行した時点で達成になる項目は行動目標へ）: "
                    + i.strip()
                )
        else:
            self.ok("成果目標に実行完了型なし")

        # C3: 売上貢献の合計と売上目標の突合
        #
        # 突合できなかったときは黙って消えてはいけない。黙って消えると STATUS: PASS が
        # 「突合した結果つながっていた」と読めてしまう。判定できない理由を必ず印字する。
        target = self._current_sales_target()
        if target is None:
            print(
                f"INFO: 突合: 【{self._period_word()}の売上目標】から数値を1つ読み取れず、"
                "突合を実施していません（このセクションには数値1行だけを書いてください。"
                "PASS は突合済みを意味しません）"
            )
        elif missing:
            # 貢献額を欠く項目があっても、既知分だけで暫定の突合結果を出す。1回の実行で
            # 直すべき違反を出し切らないと、改善リトライ（最大3回）を検査の段数で使い切る。
            print(
                f"INFO: 突合（暫定）: 判明分の貢献合計 {total} / 売上目標 {target}"
                f"（未記入 {len(missing)} 件を除く）。上の売上貢献の欠落を直すと確定します"
            )
        else:
            verdict, message = judge_sales_coverage(total, target)
            if verdict == "fail":
                self.fail(message)
            elif verdict == "warn":
                self.warn(message)
            elif verdict == "ok":
                self.ok(message)
            else:
                print(f"INFO: {message}")

        # C4/C5: 各行動目標が実在する成果目標を支えているか
        action_groups = self._current_action_groups()
        blocks = [b for _, _, bs in action_groups for b in bs]
        if not blocks:
            print(
                f"INFO: 紐づけ検査: 【{self._period_word()}の行動目標】に箇条書き項目が無く、"
                "C4/C5/C6 を実施していません"
            )
            return
        # S3: シンプルさ（行動目標の件数・長さ）
        if len(blocks) > self.MAX_ACTION_ITEMS:
            if self.kind == "week":
                self.fail(f"行動目標が{len(blocks)}件です（上限{self.MAX_ACTION_ITEMS}件）。やらないことを増やしてください")
            else:
                self.warn(f"行動目標が{len(blocks)}件です（推奨{self.MAX_ACTION_ITEMS}件以下）。必要な主要行動を残し、重複を確認してください")
        else:
            self.ok(f"行動目標 {len(blocks)} 件（上限{self.MAX_ACTION_ITEMS}件）")
        for block in blocks:
            head = re.sub(r"^([*-] |・)\s*(\[[ xX]\]\s*)?", "", block[0]).strip()
            if len(head) > self.MAX_ACTION_CHARS:
                self.fail(
                    f"行動目標が長すぎます（{len(head)}字・上限{self.MAX_ACTION_CHARS}字）: {head}"
                )

        keys = [self._outcome_key(i) for i in outcome_items]
        keys = [k for k in keys if k]
        unlinked = 0
        dangling = 0
        linked_keys: set[str] = set()
        # C4b（R-c）: グループ見出しの金額と、その成果目標の貢献額の一致。
        # 見出しの金額は「この行動群は何円のために動いているか」を読み手へ渡す唯一の
        # 数字なので、成果目標側と食い違ったまま通すと、目次だけが別の計画を語る。
        # 金額の無い見出し（`### → （土台）` 等の免除グループ）は対象外。
        #
        # R-d: グループの並び順（貢献額の降順）は機械検査しない。同額のときに順序が
        # 一意に決まらず、正しく書いても直しようのない FAIL が出るため、意図的に
        # 非検査としている（実装し忘れではない）。
        # C4c: 0円の見出しは `（0円）` だけ。`（0円・8月の仕込み）` のような補足は、成果目標の
        # 貢献0の括弧（C1f）と別の自由記述の置き場になり、同じ理由が2か所でずれていく。
        for line in self.capture_awk(self._is_managed_action_heading):
            if not self.ACTION_GROUP_RX.match(line) or self._group_amount(line) != 0:
                continue
            bracket = re.search(r"[（(]\s*[0-9][0-9,]*\s*円[^）)]*[）)]?", line)
            if bracket is None or bracket.group(0) != "（0円）":
                self.fail(f"0円のグループ見出しは `（0円）` だけで書いてください（補足は成果目標の貢献0の括弧へ）: {line.strip()}")

        for group_ref, group_amount, _blocks in action_groups:
            if not group_ref or group_amount is None:
                continue
            matched = [k for k in keys if self._ref_matches_key(group_ref, k)]
            for k in matched:
                if k in key_amounts and key_amounts[k] != group_amount:
                    self.fail(
                        f"行動目標グループの金額が成果目標の貢献額と違います"
                        f"（見出し {group_amount} / 成果目標「{k}」{key_amounts[k]}）: "
                        f"### → {group_ref}"
                    )

        for group_ref, _group_amount, group_blocks in action_groups:
            for block in group_blocks:
                head = block[0].strip()
                # グループ見出し（`### → 成果目標名：…`）が正。見出しが無いときだけ、
                # 旧記法の行内注記へフォールバックする（既存ファイルを読めるように）。
                inline = next(
                    (l for l in block if re.search(r"→\s*支える成果目標\s*[：:]", l)), None
                )
                if group_ref:
                    value = group_ref
                elif inline is not None:
                    value = re.split(
                        r"→\s*支える成果目標\s*[：:]", inline, maxsplit=1
                    )[1].strip()
                else:
                    self.fail(
                        "行動目標がどの成果目標に属するか分かりません"
                        "（`### → 成果目標名：要約（金額円）` の見出しでグループ化してください）: "
                        + head
                    )
                    unlinked += 1
                    continue
                for ref in [r.strip() for r in value.split("・") if r.strip()]:
                    if ref.startswith("（") or ref.startswith("("):
                        continue  # （土台）／（関係維持）は成果への紐づけを免除
                    matched = [k for k in keys if self._ref_matches_key(ref, k)]
                    if not matched:
                        self.fail(
                            f"行動目標が実在しない成果目標を参照しています: 「{ref}」← {head}"
                        )
                        dangling += 1
                    else:
                        linked_keys.update(matched)
        if unlinked == 0 and dangling == 0:
            self.ok(f"全 {len(blocks)} 件の行動目標が実在する成果目標に紐づいています")

        # C6: 支える行動が1件もない成果目標（成果側から見た抜け）
        # C5 と同じ述語の結果（linked_keys）だけを見るので、両検査は必ず整合する。
        orphan = [k for k in keys if k not in linked_keys]
        if orphan:
            for k in orphan:
                self.warn(f"成果目標「{k}」を支える行動目標がありません")
        else:
            self.ok("全ての成果目標に、それを支える行動目標があります")

    def check_peer_consistency(self) -> None:
        """他層ファイルとの期アンカー2値の突き合わせ。不一致は WARN（FAIL にしない）。

        「不一致0件」は「比較して0件だった」と「比較対象が0件だった」を区別しないので、
        必ず比較した項目数（分母）を印字する。
        """
        print("")
        print("--- 層間整合チェック（--peer） ---")
        mine = extract_peer_anchors(self.text)
        for peer_name, peer_text in self.peers:
            theirs = extract_peer_anchors(peer_text)
            print(f"PEER: {peer_name}")
            print(KEY_NUMBER_SKIP_NOTE)
            compared = 0
            mismatched = 0
            for name, _rx, _kind in PEER_ANCHORS:
                a, b = mine.get(name), theirs.get(name)
                if a is None or b is None:
                    missing = []
                    if a is None:
                        missing.append("対象")
                    if b is None:
                        missing.append("peer")
                    print(f"  SKIP: {name}（{'・'.join(missing)}に値なし・比較対象外）")
                    continue
                compared += 1
                if a == b:
                    print(f"  MATCH: {name} = {a}")
                else:
                    mismatched += 1
                    self.warn(
                        f"層間の値ズレ: {name} 対象={a} / peer({peer_name})={b}"
                        "（期アンカーは全レベル同値。継承は作成時 pull のみなので運用上ズレ得る）"
                    )
            print(f"  層間比較: 比較{compared}項目中 不一致{mismatched}件")
            if compared == 0:
                print("  （比較できる項目が1件もありませんでした。不一致0件は検査結果ではありません）")

    def run(self) -> int:
        print("=== UBM目標設定 バリデーション ===")
        print(f"対象: {self.basename}")
        print("")

        # 0. 未展開テンプレート変数
        unexpanded = [l for l in self.lines if re.search(r"\{\{[^}]*\}\}", l)]
        if not unexpanded:
            self.ok("未展開テンプレート変数なし")
        else:
            self.fail("未展開テンプレート変数 {{...}} が残っています")

        # 1. ファイル名チェック
        if re.search(r"^UBM - [1-4]-", self.basename):
            self.ok("ファイル名プレフィックス")
        else:
            self.fail("ファイル名が 'UBM - {1,2,3,4}-' で始まっていません")
        if re.search(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[〜~][0-9]{4}-[0-9]{2}-[0-9]{2}", self.basename):
            self.ok("日付パターン")
        else:
            self.fail("ファイル名に日付パターン (YYYY-MM-DD〜YYYY-MM-DD) がありません")

        # 2. 全角数字 (見出し行・１ヶ月・３ヶ月 除外。２ヶ月は旧期報の後方互換で除外を継続)
        zenkaku = [
            l for l in self.lines
            if re.search(r"[０-９]", l)
            and not l.startswith("##")
            and "１ヶ月" not in l
            and "２ヶ月" not in l
            and "３ヶ月" not in l
            and "１年" not in l
        ]
        if not zenkaku:
            self.ok("全角数字なし")
        else:
            self.fail("全角数字が含まれています")

        # 3. 差分の +/- 表記
        diff_lines = [l for l in self.lines if "差分" in l]
        if diff_lines:
            diff_values = [l for l in diff_lines if "##" not in l]
            if diff_values:
                no_sign = [
                    l for l in diff_values
                    if re.search(r"[0-9]", l) and not re.search(r"[+-]", l) and "差分】" not in l
                ]
                if not no_sign:
                    self.ok("差分の +/- 表記")
                else:
                    self.warn("差分値に +/- が付いていない可能性があります")

        # 4. 種別別 必須セクション
        # タイトル見出しは --type と一致していること（種別の取り違えを error にする）
        self.check_title_matches_type()

        if self.kind == "week":
            # 今週の見直し記録: 週の途中で行動を軌道修正した記録の置き場（無い週は `- なし`）。
            # 前週ブロック12見出しは他の層と同じく必須（初回は各欄に初回マーカーを置く）。
            for lbl in ["前週の売上目標", "前週の売上実績", "前週の売上目標と実績の差分",
                        "前週の売上に対して未達を挽回するための行動",
                        "前週の売上以外の成果目標", "前週の売上以外の成果実績",
                        "前週の売上以外の成果目標と実績の差分",
                        "前週の売上以外の成果に対して未達を挽回するための行動",
                        "前週の行動目標（行動管理）", "前週の行動実績（行動管理）",
                        "前週の行動目標と実績の差分", "前週の行動に対して未達を挽回するための行動",
                        "今週の最重要数字", "今週の売上目標", "今週の売上以外の成果目標",
                        "今週の行動目標（行動管理・優先順位付き）", "今週の見直し記録",
                        "習慣目標（仕組みで動く土台）", "今週の判断基準", "現在のグリッドパートナー数"]:
                self.check_require_exact(lbl)
            for opt in ["到達ライン", "今期の売上目標", "前回のアカデミーへの参加日",
                        "次回のアカデミーへの参加日", "次回の壁打ち予定日", "現在事業パートナー数"]:
                self.check_section_optional(opt)
        elif self.kind == "month":
            for lbl in ["確認された情報", "今期の売上目標", "今期の累計売上実績", "前月の売上目標",
                        "前月の売上実績", "前月の売上目標と実績の差分", "前月の売上に対して未達を挽回するための行動",
                        "前月の売上以外の成果目標", "前月の売上以外の成果実績",
                        "前月の売上以外の成果に対して未達を挽回するための行動", "前月の売上以外の成果目標と実績の差分",
                        "前月の行動目標（行動管理）", "前月の行動実績（行動管理）", "前月の行動目標と実績の差分",
                        "前月の行動に対して未達を挽回するための行動", "今月の売上目標", "今月の売上以外の成果目標",
                        "今月の行動目標（行動管理・優先順位付き）", "現在事業パートナー数", "現在のグリッドパートナー数",
                        "プロジェクト別タスク", "今月やらないこと（明確に排除するもの）", "今月末の振り返りチェックリスト"]:
                if self.concise_monthly and lbl == "プロジェクト別タスク":
                    continue
                self.check_require_exact(lbl)
        elif self.kind == "period":
            for lbl in ["確認された情報", "今期の累計売上実績", "前期の売上目標", "前期の売上実績",
                        "前期の売上目標と実績の差分", "前期の売上に対して未達を挽回するための行動",
                        "前期の売上以外の成果目標", "前期の売上以外の成果実績",
                        "前期の売上以外の成果に対して未達を挽回するための行動", "前期の売上以外の成果目標と実績の差分",
                        "前期の行動目標（行動管理）", "前期の行動実績（行動管理）", "前期の行動目標と実績の差分",
                        "前期の行動に対して未達を挽回するための行動", "今期の売上目標", "今期の売上以外の成果目標",
                        "今期の行動目標（行動管理・優先順位付き）", "現在事業パートナー数", "現在のグリッドパートナー数",
                        "今期やらないこと（明確に排除するもの）", "今期末の振り返りチェックリスト", "事業の柱"]:
                self.check_require_exact(lbl)
        elif self.kind == "year":
            # 1年層。期報（period）と同じ骨格で、期間語を「今年/前年」に置き換えたもの。
            # 最重要数字を必須にしているのは、この層の数字（到達点）が3ヶ月→1ヶ月→1週間へ
            # 割られていく起点で、ここが空だと下位層の分母が決まらないため。
            for lbl in ["確認された情報", "今年の最重要数字", "今年の累計売上実績",
                        "前年の売上目標", "前年の売上実績",
                        "前年の売上目標と実績の差分", "前年の売上に対して未達を挽回するための行動",
                        "前年の売上以外の成果目標", "前年の売上以外の成果実績",
                        "前年の売上以外の成果に対して未達を挽回するための行動", "前年の売上以外の成果目標と実績の差分",
                        "前年の行動目標（行動管理）", "前年の行動実績（行動管理）", "前年の行動目標と実績の差分",
                        "前年の行動に対して未達を挽回するための行動", "今年の売上目標", "今年の売上以外の成果目標",
                        "今年の行動目標（行動管理・優先順位付き）", "現在事業パートナー数", "現在のグリッドパートナー数",
                        "今年やらないこと（明確に排除するもの）", "今年末の振り返りチェックリスト", "事業の柱"]:
                self.check_require_exact(lbl)

        # 5. 空セクション
        # 見出しの直後に空行を1行置くのは通常の Markdown。直後の1行だけを見ると
        # 正しく書かれた節が全部「空」になるので、次の見出しまでに本文があるかで判定する。
        empty_sections = []
        for i, line in enumerate(self.lines):
            if not line.startswith("## 【"):
                continue
            j = i + 1
            has_body = False
            while j < len(self.lines) and not self.lines[j].startswith("## "):
                if self.lines[j].strip() and not re.match(r"^\s*-{3,}\s*$", self.lines[j]):
                    has_body = True
                    break
                j += 1
            if not has_body:
                empty_sections.append(line)
        if empty_sections:
            self.warn("空のセクションがあります: " + " / ".join(empty_sections))

        # 5b. 重複見出し
        counts: dict[str, int] = {}
        for l in self.lines:
            if l.startswith("## 【"):
                key = re.sub(r"[ \t]+$", "", l)
                counts[key] = counts.get(key, 0) + 1
        dups = {k: c for k, c in counts.items() if c > 1}
        if not dups:
            self.ok("重複見出しなし")
        else:
            self.fail("完全一致する見出し「## 【…】」が2回以上出現しています（重複禁止）")

        # --- 目標・実績・差分フォーマット ---
        print("")
        print("--- 目標・実績・差分フォーマットチェック ---")
        self.check_goal_section(r"【前.*の売上目標】", "前期間の売上目標", "numeric")
        self.check_goal_section(r"【前.*の売上実績】", "前期間の売上実績", "numeric")
        self.check_goal_section(r"【前.*の売上目標と実績の差分】", "前期間の売上差分", "numeric")
        self.check_goal_section(r"【今(週|月|期|年)の売上目標】", "今期間の売上目標", "numeric")
        self.check_goal_section(r"【前.*の売上以外の成果目標】", "前期間の売上以外の成果目標", "bullet")
        self.check_goal_section(r"【前.*の売上以外の成果実績】", "前期間の売上以外の成果実績", "bullet")
        self.check_goal_section(r"【前.*の売上以外の成果目標と実績の差分】", "前期間の売上以外の成果差分", "bullet")
        self.check_goal_section(r"【前.*の行動目標", "前期間の行動目標", "bullet")
        self.check_goal_section(r"【前.*の行動実績", "前期間の行動実績", "bullet")
        self.check_goal_section(r"【前.*の行動目標と実績の差分】", "前期間の行動差分", "bullet")

        self.check_goal_chain()
        self.check_report_alignment()
        self.check_key_number_sales_line()

        print("")
        print("--- 挽回の対応行・見直し記録・日付索引 ---")
        self.check_recovery_lines()
        self.check_revision_records()
        self.check_date_index()

        # --- 品質チェック ---
        print("")
        print("--- 品質チェック ---")

        # 行動行の合格基準は「何をする＋期日」。誰に・数値・人名は必須にしない。
        # 提出用は管理用と同じ期日を必ず書くので、期日の検査は提出用も対象にする。
        action_section = self.capture_awk(self._is_current_action_heading)
        action_items = [l for l in action_section if re.match(r"^([*-] |・)", l)]
        if action_section:
            ng = [l for l in action_section if GOAL_SPIRIT_RE.search(l)]
            if not ng:
                self.ok("NG表現なし（行動目標セクション）")
            else:
                self.fail("行動目標に精神論が含まれています")
            # 【考え】【思い】の注記は依頼されたときだけ書く。依頼の有無は本文から
            # 判定できないので FAIL にはせず、既定の出力に紛れ込んだことを知らせる。
            if any(re.match(r"^\s*(?:→\s*)?【(?:考え|思い)】", l) for l in action_section):
                self.warn("行動目標に【考え】【思い】の注記があります（依頼されたときだけ書く）")
            if action_items:
                # 今回の期間の行動行だけに掛ける。前回ブロックへの転記・習慣目標・振り返りは
                # 見出しが別なのでここには入らない（前回は当時のまま転記するため）。
                deadline_rx = self._deadline_rx()
                no_date = [l for l in action_items if not deadline_rx.search(l)]
                if not no_date:
                    self.ok(f"行動目標 {len(action_items)} 行の行末に期日あり")
                for l in no_date:
                    self.fail(f"期日のない行動目標があります（{self._deadline_hint()}）: {l.strip()}")

        # 9. やらないこと 3項目以上
        def notdoing_pred(line: str) -> bool:
            return ("やらないこと" in line and re.search(r"今(週|月|期|年)", line)
                    and "守れたか" not in line)

        not_doing = self.capture_awk(notdoing_pred)
        if not_doing:
            bullet_count = sum(1 for l in not_doing if re.match(r"^([*-] |・)", l))
            table_count = count_table_data_rows(not_doing)
            heading_count = sum(1 for l in not_doing if re.match(r"^### ", l))
            total = bullet_count + table_count + heading_count
            if total >= 3:
                self.ok(f"「やらないこと」{total}項目")
            else:
                self.fail(f"「やらないこと」が{total}項目です（必須: 3項目以上）")

        # 11. プロジェクト別タスク
        project_section = self.sed_range("【プロジェクト別タスク】", r"^## ")
        has_project = any("【プロジェクト別タスク】" in l for l in self.lines)
        if self.kind == "period" and has_project:
            self.fail("期報にプロジェクト別タスクが含まれています（期報では出力禁止）")
        if self.kind == "year" and has_project:
            self.fail("1年目標にプロジェクト別タスクが含まれています（1年層では出力禁止）")
        if self.kind == "week" and has_project:
            self.fail("週報にプロジェクト別タスクが含まれています（週報の実行管理は【今週の行動目標】と"
                      "【今週の大きな到達ライン】の日付索引だけ。週報では出力しない）")
        if self.kind == "month" and not has_project and not self.concise_monthly:
            self.fail("月報にプロジェクト別タスクがありません（月報では必須）")
        if has_project and self.kind == "month":
            checkbox_lines = [l for l in project_section if re.match(r"^(- |・)\[[ x]\] ", l)]
            checkbox_count = len(checkbox_lines)
            if checkbox_count >= 1:
                self.ok(f"プロジェクト別タスクにチェックボックスが {checkbox_count} 件あり")
            else:
                self.fail("プロジェクト別タスクにチェックボックス（- [ ] / - [x]）が1件もありません")
            # 行の書式は共通部品A の管理用と同じ。宛先が判定に必要なら本文に書く。
            deadline_rx = self._deadline_rx()
            bad_task = 0
            for l in checkbox_lines:
                m = deadline_rx.search(l)
                body = l[:m.start()] if m else l
                parts = re.match(r"^(?:- |・)\[[ x]\]\s*([^：:\s][^：:]*?)\s*[：:]\s*(\S.*?)\s*$", body)
                if m is None or parts is None:
                    bad_task += 1
                    self.fail("プロジェクト別タスクは '- [ ] {項目名}：{何をする}　期日{トークン}' で書いてください"
                              f"（{self._deadline_hint()}）: {l.strip()}")
            if checkbox_count and not bad_task:
                self.ok("プロジェクト別タスクが '- [ ] {項目名}：{何をする}　期日{トークン}' 形式")
            client_owner = sum(1 for l in project_section if re.match(r"^(- |・)先方担当者: .+", l))
            project_heading = sum(1 for l in project_section if re.match(r"^### ", l))
            if client_owner >= project_heading:
                self.ok("各プロジェクトに先方担当者あり")
            else:
                self.fail("各プロジェクトに '- 先方担当者: ...' を記載してください")
            if any(re.match(r"^##### ", l) for l in project_section):
                self.fail("プロジェクト別タスクが3階層以上になっています（2階層まで）")

        # 12. 行動目標チェックボックス (週報のみ)
        if self.kind == "week":
            action_full = self.capture_from_start(r"^## 【今週.*行動目標")
            action_checkboxes = sum(1 for l in action_full if re.match(r"^(- |・)\[[ x]\] ", l))
            if action_checkboxes >= 3:
                self.ok(f"行動目標がチェックボックス形式（{action_checkboxes}項目）")
            else:
                self.fail("行動目標は '- [ ] ...' チェックボックス形式で3項目以上にしてください（済/未済の二値性）")

        # 13. 習慣目標 (週報のみ)
        if self.kind == "week":
            habit_section = self.sed_range("【習慣目標", r"^## ")
            if any("【習慣目標" in l for l in self.lines):
                habit_checkboxes = sum(1 for l in habit_section if re.match(r"^(- |・)\[[ x]\] ", l))
                if habit_checkboxes >= 6:
                    self.ok("習慣目標に3原則 × 2項目以上のチェックボックスあり")
                else:
                    self.warn("習慣目標のチェックボックスが少ないです（推奨: 各原則2項目以上）")

        # 14. 層間整合（--peer 指定時のみ。未指定なら既存の挙動と完全に同一）
        if self.peers:
            self.check_peer_consistency()

        print("")
        print("=== 結果 ===")
        print(f"エラー: {self.errors} 件")
        print(f"警告: {self.warnings} 件")
        if self.errors == 0:
            print("STATUS: PASS")
            return 0
        print("STATUS: FAIL")
        return 1


# GFM の区切り行はハイフン1個以上（`|--|`・`|:-:|` も区切り行）。3個以上に絞ると短い区切り行を
# データ行と数え、表の行数が1つ多くなる。GFM では行の両端の `|` も省ける（`|---|---`・`---|---|`・
# `---|---` も区切り行）。両端を必須にすると、末尾の `|` が無い区切り行で見出し行と区切り行を
# データ行と数え（偽 PASS）、先頭の `|` が無い表を0行と数える（偽 FAIL）。ただし `|` を1つも
# 含まない `---` は区切り線（水平線）なので、先読みで `|` を1つ以上要求する。
TABLE_SEPARATOR_RE = re.compile(r"^(?=[^|]*\|)\|?(?:\s*:?-+:?\s*\|)*\s*:?-+:?\s*\|?\s*$")

# 表の途中でも、ここに当たる行は別のブロック（箇条書き・見出し・引用）の始まりなので表を閉じる。
# 見出しは `#`〜`######` の後に空白か行末が続く行だけ。`#1 交流会 | 時間` のように `#` で始まる
# セルは見出しではないので、`#` 1文字で閉じると先頭の `|` を省いた表の行を数え落とす。
_BLOCK_START_RE = re.compile(r"^\s*(?:[*+-]\s|・|#{1,6}(?:\s|$)|>)")


def has_markdown_table(lines: list[str]) -> bool:
    """`|` で始まる行か区切り行が1行でもあれば、節に表があるとみなす。

    先頭の `|` を省いた表も区切り行は必ず持つので、区切り行の有無で拾える。
    """
    return any(line.startswith("|") or TABLE_SEPARATOR_RE.match(line) for line in lines)


def count_table_data_rows(lines: list[str]) -> int:
    """表の行のうち、見出し行（区切り行の直前の行）と区切り行を除いた行数を返す。

    「表の行数 - 2」と決め打ちすると、区切り行の無い表や、表が2つある節で数がずれる。
    区切り行の後に続く `|` を含む行は、先頭が `|` でなくても表の行として数える（GFM は
    両端の `|` を省ける）。表は空行・`|` を含まない行・別のブロックの始まりで閉じる。
    区切り行の無い `|` 始まりの行は、これまでどおり表の行として数える。
    """
    count = 0
    in_table = False
    for i, line in enumerate(lines):
        if TABLE_SEPARATOR_RE.match(line):
            in_table = True
            continue
        if i + 1 < len(lines) and TABLE_SEPARATOR_RE.match(lines[i + 1]):
            continue  # 見出し行
        if in_table and "|" in line and not _BLOCK_START_RE.match(line):
            count += 1
            continue
        in_table = False
        if line.startswith("|"):
            count += 1
    return count


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="UBM目標設定 出力バリデーション", add_help=True)
    ap.add_argument("--file", required=True, help="検証対象の Markdown ファイル")
    ap.add_argument("--type", required=True, choices=list(TYPE_MAP.keys()),
                    help="目標種別 weekly|monthly|quarterly|yearly（bimonthly は quarterly の後方互換の別名）")
    ap.add_argument("--peer", action="append", default=None, metavar="PATH",
                    help="層間整合を突き合わせる他層のファイル（任意・複数指定可）。"
                         "期アンカー2値の不一致を WARN で報告する（FAIL にはしない）")
    if ACTION_POLICY_ERROR is not None and not {"-h", "--help"} & set(argv):
        print(f"ERROR: 行動の語彙契約を読めません: {ACTION_POLICY_PATH}: {ACTION_POLICY_ERROR}", file=sys.stderr)
        return 2
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        # --help は argparse が SystemExit(0) を投げる。これを 2 に潰すと
        # 「usage は正常に出たのに異常終了」になり、rc で成否を見る側が誤判定する。
        return 0 if e.code == 0 else 2

    # 入力を読めないのは検査の FAIL (1) ではない。2 にして「直すのは下書きではなく呼び出し」と区別する。
    path = Path(args.file)
    text = read_input(path, "--file")
    if text is None:
        return 2

    peers: list[tuple[str, str]] = []
    for peer in args.peer or []:
        ppath = Path(peer)
        ptext = read_input(ppath, "--peer")
        if ptext is None:
            return 2
        peers.append((ppath.name, ptext))

    kind = TYPE_MAP[args.type]
    return Validator(text, path.name, kind, args.type, peers).run()


def read_input(path: Path, flag: str) -> str | None:
    """入力ファイルを UTF-8 で読む。読めなければ stderr に理由を出して None を返す。

    utf-8-sig で開いて先頭の BOM を外す。BOM が残ると1行目のタイトル見出しが `## ` で始まらず、
    必須タイトル見出しが無いと誤って FAIL する（validate-cross-level.py は BOM 付きでも通る）。
    """
    if not path.is_file():
        print(f"ERROR: {flag} のファイルが見つかりません（またはファイルでない）: {path}", file=sys.stderr)
        return None
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"ERROR: {flag} のファイルを UTF-8 で読めません: {path}: {type(exc).__name__}", file=sys.stderr)
        return None


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
