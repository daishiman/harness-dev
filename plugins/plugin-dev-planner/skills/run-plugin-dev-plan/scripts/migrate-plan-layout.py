#!/usr/bin/env python3
# /// script
# name: migrate-plan-layout
# purpose: flat plan 配置 plugin-plans/<slug>/ を cycle スコープ配置 plugin-plans/<slug>/<cycle_id>/ へ移行し plan-ledger.json へ entry 追記する (C13)。
# inputs:
#   - argv: --old-plan-dir <path> --slug <slug> --cycle-id <cycle_id> [--status active] [--summary <text>]
# outputs:
#   - stdout: 移行結果 JSON {"moved":[...],"ledger_path":...,"cycle_id":...}
#   - exit: 0=OK / 1=cycle_id 形式不正 or 同時 active 重複 / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: <old-plan-dir>/<cycle_id>/ (移動先) + <old-plan-dir>/plan-ledger.json
# dependencies: []
# requires-python: ">=3.10"
# ///
"""flat plan 配置を cycle スコープ配置へ移行する (C13)。

既存 flat 配置 `plugin-plans/<slug>/` 配下のファイルを `plugin-plans/<slug>/<cycle_id>/`
へ移動し (shutil.move)、`plugin-plans/<slug>/plan-ledger.json` へ新規 entry を追記する。
plan-ledger.json 自体は移動せず slug 直下に残す (台帳は cycle スコープの外側に居る)。
追記後は check-plan-ledger.validate_ledger() を再実行して fail-closed 検証してから書き込む
ため、既存 active がある台帳へ status=active を足そうとすると同時 active 重複で ValueError
となる (非決定的な自動解決をしない)。cycle_id は specfm.CYCLE_ID_RE で検証する。

既存 `plugin-plans/finish/<slug>/` 配下の完了 plan は本 migrate の対象外 (触れない)。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

_LEDGER_NAME = "plan-ledger.json"


def _validate_ledger(ledger: dict) -> list[str]:
    """check-plan-ledger.py の validate_ledger を同一ディレクトリから動的ロードして再利用する。

    ハイフン名の兄弟 script を通常 import できないため importlib で読み込む
    (循環 import を避けつつ検証ロジックの単一正本を共有する)。
    """
    src = Path(__file__).resolve().parent / "check-plan-ledger.py"
    spec = importlib.util.spec_from_file_location("check_plan_ledger", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.validate_ledger(ledger)


def migrate(
    old_plan_dir: Path,
    slug: str,
    cycle_id: str,
    status: str = "active",
    summary: str | None = None,
) -> dict:
    """flat plan 配置を cycle スコープ配置へ移行し ledger へ entry 追記する。

    old_plan_dir 配下のファイル (plan-ledger.json を除く) を old_plan_dir/<cycle_id>/ へ
    移動し、old_plan_dir/plan-ledger.json へ {cycle_id,status,plan_dir,summary} entry を
    追記する。追記後の台帳を validate_ledger() で検証し、違反があれば書き込まず ValueError。

    返り値: {"moved": [移動したファイル名...], "ledger_path": str, "cycle_id": str}。
    """
    old_plan_dir = Path(old_plan_dir)
    cycle_id = str(cycle_id).strip()
    if not specfm.CYCLE_ID_RE.match(cycle_id):
        raise ValueError(f"cycle_id={cycle_id!r} は {specfm.CYCLE_ID_RE.pattern} に不一致")
    if status not in specfm.LEDGER_STATUSES:
        raise ValueError(f"status={status!r} が値域外 {list(specfm.LEDGER_STATUSES)}")

    target = old_plan_dir / cycle_id
    ledger_path = old_plan_dir / _LEDGER_NAME
    target.mkdir(parents=True, exist_ok=True)

    moved: list[str] = []
    for item in sorted(old_plan_dir.iterdir()):
        if item.name in (_LEDGER_NAME, cycle_id):
            continue  # 台帳は移動しない / 移動先 dir 自身も対象外
        shutil.move(str(item), str(target / item.name))
        moved.append(item.name)

    plan_dir = specfm.plan_output_dir(slug, cycle_id=cycle_id)
    if summary is None or not str(summary).strip():
        summary = f"cycle {cycle_id} を flat→cycle スコープ配置へ移行 (status={status})"

    if ledger_path.is_file():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        if not isinstance(ledger, dict):
            raise ValueError(f"既存 plan-ledger が object でない: {ledger_path}")
    else:
        ledger = {"schema_version": "1.0", "entries": []}
    ledger.setdefault("entries", [])
    ledger["entries"].append(
        {"cycle_id": cycle_id, "status": status, "plan_dir": plan_dir, "summary": summary}
    )

    errs = _validate_ledger(ledger)
    if errs:
        raise ValueError("plan-ledger 検証失敗 (書き込み中止): " + "; ".join(errs))

    ledger_path.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {"moved": moved, "ledger_path": str(ledger_path), "cycle_id": cycle_id}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="flat plan 配置を cycle スコープ配置へ移行する (C13)")
    ap.add_argument("--old-plan-dir", required=True, help="flat plan dir (plugin-plans/<slug>/)")
    ap.add_argument("--slug", required=True, help="対象 plugin の kebab slug")
    ap.add_argument("--cycle-id", required=True, help="YYYYMMDD-<concept-slug>")
    ap.add_argument("--status", default="active", help="ledger status (既定 active)")
    ap.add_argument("--summary", default=None, help="entry の summary (省略時は既定文)")
    args = ap.parse_args(argv)

    try:
        result = migrate(
            Path(args.old_plan_dir), args.slug, args.cycle_id, args.status, args.summary
        )
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
