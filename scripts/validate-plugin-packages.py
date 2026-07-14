#!/usr/bin/env python3
"""全 plugin の package completeness (PKG-002〜008) を一括検査する advisory ラッパー。

背景:
  実検査器は単一 plugin 用 (`--plugin <name>` 必須):
    plugins/harness-creator/skills/assign-plugin-package-evaluator/scripts/validate-plugin-package.py
  Makefile の `plugin-package-check` target は存在しないパス
  (`scripts/validate-plugin-package.py`) を no-arg で呼んでおり origin/main 時点から
  壊れていた。本スクリプトが正しいパスへ全 plugin を回して橋渡しする。

advisory である理由:
  PKG-002 (plugin.json の package_mode/entry_points) と PKG-004 (SKILL.md 推奨キー
  responsibility_refs/schema_refs/manifest) は **repo 全 plugin が未採用の将来標準**
  (検査器の方が plugin 群より新しい)。現状は全 plugin が同一に fail するため、
  ブロッキングにすると `make test` が恒久 red になる。よって本スクリプトは結果を
  サマリ表示し **exit 0 (非ブロッキング)** とする。plugin.json が JSON 破損で読めない
  等の構造異常 (検査器自体がエラー) のみ exit 1 とする。

正式採用 (ブロッキング化) は entry_points スキーマ定義を伴う repo 横断マイグレーション
で行うこと。その際は本スクリプトの ADVISORY_PKG を空にすれば fail を昇格できる。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = (
    REPO_ROOT
    / "plugins/harness-creator/skills/assign-plugin-package-evaluator/scripts/validate-plugin-package.py"
)
# 現状 advisory 扱いとする (未採用の将来標準) PKG。空にすると fail を昇格できる。
# PKG-014: kind/combinator ↔ runtime 宣言の整合を強化した際に追加した「構造→combinator 宣言」
#   の逆方向チェック (例: feedback_contract ブロックがあるなら with-feedback-contract combinator を
#   宣言せよ) が、convention 制定前の既存 plugin 群 (mf-kessai / notion-gmail-send / skill-intake /
#   slide-report-generator / ubm-goal-setting 等) を横断で fail させる。新規 plugin は既に準拠済み。
#   repo 横断マイグレーションが済むまで PKG-002/004 と同じく非ブロッキング advisory に留める
#   (findings は引き続き報告される)。
ADVISORY_PKG = {"PKG-002", "PKG-004", "PKG-014"}


def discover_plugins() -> list[str]:
    return sorted(
        p.parent.parent.name
        for p in REPO_ROOT.glob("plugins/*/.claude-plugin/plugin.json")
    )


def main() -> int:
    if not VALIDATOR.is_file():
        print(f"ERROR: validator が見つかりません: {VALIDATOR}", file=sys.stderr)
        return 1

    plugins = discover_plugins()
    if not plugins:
        print("WARN: plugins/ に plugin.json が見つかりません", file=sys.stderr)
        return 0

    print(f"[plugin-package-check] {len(plugins)} plugin を検査 (advisory: {sorted(ADVISORY_PKG)} は非ブロッキング)")
    hard_fail = False
    advisory_total = 0
    for name in plugins:
        proc = subprocess.run(
            [sys.executable, str(VALIDATOR), "--plugin", name, "--check", "all"],
            capture_output=True, text=True,
        )
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            print(f"  {name:<32} ERROR (検査器が JSON を返さず: {proc.stderr.strip()[:80]})")
            hard_fail = True
            continue

        checks = data.get("pkg_checks") or {}
        blocking = [
            cid for cid, c in checks.items()
            if c.get("status") == "fail" and cid not in ADVISORY_PKG
        ]
        advisory = [
            cid for cid, c in checks.items()
            if c.get("status") == "fail" and cid in ADVISORY_PKG
        ]
        advisory_total += len(advisory)
        if blocking:
            print(f"  {name:<32} FAIL (blocking): {sorted(blocking)}")
            hard_fail = True
        else:
            note = f"advisory={sorted(advisory)}" if advisory else "clean"
            print(f"  {name:<32} OK ({note})")

    if advisory_total:
        print(
            f"[plugin-package-check] advisory finding {advisory_total} 件 "
            "(PKG-002/004 = 未採用の将来標準。repo 横断マイグレーションで対応予定。非ブロッキング)"
        )
    if hard_fail:
        print("[plugin-package-check] blocking failure あり", file=sys.stderr)
        return 1
    print("[plugin-package-check] blocking failure なし (advisory のみ)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
