#!/usr/bin/env python3
# /// script
# name: validate-goal-output
# version: 0.1.0
# purpose: 目標設定・振り返り対話の出力 Markdown を保存前に検証する決定論ゲート。
#          未展開プレースホルダ/ファイル名日付パターン/全角数字/差分+-表記/種別別必須見出し/
#          見出し重複/NG表現/やらないこと3項目以上/プロジェクト別タスク種別方針 等を検査。
#          旧 validate-goal-output.sh 474 行の契約移植 (逐語移植ではない)。
# inputs:
#   - argv: --file PATH --type weekly|monthly|bimonthly
# outputs:
#   - stdout: PASS 詳細 / 結果サマリ
#   - stderr: (未使用・失敗理由も stdout の FAIL 行に出す)
#   - exit: 0=PASS / 1=FAIL / 2=usage
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""目標設定出力 Markdown の保存前バリデーション。

旧 validate-goal-output.sh の契約移植。種別 (週報/月報/期報) 別の必須見出し・NG表現・
やらないこと3項目以上・売上系フォーマット等を保存前に検査し違反を FAIL させる。
種別はファイル名推論でなく明示引数 --type (weekly/monthly/bimonthly) を正本とする。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# --type -> (kind, 種別ラベル)。kind は分岐キー、期報=bimonthly=3-月報。
TYPE_MAP = {
    "weekly": "week",
    "monthly": "month",
    "bimonthly": "period",
}


class Validator:
    def __init__(self, text: str, basename: str, kind: str):
        self.lines = text.split("\n")
        self.text = text
        self.basename = basename
        self.kind = kind  # week | month | period
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

    def check_require_prefix(self, label: str) -> None:
        prefix = f"## 【{label}】"
        if any(l.startswith(prefix) for l in self.lines):
            self.ok(f"必須タイトル見出し「## 【{label}】…」")
        else:
            self.fail(f"必須タイトル見出し「## 【{label}】」がありません")

    def check_section_optional(self, section: str) -> None:
        if section in self.text:
            self.ok(f"セクション「{section}」")
        else:
            self.warn(f"セクション「{section}」がありません（任意）")

    def check_goal_section(self, pattern: str, label: str, mode: str) -> None:
        for start, body in self.sections_by_regex(pattern):
            if mode == "numeric":
                table_hit = [l for l in body if re.match(r"^\|", l)]
                subhead_hit = [l for l in body if re.match(r"^### ", l)]
                if table_hit or subhead_hit:
                    self.fail(
                        f"売上系セクション「{label}」に表またはサブ見出しが含まれています（数値1つのみ許可）"
                    )
                non_empty = [
                    l for l in body
                    if not re.match(r"^\s*$", l)
                    and not l.startswith("（")
                    and not re.match(r"^\{\{.*\}\}$", l)
                ]
                if len(non_empty) > 1:
                    self.warn(f"売上系セクション「{label}」が複数行になっています（数値1つのみ推奨）")
            elif mode == "bullet":
                table_hit = [l for l in body if re.match(r"^\|", l)]
                if table_hit:
                    self.fail(f"「{label}」セクションに Markdown 表が含まれています（箇条書きのみ許可）")

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
        if re.search(r"^UBM - [1-3]-", self.basename):
            self.ok("ファイル名プレフィックス")
        else:
            self.fail("ファイル名が 'UBM - {1,2,3}-' で始まっていません")
        if re.search(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[〜~][0-9]{4}-[0-9]{2}-[0-9]{2}", self.basename):
            self.ok("日付パターン")
        else:
            self.fail("ファイル名に日付パターン (YYYY-MM-DD〜YYYY-MM-DD) がありません")

        # 2. 全角数字 (見出し行・１ヶ月・２ヶ月 除外)
        zenkaku = [
            l for l in self.lines
            if re.search(r"[０-９]", l)
            and not l.startswith("##")
            and "１ヶ月" not in l
            and "２ヶ月" not in l
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
        if self.kind == "week":
            self.check_require_prefix("1週間の目標")
            for lbl in ["今週の最重要数字", "今週の売上目標", "今週の売上以外の成果目標",
                        "今週の行動目標（行動管理・優先順位付き）", "習慣目標（仕組みで動く土台）",
                        "今週やらないこと", "今週の判断基準", "現在のグリッドパートナー数"]:
                self.check_require_exact(lbl)
            for opt in ["到達ライン", "今期の売上目標", "前回のアカデミーへの参加日",
                        "次回のアカデミーへの参加日", "次回の壁打ち予定日", "現在事業パートナー数"]:
                self.check_section_optional(opt)
        elif self.kind == "month":
            self.check_require_prefix("1ヶ月の目標")
            for lbl in ["確認された情報", "今期の売上目標", "今期の累計売上実績", "前月の売上目標",
                        "前月の売上実績", "前月の売上目標と実績の差分", "前月の売上に対して未達を挽回するための行動",
                        "前月の売上以外の成果目標", "前月の売上以外の成果実績",
                        "前月の売上以外の成果に対して未達を挽回するための行動", "前月の売上以外の成果目標と実績の差分",
                        "前月の行動目標（行動管理）", "前月の行動実績（行動管理）", "前月の行動目標と実績の差分",
                        "前月の行動に対して未達を挽回するための行動", "今月の売上目標", "今月の売上以外の成果目標",
                        "今月の行動目標（行動管理・優先順位付き）", "現在事業パートナー数", "現在のグリッドパートナー数",
                        "プロジェクト別タスク", "今月やらないこと（明確に排除するもの）", "今月末の振り返りチェックリスト"]:
                self.check_require_exact(lbl)
        elif self.kind == "period":
            self.check_require_prefix("2ヶ月の目標")
            for lbl in ["確認された情報", "今期の累計売上実績", "前期の売上目標", "前期の売上実績",
                        "前期の売上目標と実績の差分", "前期の売上に対して未達を挽回するための行動",
                        "前期の売上以外の成果目標", "前期の売上以外の成果実績",
                        "前期の売上以外の成果に対して未達を挽回するための行動", "前期の売上以外の成果目標と実績の差分",
                        "前期の行動目標（行動管理）", "前期の行動実績（行動管理）", "前期の行動目標と実績の差分",
                        "前期の行動に対して未達を挽回するための行動", "今期の売上目標", "今期の売上以外の成果目標",
                        "今期の行動目標（行動管理・優先順位付き）", "現在事業パートナー数", "現在のグリッドパートナー数",
                        "今期やらないこと（明確に排除するもの）", "今期末の振り返りチェックリスト", "事業の柱"]:
                self.check_require_exact(lbl)

        # 5. 空セクション
        empty_sections = [
            self.lines[i] for i in range(len(self.lines))
            if self.lines[i].startswith("## 【")
            and (i + 1 >= len(self.lines) or self.lines[i + 1] == "")
        ]
        if empty_sections:
            self.warn("空のセクションがあります")

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
        self.check_goal_section(r"【今(週|月|期)の売上目標】", "今期間の売上目標", "numeric")
        self.check_goal_section(r"【前.*の売上以外の成果目標】", "前期間の売上以外の成果目標", "bullet")
        self.check_goal_section(r"【前.*の売上以外の成果実績】", "前期間の売上以外の成果実績", "bullet")
        self.check_goal_section(r"【前.*の売上以外の成果目標と実績の差分】", "前期間の売上以外の成果差分", "bullet")
        self.check_goal_section(r"【前.*の行動目標", "前期間の行動目標", "bullet")
        self.check_goal_section(r"【前.*の行動実績", "前期間の行動実績", "bullet")
        self.check_goal_section(r"【前.*の行動目標と実績の差分】", "前期間の行動差分", "bullet")

        # --- 品質チェック ---
        print("")
        print("--- 品質チェック ---")

        def action_pred(line: str) -> bool:
            return ("行動目標" in line and re.search(r"今(週|月|期)", line)
                    and not re.search(r"差分|実績", line))

        action_section = self.capture_awk(action_pred)
        action_items = [l for l in action_section if re.match(r"^([*-] |・)", l)]
        if action_section:
            ng = [l for l in action_section if re.search(r"頑張る|意識する|気をつける|心がける|努力する", l)]
            if not ng:
                self.ok("NG表現なし（行動目標セクション）")
            else:
                self.fail("行動目標に精神論が含まれています")
            if action_items:
                no_number = [l for l in action_items if not re.search(r"[0-9]", l)]
                if not no_number:
                    self.ok("行動目標に数値あり")
                else:
                    self.warn("数値のない行動目標があります")
                no_date = [
                    l for l in action_items
                    if not re.search(r"[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}|月曜|火曜|水曜|木曜|金曜|毎日|毎朝|毎週|今週|までに", l)
                ]
                if not no_date:
                    self.ok("行動目標に期日あり")
                else:
                    self.warn("期日のない行動目標があります")

        # 9. やらないこと 3項目以上
        def notdoing_pred(line: str) -> bool:
            return ("やらないこと" in line and re.search(r"今(週|月|期)", line)
                    and "守れたか" not in line)

        not_doing = self.capture_awk(notdoing_pred)
        if not_doing:
            bullet_count = sum(1 for l in not_doing if re.match(r"^([*-] |・)", l))
            table_count = sum(1 for l in not_doing if re.match(r"^\|", l))
            heading_count = sum(1 for l in not_doing if re.match(r"^### ", l))
            table_count = table_count - 2 if table_count > 2 else 0
            total = bullet_count + table_count + heading_count
            if total >= 3:
                self.ok(f"「やらないこと」{total}項目")
            else:
                self.fail(f"「やらないこと」が{total}項目です（必須: 3項目以上）")

        # 10. 固有名詞
        if action_section:
            if any(re.search(r"さん|様", l) for l in action_section):
                self.ok("行動目標に固有名詞あり")
            else:
                self.warn("行動目標に人の名前が入っていません（推奨: 具体的な人名を含める）")

        # 11. プロジェクト別タスク
        project_section = self.sed_range("【プロジェクト別タスク】", r"^## ")
        has_project = any("【プロジェクト別タスク】" in l for l in self.lines)
        if self.kind == "period" and has_project:
            self.fail("期報にプロジェクト別タスクが含まれています（期報では出力禁止）")
        if self.kind == "month" and not has_project:
            self.fail("月報にプロジェクト別タスクがありません（月報では必須）")
        if has_project and self.kind != "period":
            checkbox_count = sum(1 for l in project_section if re.match(r"^(- |・)\[[ x]\] ", l))
            if checkbox_count >= 1:
                self.ok(f"プロジェクト別タスクにチェックボックスが {checkbox_count} 件あり")
            else:
                self.fail("プロジェクト別タスクにチェックボックス（- [ ] / - [x]）が1件もありません")
            recipient_count = sum(1 for l in project_section if re.match(r"^(- |・)\[[ x]\] \[[^\]]+\] \[[^\]]+\] .+", l))
            if recipient_count >= checkbox_count:
                self.ok("プロジェクト別タスクが [期日] [提出先・宛先] 形式")
            else:
                self.fail("プロジェクト別タスクは '- [ ] [期日] [提出先・宛先] 対象物・行動' 形式で記載してください")
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

        print("")
        print("=== 結果 ===")
        print(f"エラー: {self.errors} 件")
        print(f"警告: {self.warnings} 件")
        if self.errors == 0:
            print("STATUS: PASS")
            return 0
        print("STATUS: FAIL")
        return 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="UBM目標設定 出力バリデーション", add_help=True)
    ap.add_argument("--file", required=True, help="検証対象の Markdown ファイル")
    ap.add_argument("--type", required=True, choices=list(TYPE_MAP.keys()),
                    help="目標種別 weekly|monthly|bimonthly")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2

    path = Path(args.file)
    if not path.is_file():
        print(f"ERROR: ファイルが見つかりません: {path}", file=sys.stderr)
        return 1

    kind = TYPE_MAP[args.type]
    text = path.read_text(encoding="utf-8")
    return Validator(text, path.name, kind).run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
