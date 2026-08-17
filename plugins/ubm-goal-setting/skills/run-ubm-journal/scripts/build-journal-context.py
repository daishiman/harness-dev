#!/usr/bin/env python3
# /// script
# name: build-journal-context
# version: 0.5.0
# purpose: 日次ジャーナル作成の決定論的な前提 (通し番号・出力パス・目標4階層の期間と残日数・
#          最新週報から引き継ぐ習慣目標/判断基準/当日タスク・前回ジャーナルの継承値) を
#          1 回の実行で JSON 化する。番号採番と日数計算を LLM に推測させないための決定論ゲート。
# inputs:
#   - argv: --vault-root <path> (省略時 env UBM_VAULT_ROOT) / --date YYYY-MM-DD (省略時 today)
#   - files: {vault}/02_Configs/Daily/*.md, {vault}/05_Project/UBM/目標設定/*.md
#   - files: {skill}/references/daily-habits.json (欠落・破損は fail-closed で exit 2)
# outputs:
#   - stdout: context JSON (下記 SCHEMA 節)
#   - exit: 0=解決成功 / 2=引数不正・vault 解決不能・Daily ディレクトリ不在・
#           daily-habits.json 欠落/破損 (すべて fail-closed。1 は使わない)
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""日次ジャーナルの文脈解決 — 通し番号・残日数・週報引き継ぎを決定論で確定する。

番号は「Daily 配下の既存ジャーナルの最大値 +1」が仕様であるため、Daily/ 配下の全ファイルから
`# No.<数字> - ジャーナル（YYYY-MM-DD）` を走査して最大値を取り、対象日のファイルが既に
番号を持つ場合はそれを再利用する (再生成で番号が飛ばない)。

残日数は「対象日から期間終了日までの日数」で、終了済みは 0 + expired=True を返す。
目標本文の要約文は最新レポート側に存在しないため前回ジャーナルから継承し、レポートの期間が
前回ジャーナルの期間と食い違う場合だけ warnings に出して呼び出し側へ再要約を促す。

SCHEMA
------
stdout は以下の形の JSON オブジェクト 1 個。キーは常に全て存在する (値が null でも省略しない)。
消費側が `in` 判定でなく値の null 判定を書けるようにするための不変条件である。

    {
      "target_date":     "YYYY-MM-DD",
      "journal_number":  int,               # 採番済みの通し番号
      "is_regeneration": bool,              # 同じ日のジャーナルの作り直しか
      "existing_file":   {                  # 出力先の現況。write_mode を必ず持つ
        "write_mode": "new" | "regenerate" | "blocked",
        "path": str, "number": int|null, "heading_date": "YYYY-MM-DD"|null
        # path/number/heading_date は write_mode="new" のとき存在しない
      },
      "output_path":     str,
      "heading":         str,               # 生成すべき H1 見出しそのもの
      "previous_journal": null | {
        "path": str, "file_date": "YYYY-MM-DD", "number": int,
        "heading_date": "YYYY-MM-DD"|null,
        "ultimate_purpose": [str], "prohibitions": [str], "phase_checklist": str,
        "goals": { <key>: {"period_start":…, "period_end":…, "goal": str} }
      },
      "goals": {                            # key = yearly|quarterly|monthly|weekly (4 件固定)
        <key>: {
          "period_start": "YYYY-MM-DD"|null, "period_end": "YYYY-MM-DD"|null,
          "goal": str,
          "source": "report" | "previous_journal" | "unresolved",
          "days_remaining": int|null,       # 期間終了日までの日数。終了済みは 0
          "days_overdue":   int|null,       # 超過日数。未終了は 0 (キーは常に存在する)
          "expired": bool|null              # 期間不明のときだけ null
        }
      },
      "report_sources": { <key>: {"path": str, "period": str, "covers_target": bool} },
      "weekly_report":  {} | {              # 週報が見つからないときだけ空 dict
        "path": str, "period": str,
        "habit_goals": [{"title": str, "items": [{"text": str, "checked_in_report": bool}]}],
        "judgment_criteria": str, "day_tasks": [str],
        "key_numbers": [str], "outcome_goals": [str], "weekly_revenue_goal": str
      },
      "daily_habits": [ … ],                # references/daily-habits.json の habits をそのまま
      "warnings":     [str]                 # 人間に確認を促す文。空でも必ずキーは存在する
    }
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

DAILY_REL = "02_Configs/Daily"
GOALS_REL = "05_Project/UBM/目標設定"

# 毎日必ずヒアリングする固定習慣の正本 (週報の【習慣目標】= 週ごとに変わる4群とは別軸)。
# plugin 同梱のため欠落は「壊れた install」であり、素通しせず fail-closed で止める。
DAILY_HABITS_PATH = Path(__file__).resolve().parents[1] / "references" / "daily-habits.json"

# ジャーナル見出し: 「# No.388 - ジャーナル（2026-08-16）」
HEADING_RE = re.compile(r"^#\s*No\.\s*(\d+)\s*[-–—]\s*ジャーナル\s*[（(]\s*([\d]{4}[-/][\d]{2}[-/][\d]{2})\s*[)）]")
# レポート先頭: 「## 【1週間の目標】2026-08-10〜2026-08-16」
REPORT_HEAD_RE = re.compile(r"^##\s*【(?P<label>[^】]*の目標)】\s*(?P<period>.+?)\s*$")
PERIOD_RE = re.compile(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s*[〜～~]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})")
FILE_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
# 「目標：」「目標:」「目標 :」等の先頭ラベル。本文側のコロンには一致させない。
GOAL_LABEL_RE = re.compile(r"^目標\s*[：:]\s*")

# ジャーナル側の目標見出し → context キー
GOAL_KEYS = {
    "1年目標": "yearly",
    "3ヶ月目標": "quarterly",
    "2ヶ月目標": "quarterly",
    "1ヶ月目標": "monthly",
    "1週間目標": "weekly",
}
# レポート側ラベル → context キー (期報は 2ヶ月 = quarterly 枠に入れる)
REPORT_LABELS = {
    "1週間の目標": "weekly",
    "1ヶ月の目標": "monthly",
    "2ヶ月の目標": "quarterly",
    "3ヶ月の目標": "quarterly",
}


def parse_date(text: str) -> date | None:
    t = text.strip().replace("/", "-")
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", t)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def parse_period(text: str) -> tuple[date | None, date | None]:
    m = PERIOD_RE.search(text)
    if not m:
        return None, None
    return parse_date(m.group(1)), parse_date(m.group(2))


def days_remaining(target: date, end: date | None) -> dict[str, Any]:
    """残日数・超過日数・期間終了フラグ。キー集合は入力によらず常に同一にする。

    days_overdue を expired のときだけ生やすと、消費側が `"days_overdue" in goal` と
    `goal["days_overdue"] > 0` のどちらを書くかで挙動が変わる。値の有無ではなく値そのもので
    判断できるよう、未終了は 0、期間不明は None を明示的に入れる。
    """
    if end is None:
        return {"days_remaining": None, "days_overdue": None, "expired": None}
    delta = (end - target).days
    if delta < 0:
        return {"days_remaining": 0, "days_overdue": -delta, "expired": True}
    return {"days_remaining": delta, "days_overdue": 0, "expired": False}


def has_value(entry: dict[str, Any] | None) -> bool:
    """継承エントリが「引き継げた」と言えるか。

    期間だけ拾えて目標本文が空のときまで True にすると、呼び出し側が
    source="previous_journal" を立てて未解決を未解決として出さなくなる
    (呼び出し側のコメントが明示している意図と矛盾していた)。よって
    goal 本文があることを必須とする。
    """
    if not entry:
        return False
    return bool(str(entry.get("goal") or "").strip())


def read(path: Path) -> str:
    """テキストを読む。読めないファイルは "" にする (呼び出し側が判別不能として扱える)。

    UnicodeDecodeError は OSError を継承しない。捕まえないと Daily 配下に非 UTF-8 の .md が
    1 つ紛れているだけで raw traceback になり、「vault パスが違う」という誤った原因へ誘導する。
    "" を返せば見出しなし扱いとなり、対象日ファイルなら write_mode="blocked" へ倒れる。
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


HRULE_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
# 「今期の目標」ではなく「過去の結果」を書く節を見分ける語。section_body の部分一致で使う。
RETROSPECTIVE_RE = re.compile(r"振り返り|振返り|反省|レビュー")
# 見出しの装飾。実データの `## 【今週の判断基準】` は 【】 を落とさないと完全一致せず、
# 常に部分一致経路へ落ちて RETROSPECTIVE_RE の巻き添えを受ける。
TITLE_DECOR = "◇◆・:：【】《》[]「」 　"
# 括弧の中は節の性格ではなく補足。`## 今週の判断基準（週次レビューで使う）` の
# 「レビュー」まで振り返り扱いすると、判断基準が warning なしで空になる (実測)。
# 除外語は括弧を除いた芯だけに掛ける。
PAREN_RE = re.compile(r"[（(][^）)]*[）)]")


def section_body(
    text: str,
    heading: str | tuple[str, ...],
    level: str = "##",
    notes: list[str] | None = None,
) -> str:
    """`{level} {heading}` 見出し直下から、同レベル以上の次見出しまでの本文を返す。

    Markdown の水平線 (`---`) はセクションの実質的な終端として扱う。ハイフン始まりゆえ
    そのままでは箇条書きと区別がつかず、次セクションの区切り線が本文へ混入する。

    `heading` にタプルを渡すと、同じ節の正規表記ゆれを**すべて完全一致の候補**として扱う
    (先頭が代表表記で、notes のメッセージにはこれを使う)。括弧付きの正式名
    (`## 【習慣目標（仕組みで動く土台）】`) を別名で持たない場合、その正式名は部分一致
    fallback 経由でしか拾えず、正しい節を読んでいるのに毎回「別の期の内容では」と
    警告が出る。括弧の中を無視する規則で救うことはできない
    (`### 1年目標（2025年度の振り返り）` を黙って採用する経路が復活するため)。

    `notes` を渡すと、完全一致が取れず部分一致で節を採用したこと・部分一致候補を
    振り返り節として全て除外したことを 1 行ずつ追記する。

    なぜ黙らせないか
    ----------------
    この関数の部分一致 fallback は、同じクラスの欠陥を 3 度出している:
    `### 1年目標` を `### 1年目標の振り返り` として掴む (過去データへ黙って入替) →
    除外語を足す (`## 今週の判断基準（週次レビューで使う）` が黙って空になる) →
    括弧を除いて判定する (`### 1年目標（2025年度の振り返り）` が再び黙って入替)。
    いずれも「どの見出しを採用したか」を外へ出さないことが根因で、除外語をどれだけ
    細くしても入力側の書き方次第で符号を変えて再発する。採用結果を warnings へ出せば、
    規則の当たり外れに関わらず人が気づける (extract_day_tasks の ambiguous と同じ方針)。
    """
    lines = text.splitlines()
    depth = len(level)
    start = None
    # 装飾は見出し側だけでなく引数側にも付く (`section_body(text, "【禁止事項】")`)。
    # 片側だけ落とすと完全一致も部分一致も成立せず、節が丸ごと空になる。
    aliases = (heading,) if isinstance(heading, str) else tuple(heading)
    accepted = [h.strip(TITLE_DECOR).strip() for h in aliases]
    wanted = accepted[0]
    # 部分一致だけで探すと `### 1年目標` が `### 1年目標の振り返り` に、
    # `## 習慣目標` が `## 先週の習慣目標の振り返り` に化けて、振り返り文を
    # 今期の目標として読み込む。まず完全一致 (装飾記号を落とした上で) を探し、
    # 見つからないときだけ部分一致へ落とす二段構えにする。
    candidates: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith(level + " "):
            continue
        title = stripped[depth:].strip().strip(TITLE_DECOR).strip()
        if title in accepted:
            start = i + 1
            break
        if any(a in title for a in accepted):
            candidates.append((i, title))
    if start is None and candidates:
        # 部分一致へ落とす場合も「振り返り」系の節は除く。週報の `## 1年目標の振り返り`
        # は先週の結果であって今期の目標ではないので、目標として読み込むと
        # 期間・本文がまるごと過去の内容に入れ替わる。
        usable = [c for c in candidates if not RETROSPECTIVE_RE.search(PAREN_RE.sub("", c[1]))]
        if usable:
            start = usable[0][0] + 1
            if notes is not None:
                notes.append(
                    f"「{wanted}」に完全一致する見出しが無いため、部分一致した"
                    f"「{usable[0][1]}」を採用しました。別の期の内容を読んでいないか確認してください。"
                )
        elif notes is not None:
            excluded = " / ".join(c[1] for c in candidates)
            notes.append(
                f"「{wanted}」に完全一致する見出しが無く、部分一致した「{excluded}」は"
                "振り返り節と判定して除外しました。この節は空のまま出力されます。"
            )
    if start is None:
        if notes is not None and not candidates:
            notes.append(f"「{wanted}」の見出しが見つかりませんでした。この節は空のまま出力されます。")
        return ""
    out: list[str] = []
    for line in lines[start:]:
        s = line.strip()
        if s.startswith("#"):
            hashes = len(s) - len(s.lstrip("#"))
            if hashes <= depth:
                break
        if HRULE_RE.match(line):
            break
        out.append(line)
    return "\n".join(out).strip("\n")


def bullets(body: str) -> list[str]:
    """`- ` / `- [ ] ` 行を本文だけのリストにして返す (ネストは維持せず平坦化)。"""
    items = []
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("-") or HRULE_RE.match(line):
            continue
        s = s[1:].strip()
        s = re.sub(r"^\[[ xX]\]\s*", "", s)
        if s:
            items.append(s)
    return items


# ---------- Daily (ジャーナル) 側 ----------

def scan_journals(daily_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not daily_dir.is_dir():
        return entries
    for path in sorted(daily_dir.glob("*.md")):
        m = FILE_DATE_RE.match(path.name)
        if not m:
            continue
        file_date = parse_date(m.group(1))
        if file_date is None:
            continue
        number = None
        heading_date = None
        for line in read(path).splitlines():
            hm = HEADING_RE.match(line.strip())
            if hm:
                number = int(hm.group(1))
                heading_date = parse_date(hm.group(2))
                break
        entries.append(
            {"path": path, "file_date": file_date, "number": number, "heading_date": heading_date}
        )
    return entries


def extract_journal_goals(text: str, notes: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """前回ジャーナルの目標4階層 (期間・目標本文) を取り出す。

    GOAL_KEYS は 3ヶ月/2ヶ月 のように 1 つの階層に複数の表記を持つ。実在するのは
    片方だけが正常 (正本テンプレは `### 3ヶ月目標`) なので、見出しごとの notes を
    そのまま外へ出すと「2ヶ月目標が見つかりません」が毎回出る。階層単位で保留し、
    どの表記でも解決しなかったときだけ出す。
    """
    goals: dict[str, dict[str, Any]] = {}
    pending: dict[str, list[str]] = {}
    for heading, key in GOAL_KEYS.items():
        local: list[str] | None = None if notes is None else []
        body = section_body(text, heading, level="###", notes=local)
        if not body:
            if local:
                pending.setdefault(key, []).extend(local)
            continue
        if notes is not None and local and key not in goals:
            # 部分一致で採用したメモは、その節を実際に採用したときだけ意味がある。
            notes.extend(local)
        period_start = period_end = None
        goal_text = ""
        for item in bullets(body):
            if item.startswith("期間"):
                period_start, period_end = parse_period(item)
            elif item.startswith("目標"):
                # 「目標：」ラベルだけを剥がす。split を全角→半角と二段でかけると
                # 本文に含まれる半角コロン (22:00、https:// など) でもう一度切れて
                # 目標文の先頭が黙って消える。落とすのは先頭ラベルに限る。
                goal_text = GOAL_LABEL_RE.sub("", item, count=1).strip()
        entry = {
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
            "goal": goal_text,
        }
        # 3ヶ月/2ヶ月が両方ある場合は先に出た方 (= ジャーナルの実表記) を優先
        goals.setdefault(key, entry)
        pending.pop(key, None)
    if notes is not None:
        for key, buffered in pending.items():
            if key not in goals:
                notes.extend(buffered)
    return goals


# ---------- 目標設定 (週報/月報/期報) 側 ----------

def scan_reports(goals_dir: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    if not goals_dir.is_dir():
        return reports
    for path in sorted(goals_dir.glob("*.md")):
        text = read(path)
        head = None
        for line in text.splitlines():
            if line.strip().startswith("## "):
                head = REPORT_HEAD_RE.match(line.strip())
                break
        if not head:
            continue
        key = REPORT_LABELS.get(head.group("label"))
        if key is None:
            continue
        start, end = parse_period(head.group("period"))
        if start is None or end is None:
            continue
        reports.append({"path": path, "kind": key, "start": start, "end": end, "text": text})
    return reports


def pick_report(reports: list[dict[str, Any]], kind: str, target: date) -> dict[str, Any] | None:
    """対象日を含むレポートを優先し、なければ直近過去、それも無ければ最も新しいものを返す。"""
    same_kind = [r for r in reports if r["kind"] == kind]
    if not same_kind:
        return None
    covering = [r for r in same_kind if r["start"] <= target <= r["end"]]
    if covering:
        return max(covering, key=lambda r: r["start"])
    past = [r for r in same_kind if r["end"] < target]
    if past:
        return max(past, key=lambda r: r["end"])
    return max(same_kind, key=lambda r: r["start"])


def extract_habit_goals(text: str, notes: list[str] | None = None) -> list[dict[str, Any]]:
    """週報の【習慣目標（仕組みで動く土台）】を `### N. タイトル` 単位で構造化する。

    正式名は run-ubm-goal-setting が週報の必須セクションとして検査している
    `## 【習慣目標（仕組みで動く土台）】` なので、これを別名として完全一致側へ入れる。
    入れないと正しい節を読んでいるのに毎回部分一致 fallback の警告が出る (実測)。
    """
    body = section_body(text, ("習慣目標", "習慣目標（仕組みで動く土台）"), notes=notes)
    if not body:
        return []
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("### "):
            current = {"title": re.sub(r"^###\s*\d+[.．]?\s*", "", s).strip(), "items": []}
            groups.append(current)
        elif s.startswith("-") and current is not None and not HRULE_RE.match(line):
            item = re.sub(r"^-\s*", "", s)
            checked = item.startswith("[x]") or item.startswith("[X]")
            item = re.sub(r"^\[[ xX]\]\s*", "", item)
            if item:
                current["items"].append({"text": item, "checked_in_report": checked})
    return groups


# 日付ブロックの見出し行: 「- 8/17（日）：」「- [x] 8/18 月曜」「- 8/19:」「- 8/20」。
# 以前はカッコを必須にしていたため「- 8/18 月曜」が見出しと認識されず、直前の 8/17 の
# 子タスクとして吸収されていた。当日タスクは生成本文へ直接載るので、この取り違えは
# 「別の日の予定を今日やったことにする」silent なデータ誤りになる。
# 日付見出しの書かれ方は週報ごとに揺れる。`-` 決め打ち・`/` 決め打ちにすると、
# 実在する `* 8/19（火）：` `**8/19（火）**` `2026/8/19（火）：` `8.19（火）：` を
# 見出しと認識できず、その日のタスクが直前の見出し (= 対象日) の子として
# 黙って混入する。実入力で再現済みで、警告も出なかった。
_BULLET = r"(?:[-*+]\s*)?"          # 箇条書き記号は任意 (行頭に日付だけの行もある)
_CHECK = r"(?:\[[ xX]\]\s*)?"
_EMPH = r"(?:\*\*|__|\*)?"          # 太字・斜体の装飾
_YEAR = r"(?:(?P<year>\d{4})[/.-])?"
_HEAD = rf"^{_BULLET}{_CHECK}{_EMPH}{_YEAR}"
# 曜日注記は括弧型 `（火）` と「火曜」型の両方。「曜」まで揃って初めて曜日とみなす。
# 「曜」を任意にすると「- 8/27 日程調整する」の『日』が曜日に化ける。
_WD_CORE = r"(?:\s*[（(]\s*[月火水木金土日]\s*[）)]|\s*[月火水木金土日]曜日?)"
_WD = rf"(?:{_WD_CORE})?"
# 見出しと確定できる形: 日付 (+曜日) の直後が行末か `：` のときだけ。
# 「- 8/18 の資料を作る」のように本文が続く行は見出しにせず ambiguous 側へ倒す。
# (?P<rest>.*) は `- 8/19（火）：資料を作る` のように見出しと同じ行へ書かれたタスク本文。
# 以前は見出し行を丸ごと捨てていたため、この書き方だとタスクが黙って消えていた。
_TAIL = rf"\s*{_EMPH}\s*(?:[：:]\s*(?P<rest>.*))?$"

# 区切り記号ごとに別の正規表現へ分ける。1本の `[/.]` にまとめると、`.` が
# 小数・時刻と衝突する。`- 2.0：リリースする` が 2/0 の見出しに、`- 9.30：朝会` が
# 9/30 の見出しに化け、以降のタスクが collecting=False のまま warning ゼロで消えた
# (実測)。`.` 区切りの日付は実データでは必ず曜日注記を伴うので、`.` のときだけ
# 曜日を必須にして小数・時刻と切り分ける。
_MD_SLASH = r"(?P<month>\d{1,2})[/-](?P<day>\d{1,2})"
_MD_DOT = r"(?P<month>\d{1,2})\.(?P<day>\d{1,2})"
# 和文表記 `8月19日（水）：` は最も自然な書き方なのに、記号区切りだけを見ていた頃は
# 見出しと認識されず、その行自体がタスクとして混入したうえ以降が別日のまま残った。
_MD_JP = r"(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日"

DAY_HEAD_RES = (
    re.compile(rf"{_HEAD}{_MD_SLASH}{_WD}{_TAIL}"),
    re.compile(rf"{_HEAD}{_MD_DOT}{_WD_CORE}{_TAIL}"),
    re.compile(rf"{_HEAD}{_MD_JP}{_WD}{_TAIL}"),
)
# 見出しか子タスクか決めきれない行 (例: 「- 8/18 の資料を作る」)。下の判定では子タスク側に
# 倒すが、倒した事実を黙らせない。誤帰属していれば人が気づけるよう warnings へ出す。
DAY_LIKE_RES = (
    re.compile(rf"{_HEAD}{_MD_SLASH}\b"),
    re.compile(rf"{_HEAD}{_MD_JP}"),
)


def _valid_md(m: re.Match[str]) -> bool:
    """暦として成立する月日か。正規表現は桁数しか見ないので範囲はここで弾く。

    `2.0` の day=0 や `13/40` を見出しとして通すと、その行以降のタスクが
    存在しない日付に紐づいて黙って落ちる。
    """
    return 1 <= int(m.group("month")) <= 12 and 1 <= int(m.group("day")) <= 31


def match_day_heading(s: str) -> re.Match[str] | None:
    """日付見出し行なら Match を返す。表記ゆれ 3 系統を順に試す。"""
    for rx in DAY_HEAD_RES:
        m = rx.match(s)
        if m and _valid_md(m):
            return m
    return None


def looks_like_day(s: str) -> bool:
    """見出しと確定できないが日付で始まる行か (ambiguous 判定用)。"""
    return any((m := rx.match(s)) and _valid_md(m) for rx in DAY_LIKE_RES)
# 箇条書き記号は `-` だけではない。`-` 決め打ちにすると `* 資料を作る` が
# 対象日の子タスクとして数えられず、その日のタスクが静かに欠落する。
BULLET_LINE_RE = re.compile(r"^[-*+]\s")


def extract_day_tasks(text: str, target: date, notes: list[str] | None = None) -> tuple[list[str], list[str]]:
    """【今週の大きな到達ライン】から対象日 (M/D) の子タスクを取り出す。

    返り値は (対象日のタスク, 日付見出しと判別しきれなかった行) の組。
    """
    body = section_body(text, "今週の大きな到達ライン", notes=notes)
    if not body:
        return [], []
    collecting = False
    tasks: list[str] = []
    ambiguous: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        m = match_day_heading(s)
        if m:
            # 年が書かれていれば照合する。M/D だけで判定すると、対象日を含まない
            # (covers_target=false) 別年のレポートを参照したときに 8/19 が一致し、
            # 去年のタスクが今日のものとして混ざる。年の記載が無い場合は
            # 「そのレポートの年」を主張できないので従来どおり M/D だけで見る。
            year = m.group("year")
            same_day = int(m.group("month")) == target.month and int(m.group("day")) == target.day
            collecting = same_day and (year is None or int(year) == target.year)
            rest = (m.group("rest") or "").strip()
            if collecting and rest:
                # 見出しと同じ行に書かれた本文。continue で捨てると黙って消える。
                tasks.append(rest)
            continue
        if not BULLET_LINE_RE.match(s):
            continue
        if looks_like_day(s):
            ambiguous.append(s)
        item = re.sub(r"^[-*+]\s*", "", s)
        item = re.sub(r"^\[[ xX]\]\s*", "", item).strip()
        if collecting and item:
            tasks.append(item)
    return tasks, ambiguous


def load_daily_habits() -> list[dict[str, Any]]:
    """毎日固定の習慣リストを読む。欠落・壊れは fail-closed (毎日確認する契約を素通しさせない)。"""
    if not DAILY_HABITS_PATH.exists():
        print(
            f"[build-journal-context] daily-habits.json が見つかりません: {DAILY_HABITS_PATH}",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        data = json.loads(DAILY_HABITS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[build-journal-context] daily-habits.json の解析失敗: {exc}", file=sys.stderr)
        sys.exit(2)
    # top-level が dict でない (例: JSON 配列) と .get が AttributeError になり、
    # frontmatter が宣言した exit 0/2 ではなく traceback 付き exit 1 で落ちる。
    if not isinstance(data, dict):
        print(
            "[build-journal-context] daily-habits.json の top-level が object ではありません",
            file=sys.stderr,
        )
        sys.exit(2)
    habits = data.get("habits")
    if not isinstance(habits, list) or not habits:
        print("[build-journal-context] daily-habits.json の habits が空です", file=sys.stderr)
        sys.exit(2)
    # 個々の habit の形も読み込み時に確定させる。ここを素通しすると、下流の
    # 素の添字アクセスが KeyError → traceback + exit 1 になり、frontmatter が
    # 宣言した「破損 = exit 2」と食い違う。SKILL.md は利用者をこの JSON の
    # 編集へ誘導しているので、壊し方は現実的な経路である。
    for i, h in enumerate(habits):
        for problem in habit_schema_problems(h, i):
            print(f"[build-journal-context] daily-habits.json {problem}", file=sys.stderr)
            sys.exit(2)
    return habits


def habit_schema_problems(h: object, i: int) -> list[str]:
    """habit 1件の形の不備を列挙する。validate-journal-output.py と同じ検査を、
    `id` (context JSON へ載り LLM が習慣を名指しするキー) の分だけ厳しくしたもの。
    厳しい側が先に立つ配置なので、Phase0 を通った JSON は Phase5 でも必ず通る。

    SKILL.md Gotchas は「Phase0 の exit 2 は daily-habits.json 破損を含む」と宣言している。
    ここで id/label しか見ないと、target_section 欠落・keywords が文字列・
    search_scopes[].heading 欠落は Phase0 を通過し、利用者が 5〜10 分の対話を終えた
    Phase5 で初めて壊れが判明する。検知は最初のゲートで済ませる。
    """
    where = f"habits[{i}]"
    if not isinstance(h, dict):
        return [f"{where} が object ではありません"]
    problems = []
    for key in ("id", "label", "target_section"):
        if not isinstance(h.get(key), str) or not h[key].strip():
            problems.append(f"{where} の {key} が非空文字列ではありません")
    kws = h.get("keywords")
    if not isinstance(kws, list) or not kws or not all(isinstance(k, str) and k for k in kws):
        problems.append(f"{where} の keywords が非空文字列の配列ではありません")
    scopes = h.get("search_scopes")
    if scopes is not None:
        if not isinstance(scopes, list) or not scopes:
            problems.append(f"{where} の search_scopes が非空配列ではありません")
        else:
            for j, sc in enumerate(scopes):
                if not isinstance(sc, dict):
                    problems.append(f"{where}.search_scopes[{j}] が object ではありません")
                    continue
                if not isinstance(sc.get("heading"), str) or not sc["heading"]:
                    problems.append(f"{where}.search_scopes[{j}] の heading がありません")
                lv = sc.get("level", 2)
                if not isinstance(lv, int) or isinstance(lv, bool) or not 1 <= lv <= 6:
                    problems.append(f"{where}.search_scopes[{j}] の level が 1-6 の整数ではありません")
    return problems


def classify_existing_file(same_day: dict[str, Any] | None, target: date) -> dict[str, Any]:
    """対象日のファイルが既にある場合の「書き込んで安全か」を判定する。

    ジャーナルは毎回 Write で全置換されるため、既存ファイルの扱いを誤ると
    利用者の実データが消える。実際に 2026-08-17.md には見出し
    `# No.388 - ジャーナル（2026-08-16）` を持つ 27KB の別日ジャーナルが存在し、
    無引数実行で丸ごと置換される状態だった (C-1)。

    same_day は scan_journals の要素 (path / file_date / number / heading_date) か
    None。返り値は最低限 "write_mode" を持つ dict とし、呼び出し側はこれを
    context["existing_file"] としてそのまま露出する。

    write_mode の取りうる値:
      "new"      = 対象パスにファイルが無い。そのまま Write してよい。
      "regenerate" = 同じ日のジャーナルを作り直す。番号を維持し、確認のうえ Write。
      "blocked"  = 別日の内容が入っている。Write すると失われるので停止する。
    """
    if same_day is None:
        # scan_journals は FILE_DATE_RE (^YYYY-MM-DD\.md$) にマッチする全ファイルを
        # 見出しの有無に関わらず entries へ入れる。よって None は「対象パスにファイルが
        # 無い」と同義で、新規作成してよい唯一のケース。
        return {"write_mode": "new"}

    info = {
        "path": str(same_day["path"]),
        "number": same_day["number"],
        "heading_date": same_day["heading_date"].isoformat() if same_day["heading_date"] else None,
    }

    if same_day["heading_date"] == target:
        return {**info, "write_mode": "regenerate"}

    # heading_date が None (旧形式の `# No.149 - ジャーナル` や見出しの無い手書きメモ) の
    # 場合も blocked にする。中身が対象日のものか判別できない以上、「判別できない」を
    # 「上書きしてよい」と読み替えるのは、消えるのが利用者の実データである以上許されない。
    # 誤って止まっても失うのは一手間だが、誤って書けば失うのは記録そのもの。
    return {**info, "write_mode": "blocked"}


def build_context(vault: Path, target: date) -> dict[str, Any]:
    daily_dir = vault / DAILY_REL
    goals_dir = vault / GOALS_REL
    warnings: list[str] = []

    journals = scan_journals(daily_dir)
    numbered = [j for j in journals if j["number"] is not None]
    same_day = next((j for j in journals if j["file_date"] == target), None)
    existing = classify_existing_file(same_day, target)
    if existing.get("write_mode") == "blocked":
        # heading_date が None なのは「別日」ではなく「日付を判別できない中身」。
        # 空ファイルや旧形式の見出しを「別日 (None) のジャーナル」と書くと事実と食い違う。
        head = existing.get("heading_date")
        what = f"別日 ({head}) のジャーナル" if head else "日付を判別できない内容"
        warnings.append(
            f"{target.isoformat()}.md には{what}が入っています。"
            "Write すると失われるため、上書きせず停止して利用者へ確認してください。"
        )

    # 番号を維持してよいのは regenerate (同じ日のジャーナルを作り直す) のときだけ。
    # blocked は「別日のジャーナルが入っている」状態なので、その番号は他日のものであり
    # 再利用すると番号が重複する。停止指示と「番号を維持して更新扱い」を同時に出さない。
    if existing.get("write_mode") == "regenerate" and same_day["number"] is not None:
        number = same_day["number"]
        is_regeneration = True
        warnings.append(
            f"{target.isoformat()} のジャーナルは既に存在します (No.{number})。番号を維持して更新扱いにします。"
        )
    else:
        max_number = max((j["number"] for j in numbered), default=0)
        number = max_number + 1
        is_regeneration = existing.get("write_mode") == "regenerate"
        if not numbered:
            warnings.append("既存ジャーナルから番号を検出できなかったため No.1 から採番します。")

    previous = None
    # section_body の見出し解決メモ。どの文書を読んだ結果かを取り違えないよう
    # ソース別に集め、warnings へ出すときに出所を前置きする。
    prev_notes: list[str] = []
    wk_notes: list[str] = []
    past_journals = [j for j in journals if j["file_date"] < target and j["number"] is not None]
    if past_journals:
        prev = max(past_journals, key=lambda j: j["file_date"])
        prev_text = read(prev["path"])
        previous = {
            "path": str(prev["path"]),
            "file_date": prev["file_date"].isoformat(),
            "number": prev["number"],
            "heading_date": prev["heading_date"].isoformat() if prev["heading_date"] else None,
            "ultimate_purpose": bullets(section_body(prev_text, "人生の究極目的", notes=prev_notes)),
            "goals": extract_journal_goals(prev_text, notes=prev_notes),
            "prohibitions": bullets(section_body(prev_text, "【禁止事項】", notes=prev_notes)),
            "phase_checklist": section_body(prev_text, "フェーズ別 課題チェックシート", level="#", notes=prev_notes),
        }
        if prev["number"] is not None and number != prev["number"] + 1 and not is_regeneration:
            warnings.append(
                f"前回 No.{prev['number']} に対し今回 No.{number} です (Daily 全体の最大値 +1 で採番)。"
            )
    else:
        warnings.append(
            "前回ジャーナルが見つかりません。目標本文・究極目的・フェーズ別チェックは対話で確定し、"
            "あわせてジャーナル習慣が途切れていないかも確認してください。"
        )

    reports = scan_reports(goals_dir)
    if not reports:
        warnings.append(f"{goals_dir} に週報/月報/期報が見つかりません。目標の期間は対話で確定してください。")

    prev_goals = (previous or {}).get("goals", {})
    goals: dict[str, Any] = {}
    report_info: dict[str, Any] = {}

    for key in ("weekly", "monthly", "quarterly"):
        report = pick_report(reports, key, target)
        inherited = prev_goals.get(key, {})
        start = end = None
        if report:
            start, end = report["start"], report["end"]
            report_info[key] = {
                "path": str(report["path"]),
                "period": f"{start.isoformat()}〜{end.isoformat()}",
                "covers_target": report["start"] <= target <= report["end"],
            }
            if not report_info[key]["covers_target"]:
                warnings.append(
                    f"{key}: 対象日 {target.isoformat()} を含むレポートが無く、直近の"
                    f" {start.isoformat()}〜{end.isoformat()} を参照しています。"
                )
            inherited_end = parse_date(inherited.get("period_end") or "")
            if inherited_end and inherited_end != end:
                warnings.append(
                    f"{key}: 前回ジャーナルの期間終了日 {inherited_end.isoformat()} と"
                    f" レポートの {end.isoformat()} が異なります。目標本文を新しい期間の内容へ更新してください。"
                )
        else:
            start = parse_date(inherited.get("period_start") or "")
            end = parse_date(inherited.get("period_end") or "")

        # inherited が空でない dict であることを継承成立とみなすと、期間だけ拾えて目標本文が
        # 空のときまで source="previous_journal" になり、未解決が未解決として出てこない。
        # 「引き継げた」と言えるのは実際に値が入っている場合だけに限る。
        #
        # report の有無を source の第一条件にしていたのも同じ穴だった。目標本文を
        # 供給するのは前回ジャーナルだけで、レポートが与えるのは期間である。よって
        # レポートがあるだけで source="report" にすると、goal="" のまま「解決済み」と
        # 名乗り、消費側が未解決を未解決として扱えなくなる (実測で再現)。
        # source は「目標本文が取れたか」で決め、期間の出所はそこに混ぜない。
        resolved = has_value(inherited)
        entry = {
            "period_start": start.isoformat() if start else None,
            "period_end": end.isoformat() if end else None,
            "goal": inherited.get("goal", ""),
            "source": ("report" if report else "previous_journal") if resolved else "unresolved",
        }
        entry.update(days_remaining(target, end))
        if not resolved:
            warnings.append(
                f"{key}: 目標本文を引き継げませんでした (前回ジャーナルに記載なし)。"
                "対話で確認して埋めてください。"
            )
        goals[key] = entry

    # 1年目標はレポートに対応物が無いため前回ジャーナルからの継承のみ
    yearly = dict(prev_goals.get("yearly", {}))
    yearly_end = parse_date(yearly.get("period_end") or "")
    yearly_entry = {
        "period_start": yearly.get("period_start"),
        "period_end": yearly.get("period_end"),
        "goal": yearly.get("goal", ""),
        "source": "previous_journal" if has_value(yearly) else "unresolved",
    }
    yearly_entry.update(days_remaining(target, yearly_end))
    if yearly_entry.get("expired"):
        warnings.append("1年目標の期間が終了しています。新サイクルの1年目標を設定するか確認してください。")
    goals["yearly"] = yearly_entry

    weekly_report = pick_report(reports, "weekly", target)
    weekly_payload: dict[str, Any] = {}
    if weekly_report:
        wtext = weekly_report["text"]
        day_tasks, ambiguous_days = extract_day_tasks(wtext, target, notes=wk_notes)
        weekly_payload = {
            "path": str(weekly_report["path"]),
            "period": f"{weekly_report['start'].isoformat()}〜{weekly_report['end'].isoformat()}",
            "habit_goals": extract_habit_goals(wtext, notes=wk_notes),
            "judgment_criteria": section_body(wtext, "今週の判断基準", notes=wk_notes).strip(),
            "day_tasks": day_tasks,
            "key_numbers": bullets(section_body(wtext, "今週の最重要数字", notes=wk_notes)),
            "outcome_goals": bullets(section_body(wtext, "今週の売上以外の成果目標", notes=wk_notes)),
            "weekly_revenue_goal": section_body(wtext, "今週の売上目標", notes=wk_notes).strip(),
        }
        if not weekly_payload["day_tasks"]:
            warnings.append(
                f"週報の到達ラインに {target.month}/{target.day} の行が無く、当日タスクを引き継げませんでした。"
            )
        if ambiguous_days:
            warnings.append(
                "週報の到達ラインに日付見出しか子タスクか判別できない行があります"
                f" ({' / '.join(ambiguous_days)})。子タスクとして扱ったため、"
                "別の日の予定が当日タスクへ混ざっていないか確認してください。"
            )

    daily_habits = load_daily_habits()

    # 前回ジャーナル不在の warning は上流 (継承材料の不在) で 1 本出している。
    # ここで習慣シグナル分をもう 1 本足すと、同じ事実で 2 回聞く導線になるため統合済み。

    # 見出し解決メモを warnings へ合流させる。重複は落とすが件数の上限は設けない
    # (「気づけるように出す」のが目的なので、多いこと自体は隠す理由にならない)。
    for label, notes in (("前回ジャーナル", prev_notes), ("週報", wk_notes)):
        for note in dict.fromkeys(notes):
            warnings.append(f"{label}: {note}")

    return {
        "target_date": target.isoformat(),
        "journal_number": number,
        "is_regeneration": is_regeneration,
        "existing_file": existing,
        "output_path": str(daily_dir / f"{target.isoformat()}.md"),
        "heading": f"# No.{number} - ジャーナル（{target.isoformat()}）",
        "previous_journal": previous,
        "goals": goals,
        "report_sources": report_info,
        "weekly_report": weekly_payload,
        "daily_habits": daily_habits,
        "warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="日次ジャーナルの文脈 (番号・目標・週報引き継ぎ) を解決する")
    ap.add_argument("--vault-root", default=os.environ.get("UBM_VAULT_ROOT", ""))
    ap.add_argument("--date", default="", help="対象日 YYYY-MM-DD (省略時は今日)")
    args = ap.parse_args()

    if not args.vault_root.strip():
        sys.stderr.write("build-journal-context: --vault-root か UBM_VAULT_ROOT が必要です。\n")
        return 2
    vault = Path(os.path.expanduser(args.vault_root.strip())).resolve()

    if args.date.strip():
        target = parse_date(args.date)
        if target is None:
            sys.stderr.write(f"build-journal-context: --date を解釈できません: {args.date}\n")
            return 2
    else:
        target = datetime.now().date()

    daily_dir = vault / DAILY_REL
    if not daily_dir.is_dir():
        sys.stderr.write(f"build-journal-context: Daily ディレクトリが見つかりません: {daily_dir}\n")
        return 2

    context = build_context(vault, target)
    json.dump(context, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
