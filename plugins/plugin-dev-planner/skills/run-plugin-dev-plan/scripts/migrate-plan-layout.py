#!/usr/bin/env python3
# /// script
# name: migrate-plan-layout
# purpose: flat plan 配置 plugin-plans/<slug>/ を cycle スコープ配置 plugin-plans/<slug>/<cycle_id>/ へ移行し plan-ledger.json へ entry 追記する (C13)。
# inputs:
#   - argv: --old-plan-dir <path> --slug <slug> --cycle-id <cycle_id> [--status active] [--summary <text>]
# outputs:
#   - stdout: 移行結果 JSON {"moved":[...],"ledger_path":...,"cycle_id":...}
#   - exit: 0=OK / 1=cycle_id・status の不正、台帳の不正 (読めない・形が違う・同時 active 重複・同じ cycle_id)、移すファイルが無い・移動先に同名がある、移動か台帳の書き込みの失敗 (動かした分は戻す) / 2=usage error (引数・存在しない --old-plan-dir・plugin-plans/<slug>/ の形でない dir・--slug と dir 名の不一致・完了 plan を置く plugin-plans/finish/)
# contexts: [A, E]
# network: false
# write-scope: <old-plan-dir>/<cycle_id>/ (移動先) + <old-plan-dir>/plan-ledger.json
# dependencies: []
# requires-python: ">=3.10"
# ///
"""flat plan 配置を cycle スコープ配置へ移行する (C13)。

既存 flat 配置 `plugin-plans/<slug>/` 直下のファイルを `plugin-plans/<slug>/<cycle_id>/`
へ移動し (shutil.move)、`plugin-plans/<slug>/plan-ledger.json` へ新規 entry を追記する。
plan-ledger.json 自体は移動せず slug 直下に残す (台帳は cycle スコープの外側に居る)。
cycle_id の形 (specfm.CYCLE_ID_RE) の dir は台帳に有っても無くても既にある cycle スコープとみなし、
動かさない (2 回目の移行で前の cycle が今回の cycle の中へ入れ子になるのを防ぐ)。

止まるときは動かす前に止まる。台帳の読み込みと、entry を足した後の
check-plan-ledger.validate_ledger() の検証、同じ cycle_id の有無、移すファイルの有無、
移動先の同名の有無を先に確かめる。既存 active がある台帳へ status=active を足そうとすると
同時 active 重複で ValueError となる (非決定的な自動解決をしない)。動かした後で移動か台帳の
書き込みに失敗したら、動かした分を元の場所へ戻してから例外を上げる。

既存 `plugin-plans/finish/<slug>/` 配下の完了 plan は本 migrate の対象外 (触れない)。
`--old-plan-dir` が `plugin-plans/finish` を指すときは usage error で止める (`finish/<slug>` は形の検査で止まる)。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

_LEDGER_NAME = "plan-ledger.json"
_FINISH_DIR_NAME = "finish"  # 完了 plan の置き場 plugin-plans/finish/<slug>/ (本 migrate は触れない)


class UsageError(ValueError):
    """引数の誤り (exit 2)。ValueError の子なので migrate() を ValueError で受ける呼び出し元はそのまま動く。"""


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


def _load_ledger(ledger_path: Path) -> dict:
    """既存の台帳を読む (無ければ空の台帳)。読めない・形が違うときは ValueError。"""
    if not ledger_path.exists() and not ledger_path.is_symlink():
        return {"schema_version": "1.0", "entries": []}
    if not ledger_path.is_file():
        raise ValueError(f"plan-ledger が通常のファイルでない: {ledger_path}")
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except ValueError as exc:  # JSONDecodeError と UnicodeDecodeError
        raise ValueError(f"plan-ledger を JSON として読めない: {ledger_path}: {exc}") from exc
    if not isinstance(ledger, dict):
        raise ValueError(f"既存 plan-ledger が object でない: {ledger_path}")
    if not isinstance(ledger.setdefault("entries", []), list):
        raise ValueError(f"既存 plan-ledger の entries が配列でない: {ledger_path}")
    return ledger


def _write_ledger(ledger_path: Path, ledger: dict) -> None:
    """同じ dir の一時ファイルへ書いてから置き換える (途中で落ちても壊れた台帳を残さない)。"""
    try:
        mode = ledger_path.stat().st_mode & 0o7777
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    fd, tmp = tempfile.mkstemp(prefix=f".{ledger_path.name}.", suffix=".tmp", dir=ledger_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
        os.chmod(tmp, mode)
        os.replace(tmp, ledger_path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _restore(old_plan_dir: Path, target: Path, moved: list[str], created_target: bool) -> None:
    """動かした分を後ろから元の場所へ戻し、この回で作った移動先 dir が空なら消す。"""
    left: list[str] = []
    for name in reversed(moved):
        try:
            shutil.move(str(target / name), str(old_plan_dir / name))
        except OSError:
            left.append(name)
    if left:
        raise OSError(f"移行を戻せなかった: {target} に {sorted(left)} が残っている")
    if created_target:
        try:
            target.rmdir()
        except OSError:
            pass


def migrate(
    old_plan_dir: Path,
    slug: str,
    cycle_id: str,
    status: str = "active",
    summary: str | None = None,
) -> dict:
    """flat plan 配置を cycle スコープ配置へ移行し ledger へ entry 追記する。

    old_plan_dir 直下のファイル (plan-ledger.json と cycle_id の形の dir を除く) を
    old_plan_dir/<cycle_id>/ へ移動し、old_plan_dir/plan-ledger.json へ
    {cycle_id,status,plan_dir,summary} entry を追記する。検証はすべて動かす前に行い、
    違反があれば何も動かさず書き込まず ValueError (引数の誤りは子の UsageError)。
    動かした後の失敗は、動かした分を戻してから例外を上げる。

    返り値: {"moved": [移動したファイル名...], "ledger_path": str, "cycle_id": str}。
    """
    old_plan_dir = Path(old_plan_dir)
    cycle_id = str(cycle_id).strip()
    if not specfm.CYCLE_ID_RE.match(cycle_id):
        raise ValueError(f"cycle_id={cycle_id!r} は {specfm.CYCLE_ID_RE.pattern} に不一致")
    if status not in specfm.LEDGER_STATUSES:
        raise ValueError(f"status={status!r} が値域外 {list(specfm.LEDGER_STATUSES)}")
    if not old_plan_dir.is_dir():
        raise UsageError(f"--old-plan-dir が既存の dir でない: {old_plan_dir}")
    # 台帳の plan_dir は plan_output_dir() の `plugin-plans/<slug>/<cycle_id>` なので、実際の dir と同じ形でなければ止める。
    resolved = old_plan_dir.resolve()
    if specfm.plan_slug(slug) != resolved.name:
        raise UsageError(
            f"--slug {slug!r} (slug={specfm.plan_slug(slug)!r}) が --old-plan-dir の dir 名 {resolved.name!r} と合わない"
        )
    if resolved.parent.name != specfm.PLAN_OUTPUT_BASE:
        raise UsageError(f"--old-plan-dir が {specfm.PLAN_OUTPUT_BASE}/<slug>/ の形でない: {old_plan_dir}")
    if resolved.name == _FINISH_DIR_NAME:
        raise UsageError(f"--old-plan-dir が完了 plan の置き場 {specfm.PLAN_OUTPUT_BASE}/{_FINISH_DIR_NAME}/ を指す (触れない): {old_plan_dir}")

    target = old_plan_dir / cycle_id
    ledger_path = old_plan_dir / _LEDGER_NAME
    ledger = _load_ledger(ledger_path)
    if any(isinstance(e, dict) and str(e.get("cycle_id", "")).strip() == cycle_id for e in ledger["entries"]):
        raise ValueError(f"cycle_id={cycle_id} は台帳に既にある (同じ cycle を二度移行しない): {ledger_path}")

    plan_dir = specfm.plan_output_dir(slug, cycle_id=cycle_id)
    if summary is None or not str(summary).strip():
        summary = f"cycle {cycle_id} を flat→cycle スコープ配置へ移行 (status={status})"
    ledger["entries"].append(
        {"cycle_id": cycle_id, "status": status, "plan_dir": plan_dir, "summary": summary}
    )
    errs = _validate_ledger(ledger)
    if errs:
        raise ValueError("plan-ledger 検証失敗 (書き込み中止): " + "; ".join(errs))

    items = [
        item
        for item in sorted(old_plan_dir.iterdir())
        if item.name != _LEDGER_NAME
        and not (item.is_dir() and specfm.CYCLE_ID_RE.match(item.name))  # 既にある cycle スコープ (今回の移動先を含む)
    ]
    if not items:
        raise ValueError(f"flat 配置に移すファイルが無い (移行済みか空): {old_plan_dir}")
    if target.exists() and not target.is_dir():
        raise ValueError(f"移動先が dir でない: {target}")
    clashes = [i.name for i in items if (target / i.name).exists() or (target / i.name).is_symlink()]
    if clashes:
        raise ValueError(f"移動先に同じ名前が既にある (上書きしない): {target}: {clashes}")

    created_target = not target.exists()
    target.mkdir(exist_ok=True)
    moved: list[str] = []
    try:
        for item in items:
            shutil.move(str(item), str(target / item.name))
            moved.append(item.name)
        _write_ledger(ledger_path, ledger)
    except BaseException:
        _restore(old_plan_dir, target, moved, created_target)
        raise
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
    except UsageError as exc:
        sys.stderr.write(f"usage error: {exc}\n")
        return 2
    except (ValueError, OSError) as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
