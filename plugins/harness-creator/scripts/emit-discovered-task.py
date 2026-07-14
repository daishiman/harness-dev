#!/usr/bin/env python3
# /// script
# name: emit-discovered-task
# purpose: E4 境界の consumer 側 emit 口 (TG-C04)。build 進行中 (in-flight) に単一 route 実行者が発見した plan 未網羅タスクを producer discovered-task.schema.json 正準準拠 form へ正規化し、inbox 定位置 (resolve_build_dir(...)/discovered-tasks/<uuid>.json) へ書く。status は書かず (emit=pending) 外ループ (spec-improvement loop) の producer accept-discovered-task.py が受理する。
# inputs:
#   - argv: --discovering-task-id T --reason R --produces-ref A
#           --node-id N --node-title TT --node-phase-ref P --node-write-scope W
#           [--node-entity-ref E] [--node-state ST] [--node-acceptance-criterion AC] [--node-couples-with ENTITY_ID ...]
#           --route-id RID [--change-level additive|structural]
#           (--task-graph G | --plan-dir D) --target-plugin-slug S [--cycle-id C] [--output O]
# outputs:
#   - stdout: {"emitted": <path>, "change_level":..., "proposed_node_id":...}
#   - stderr: ValueError (discovering_task_id 不在) / usage / IO error
#   - exit: 0=OK / 1=discovering_task_id 不在 / 2=usage/IO error
#   - write-scope: <--output or resolve_build_dir(...)/discovered-tasks/<uuid>.json> discovered-task form (emit のみ)
# contexts: [C, E]
# network: false
# write-scope: <--output or resolve_build_dir(...)/discovered-tasks/<uuid>.json> discovered-task form
# dependencies: []
# requires-python: ">=3.10"
# ///
"""discovered-task form の consumer 側 emitter (TG-C04・E4 境界)。

design: plugin-plans/harness-creator/phase-05-implementation.md (TG-C04)。build 進行中に
単一 route 実行者が発見した plan 未網羅タスクを producer=plugin-dev-planner 所有の
discovered-task.schema.json (E4 境界) 正準準拠 form へ正規化する。form は inbox 定位置
resolve_build_dir(...)/discovered-tasks/<uuid>.json へ書き、status は一切書かない
(未設定=pending=未処理: consumer TG-C08 完了ゲートが block し、次の planner --mode update
--discovered-inbox ドレインが accept-discovered-task.py で取込む非同期還流の帰路)。

E4 境界の実装上の担保: 本 script は E3 (build 完了後の全体改善還流) 境界の schema を
一切 import/参照せず、plan 本体 (component-inventory.json / phase-*.md) への書き込み処理を
一切持たない (emit のみ・受理は producer 側 accept-discovered-task.py の責務)。
resolve_build_dir は同一 plugin の TG-C02 (sync-task-state.py) を SSOT とし importlib で
sibling ロードして再利用する (周回衝突排除ロジックの再実装を避ける)。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import uuid
from pathlib import Path

# discovered-task.schema.json 準拠。emit は additive default で status を書かない。
CHANGE_LEVELS = ("additive", "structural")
NODE_STATES = ("pending", "running", "done", "blocked")


class UsageError(Exception):
    """usage 由来 (task-graph 未解決等) の exit2 エラー。ValueError (exit1) と区別する。"""


def _load_sibling(stem: str):
    """同一 scripts/ 配下のハイフン名 module を importlib で読み込む (TG-C02 SSOT 共有)。"""
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# TG-C02 の resolve_build_dir を SSOT として再利用 (周回衝突排除は sync-task-state に一元化)。
resolve_build_dir = _load_sibling("sync-task-state").resolve_build_dir


def _resolve_task_graph_path(args: argparse.Namespace) -> Path:
    """--task-graph 明示指定を最優先、省略時は <plan-dir>/task-graph.json を既定とする。"""
    if args.task_graph:
        return Path(args.task_graph)
    if args.plan_dir:
        return Path(args.plan_dir) / "task-graph.json"
    raise UsageError("--task-graph か --plan-dir のいずれかが必須 (discovering_task_id 検証用)")


def _node_ids(task_graph: dict) -> set[str]:
    return {n.get("id") for n in task_graph.get("nodes", [])}


def build_discovered_task(args: argparse.Namespace) -> dict:
    """discovered-task.schema.json 正準準拠 form を構築する (status は書かない=pending)。

    - --discovering-task-id が task-graph の node id 集合に実在しなければ ValueError (exit1)。
    - proposed_node は schema 必須キー id/title/phase_ref/entity_ref/state/write_scope を全て埋める
      (entity_ref は --node-entity-ref 省略時 null・state 既定 pending)。
    - change_level は additive (既定) | structural (外ループ stall 由来は structural)。
    - E3 境界の schema は一切参照しない (emit のみ・E4 境界)。
    """
    task_graph_path = _resolve_task_graph_path(args)
    task_graph = json.loads(task_graph_path.read_text(encoding="utf-8"))
    node_ids = _node_ids(task_graph)
    if args.discovering_task_id not in node_ids:
        raise ValueError(
            f"discovering_task_id={args.discovering_task_id!r} が task-graph の nodes に不在 "
            f"({task_graph_path})"
        )

    proposed_node = {
        "id": args.node_id,
        "title": args.node_title,
        "phase_ref": args.node_phase_ref,
        "entity_ref": args.node_entity_ref,  # 省略時 None → null (schema: string|null)
        "state": args.node_state,
        "write_scope": args.node_write_scope,
    }
    if args.node_acceptance_criterion is not None:
        proposed_node["acceptance_criterion"] = args.node_acceptance_criterion
    if args.node_couples_with:
        # 接合が密な既存兄弟 (entity_ref id) を宣言 → accept-discovered-task が同一 phase 兄弟の後へ
        # 直列化し外ループ追記でも盲目並列を防ぐ (統合 finding 先送りの再発防止)。
        proposed_node["couples_with"] = list(args.node_couples_with)

    # status を書かない (未設定=pending=未処理)。additionalProperties:false ゆえ余分キー禁止。
    form = {
        "schema_version": "1.0",
        "discovering_task_id": args.discovering_task_id,
        "reason": args.reason,
        "discovered_at_artifact": args.produces_ref,  # top-level (provenance へネストしない)
        "proposed_node": proposed_node,
        "change_level": args.change_level,
        "provenance": {"route_id": args.route_id},
    }
    return form


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="emit-discovered-task.py",
        description="build 進行中発見タスクを discovered-task.schema.json 準拠 form へ emit する (TG-C04・E4)。",
    )
    p.add_argument("--discovering-task-id", required=True, help="発見元 task の id (task-graph 上に実在)")
    p.add_argument("--reason", required=True, help="発見理由")
    p.add_argument("--produces-ref", required=True, help="discovered_at_artifact (発見時点成果物参照・top-level)")
    # proposed_node (schema 必須キーを全て埋める)。
    p.add_argument("--node-id", required=True)
    p.add_argument("--node-title", required=True)
    p.add_argument("--node-phase-ref", required=True)
    p.add_argument("--node-write-scope", required=True)
    p.add_argument("--node-entity-ref", default=None, help="省略時 null (schema: string|null)")
    p.add_argument("--node-state", default="pending", choices=list(NODE_STATES))
    p.add_argument("--node-acceptance-criterion", default=None)
    p.add_argument("--node-couples-with", action="append", default=[], metavar="ENTITY_ID",
                   help="接合が密な既存兄弟 component の entity_ref id (複数可)。accept 時に同一 phase 兄弟の後へ直列化 (外ループ追記の盲目並列防止)")
    # provenance / lifecycle。
    p.add_argument("--route-id", required=True, help="provenance.route_id (呼び出し元 route id)")
    p.add_argument("--change-level", default="additive", choices=list(CHANGE_LEVELS),
                   help="additive=追加ノードのみ (既定) / structural=既存エッジ張替え/component 追加")
    # discovering 検証用 task-graph。
    p.add_argument("--task-graph", default=None, help="省略時 <plan-dir>/task-graph.json")
    p.add_argument("--plan-dir", default=None, help="--task-graph 省略時の task-graph.json 探索元")
    # 出力先。
    p.add_argument("--target-plugin-slug", default=None)
    p.add_argument("--cycle-id", default=None)
    p.add_argument("--output", default=None,
                   help="省略時 resolve_build_dir(...)/discovered-tasks/<uuid>.json")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse usage error / --help
        return int(exc.code) if isinstance(exc.code, int) else 2

    try:
        form = build_discovered_task(args)
    except (UsageError, OSError, json.JSONDecodeError) as exc:
        # json.JSONDecodeError は ValueError サブクラスのため先に捕捉する (IO/usage=exit2)。
        print(f"usage/IO error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        # discovering_task_id 不在等の状態検証違反 (exit1)。
        print(f"invalid discovered-task: {exc}", file=sys.stderr)
        return 1

    # 出力先解決: --output 明示が最優先、省略時は inbox 定位置 (resolve_build_dir 由来)。
    if args.output:
        out_path = Path(args.output)
    else:
        if not args.target_plugin_slug:
            print("--output 省略時は --target-plugin-slug が必須 (inbox 定位置導出)", file=sys.stderr)
            return 2
        inbox = Path(resolve_build_dir(args.target_plugin_slug, args.cycle_id)) / "discovered-tasks"
        out_path = inbox / f"{uuid.uuid4().hex}.json"

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(form, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"write error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({
        "emitted": str(out_path),
        "change_level": form["change_level"],
        "proposed_node_id": form["proposed_node"]["id"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
