#!/usr/bin/env python3
"""抽出済みの決定事項・宿題 JSON を Markdown の表に整形する。

使い方: render-minutes-table.py --input items.json [--out summary.md]
exit: 0=成功 / 1=入力不正 / 2=出力先が既に存在 (上書きしない)
"""
import argparse
import json
import sys
from pathlib import Path

UNSET = "未定"


def cell(value) -> str:
    text = str(value).strip() if value is not None else ""
    return text.replace("|", "\\|").replace("\n", " ")


def render(data: dict) -> str:
    decisions = data.get("decisions", [])
    actions = data.get("actions", [])
    if not isinstance(decisions, list) or not isinstance(actions, list):
        raise ValueError("decisions と actions は配列であること")

    out = [f"# 会議メモまとめ: {cell(data.get('source', ''))}", "", "## 決定事項", ""]
    if decisions:
        out += ["| # | 決定事項 | 根拠 |", "|---|---|---|"]
        for i, d in enumerate(decisions, 1):
            if not cell(d.get("text")):
                raise ValueError(f"decisions[{i - 1}].text が空")
            out.append(f"| {i} | {cell(d['text'])} | {cell(d.get('lines'))} |")
    else:
        out.append("(なし)")

    out += ["", "## 宿題", ""]
    pending = []
    if actions:
        out += ["| # | 内容 | 担当者 | 期限 | 根拠 |", "|---|---|---|---|---|"]
        for i, a in enumerate(actions, 1):
            if not cell(a.get("text")):
                raise ValueError(f"actions[{i - 1}].text が空")
            owner = cell(a.get("owner")) or UNSET
            due = cell(a.get("due")) or UNSET
            missing = [n for n, v in (("担当者", owner), ("期限", due)) if v == UNSET]
            if missing:
                pending.append(f"- 宿題 #{i}「{cell(a['text'])}」: {'・'.join(missing)}が未定")
            out.append(f"| {i} | {cell(a['text'])} | {owner} | {due} | {cell(a.get('lines'))} |")
    else:
        out.append("(なし)")

    if pending:
        out += ["", "## 要確認", ""] + pending
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    try:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        md = render(data)
    except (OSError, ValueError, AttributeError, KeyError) as e:
        print(f"入力エラー: {e}", file=sys.stderr)
        return 1
    if args.out:
        out = Path(args.out)
        if out.exists():
            print(f"出力先が既に存在するため上書きしません: {out}", file=sys.stderr)
            return 2
        out.write_text(md, encoding="utf-8")
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
