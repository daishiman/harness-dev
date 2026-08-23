#!/usr/bin/env python3
# /// script
# name: plan-dispatch-batch
# purpose: task-graph 駆動 build の dispatch batch 機械導出器 (TG-C10)。TG-C01 (dispatch-ready-set.py) の ready-set 算出を subprocess 再利用した上で、runtime 契約の束ね規則 — route 束ね (entity_ref/route_ref==route.id)・決定論 validator 直実行判別・conflict/file_ownership 回避・--max-workers 制限 — を決定論適用し、direct_validator_batch[] (dispatcher 自身が Bash 実行する read-only validator)・subagent_batches[] (最小コンテキスト付き SubAgent dispatch 単位)・delayed[] (今回見送り+理由) を emit する。AI 判断が必要な要素 (build 本体の内容・discovered-task の --node-title/--reason) は生成しない。曖昧・解決不能は fail-closed で subagent_batches 側へ倒すか理由付き delayed にする。
# inputs:
#   - argv: --task-graph <task-graph.json> --task-state <task-state.json> --handoff <handoff.json> [--max-workers N] [--in-flight <json path>] [--planner-root <path>] [--repo-root <path>] [--out <path>]
# outputs:
#   - stdout: {"direct_validator_batch":[{task_ids,phase_ref,command}],"subagent_batches":[{task_ids,route_id,phase_refs,file_ownership,context_files}],"delayed":[{task_id,reason}],"blocked":[...],"graph_hash_pin":...} JSON (--out 指定時は同内容をファイルへも書く)
#   - stderr: 読込/subprocess エラー
#   - exit: 0=OK (batch 空でも正常) / 1=TG-C01 失敗 | graph_hash pin mismatch / 2=読込不能/usage error
# contexts: [C, E]
# network: false
# write-scope: --out 指定時のみ当該パス (既定は stdout のみ・plan/state は書かない)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""dispatch batch 機械導出器 (TG-C10)。

design: `references/capability-build-runtime-contract.md` 「task-graph route モード」内ループ
手順 1-2 の束ね規則を LLM dispatcher の散文解釈から本 script へ移す (束ね規則の正本は本 header)。
ready-set 算出は TG-C01 を subprocess で再利用し writer/checker SSOT を保つ (再実装しない)。

束ね規則 (決定論・全て fail-closed):
1. route 束ね — node の route join は `route_ref` 明示値、無ければ `entity_ref` を handoff
   `routes[].id` と突合する (自然文 title 解釈に依存しない)。同一 route の ready node は
   1 subagent batch へ束ね、`file_ownership` は各 node write_scope + route `build_target`。
   entity_ref があるのに handoff routes に見つからない node は単独 subagent batch へ倒す。
2. 決定論 validator 直実行判別 — `entity_ref=null` node のうち、受入根拠 (title +
   acceptance_criterion) が backtick 内の単一 `python3 <script>.py [安全 token...]` command
   だけで閉じ、script basename が `validate-|lint-|check-|verify-` で始まり、かつ repo_root
   基点で実在する場合に限り `direct_validator_batch` へ入れる (dispatcher が SubAgent を
   起動せず自身で Bash 実行し checklist-verification report へ記録する対象)。command が
   0 件・複数・shell metacharacter 含み・allowlist 外・実在しない場合は判別不能として
   subagent 側へ倒す。同一 (phase_ref, command) は 1 項目へ束ねる。
3. それ以外の `entity_ref=null` node は異なる判断責務を束ねず 1 node = 1 subagent batch。
4. 選抜 — subagent batch は route id 昇順→先頭 task id 昇順の決定論順で、
   (a) TG-C01 `conflicts` ペアが in-flight/選抜済みと同時にならない、
   (b) `file_ownership` が in-flight/選抜済みとパス prefix 重複しない、
   (c) 選抜数が max(0, --max-workers - in-flight 数) を超えない、
   を満たすものだけ選び、外れた task は理由付き `delayed` へ入れる。
   direct validator は read-only ゆえ worker slot を消費せず全件通す。
5. 最小コンテキスト (③) — 各 subagent batch の `context_files` は対象 phase ファイル
   (plan_dir/phase-NN-*.md)・task_spec_ref・TG-C03 (inject-task-inputs.py) が返す注入
   artifact パスのみ。TG-C03 が拒否 (rc!=0) した task を含む batch は理由付き delayed。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT_DEFAULT = str(_SCRIPTS_DIR.parents[2])

# backtick 内の python3 command 抽出 (受入根拠テキストから)。
_CMD_RE = re.compile(r"`(python3 [^`]+)`")
# command token の安全形 (shell metacharacter を含まない)。
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.@:/=-]+$")
# read-only/deterministic validator と見なす script basename の allowlist prefix。
_VALIDATOR_BASENAME_RE = re.compile(r"^(validate|lint|check|verify)[-_].+\.py$")


# ── TG-C01 / TG-C03 subprocess 呼出し (test で monkeypatch 可能) ──────────────
def invoke_ready_set(task_graph: str, task_state: str, planner_root: str | None,
                     repo_root: str) -> subprocess.CompletedProcess:
    """兄弟 TG-C01 dispatch-ready-set.py を subprocess 起動する (SSOT 再利用・再実装禁止)。"""
    cmd = [sys.executable, str(_SCRIPTS_DIR / "dispatch-ready-set.py"),
           "--task-graph", task_graph, "--task-state", task_state,
           "--repo-root", repo_root]
    if planner_root:
        cmd += ["--planner-root", planner_root]
    return subprocess.run(cmd, capture_output=True, text=True)


def invoke_inject(task_graph: str, task_state: str, task_ids: str | list[str]) -> subprocess.CompletedProcess:
    """兄弟 TG-C03 を1 batch=1 subprocess で起動する (注入物パス解決・read-only)。"""
    ids = [task_ids] if isinstance(task_ids, str) else list(task_ids)
    task_args = [arg for task_id in ids for arg in ("--task-id", task_id)]
    return subprocess.run(
        [sys.executable, str(_SCRIPTS_DIR / "inject-task-inputs.py"),
         "--task-graph", task_graph, "--task-state", task_state, *task_args],
        capture_output=True, text=True)


def invoke_inject_unit(task_graph: str, task_state: str, execution_contract: str,
                       unit_id: str) -> subprocess.CompletedProcess:
    """execution scheduler と同じ unit DAG を使い、1 unit=1 subprocess で入力解決。"""
    return subprocess.run(
        [sys.executable, str(_SCRIPTS_DIR / "inject-task-inputs.py"),
         "--task-graph", task_graph, "--task-state", task_state,
         "--execution-contract", execution_contract, "--unit-id", unit_id],
        capture_output=True, text=True,
    )


# ── 束ね規則 (純関数群) ────────────────────────────────────────────────────────
def resolve_validator_command(node: dict, repo_root: str) -> str | None:
    """entity_ref=null node の受入根拠から決定論 validator command を解決する。

    単一 backtick command・全 token 安全形・basename allowlist・script 実在の全条件を
    満たす場合のみ command 文字列を返し、それ以外は None (fail-closed → subagent 側)。
    """
    text = " ".join(s for s in (node.get("title"), node.get("acceptance_criterion"))
                    if isinstance(s, str))
    cmds = sorted(set(_CMD_RE.findall(text)))
    if len(cmds) != 1:
        return None
    tokens = cmds[0].split()
    if len(tokens) < 2 or tokens[0] != "python3":
        return None
    if any(not _SAFE_TOKEN_RE.match(t) for t in tokens):
        return None
    script = tokens[1]
    if not _VALIDATOR_BASENAME_RE.match(Path(script).name):
        return None
    if not (Path(repo_root) / script).is_file():
        return None
    return " ".join(tokens)


def resolve_route_id(node: dict, routes_by_id: dict) -> str | None:
    """node→route join。route_ref 明示値を優先し、無ければ entity_ref を routes 突合。"""
    ref = node.get("route_ref") or node.get("entity_ref")
    return ref if ref in routes_by_id else None


def _scopes_overlap(a: str, b: str) -> bool:
    return a == b or a.startswith(b.rstrip("/") + "/") or b.startswith(a.rstrip("/") + "/")


def _ownership_conflicts(ownership: list[str], held: list[str]) -> bool:
    return any(_scopes_overlap(o, h) for o in ownership for h in held)


def _phase_file(plan_dir: Path, phase_ref: str) -> str | None:
    """phase_ref (P01..P13) に対応する plan_dir/phase-NN-*.md を 1 件返す (無ければ None)。"""
    if not re.match(r"^P\d{2}$", phase_ref or ""):
        return None
    hits = sorted(plan_dir.glob(f"phase-{phase_ref[1:]}-*.md"))
    return str(hits[0]) if len(hits) == 1 else None


def classify(nodes_by_id: dict, ready_ids: list[str], routes_by_id: dict,
             repo_root: str) -> tuple[list[dict], list[dict]]:
    """ready node を direct validator 項目と subagent batch 候補へ決定論分類する。"""
    direct: dict[tuple[str, str], list[str]] = {}
    route_groups: dict[str, list[dict]] = {}
    singles: list[dict] = []
    for tid in sorted(ready_ids):
        node = nodes_by_id.get(tid)
        if not isinstance(node, dict):
            continue
        route_id = resolve_route_id(node, routes_by_id)
        if route_id is not None:
            route_groups.setdefault(route_id, []).append(node)
            continue
        if node.get("entity_ref") is None:
            cmd = resolve_validator_command(node, repo_root)
            if cmd is not None:
                direct.setdefault((node.get("phase_ref") or "", cmd), []).append(tid)
                continue
        singles.append(node)  # 判別不能/意味解釈が要る node は fail-closed で SubAgent 側

    direct_batch = [
        {"task_ids": sorted(tids), "phase_ref": phase_ref, "command": cmd}
        for (phase_ref, cmd), tids in sorted(direct.items())
    ]
    candidates: list[dict] = []
    for route_id in sorted(route_groups):
        group = sorted(route_groups[route_id], key=lambda n: n["id"])
        route = routes_by_id[route_id]
        ownership = sorted({n.get("write_scope") for n in group if n.get("write_scope")}
                           | ({route.get("build_target")} if route.get("build_target") else set()))
        candidates.append({
            "task_ids": [n["id"] for n in group],
            "route_id": route_id,
            "phase_refs": sorted({n.get("phase_ref") for n in group if n.get("phase_ref")}),
            "file_ownership": ownership,
            "nodes": group,
        })
    for node in sorted(singles, key=lambda n: n["id"]):
        candidates.append({
            "task_ids": [node["id"]],
            "route_id": None,
            "phase_refs": [node["phase_ref"]] if node.get("phase_ref") else [],
            "file_ownership": [node["write_scope"]] if node.get("write_scope") else [],
            "nodes": [node],
        })
    return direct_batch, candidates


def classify_execution_units(
    graph: dict,
    task_state: dict,
    contract: dict,
    routes_by_id: dict,
    stage: str,
) -> tuple[list[dict], list[dict]]:
    """execution-unit contract を実行可能 batch と gate proof projection へ射影する。"""
    nodes_by_id = {str(node.get("id")): node for node in graph.get("nodes", []) if isinstance(node, dict)}
    claim_ids = {
        task_id for task_id, node in nodes_by_id.items()
        if node.get("execution_kind") == "verification-claim"
    }
    state_by_id = {
        str(node.get("id")): node for node in task_state.get("nodes", []) if isinstance(node, dict)
    }
    obligations = contract.get("obligations")
    if not isinstance(obligations, list):
        raise ValueError("execution contract obligations が list でない")
    units: dict[str, dict] = {}
    assignment: dict[str, str] = {}
    for obligation in obligations:
        if not isinstance(obligation, dict):
            raise ValueError("execution contract obligation が object でない")
        unit = (obligation.get("parameters") or {}).get("execution_unit")
        if not isinstance(unit, dict) or unit.get("id") != obligation.get("id"):
            raise ValueError(f"obligation {obligation.get('id')} がexecution_unit契約を欠く")
        unit_id = str(unit["id"])
        if unit_id in units:
            raise ValueError(f"execution unit id 重複: {unit_id}")
        covered = unit.get("covered_task_ids")
        if not isinstance(covered, list) or not covered or len(set(covered)) != len(covered):
            raise ValueError(f"execution unit {unit_id} covered_task_ids が空/重複")
        parameter_covered = (obligation.get("parameters") or {}).get("covered_task_ids")
        if parameter_covered != covered:
            raise ValueError(f"execution unit {unit_id} の covered_task_ids 二重表現が不一致")
        for task_id in covered:
            if task_id in assignment:
                raise ValueError(f"claim {task_id} が {assignment[task_id]} / {unit_id} に重複割当")
            assignment[task_id] = unit_id
        units[unit_id] = obligation
    missing, extra = sorted(claim_ids - set(assignment)), sorted(set(assignment) - claim_ids)
    if missing or extra:
        raise ValueError(f"execution contract coverage 不一致: missing={missing} extra={extra}")
    for unit_id, obligation in units.items():
        unknown = set(obligation.get("depends_on") or []) - set(units)
        if unknown or unit_id in set(obligation.get("depends_on") or []):
            raise ValueError(f"execution unit dependency 不正: {unit_id} unknown/self={sorted(unknown)}")

    def _task_state(task_id: str) -> str:
        return str(state_by_id.get(task_id, {}).get("state") or "pending")

    complete_units = {
        unit_id for unit_id, obligation in units.items()
        if all(_task_state(task_id) == "done"
               for task_id in obligation["parameters"]["execution_unit"]["covered_task_ids"])
    }
    candidates: list[dict] = []
    for unit_id, obligation in sorted(units.items()):
        unit = obligation["parameters"]["execution_unit"]
        if stage == "draft" and obligation.get("stage", "draft") != "draft":
            continue
        covered = list(unit["covered_task_ids"])
        states = {_task_state(task_id) for task_id in covered}
        if states == {"done"}:
            continue
        if states != {"pending"}:
            raise ValueError(f"execution unit {unit_id} が部分遷移/実行中: {sorted(states)}")
        if not set(obligation.get("depends_on") or []) <= complete_units:
            continue
        route_id = unit.get("route_id")
        route = routes_by_id.get(route_id) if route_id is not None else None
        nodes = [nodes_by_id[task_id] for task_id in covered]
        ownership = {str(node.get("write_scope")) for node in nodes if node.get("write_scope")}
        if route and route.get("build_target"):
            ownership.add(str(route["build_target"]))
        candidates.append({
            "unit_id": unit_id,
            "task_ids": covered,
            "route_id": route_id,
            "phase_refs": [unit["phase_ref"]],
            "file_ownership": sorted(ownership),
            "nodes": nodes,
        })

    projections: list[dict] = []
    for projection in contract.get("proof_projections") or []:
        task_id = projection.get("task_id")
        if state_by_id.get(task_id, {}).get("state") == "done":
            continue
        required = projection.get("required_claim_ids") or []
        if required and all(_task_state(claim_id) == "done" for claim_id in required):
            projections.append(projection)
    return candidates, projections


def select(candidates: list[dict], conflicts: list, in_flight: list[dict],
           max_workers: int) -> tuple[list[dict], list[dict]]:
    """候補 batch を conflict/file_ownership/max-workers 規則で選抜し、外れを delayed へ。"""
    conflict_pairs = {frozenset(p) for p in conflicts if isinstance(p, (list, tuple)) and len(p) == 2}
    held_scopes: list[str] = [s for f in in_flight for s in f.get("file_ownership", [])]
    held_ids: set[str] = {f["task_id"] for f in in_flight if f.get("task_id")}
    capacity = max(0, max_workers - len(in_flight))

    selected: list[dict] = []
    delayed: list[dict] = []

    def _delay(batch: dict, reason: str) -> None:
        delayed.extend({"task_id": t, "reason": reason} for t in batch["task_ids"])

    for batch in candidates:
        partner = next((frozenset(p) for t in batch["task_ids"] for p in conflict_pairs
                        if t in p and (p - {t}) & held_ids), None)
        if partner is not None:
            _delay(batch, f"conflict:{sorted(partner)}")
            continue
        if _ownership_conflicts(batch["file_ownership"], held_scopes):
            _delay(batch, "file-ownership-conflict")
            continue
        if capacity <= 0:
            _delay(batch, "max-workers")
            continue
        selected.append(batch)
        held_scopes.extend(batch["file_ownership"])
        held_ids.update(batch["task_ids"])
        capacity -= 1
    return selected, delayed


# ── main ─────────────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="plan-dispatch-batch.py",
        description="TG-C01 ready-set に束ね規則を適用し dispatch batch を機械導出する (TG-C10)。",
    )
    p.add_argument("--task-graph", required=True, help="task-graph.json のパス")
    p.add_argument("--task-state", required=True, help="task-state.json のパス")
    p.add_argument("--handoff", required=True, help="handoff-run-plugin-dev-plan.json のパス")
    p.add_argument("--execution-contract", default=None,
                   help="verification-claim を束ねた execution-unit contract JSON")
    p.add_argument("--stage", choices=["draft", "release"], default="draft",
                   help="execution contract で dispatch する stage (既定 draft)")
    p.add_argument("--max-workers", type=int, default=2, help="同時 SubAgent 上限 (既定2)")
    p.add_argument("--in-flight", default=None,
                   help="実行中 task の JSON list [{task_id, file_ownership:[...]}] のパス (省略時なし)")
    p.add_argument("--planner-root", default=None, help="TG-C01 へ透過する producer root")
    p.add_argument("--repo-root", default=_REPO_ROOT_DEFAULT,
                   help="validator script 実在検査と plan_dir 解決の基点")
    p.add_argument("--out", default=None, help="出力 JSON の書込先 (省略時 stdout のみ)")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2
    if args.max_workers < 1:
        print("--max-workers は正の整数", file=sys.stderr)
        return 2

    def _read_json(path: str, label: str):
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"{label} 読込/parse 失敗: {path}: {exc}", file=sys.stderr)
            return None

    graph = _read_json(args.task_graph, "task-graph")
    handoff = _read_json(args.handoff, "handoff")
    if graph is None or handoff is None:
        return 2
    in_flight: list[dict] = []
    if args.in_flight:
        loaded = _read_json(args.in_flight, "in-flight")
        if loaded is None:
            return 2
        in_flight = [f for f in loaded if isinstance(f, dict)]
    execution_contract = None
    task_state_payload = None
    if args.execution_contract:
        execution_contract = _read_json(args.execution_contract, "execution-contract")
        task_state_payload = _read_json(args.task_state, "task-state")
        if execution_contract is None or task_state_payload is None:
            return 2

    proc = invoke_ready_set(args.task_graph, args.task_state, args.planner_root, args.repo_root)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        try:  # pin mismatch は TG-C01 が stdout JSON で報告するため透過する
            upstream = json.loads(proc.stdout)
        except json.JSONDecodeError:
            upstream = {}
        if upstream.get("graph_hash_pin") == "mismatch":
            print(json.dumps({"graph_hash_pin": "mismatch", "direct_validator_batch": [],
                              "subagent_batches": [], "delayed": [], "blocked": [],
                              "source": "plan-dispatch-batch.py"}, ensure_ascii=False, indent=2))
        else:
            print(f"dispatch-ready-set.py 失敗 (rc={proc.returncode})", file=sys.stderr)
        return 1
    try:
        ready = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        print(f"dispatch-ready-set.py 出力 parse 失敗: {exc}", file=sys.stderr)
        return 1

    nodes_by_id = {n.get("id"): n for n in graph.get("nodes", []) if isinstance(n, dict)}
    routes_by_id = {r.get("id"): r for r in handoff.get("routes", [])
                    if isinstance(r, dict) and r.get("id")}

    proof_projection_batch: list[dict] = []
    try:
        if execution_contract is not None:
            candidates, proof_projection_batch = classify_execution_units(
                graph, task_state_payload, execution_contract, routes_by_id, args.stage)
            direct_batch = []
        else:
            direct_batch, candidates = classify(
                nodes_by_id, ready.get("ready_batch", []), routes_by_id, args.repo_root)
    except ValueError as exc:
        print(f"execution contract violation: {exc}", file=sys.stderr)
        return 1
    selected, delayed = select(candidates, ready.get("conflicts", []), in_flight,
                               args.max_workers)

    plan_dir = Path(args.repo_root) / handoff.get("plan_dir", "")
    subagent_batches: list[dict] = []
    for batch in selected:
        context_files: list[str] = []
        for pref in batch["phase_refs"]:
            pf = _phase_file(plan_dir, pref)
            if pf:
                context_files.append(pf)
        for node in batch["nodes"]:
            if node.get("task_spec_ref"):
                context_files.append(str(plan_dir / node["task_spec_ref"]))
        rejected = None
        if execution_contract is not None:
            inj = invoke_inject_unit(
                args.task_graph, args.task_state, args.execution_contract, batch["unit_id"])
        else:
            inj = invoke_inject(args.task_graph, args.task_state, batch["task_ids"])
        if inj.returncode != 0:
            rejected = batch["task_ids"][0]
            payload = {}
        else:
            try:
                payload = json.loads(inj.stdout)
            except json.JSONDecodeError:
                rejected = batch["task_ids"][0]
                payload = {}
        injection_results = payload.get("tasks")
        if not isinstance(injection_results, list):
            injection_results = [payload]  # 単数旧 CLI / test double 後方互換
        for result in injection_results:
            context_files.extend(
                item.get("artifact_path") for item in result.get("injected_inputs", [])
                if isinstance(item, dict) and item.get("artifact_path"))
        if rejected is not None:  # TG-C03 fail-closed 拒否は理由付き delayed へ
            delayed.extend({"task_id": t, "reason": f"inject-rejected:{rejected}"}
                           for t in batch["task_ids"])
            continue
        subagent_batches.append({
            **({"unit_id": batch["unit_id"]} if batch.get("unit_id") else {}),
            "task_ids": batch["task_ids"],
            "route_id": batch["route_id"],
            "phase_refs": batch["phase_refs"],
            "file_ownership": batch["file_ownership"],
            "context_files": sorted(set(context_files)),
        })

    out = {
        "schema_version": "1.0",
        "source": "plan-dispatch-batch.py",
        "graph_hash_pin": ready.get("graph_hash_pin"),
        "max_workers": args.max_workers,
        "direct_validator_batch": direct_batch,
        "subagent_batches": subagent_batches,
        "proof_projection_batch": proof_projection_batch,
        "delayed": sorted(delayed, key=lambda d: d["task_id"]),
        "blocked": ready.get("blocked", []),
    }
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out:
        try:
            Path(args.out).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"--out 書込失敗: {args.out}: {exc}", file=sys.stderr)
            return 2
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
