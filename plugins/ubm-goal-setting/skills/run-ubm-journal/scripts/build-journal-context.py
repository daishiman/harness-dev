#!/usr/bin/env python3
# /// script
# name: build-journal-context
# version: 0.1.0
# purpose: 日次ジャーナル作成の決定論的な前提 (通し番号・出力パス・目標4階層の期間と残日数・
#          最新週報から引き継ぐ習慣目標/判断基準/当日タスク・前回ジャーナルの継承値) を
#          1 回の実行で JSON 化する。番号採番と日数計算を LLM に推測させないための決定論ゲート。
# inputs:
#   - argv: --vault-root <path> (省略時 env UBM_VAULT_ROOT) / --date YYYY-MM-DD (省略時 today)
#   - files: {vault}/02_Configs/Daily/*.md, {vault}/05_Project/UBM/目標設定/*.md
# outputs:
#   - stdout: context JSON (下記 SCHEMA)
#   - exit: 0=解決成功 / 1=vault 解決不能・Daily ディレクトリ不在 (fail-closed)
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
    if end is None:
        return {"days_remaining": None, "expired": None}
    delta = (end - target).days
    if delta < 0:
        return {"days_remaining": 0, "expired": True, "days_overdue": -delta}
    return {"days_remaining": delta, "expired": False}


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


HRULE_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")


def section_body(text: str, heading: str, level: str = "##") -> str:
    """`{level} {heading}` 見出し直下から、同レベル以上の次見出しまでの本文を返す。

    Markdown の水平線 (`---`) はセクションの実質的な終端として扱う。ハイフン始まりゆえ
    そのままでは箇条書きと区別がつかず、次セクションの区切り線が本文へ混入する。
    """
    lines = text.splitlines()
    depth = len(level)
    start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(level + " ") and heading in stripped[depth:]:
            start = i + 1
            break
    if start is None:
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


def extract_journal_goals(text: str) -> dict[str, dict[str, Any]]:
    """前回ジャーナルの目標4階層 (期間・目標本文) を取り出す。"""
    goals: dict[str, dict[str, Any]] = {}
    for heading, key in GOAL_KEYS.items():
        body = section_body(text, heading, level="###")
        if not body:
            continue
        period_start = period_end = None
        goal_text = ""
        for item in bullets(body):
            if item.startswith("期間"):
                period_start, period_end = parse_period(item)
            elif item.startswith("目標"):
                goal_text = item.split("：", 1)[-1].split(":", 1)[-1].strip()
        entry = {
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
            "goal": goal_text,
        }
        # 3ヶ月/2ヶ月が両方ある場合は先に出た方 (= ジャーナルの実表記) を優先
        goals.setdefault(key, entry)
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


def extract_habit_goals(text: str) -> list[dict[str, Any]]:
    """週報の【習慣目標（仕組みで動く土台）】を `### N. タイトル` 単位で構造化する。"""
    body = section_body(text, "習慣目標")
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


def extract_day_tasks(text: str, target: date) -> list[str]:
    """【今週の大きな到達ライン】から対象日 (M/D) の子タスクだけを取り出す。"""
    body = section_body(text, "今週の大きな到達ライン")
    if not body:
        return []
    day_head = re.compile(r"^-\s*(?:\[[ xX]\]\s*)?(\d{1,2})/(\d{1,2})\s*[（(]")
    collecting = False
    tasks: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        m = day_head.match(s)
        if m:
            collecting = int(m.group(1)) == target.month and int(m.group(2)) == target.day
            continue
        if collecting and s.startswith("-"):
            item = re.sub(r"^-\s*", "", s)
            item = re.sub(r"^\[[ xX]\]\s*", "", item).strip()
            if item:
                tasks.append(item)
    return tasks


def load_daily_habits() -> list[dict[str, Any]]:
    """毎日固定の習慣リストを読む。欠落・壊れは fail-closed (毎日確認する契約を素通しさせない)。"""
    if not DAILY_HABITS_PATH.exists():
        print(
            f"[build-journal-context] daily-habits.json が見つかりません: {DAILY_HABITS_PATH}",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        data = json.loads(DAILY_HABITS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[build-journal-context] daily-habits.json の解析失敗: {exc}", file=sys.stderr)
        sys.exit(1)
    habits = data.get("habits")
    if not isinstance(habits, list) or not habits:
        print("[build-journal-context] daily-habits.json の habits が空です", file=sys.stderr)
        sys.exit(1)
    return habits


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
        warnings.append(
            f"{target.isoformat()}.md には別日 "
            f"({existing.get('heading_date')}) のジャーナルが入っています。"
            "Write すると失われるため、上書きせず停止して利用者へ確認してください。"
        )

    if same_day is not None and same_day["number"] is not None:
        number = same_day["number"]
        is_regeneration = True
        warnings.append(
            f"{target.isoformat()} のジャーナルは既に存在します (No.{number})。番号を維持して更新扱いにします。"
        )
    else:
        max_number = max((j["number"] for j in numbered), default=0)
        number = max_number + 1
        is_regeneration = same_day is not None
        if not numbered:
            warnings.append("既存ジャーナルから番号を検出できなかったため No.1 から採番します。")

    previous = None
    past_journals = [j for j in journals if j["file_date"] < target and j["number"] is not None]
    if past_journals:
        prev = max(past_journals, key=lambda j: j["file_date"])
        prev_text = read(prev["path"])
        previous = {
            "path": str(prev["path"]),
            "file_date": prev["file_date"].isoformat(),
            "number": prev["number"],
            "heading_date": prev["heading_date"].isoformat() if prev["heading_date"] else None,
            "ultimate_purpose": bullets(section_body(prev_text, "人生の究極目的")),
            "goals": extract_journal_goals(prev_text),
            "prohibitions": bullets(section_body(prev_text, "【禁止事項】")),
            "phase_checklist": section_body(prev_text, "フェーズ別 課題チェックシート", level="#"),
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

        entry = {
            "period_start": start.isoformat() if start else None,
            "period_end": end.isoformat() if end else None,
            "goal": inherited.get("goal", ""),
            "source": "report" if report else ("previous_journal" if inherited else "unresolved"),
        }
        entry.update(days_remaining(target, end))
        goals[key] = entry

    # 1年目標はレポートに対応物が無いため前回ジャーナルからの継承のみ
    yearly = dict(prev_goals.get("yearly", {}))
    yearly_end = parse_date(yearly.get("period_end") or "")
    yearly_entry = {
        "period_start": yearly.get("period_start"),
        "period_end": yearly.get("period_end"),
        "goal": yearly.get("goal", ""),
        "source": "previous_journal" if yearly else "unresolved",
    }
    yearly_entry.update(days_remaining(target, yearly_end))
    if yearly_entry.get("expired"):
        warnings.append("1年目標の期間が終了しています。新サイクルの1年目標を設定するか確認してください。")
    goals["yearly"] = yearly_entry

    weekly_report = pick_report(reports, "weekly", target)
    weekly_payload: dict[str, Any] = {}
    if weekly_report:
        wtext = weekly_report["text"]
        weekly_payload = {
            "path": str(weekly_report["path"]),
            "period": f"{weekly_report['start'].isoformat()}〜{weekly_report['end'].isoformat()}",
            "habit_goals": extract_habit_goals(wtext),
            "judgment_criteria": section_body(wtext, "今週の判断基準").strip(),
            "day_tasks": extract_day_tasks(wtext, target),
            "key_numbers": bullets(section_body(wtext, "今週の最重要数字")),
            "outcome_goals": bullets(section_body(wtext, "今週の売上以外の成果目標")),
            "weekly_revenue_goal": section_body(wtext, "今週の売上目標").strip(),
        }
        if not weekly_payload["day_tasks"]:
            warnings.append(
                f"週報の到達ラインに {target.month}/{target.day} の行が無く、当日タスクを引き継げませんでした。"
            )

    daily_habits = load_daily_habits()

    # 前回ジャーナル不在の warning は上流 (継承材料の不在) で 1 本出している。
    # ここで習慣シグナル分をもう 1 本足すと、同じ事実で 2 回聞く導線になるため統合済み。

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
        return 1
    vault = Path(os.path.expanduser(args.vault_root.strip())).resolve()

    if args.date.strip():
        target = parse_date(args.date)
        if target is None:
            sys.stderr.write(f"build-journal-context: --date を解釈できません: {args.date}\n")
            return 1
    else:
        target = datetime.now().date()

    daily_dir = vault / DAILY_REL
    if not daily_dir.is_dir():
        sys.stderr.write(f"build-journal-context: Daily ディレクトリが見つかりません: {daily_dir}\n")
        return 1

    context = build_context(vault, target)
    json.dump(context, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
