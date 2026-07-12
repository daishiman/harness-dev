#!/usr/bin/env python3
# /// script
# name: sync-task-state
# purpose: task-graph 駆動 build の runtime state (producer component C16 task-state.schema.json shape) への単一 writer (TG-C02)。状態遷移 (ALLOWED_TRANSITIONS)・lease 回収/延長・graph_hash pin・blocked 伝播/回復・実行イベントログ (task-events.jsonl) を一箇所へ閉じ、canonical serialization 規約 (id 昇順) を task-state shape へ踏襲する。他 consumer script (TG-C05/TG-C07) は resolve_build_dir を import 再利用する SSOT。
# inputs:
#   - argv: --target-plugin-slug S [--cycle-id C] [--task-state P] [--events E] [--task-graph G]
#           (--task-id T (--to-state ST [--route-report R] [--require-covered] [--reason origin-failure|propagated] [--propagate-blocked] | --reap-lease | --renew-lease)
#            | --pin-graph-hash H | --repin-graph-hash H --authorized-hash H2
#            | --reactivate-cascade ORIGIN [--include-origin]) [--lease-seconds N] [--event-extra JSON]
# outputs:
#   - stdout: 更新サマリ JSON
#   - stderr: ValueError (不正遷移/理由欠落/成果物欠落/covered 不一致・不在/未知 task-id/再pin 異値) メッセージ
#   - exit: 0=OK / 1=ValueError (状態違反) / 2=usage/IO error
#   - write-scope: <--task-state> task-state.json (canonical 上書き・単一 writer) + <--events> task-events.jsonl (append-only)
# contexts: [C, E]
# network: false
# write-scope: <--task-state> task-state.json + <--events> task-events.jsonl (co-located build dir)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""task-state.json への単一 writer (TG-C02)。

producer=plugin-dev-planner が所有する task-state.schema.json (producer component C16) の shape
(`{schema_version, graph_hash, nodes:[{id, state, started_at, lease_expires_at,
blocked_reason?, route_report?, handoff_notes?}]}`) を、consumer=harness-creator の
実行系が唯一書き込む。運用フィールド route_report/handoff_notes は additive で、
producer 必須キー id/state/started_at/lease_expires_at + blocked 時 blocked_reason を
壊さない。canonical serialization は producer 側 derive-task-graph.canonicalize() が採用する
決定論規約 (id 昇順ソート・json.dumps indent=2 ensure_ascii=False) を task-state の shape へ
そのまま踏襲する (独自シリアライザは発明しない)。cross-plugin import を避け stdlib のみで
自己完結する (TG-C05 summarize / TG-C07 manage-build-lease は resolve_build_dir を import 再利用)。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── 状態遷移表 (producer component C16 永続 4 値。done は終端・後退遷移不可) ───
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "blocked"},
    "running": {"done", "blocked"},
    "blocked": {"pending", "running"},
    "done": set(),
}
# blocked 遷移の第一級 field 値域 (origin-failure=起点故障 / propagated=下流連鎖)。
BLOCKED_REASONS = {"origin-failure", "propagated"}
DEFAULT_LEASE_SECONDS = 3600
# task-graph edge 方向は type ごとに異なる。depends_on は consumer task→producer
# task、produces は producer task→artifact、consumes は artifact→consumer task。
# consumes を depends_on と同じ endpoint として扱う edge-type 集合は持たない。


# ── 時刻ユーティリティ (timezone-aware UTC・Z 表記) ─────────────────────────────
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    """UTC ISO8601 (末尾 Z 表記)。RFC3339/date-time 準拠。"""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(s: str) -> datetime:
    """ISO8601 (Z 許容) を timezone-aware UTC datetime へ。"""
    text = s[:-1] + "+00:00" if s.endswith("Z") else s
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ── state 純関数ヘルパ (入力を破壊しない浅コピー) ──────────────────────────────
def _clone_state(task_state: dict) -> dict:
    """task_state と各 node を浅コピーし独立に更新可能な複製を返す (入力不変)。"""
    clone = dict(task_state)
    clone["nodes"] = [dict(n) for n in task_state.get("nodes", [])]
    return clone


def _find_node(state: dict, task_id: str) -> dict | None:
    for n in state["nodes"]:
        if n.get("id") == task_id:
            return n
    return None


def _new_node(task_id: str) -> dict:
    return {"id": task_id, "state": "pending", "started_at": None, "lease_expires_at": None}


def current_state(task_state: dict, task_id: str) -> str:
    """未登録 node は既定 pending として現状態を返す。"""
    node = _find_node(task_state, task_id) if task_state.get("nodes") else None
    return node.get("state", "pending") if node else "pending"


def _assert_covered(route_report_path: str, task_id: str, require_covered: bool = False) -> None:
    """route-build-report の additive covered_task_ids に task_id が含まれることを照合。

    covered_task_ids 不在の従来 route-report (PR#70 単一 task 契約) は task_id を暗黙の
    唯一 covered とみなし後方互換を保つ。require_covered=True はこの暗黙互換を無効化し、
    不在自体を violation とする (covered 宣言を欠いた done を封鎖する厳格運用)。
    """
    try:
        data = json.loads(Path(route_report_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"route-report 読込/parse 失敗: {route_report_path}: {exc}")
    covered = data.get("covered_task_ids")
    if covered is None:
        if require_covered:
            raise ValueError(
                f"require-covered 指定時は route-report に covered_task_ids が必須: {route_report_path}"
            )
        return  # 後方互換: 単一 task を賄う既存 route-report
    if task_id not in covered:
        raise ValueError(
            f"task {task_id!r} が route-report covered_task_ids {covered} に不在"
        )


def assert_task_in_graph(task_graph: dict, task_id: str) -> None:
    """task_id が task-graph nodes に存在することを検査する (未知 id の fail-open 封鎖)。

    graph 外の id は typo/迷子 task の混入であり、暗黙の pending node 生成で受理しては
    ならない。graph 未指定の呼び出し経路は従来挙動のまま (後方互換)。
    """
    known = {n.get("id") for n in task_graph.get("nodes", [])}
    if task_id not in known:
        raise ValueError(f"task {task_id!r} が task-graph nodes に不在 (未知 task-id)")


# ── 公開 API: 状態遷移 ────────────────────────────────────────────────────────
def transition(
    task_state: dict,
    task_id: str,
    to_state: str,
    *,
    route_report: str | None = None,
    reason: str | None = None,
    require_covered: bool = False,
    now: datetime | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> dict:
    """現状態→to_state を ALLOWED_TRANSITIONS で検査し新 task_state を返す (純関数)。

    - to_state が ALLOWED_TRANSITIONS 外なら ValueError。
    - running: started_at (UTC ISO8601 Z) と lease_expires_at (started_at+lease_seconds) を設定。
    - done: route_report の os.path.exists 必須 (欠落 ValueError) + covered_task_ids 照合
      (require_covered=True は covered_task_ids 不在も violation)。
    - blocked: reason (origin-failure|propagated) 必須で第一級 field blocked_reason へ書く。
    非 blocked への遷移時は残存 blocked_reason を除去し schema 違反 (非 blocked での付与) を防ぐ。
    """
    if now is None:
        now = _utc_now()
    clone = _clone_state(task_state)
    node = _find_node(clone, task_id)
    if node is None:
        node = _new_node(task_id)
        clone["nodes"].append(node)
    current = node.get("state", "pending")
    if to_state not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"不正遷移 {current!r}->{to_state!r} (task={task_id!r})")

    if to_state == "running":
        started = _iso(now)
        node["started_at"] = started
        node["lease_expires_at"] = _iso(now + timedelta(seconds=lease_seconds))
    elif to_state == "done":
        if route_report is None or not os.path.exists(route_report):
            raise ValueError(
                f"done 遷移には実在する --route-report が必須 (received={route_report!r})"
            )
        _assert_covered(route_report, task_id, require_covered)
        node["route_report"] = route_report
    elif to_state == "blocked":
        if reason not in BLOCKED_REASONS:
            raise ValueError(
                f"blocked 遷移には reason {sorted(BLOCKED_REASONS)} が必須 (received={reason!r})"
            )
        node["blocked_reason"] = reason

    if to_state != "blocked":
        node.pop("blocked_reason", None)
    node["state"] = to_state
    return clone


def reap_expired_lease(task_state: dict, task_id: str, now: datetime) -> dict:
    """running かつ lease_expires_at < now の node のみ running→pending へ回収する。

    ALLOWED_TRANSITIONS を緩めず lease 回収という限定文脈でのみ発火する専用経路。
    条件を満たさない呼び出しは ValueError。
    """
    clone = _clone_state(task_state)
    node = _find_node(clone, task_id)
    if node is None or node.get("state") != "running":
        raise ValueError(f"reap 対象は running node のみ (task={task_id!r})")
    lease = node.get("lease_expires_at")
    if lease is None or _parse_iso(lease) >= now:
        raise ValueError(
            f"lease 未期限のため reap 拒否 (task={task_id!r} lease_expires_at={lease!r})"
        )
    node["state"] = "pending"
    node["started_at"] = None
    node["lease_expires_at"] = None
    return clone


def renew_lease(task_state: dict, task_id: str, now: datetime, lease_seconds: int) -> dict:
    """running node の lease_expires_at を now+lease_seconds へ延長する (state 不変)。

    dispatcher の heartbeat 用。running 以外は ValueError。
    """
    clone = _clone_state(task_state)
    node = _find_node(clone, task_id)
    if node is None or node.get("state") != "running":
        raise ValueError(f"renew 対象は running node のみ (task={task_id!r})")
    node["lease_expires_at"] = _iso(now + timedelta(seconds=lease_seconds))
    return clone


def pin_graph_hash(task_state: dict, graph_hash: str) -> dict:
    """graph_hash を初回 pin する。設定済みで異値なら ValueError (再 pin は危険操作)。"""
    clone = _clone_state(task_state)
    existing = clone.get("graph_hash")
    if existing in (None, ""):
        clone["graph_hash"] = graph_hash
    elif existing != graph_hash:
        raise ValueError(
            f"graph_hash 再 pin 拒否 (existing={existing!r} != new={graph_hash!r})"
        )
    return clone


def repin_graph_hash(task_state: dict, new_hash: str, authorized_hashes: set[str]) -> dict:
    """外ループ再入用の provenance-gated 再 pin (SS-4/crux)。

    pin_graph_hash が異値再 pin を一律拒否する (実行中の不正な graph 混入=F10 を防ぐ) のに対し、
    本関数は「新 graph_hash が accepted discovered-task の resulting_graph_hash 集合と一致する」
    ときに限り pin を新 hash へ更新する。planner drain 由来の正当な仕様改善だけを再入させ、
    どの accepted form の resulting_graph_hash とも一致しない任意の graph 差替え (混入) は
    fail-closed で ValueError 拒否する。安全 (F10) と活性 (外ループ再入) を止揚する。
    """
    clone = _clone_state(task_state)
    existing = clone.get("graph_hash")
    if existing == new_hash:
        return clone  # 既に新 hash で pin 済み (冪等)
    if new_hash not in authorized_hashes:
        raise ValueError(
            f"未認可 re-pin 拒否: new={new_hash!r} が accepted discovered-task の "
            f"resulting_graph_hash 集合に不在 (drain 由来でない graph 混入)"
        )
    clone["graph_hash"] = new_hash
    return clone


# ── 依存解決 + 下流閉包 (depends_on 直接 / consumes は produces 逆引き) ───────
def resolve_dependency_producers(task_graph: dict) -> tuple[dict[str, set[str]], list[dict]]:
    """consumer task -> producer task 集合と consumes 契約 violation を返す。

    depends_on は ``from=consumer task, to=producer task`` を直接読む。consumes は
    ``from=artifact, to=consumer task`` の artifact を ``produces``
    (``from=producer task, to=artifact``) で逆引きして producer task へ解決する。
    artifact producer 不在・producer/consumer task endpoint 不在は issues に残し、
    呼出側が fail-closed で拒否/診断できるようにする。
    """
    node_ids = {
        n.get("id") for n in task_graph.get("nodes", []) or []
        if isinstance(n, dict) and n.get("id") is not None
    }
    producers_by_artifact: dict[str, set[str]] = {}
    for edge in task_graph.get("edges", []) or []:
        if edge.get("type") == "produces":
            producer, artifact = edge.get("from"), edge.get("to")
            if producer is not None and artifact is not None:
                producers_by_artifact.setdefault(artifact, set()).add(producer)

    producers_by_consumer: dict[str, set[str]] = {}
    issues: list[dict] = []
    for edge in task_graph.get("edges", []) or []:
        edge_type = edge.get("type")
        if edge_type == "depends_on":
            consumer, producer = edge.get("from"), edge.get("to")
            if consumer is not None and producer is not None:
                producers_by_consumer.setdefault(consumer, set()).add(producer)
        elif edge_type == "consumes":
            artifact, consumer = edge.get("from"), edge.get("to")
            if consumer not in node_ids:
                issues.append({
                    "kind": "missing-consumer-task", "artifact_id": artifact,
                    "consumer_task_id": consumer,
                })
            artifact_producers = producers_by_artifact.get(artifact, set())
            if not artifact_producers:
                issues.append({
                    "kind": "missing-artifact-producer", "artifact_id": artifact,
                    "consumer_task_id": consumer,
                })
            for producer in artifact_producers:
                producers_by_consumer.setdefault(consumer, set()).add(producer)
                if producer not in node_ids:
                    issues.append({
                        "kind": "missing-producer-task", "artifact_id": artifact,
                        "consumer_task_id": consumer, "producer_task_id": producer,
                    })

    # node-level fallback は canonical edge と同義の depends_on だけを許可する。
    # consumes は artifact endpoint を持つため task id list としては読まない。
    for node in task_graph.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        consumer = node.get("id")
        for producer in node.get("depends_on", []) or []:
            producers_by_consumer.setdefault(consumer, set()).add(producer)

    issues.sort(key=lambda item: (
        str(item.get("consumer_task_id")), str(item.get("artifact_id")),
        str(item.get("producer_task_id")), str(item.get("kind")),
    ))
    return producers_by_consumer, issues


def format_dependency_issue(issue: dict) -> str:
    """dependency issue を CLI/例外共通の決定論的メッセージにする。"""
    kind = issue.get("kind")
    artifact = issue.get("artifact_id")
    consumer = issue.get("consumer_task_id")
    if kind == "missing-artifact-producer":
        return f"consumes artifact {artifact!r} for consumer {consumer!r} has no producer"
    if kind == "missing-producer-task":
        return (
            f"consumes artifact {artifact!r} resolves to missing producer task "
            f"{issue.get('producer_task_id')!r} for consumer {consumer!r}"
        )
    return f"consumes artifact {artifact!r} references missing consumer task {consumer!r}"


def _downstream_closure(task_graph: dict, origin_task_id: str) -> set[str]:
    """origin に (推移的に) 依存する全 node id の集合を返す (origin 自身は除外)。

    depends_on の task→task と、consumes artifact を produces で逆引きした
    consumer task→producer task を同じ下流閉包に投影する。
    consumes の producer/consumer endpoint violation は伝播漏れに繋がるため fail-closed。
    """
    producers, issues = resolve_dependency_producers(task_graph)
    if issues:
        raise ValueError(format_dependency_issue(issues[0]))
    rev: dict[str, set[str]] = {}
    for consumer, producer_ids in producers.items():
        for producer in producer_ids:
            rev.setdefault(producer, set()).add(consumer)

    seen: set[str] = set()
    queue = [origin_task_id]
    while queue:
        cur = queue.pop()
        for consumer in rev.get(cur, ()):
            if consumer not in seen:
                seen.add(consumer)
                queue.append(consumer)
    seen.discard(origin_task_id)
    return seen


def propagate_blocked(
    task_state: dict, task_graph: dict, origin_task_id: str, now: datetime
) -> dict:
    """origin の下流閉包を blocked (blocked_reason=propagated) へ一括連鎖遷移させる。

    起点故障 (origin 自身) は transition(--reason origin-failure) が別途担う。本関数は
    下流のみ propagated で塗る (単一 writer=TG-C02 を維持)。
    """
    downstream = _downstream_closure(task_graph, origin_task_id)
    clone = _clone_state(task_state)
    by_id = {n["id"]: n for n in clone["nodes"]}
    for tid in sorted(downstream):
        node = by_id.get(tid)
        if node is None:
            node = _new_node(tid)
            clone["nodes"].append(node)
            by_id[tid] = node
        node["state"] = "blocked"
        node["blocked_reason"] = "propagated"
    return clone


def reactivate_cascade(
    task_state: dict,
    task_graph: dict,
    origin_task_id: str,
    include_origin: bool = False,
) -> dict:
    """propagate_blocked の逆操作。blocked_reason=propagated の下流閉包を pending へ復帰。

    origin 自身 (origin-failure) は誤再開防止のため include_origin=True 時のみ復帰する。
    復帰時は blocked_reason を除去する (非 blocked での付与は schema 違反のため)。
    """
    downstream = _downstream_closure(task_graph, origin_task_id)
    clone = _clone_state(task_state)
    by_id = {n["id"]: n for n in clone["nodes"]}
    for tid in sorted(downstream):
        node = by_id.get(tid)
        if node and node.get("state") == "blocked" and node.get("blocked_reason") == "propagated":
            node["state"] = "pending"
            node.pop("blocked_reason", None)
    if include_origin:
        node = by_id.get(origin_task_id)
        if node and node.get("state") == "blocked":
            node["state"] = "pending"
            node.pop("blocked_reason", None)
    return clone


# ── 実行イベントログ (append-only) ────────────────────────────────────────────
def append_event(events_path, event: dict) -> None:
    """{"ts": <UTC ISO8601>, ...event} を events_path へ 1 行 JSON append する (既存行不変)。"""
    record = {"ts": _iso(_utc_now())}
    record.update(event)
    with open(events_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── canonical serialization (producer 決定論規約を task-state shape へ踏襲) ────
def canonical_state_json(task_state: dict) -> str:
    """nodes を id 昇順ソートし json.dumps(indent=2, ensure_ascii=False)。末尾 newline は書込側。"""
    nodes = sorted(task_state.get("nodes", []), key=lambda n: str(n.get("id")))
    out = {
        "schema_version": task_state.get("schema_version", "1.0"),
        "graph_hash": task_state.get("graph_hash"),
        "nodes": nodes,
    }
    return json.dumps(out, ensure_ascii=False, indent=2)


# ── build ディレクトリ導出 (TG-C05/TG-C07 が import する SSOT) ─────────────────
def resolve_build_dir(target_plugin_slug: str, cycle_id: str | None) -> str:
    """eval-log/<slug>/build を base とし cycle_id 非 None なら base/<cycle_id> を返す。

    handoff top-level の target_plugin_slug/cycle_id の値のみから導出し、plan_dir の
    パス解析は一切しない (周回衝突排除)。cycle_id=None は後方互換 flat レイアウト。
    """
    base = f"eval-log/{target_plugin_slug}/build"
    return base if cycle_id is None else f"{base}/{cycle_id}"


def resolve_planner_root() -> Path:
    """producer (plugin-dev-planner) の plugin root を返す。C01/C03/C07 が import 再利用する SSOT。

    本 script は plugins/harness-creator/scripts/ 配下のため parents[2] が plugins/ を指し、
    sibling plugin の producer root は plugins/plugin-dev-planner となる。
    """
    return Path(__file__).resolve().parents[2] / "plugin-dev-planner"


# ── CLI ──────────────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sync-task-state.py",
        description="task-state.json への単一 writer (状態遷移/lease/pin/伝播 + task-events)。",
    )
    p.add_argument("--target-plugin-slug", default=None)
    p.add_argument("--cycle-id", default=None)
    p.add_argument("--task-state", default=None, help="省略時 resolve_build_dir(...)/task-state.json")
    p.add_argument("--events", default=None, help="省略時 resolve_build_dir(...)/task-events.jsonl")
    p.add_argument("--task-graph", default=None,
                   help="task-graph.json (指定時は遷移 task-id の nodes 存在検査 + propagate-blocked に使用)")
    p.add_argument("--task-id", default=None)
    p.add_argument("--to-state", default=None, choices=["pending", "running", "done", "blocked"])
    p.add_argument("--route-report", default=None)
    p.add_argument("--require-covered", action="store_true",
                   help="done 遷移時 route-report の covered_task_ids 不在を violation とする (既定 off=後方互換)")
    p.add_argument("--reason", default=None, choices=sorted(BLOCKED_REASONS))
    p.add_argument("--reap-lease", action="store_true")
    p.add_argument("--renew-lease", action="store_true")
    p.add_argument("--pin-graph-hash", default=None)
    p.add_argument("--repin-graph-hash", default=None,
                   help="外ループ再入用の provenance-gated 再 pin (要 --authorized-hash)")
    p.add_argument("--authorized-hash", action="append", default=[],
                   help="再 pin を認可する resulting_graph_hash (accepted discovered-task 由来・複数可)")
    p.add_argument("--propagate-blocked", action="store_true")
    p.add_argument("--reactivate-cascade", default=None, metavar="ORIGIN_TASK_ID",
                   help="propagate_blocked の逆操作: origin の下流閉包の blocked(propagated) を pending へ復帰 (要 --task-graph)")
    p.add_argument("--include-origin", action="store_true",
                   help="--reactivate-cascade で origin 自身 (origin-failure) も pending へ復帰する (誤再開防止のため明示時のみ)")
    p.add_argument("--event-extra", default=None, help="dispatcher 転送イベント (JSON 文字列・非解釈で追記)")
    p.add_argument("--lease-seconds", type=int, default=DEFAULT_LEASE_SECONDS)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse usage error / --help
        return int(exc.code) if isinstance(exc.code, int) else 2

    # task-state / events パスの解決 (--task-state 明示指定が最優先・完全上位互換)。
    if args.task_state:
        state_path = Path(args.task_state)
        build_dir = state_path.parent
    else:
        if not args.target_plugin_slug:
            print("--task-state 省略時は --target-plugin-slug が必須", file=sys.stderr)
            return 2
        build_dir = Path(resolve_build_dir(args.target_plugin_slug, args.cycle_id))
        state_path = build_dir / "task-state.json"
    events_path = Path(args.events) if args.events else build_dir / "task-events.jsonl"

    # 既存 task-state を読み込む (無ければ空 state から開始)。
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"task-state 読込/parse 失敗: {state_path}: {exc}", file=sys.stderr)
            return 2
    else:
        state = {"schema_version": "1.0", "graph_hash": None, "nodes": []}

    events: list[dict] = []
    try:
        if args.reap_lease:
            if not args.task_id:
                print("--reap-lease には --task-id が必須", file=sys.stderr)
                return 2
            frm = current_state(state, args.task_id)
            state = reap_expired_lease(state, args.task_id, _utc_now())
            events.append({"type": "lease_reaped", "task_id": args.task_id,
                           "from_state": frm, "to_state": "pending", "reason": "lease_expired"})
        elif args.renew_lease:
            if not args.task_id:
                print("--renew-lease には --task-id が必須", file=sys.stderr)
                return 2
            state = renew_lease(state, args.task_id, _utc_now(), args.lease_seconds)
            events.append({"type": "lease_renewed", "task_id": args.task_id})
        elif args.pin_graph_hash is not None:
            state = pin_graph_hash(state, args.pin_graph_hash)
            events.append({"type": "graph_hash_pinned", "graph_hash": args.pin_graph_hash})
        elif args.repin_graph_hash is not None:
            state = repin_graph_hash(state, args.repin_graph_hash, set(args.authorized_hash))
            events.append({"type": "graph_hash_repinned", "graph_hash": args.repin_graph_hash})
        elif args.reactivate_cascade is not None:
            if not args.task_graph:
                print("--reactivate-cascade には --task-graph が必須 (下流閉包導出)", file=sys.stderr)
                return 2
            try:
                task_graph = json.loads(Path(args.task_graph).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"task-graph 読込/parse 失敗: {args.task_graph}: {exc}", file=sys.stderr)
                return 2
            origin = args.reactivate_cascade
            assert_task_in_graph(task_graph, origin)
            by_id = {n["id"]: n for n in state.get("nodes", [])}
            restored = [tid for tid in sorted(_downstream_closure(task_graph, origin))
                        if by_id.get(tid, {}).get("state") == "blocked"
                        and by_id.get(tid, {}).get("blocked_reason") == "propagated"]
            if args.include_origin and by_id.get(origin, {}).get("state") == "blocked":
                restored.append(origin)
            state = reactivate_cascade(state, task_graph, origin, include_origin=args.include_origin)
            for tid in restored:
                events.append({"type": "state_transition", "task_id": tid,
                               "from_state": "blocked", "to_state": "pending",
                               "reason": "reactivated", "origin_task_id": origin})
        elif args.to_state:
            if not args.task_id:
                print("--to-state には --task-id が必須", file=sys.stderr)
                return 2
            # --task-graph 指定時は未知 task-id を fail-closed 拒否 (暗黙 pending 生成の封鎖)。
            # 未指定時は従来挙動 (後方互換)。
            task_graph = None
            if args.task_graph:
                try:
                    task_graph = json.loads(Path(args.task_graph).read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    print(f"task-graph 読込/parse 失敗: {args.task_graph}: {exc}", file=sys.stderr)
                    return 2
                assert_task_in_graph(task_graph, args.task_id)
            frm = current_state(state, args.task_id)
            state = transition(
                state, args.task_id, args.to_state,
                route_report=args.route_report, reason=args.reason,
                require_covered=args.require_covered,
                now=_utc_now(), lease_seconds=args.lease_seconds,
            )
            events.append({"type": "state_transition", "task_id": args.task_id,
                           "from_state": frm, "to_state": args.to_state})
            if args.propagate_blocked:
                if args.to_state != "blocked":
                    print("--propagate-blocked は --to-state blocked と併用する", file=sys.stderr)
                    return 2
                if task_graph is None:
                    print("--propagate-blocked には --task-graph が必須", file=sys.stderr)
                    return 2
                state = propagate_blocked(state, task_graph, args.task_id, _utc_now())
                for tid in sorted(_downstream_closure(task_graph, args.task_id)):
                    events.append({"type": "state_transition", "task_id": tid,
                                   "from_state": None, "to_state": "blocked",
                                   "blocked_reason": "propagated", "origin_task_id": args.task_id})
        else:
            print("操作 (--to-state / --reap-lease / --renew-lease / --pin-graph-hash / --repin-graph-hash) を 1 つ指定",
                  file=sys.stderr)
            return 2
    except ValueError as exc:
        print(f"state violation: {exc}", file=sys.stderr)
        return 1

    # dispatcher 転送イベント (内容を解釈せずそのまま追記)。
    if args.event_extra is not None:
        try:
            extra = json.loads(args.event_extra)
        except json.JSONDecodeError as exc:
            print(f"--event-extra は JSON 文字列: {exc}", file=sys.stderr)
            return 2
        events.append(extra if isinstance(extra, dict) else {"type": "event_extra", "payload": extra})

    # 書込 (単一 writer): task-state を canonical で上書き + task-events を append。
    try:
        build_dir.mkdir(parents=True, exist_ok=True)
        state_path.write_text(canonical_state_json(state) + "\n", encoding="utf-8")
        for ev in events:
            append_event(events_path, ev)
    except OSError as exc:
        print(f"write error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({
        "task_state": str(state_path),
        "events": str(events_path),
        "events_appended": len(events),
        "node_count": len(state.get("nodes", [])),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
