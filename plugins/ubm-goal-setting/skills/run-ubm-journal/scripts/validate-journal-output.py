#!/usr/bin/env python3
# /// script
# name: validate-journal-output
# version: 0.1.0
# purpose: 生成した日次ジャーナル Markdown が正本フォーマット (見出し17ブロック・目標4階層の
#          期間/残り/目標・3ジャーナル×3小節・フェーズ別課題チェックシート) を満たすかを
#          保存前に検査する決定論ゲート。未置換プレースホルダと空セクションを FAIL にする。
# inputs:
#   - argv: --file <path> [--expected-number N] [--expected-date YYYY-MM-DD]
# outputs:
#   - stdout: PASS/FAIL と違反一覧
#   - exit: 0=PASS / 1=FAIL / 2=引数不正・ファイル読み込み不能 (fail-closed)
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""日次ジャーナルの保存前バリデーション。

「フォーマットに合わせる」ことより「やったことを構造的にまとめる」ことが目的なので、
本文の中身までは縛らない。検査するのは (1) 骨格の存在と順序、(2) 各枠が実際に埋まって
いること、(3) テンプレのプレースホルダが残っていないこと、の3点に絞る。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 毎日固定の習慣リストの正本。build-journal-context.py と同じファイルを見る (SSOT 一本化)。
DAILY_HABITS_PATH = Path(__file__).resolve().parents[1] / "references" / "daily-habits.json"


def load_daily_habits() -> list[dict]:
    """固定習慣リストを読む。欠落・壊れは H01 検査を素通しさせないため即時終了する。"""
    try:
        data = json.loads(DAILY_HABITS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"validate-journal-output: daily-habits.json を読めません: {exc}\n")
        sys.exit(2)
    habits = data.get("habits")
    if not isinstance(habits, list) or not habits:
        sys.stderr.write("validate-journal-output: daily-habits.json の habits が空です\n")
        sys.exit(2)
    return habits

HEADING_RE = re.compile(r"^#\s*No\.\s*(\d+)\s*[-–—]\s*ジャーナル\s*[（(]\s*(\d{4}-\d{2}-\d{2})\s*[)）]\s*$")
FILE_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
PLACEHOLDER_RE = re.compile(r"\[(?:数字|名前|日数|感謝の内容|分類|3ヶ月目標|1ヶ月目標|1週間目標|yyyy/mm/dd)\]")
HRULE_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")

# (見出しレベル, 見出しに含まれるべき文字列) を出現順で並べた骨格の正本
REQUIRED_OUTLINE = [
    (1, "人生の究極の目標"),
    (1, "ジャーナル"),
    (2, "人生の究極目的"),
    (2, "目標"),
    (3, "1年目標"),
    (3, "3ヶ月目標"),
    (3, "1ヶ月目標"),
    (3, "1週間目標"),
    (2, "感謝"),
    (2, "【禁止事項】"),
    (2, "【タスク】"),
    (2, "【行動のジャーナル】"),
    (2, "【時間のジャーナル】"),
    (2, "【お金のジャーナル】"),
    (1, "フェーズ別 課題チェックシート"),
]

JOURNAL_SECTIONS = ["【行動のジャーナル】", "【時間のジャーナル】", "【お金のジャーナル】"]
JOURNAL_SUBSECTIONS = ["現状を確認する", "効果性を評価する", "更に良くする方法はないか"]
GOAL_SECTIONS = ["1年目標", "3ヶ月目標", "1ヶ月目標", "1週間目標"]
PHASE_SECTIONS = ["【0→1】", "【1→10】", "【10→100】"]


def headings(lines: list[str]) -> list[tuple[int, str, int]]:
    """(レベル, テキスト, 行番号) の一覧。"""
    out = []
    for i, line in enumerate(lines, start=1):
        s = line.strip()
        if not s.startswith("#"):
            continue
        level = len(s) - len(s.lstrip("#"))
        text = s[level:].strip()
        if text:
            out.append((level, text, i))
    return out


def section_lines(lines: list[str], level: int, needle: str) -> list[str] | None:
    """指定見出し直下の本文行 (同レベル以上の次見出しまで) を返す。見出しが無ければ None。"""
    start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if not s.startswith("#"):
            continue
        lv = len(s) - len(s.lstrip("#"))
        text = s[lv:].strip()
        if start is None:
            if lv == level and needle in text:
                start = i + 1
            continue
        if lv <= level:
            return lines[start:i]
    if start is None:
        return None
    return lines[start:]


def content_bullets(body: list[str]) -> list[str]:
    items = []
    for line in body:
        s = line.strip()
        if not s.startswith("-") or HRULE_RE.match(line):
            continue
        s = re.sub(r"^-\s*", "", s)
        s = re.sub(r"^\[[ xX]\]\s*", "", s).strip()
        if s:
            items.append(s)
    return items


def validate(path: Path, expected_number: int | None, expected_date: str | None) -> list[str]:
    violations: list[str] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # --- ファイル名と見出しの整合 ---
    fm = FILE_DATE_RE.match(path.name)
    file_date = fm.group(1) if fm else None
    if not fm:
        violations.append(f"F01: ファイル名が YYYY-MM-DD.md 形式ではありません: {path.name}")

    heading = None
    for line in lines:
        m = HEADING_RE.match(line.strip())
        if m:
            heading = m
            break
    if heading is None:
        violations.append("F02: 「# No.<数字> - ジャーナル（YYYY-MM-DD）」の見出しがありません")
    else:
        number, heading_date = int(heading.group(1)), heading.group(2)
        if file_date and heading_date != file_date:
            violations.append(
                f"F03: 見出しの日付 {heading_date} がファイル名の日付 {file_date} と一致しません"
                "（ファイル日付＝見出し日付＝振り返る日）"
            )
        if expected_number is not None and number != expected_number:
            violations.append(
                f"F04: 通し番号 No.{number} が期待値 No.{expected_number} と一致しません"
                "（build-journal-context の採番を使ってください）"
            )
        if expected_date is not None and heading_date != expected_date:
            violations.append(f"F05: 見出しの日付 {heading_date} が対象日 {expected_date} と一致しません")

    # --- 骨格の存在と順序 ---
    hs = headings(lines)
    cursor = 0
    for level, needle in REQUIRED_OUTLINE:
        found = None
        for idx in range(cursor, len(hs)):
            lv, txt, _ = hs[idx]
            if lv == level and needle in txt:
                found = idx
                break
        if found is None:
            violations.append(f"S01: 必須見出しが見つからないか順序が不正です: {'#' * level} {needle}")
        else:
            cursor = found + 1

    # --- 目標4階層: 期間・残り・目標が揃っているか ---
    for goal in GOAL_SECTIONS:
        body = section_lines(lines, 3, goal)
        if body is None:
            continue  # S01 で既に報告済み
        joined = "\n".join(body)
        for field in ("期間", "残り", "目標"):
            if not re.search(rf"^\s*-\s*{field}\s*[：:]", joined, re.MULTILINE):
                violations.append(f"G01: {goal} に「- {field}：」の行がありません")
        if not re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}\s*[〜～~]\s*\d{4}[-/]\d{1,2}[-/]\d{1,2}", joined):
            violations.append(f"G02: {goal} の期間が YYYY-MM-DD〜YYYY-MM-DD 形式で書かれていません")

    # --- 中身が埋まっているか ---
    for needle, rule, minimum in (
        ("人生の究極目的", "C01", 1),
        ("感謝", "C02", 1),
        ("【禁止事項】", "C03", 1),
    ):
        body = section_lines(lines, 2, needle)
        if body is None:
            continue
        if len(content_bullets(body)) < minimum:
            violations.append(f"{rule}: {needle} に箇条書きが {minimum} 件以上必要です")

    task_body = section_lines(lines, 2, "【タスク】")
    if task_body is not None:
        subheads = [l for l in task_body if l.strip().startswith("### ")]
        if not subheads:
            violations.append("C04: 【タスク】に分類見出し（### 【分類名】）が1つ以上必要です")
        elif not content_bullets(task_body):
            violations.append("C05: 【タスク】の分類の下に箇条書きが1件以上必要です")

    for section in JOURNAL_SECTIONS:
        body = section_lines(lines, 2, section)
        if body is None:
            continue
        for sub in JOURNAL_SUBSECTIONS:
            sub_body = section_lines(body, 3, sub)
            if sub_body is None:
                violations.append(f"J01: {section} に「### {sub}」がありません")
            elif not content_bullets(sub_body):
                violations.append(f"J02: {section} の「{sub}」が空です（箇条書き1件以上）")

    phase_body = section_lines(lines, 1, "フェーズ別 課題チェックシート")
    if phase_body is not None:
        for phase in PHASE_SECTIONS:
            if not any(phase in l for l in phase_body if l.strip().startswith("## ")):
                violations.append(f"P01: フェーズ別課題チェックシートに「## ◇{phase}」がありません")
        checks = [l for l in phase_body if re.match(r"^\s*-\s*\[[ xX]\]", l)]
        if not checks:
            violations.append("P02: フェーズ別課題チェックシートにチェックボックス行がありません")

    # --- 未置換プレースホルダ ---
    for i, line in enumerate(lines, start=1):
        m = PLACEHOLDER_RE.search(line)
        if m:
            violations.append(f"X01: L{i} にテンプレートのプレースホルダ {m.group(0)} が残っています")

    # --- 毎日固定の習慣がヒアリングされ記録されたか ---
    # 達成/未達は問わない。「毎日確認する」契約なので、どちらであれ本文に痕跡が残るはず。
    # 痕跡ゼロ = そもそも聞かなかった、と判定する。
    for habit in load_daily_habits():
        keywords = habit.get("keywords") or []
        if not any(kw in text for kw in keywords):
            violations.append(
                f"H01: 毎日の習慣「{habit['label']}」の記録がありません"
                f"（{habit['target_section']} へ達成/未達のいずれかを書く）"
            )

    return violations


def main() -> int:
    ap = argparse.ArgumentParser(description="日次ジャーナルの保存前バリデーション")
    ap.add_argument("--file", required=True)
    ap.add_argument("--expected-number", type=int, default=None)
    ap.add_argument("--expected-date", default=None)
    args = ap.parse_args()

    path = Path(args.file)
    if not path.is_file():
        sys.stderr.write(f"validate-journal-output: ファイルがありません: {path}\n")
        return 2
    try:
        violations = validate(path, args.expected_number, args.expected_date)
    except OSError as exc:
        sys.stderr.write(f"validate-journal-output: 読み込みに失敗しました: {exc}\n")
        return 2

    if violations:
        print(f"FAIL: {path.name} — 違反 {len(violations)} 件")
        for v in violations:
            print(f"  - {v}")
        return 1
    print(f"PASS: {path.name} — 違反 0 件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
